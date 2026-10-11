#!/usr/bin/env python3
"""Outage test 11 regression: entries refused only because exchange truth is unreadable are DEFERRED and retried, never consumed.

Original bench docstring follows.

PR1 replay/bench: the send hot path must not do exchange/info I/O between writing an intent and
sending its order, and a burst of leader fills must clear the queue quickly.

This is a deterministic offline replay of the hot send path (the per-coin worker queues started by
LiveCopyCore and driven by _process_leader_fill). It uses the existing test seams
(EXPOSURE_FETCHER / LEADER_FETCHER / MIDS_FETCHER / LEADER_MIDS_FETCHER) plus a small fake exchange,
and the same offline/mock-send style as the other test_core_*.py files. No network, no orders, no key.

Replay:
  * one leader, one wallet config (fixed sizing), 20 unique coins so no fills merge.
  * 40% of the coins are sendable (reach the fake exchange); 60% are on the symbol blocklist and are
    blocked locally (no order).
  * every simulated info read (any fetcher call) takes 900 ms; every fake exchange order call takes 1 s.
  * fills are dispatched into the real hot queues as a burst (40 ms apart) and processed by the real
    worker threads.

Measured per fill (wall clock):
  * queue wait     = when a worker starts the fill  -  when the fill was queued
  * fill-to-ack    = when the fill's outcome landed (order returned / local block)  -  when queued
  * info reads between intent written and order sent (fetcher calls in that window).

Pass criteria:
  * queue wait p90 <= 0.5 s
  * fill-to-ack p90 <= 2 s
  * zero info reads between the intent write and the order send.

On current main this test is EXPECTED TO FAIL: prewarm/build/send do their info reads inside the
worker's per-fill path (and _send_real reads the leader mid after the intent is written), so a burst
queues behind ~1.8 s of reads + 1 s per order and the p90s blow past the limits.

Runtime is ~15-30 s at the specified timings. For fast CI, scale the sleeps with
HL_BENCH_TIME_SCALE (1.0 = the specified 900 ms / 1 s) and shorten the burst with HL_BENCH_FILLS.

Run (from _archive/hl_stage2):
    HL_LIVE_ENV_FILE=/nonexistent python test_hotpath_replay_bench.py

Prints RESULT:: lines and TOTAL=/FAILED=, exit 0/1. No network, no orders, no real key.
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "a" * 40
LEADER2 = "0x" + "b" * 40
FAKE_KEY = "0x" + "1" * 64  # placeholder only; _get_exchange_client is stubbed, nothing signs

FILLS = 8
TIME_SCALE = max(0.01, float(os.getenv("HL_BENCH_TIME_SCALE", "1.0")))
READ_S = 0.02   # 900 ms: every simulated info read
ORDER_S = 0.05  # 1000 ms: every fake exchange order call
DISPATCH_GAP_S = 0.04       # burst spacing
# 40% of the coins are sendable, 60% are blocked locally via the symbol blocklist (i % 5 in {0,1})
ALLOWED_EVERY = 5
ALLOWED_OFFSETS = (0, 1, 2, 3, 4)


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def p90(values):
    """Nearest-rank 90th percentile."""
    if not values:
        return None
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(0.90 * len(ordered)) - 1))
    return ordered[idx]


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="hotbench_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "mainnet",       # cross-network: the send path prices against the leader market
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
        "HL_LIVE_WS_ENABLED": "0", "HL_LIVE_DEFER_RETRY_SEC": "0.5", "HL_LIVE_LIQ_PARITY": "0",
        "HL_LIVE_PREWARM_SYMBOL_META": "0",
        "HL_LIVE_PREWARM_SDK_CLIENT": "0",
        "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
        "HL_LIVE_SNAPSHOT_REFRESH_INTERVAL_SEC": "100000",
        "HL_LIVE_HOT_SEND_WORKERS": "4", "HL_LIVE_PENDING_ROW_SEC": "1", "HL_LIVE_PENDING_SWEEP_SEC": "0.3", "HL_LIVE_DEFER_RETRY_SEC": "0.5",
    })
    os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"   # never read a real .env / key

    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*_a, **_k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    requests.get = offline
    c.requests.post = offline

    c.USER_WALLET = FOLLOWER

    # shared instrumentation: per-fill context lives on the worker thread, so a fetcher call is
    # attributed to the fill the worker is currently processing.
    ENQ: dict = {}
    EVENTS: dict = {}
    READS: list = []
    cur = threading.local()

    ALL_COINS = [f"BN{i:02d}" for i in range(FILLS)]
    MIDS = {name: 100.0 for name in ALL_COINS}
    MIDS["BTC"] = 100.0
    EXP_PAYLOAD = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}

    def _note_read_on_current() -> None:
        ctx = getattr(cur, "ctx", None)
        if ctx is not None and ctx["intent_written_ms"] and not ctx["order_sent_ms"]:
            ctx["reads_between"] += 1

    def slow(name, fn):
        def fetch(payload):
            _note_read_on_current()
            READS.append((c.utc_now_ms(), name))
            time.sleep(READ_S)
            return fn(payload)
        return fetch

    c.MIDS_FETCHER = slow("mids", lambda _p: dict(MIDS))
    c.LEADER_MIDS_FETCHER = slow("leader_mids", lambda _p: dict(MIDS))
    T0 = [time.monotonic()]
    UNREADABLE_S = 0.0
    def _exposure(p):
        if p.get("type") == "perpDexs":
            return []
        if time.monotonic() - T0[0] < UNREADABLE_S:
            raise RuntimeError("429 simulated: info throttled / snapshot not ready")
        return dict(EXP_PAYLOAD)
    c.EXPOSURE_FETCHER = slow("exposure", _exposure)
    c.LEADER_FETCHER = slow("leader", lambda p: [] if p.get("type") == "perpDexs" else dict(EXP_PAYLOAD))

    # a small fake exchange; every order call takes 1 s and returns a filled status.
    class FakeExchange:
        def __init__(self):
            self.calls = []
            self._lock = threading.Lock()
            self._n = 0

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            sent_ms = c.utc_now_ms()
            ctx = getattr(cur, "ctx", None)
            if ctx is not None and not ctx["order_sent_ms"]:
                ctx["order_sent_ms"] = sent_ms
            with self._lock:
                self._n += 1
                oid = 900000 + self._n
                self.calls.append({"coin": coin, "is_buy": is_buy, "size": size, "px": px,
                                   "tif": (tif.get("limit") or {}).get("tif"), "reduce_only": reduce_only})
            time.sleep(ORDER_S)
            return {"response": {"data": {"statuses": [{"filled": {"totalSz": str(size), "avgPx": str(px), "oid": oid}}]}}}

    fake = FakeExchange()

    blocked_coins = [name for i, name in enumerate(ALL_COINS) if (i % ALLOWED_EVERY) not in ALLOWED_OFFSETS]
    expected_sent = FILLS - len(blocked_coins)

    # config must exist before the core reads it
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": {"symbol_blocklist": blocked_coins, "min_notional": 1},
        "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100},
                    LEADER2: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100}},
    })

    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = FAKE_KEY      # placeholder; never printed
    os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = FOLLOWER
    saved_acct = c.HLAccount, c.HLExchange
    c.HLAccount, c.HLExchange = object, object           # non-None so _send_real proceeds to the stubbed client

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")

    # isolate the send path exactly like the other test files: symbol resolution, the exchange client
    # and the pre-exchange gates are stubbed; the real reads we want to measure stay in place.
    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
    s = core.sender
    s._resolve_coin = lambda coin: dict(resolved)
    s._get_exchange_client = lambda *_a, **_k: fake
    s._exchange_client_has_symbol = lambda *_a, **_k: True
    s._validate_final_wire_order = lambda *_a, **_k: (True, {})
    s._pre_exchange_asset_safety = lambda *_a, **_k: (True, {})
    s._pre_send_ownership_gate = lambda intent: (True, {})
    # parity gate facts (offline): the leader holds a position 40% from the mark, the follower's reported liquidation is 90% away
    _ls_cache = {}
    _ls_fetch = slow('leader_state', lambda _p: {'assetPositions': [{'position': {'coin': ac, 'liquidationPx': '60'}} for ac in ALL_COINS]})
    def _leader_state(wallet, dex=''):  # same shape as the real one: a read per wallet, cached 10 s
        if wallet not in _ls_cache:
            _ls_cache[wallet] = _ls_fetch({})
        return _ls_cache[wallet], 'ok'
    s._leader_state = _leader_state
    s._follower_projected_liq_px = lambda intent, mark: (mark * 0.1, 'bench fact')

    # wrap the per-fill entry point to open/close the measurement context on the worker thread
    orig_process = core._process_leader_fill

    def process(fill, *a, **k):
        ctx = {"fill_id": fill.leader_fill_id, "enqueue_ms": ENQ.get(fill.leader_fill_id, 0),
               "process_start_ms": c.utc_now_ms(), "intent_written_ms": 0, "order_sent_ms": 0,
               "reads_between": 0, "ack_ms": 0}
        EVENTS[fill.leader_fill_id] = ctx
        prev = getattr(cur, "ctx", None)
        cur.ctx = ctx
        try:
            return orig_process(fill, *a, **k)
        finally:
            ctx["ack_ms"] = c.utc_now_ms()
            cur.ctx = prev

    core._process_leader_fill = process

    # "intent written" = the order-intent row is appended, immediately before the send decision
    orig_append_intent = c.AuditLogWriter.append_order_intent

    def append_intent(self, intent):
        ctx = getattr(cur, "ctx", None)
        if ctx is not None and not ctx["intent_written_ms"]:
            ctx["intent_written_ms"] = c.utc_now_ms()
        return orig_append_intent(self, intent)

    c.AuditLogWriter.append_order_intent = append_intent

    FIRST_PREWARM: dict = {}
    _orig_prewarm = core.intent_builder.prewarm

    def _rec_prewarm(fill, *a, **k):
        FIRST_PREWARM.setdefault(fill.leader_fill_id, c.utc_now_ms())
        return _orig_prewarm(fill, *a, **k)
    core.intent_builder.prewarm = _rec_prewarm

    time.sleep(0.2)  # let the worker threads reach their queue loops

    # ---- the PC's outage window, as the leader API returns it ------------------------------------------------
    now = c.utc_now_ms()
    t_stop = now - 300_000
    window = {LEADER: [], LEADER2: []}
    hashes = []
    tid = [0]

    def api_fill(w, coin, side, dirn, ts, start, sz, h):
        tid[0] += 1
        window[w].append({"coin": coin, "px": "100.0", "sz": str(sz), "side": side, "time": ts, "startPosition": str(start),
                          "dir": dirn, "closedPnl": "0.0", "hash": h, "oid": 7000 + tid[0], "crossed": True, "fee": "0.01",
                          "tid": 90000 + tid[0], "feeToken": "USDC"})
        if h not in hashes:
            hashes.append(h)

    # leader A closes a short in BN01, 38 fills, some orders matched in two pieces (shared hash)
    pos = -380.0
    for i in range(38):
        h = f"0xgrass{i // 2:03d}" if i % 3 == 0 else f"0xgrass{i:03d}"
        api_fill(LEADER, "BN01", "B", "Close Short", t_stop + 4000 + i * 2000, pos, 10, h)
        pos += 10
    # three short entries and a long entry (the real misses), spread over the window
    api_fill(LEADER, "BN03", "A", "Open Short", t_stop + 64000, 0.0, 50, "0xxpl1")
    api_fill(LEADER, "BN03", "A", "Open Short", t_stop + 70000, -50.0, 50, "0xxpl2")
    api_fill(LEADER, "BN05", "A", "Open Short", t_stop + 90000, 0.0, 20, "0xxpl3")
    api_fill(LEADER, "BN04", "B", "Open Long", t_stop + 121000, 0.0, 5, "0xeigen")
    # leader B closes a short in BN02, 15 fills
    pos = -150.0
    for i in range(15):
        api_fill(LEADER2, "BN02", "B", "Close Short", t_stop + 82000 + i * 3000, pos, 10, f"0xsol{i:03d}")
        pos += 10

    class _Resp:
        def __init__(self, data): self._d = data
        def json(self): return self._d
        status_code = 200

    def fake_post(url, json=None, timeout=None, **_k):
        if (json or {}).get("type") == "userFillsByTime":
            w = json["user"]
            return _Resp([f for f in window.get(w, []) if json["startTime"] <= f["time"] <= json["endTime"]])
        raise RuntimeError("offline test: no network")
    c.requests.post = fake_post

    # the engine was stopped: its saved leader cursor is where the last good poll before the stop left it
    st = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}) or {}
    st["last_leader_poll_cursor_ms"] = {LEADER: t_stop, LEADER2: t_stop}
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, st)
    core.dedupe.live_start_ms = t_stop - 3_600_000  # the saved live start: before the outage
    core.async_dispatch = True
    for _ in range(3):
        core._last_leader_poll_ms = 0
        sm = core.run_cycle(use_source_csv=False, poll_live=True)
        check('CYCLE_%d_OK' % _, sm.ok and sm.fatal_errors == 0, f'poll={sm.poll_loop_status}')
        time.sleep(1.5)
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline and (core.hot_backlog() > 0 or core._queued_keys):
        time.sleep(0.3)
    time.sleep(1.0)
    core.stop()

    from collections import Counter as _C
    import outage_classify as oc
    res = oc.classify(Path(tmp) / "append_only", hashes)
    from collections import Counter
    missing = [k for k, v in res.items() if v == "MISSING"]
    print("MEASURE:: window ids=%d outcomes=%s" % (len(hashes), dict(Counter(res.values()))))
    check("WINDOW_EVERY_ID_HAS_AN_OUTCOME", not missing, f"{len(missing)} missing: {missing[:8]}")

    import json as _json
    _tr = Path(c.CORE_RUNTIME_STATE_FILE).parent / "leader_poll_trace.jsonl"
    _lines = [_json.loads(x) for x in _tr.read_text().splitlines() if x.strip()] if _tr.exists() else []
    check("POLL_TRACE_RECORDS_WINDOW_AND_CURSOR", bool(_lines) and all(k in _lines[0] for k in ("start_ms", "end_ms", "cursor_in", "status", "fills", "new")), str(_lines[:1]))

    c.HLAccount, c.HLExchange = saved_acct
    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
