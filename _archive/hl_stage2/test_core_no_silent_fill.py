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
        "HL_LIVE_HOT_SEND_WORKERS": "4", "HL_LIVE_PENDING_ROW_SEC": "1", "HL_LIVE_STUCK_SEC": "1", "HL_LIVE_PENDING_SWEEP_SEC": "0.3", "HL_LIVE_DEFER_RETRY_SEC": "0.5",
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
        "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100}},
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

    # ---- every fill, whatever it is, must end in a row -------------------------------------------------
    def mk(fid, coin, side, direction, ts, raw_extra=None):
        raw = {"dir": direction, "hash": fid.split("#")[0], "tid": fid}
        raw.update(raw_extra or {})
        return c.LeaderFill(fid, LEADER, coin, side, 100.0, 1.0, ts, "WS_CAPTURED", 0, raw)
    base = c.utc_now_ms()
    ids = []
    fills = []
    # (1) a long run of closes of a position the follower never held (wallet flat) in one coin, as outage test 14
    for i in range(40):
        f = mk(f"cs{i:03d}", "BN01", "BUY", "Close Short", base + i); fills.append(f); ids.append(f.leader_fill_id)
    # (2) closes in a second coin, arriving in two bursts
    for i in range(15):
        f = mk(f"cx{i:03d}", "BN02", "BUY", "Close Short", base + 100 + i); fills.append(f); ids.append(f.leader_fill_id)
    # (3) entries
    for i, (coin, side, d) in enumerate([("BN03", "SELL", "Open Short"), ("BN04", "BUY", "Open Long"), ("BN05", "SELL", "Open Short")]):
        f = mk(f"en{i:03d}", coin, side, d, base + 200 + i); fills.append(f); ids.append(f.leader_fill_id)
    # (4) one order matched in pieces: several fills share a hash (distinct tid)
    for i in range(3):
        f = c.LeaderFill("pc", LEADER, "BN06", "SELL", 100.0, 1.0, base + 300 + i, "WS_CAPTURED", 0, {"dir": "Open Short", "hash": "pc", "tid": f"t{i}"}); fills.append(f)
    ids.append("pc")
    # ---- (5) an error while processing: held and retried, then sent; never a vanished fill --------------------------
    boom = {"n": 0}
    real_build = core.intent_builder.build

    def flaky_build(fill, *a, **k):
        if fill.leader_fill_id == "boom-1" and boom["n"] < 2:
            boom["n"] += 1
            raise RuntimeError("simulated build error")
        return real_build(fill, *a, **k)
    core.intent_builder.build = flaky_build
    # ---- (6) a slow fill: a row says it is queued, not lost -------------------------------------------------------
    real_inner = core._process_leader_fill_inner

    def slow_inner(fill, *a, **k):
        if fill.leader_fill_id == "slow-1":
            time.sleep(3.5)
        return real_inner(fill, *a, **k)
    core._process_leader_fill_inner = slow_inner
    f_boom = mk("boom-1", "BN07", "SELL", "Open Short", c.utc_now_ms())
    f_slow = mk("slow-1", "BN03", "SELL", "Open Short", c.utc_now_ms() + 5)
    core._dispatch_fill(f_boom)
    core._dispatch_fill(f_slow)
    ids += ["boom-1", "slow-1"]
    # ---- (7) a status nothing writes a row for: the final check writes one ------------------------------------------
    real_sia = core.sender.send_if_allowed
    def odd_sia(intent, ebr=""):
        if intent.fill.leader_fill_id == "odd-1":
            return False, "SOME_FUTURE_STATUS"
        return real_sia(intent, ebr)
    core.sender.send_if_allowed = odd_sia
    real_ast = core._append_send_terminal
    core._append_send_terminal = lambda fill, intent, st: None if fill.leader_fill_id == "odd-1" else real_ast(fill, intent, st)
    core._dispatch_fill(mk("odd-1", "BN08" if False else "BN06", "SELL", "Open Short", c.utc_now_ms()))
    ids.append("odd-1")
    time.sleep(1.5)
    # ---- (8) older than the saved live start: recorded, not copied, and says so --------------------------------------
    core.dedupe.live_start_ms = c.utc_now_ms() + 3_600_000
    core._dispatch_fill(mk("old-1", "BN07", "SELL", "Open Short", c.utc_now_ms()))
    ids.append("old-1")
    time.sleep(1.5)
    core.dedupe.live_start_ms = 1
    half = len(fills) // 2
    for f in fills[:half]:
        core._dispatch_fill(f)
    time.sleep(0.3)
    for f in fills[half:]:
        core._dispatch_fill(f)
    deadline = time.monotonic() + 40.0
    while time.monotonic() < deadline and (core.hot_backlog() > 0 or any(k in core._queued_keys for k in ids)):
        time.sleep(0.2)
    time.sleep(1.0)
    core.stop()

    import outage_classify as oc
    res = oc.classify(Path(tmp) / "append_only" if (Path(tmp) / "append_only").exists() else Path(tmp), ids)
    missing = [k for k, v in res.items() if v == "MISSING"]
    print("MEASURE:: classified=%d missing=%d sample=%s" % (len(res), len(missing), missing[:6]))
    from collections import Counter
    print("MEASURE:: outcomes", dict(Counter(res.values())))
    check("EVERY_FILL_HAS_A_TERMINAL_ROW", not missing, f"{len(missing)} missing, e.g. {missing[:5]}")
    # the fills that were marked handled must each have a row (the invariant behind it)
    with core._idem_lock:
        handled = set(core._idem_accepted)
    silent = [i for i in ids if i in handled and res.get(i) == "MISSING"]
    check("NO_FILL_MARKED_HANDLED_WITHOUT_A_ROW", not silent, str(silent[:5]))
    recon_rows = c.read_csv_rows(c.RECONCILIATION_CSV)
    states = lambda fid: [r.get("terminal_state") for r in recon_rows if r.get("leader_fill_id") == fid]
    check("ERROR_FILL_IS_HELD_THEN_HANDLED", "REPLAY_DEFERRED_PROCESS_EXCEPTION" in states("boom-1") and boom["n"] == 2 and res.get("boom-1") not in ("MISSING", None, ""),
          f"states={states('boom-1')} tries={boom['n']} outcome={res.get('boom-1')}")
    check("UNRECORDED_STATUS_GETS_A_FINAL_ROW", "BLOCKED_NO_TERMINAL_RECORDED" in states("odd-1"), f"states={states('odd-1')}")
    check("PRE_CUTOVER_FILL_SAYS_SO", "PRE_CUTOVER_NOT_SENT" in states("old-1"), f"states={states('old-1')}")
    check("STUCK_WORKER_IS_NAMED_AND_DUMPED", "FILL_PENDING_STUCK" in states("slow-1") and list(Path(c.CORE_RUNTIME_STATE_FILE).parent.glob("stuck_threads_*.txt")),
          f"states={states('slow-1')}")
    check("SLOW_FILL_HAS_A_PENDING_ROW", "FILL_PENDING_QUEUED" in states("slow-1"), f"states={states('slow-1')}")

    c.HLAccount, c.HLExchange = saved_acct
    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
