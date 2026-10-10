#!/usr/bin/env python3
"""PR1 replay/bench: the send hot path must not do exchange/info I/O between writing an intent and
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

FILLS = max(2, int(os.getenv("HL_BENCH_FILLS", "20")))
TIME_SCALE = max(0.01, float(os.getenv("HL_BENCH_TIME_SCALE", "1.0")))
READ_S = 0.9 * TIME_SCALE   # 900 ms: every simulated info read
ORDER_S = 1.0 * TIME_SCALE  # 1000 ms: every fake exchange order call
DISPATCH_GAP_S = 0.04       # burst spacing
# 40% of the coins are sendable, 60% are blocked locally via the symbol blocklist (i % 5 in {0,1})
ALLOWED_EVERY = 5
ALLOWED_OFFSETS = (0, 1)


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
        "HL_LIVE_WS_ENABLED": "0",
        "HL_LIVE_PREWARM_SYMBOL_META": "0",
        "HL_LIVE_PREWARM_SDK_CLIENT": "0",
        "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
        "HL_LIVE_SNAPSHOT_REFRESH_INTERVAL_SEC": "100000",
        "HL_LIVE_HOT_SEND_WORKERS": "4",
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
    c.EXPOSURE_FETCHER = slow("exposure", lambda p: [] if p.get("type") == "perpDexs" else dict(EXP_PAYLOAD))
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

    time.sleep(0.2)  # let the worker threads reach their queue loops

    # ---- replay: dispatch the burst into the real hot queues -------------------------------------------
    fills = []
    for i in range(FILLS):
        fill = c.LeaderFill(f"bench-{i:03d}", LEADER, ALL_COINS[i], "BUY", 100.0, 1.0, c.utc_now_ms(), "WS_CAPTURED")
        fills.append(fill)
        ENQ[fill.leader_fill_id] = c.utc_now_ms()
        core._dispatch_fill(fill)
        time.sleep(DISPATCH_GAP_S)

    drain_deadline = time.monotonic() + max(60.0, FILLS * (READ_S + ORDER_S) * 4)
    while time.monotonic() < drain_deadline:
        if all(EVENTS.get(f.leader_fill_id, {}).get("ack_ms") for f in fills):
            break
        time.sleep(0.1)
    core.stop()

    # ---- analysis --------------------------------------------------------------------------------------
    queue_waits, ack_latencies, reads_after_intent = [], [], []
    sent = blocked = 0
    for fill in fills:
        ctx = EVENTS.get(fill.leader_fill_id)
        if not ctx or not ctx["ack_ms"]:
            continue
        queue_waits.append(ctx["process_start_ms"] - ctx["enqueue_ms"])
        ack_latencies.append(ctx["ack_ms"] - ctx["enqueue_ms"])
        if ctx["order_sent_ms"]:
            sent += 1
            reads_after_intent.append((fill.leader_fill_id, ctx["reads_between"]))
        elif ctx["intent_written_ms"]:
            blocked += 1

    q90 = p90(queue_waits)
    a90 = p90(ack_latencies)
    offenders = [fid for fid, n in reads_after_intent if n > 0]

    print("MEASURE:: burst=%d fills, workers=%d, read=%.0f ms, order=%.0f ms, scale=%.2f"
          % (FILLS, core.hot_send_workers, READ_S * 1000, ORDER_S * 1000, TIME_SCALE))
    print("MEASURE:: sent=%d (reached the exchange), blocked locally=%d" % (sent, blocked))
    print("MEASURE:: queue wait p90 = %s ms (limit 500)" % q90)
    print("MEASURE:: fill-to-ack p90 = %s ms (limit 2000)" % a90)
    print("MEASURE:: sent fills with an info read between intent and order = %d/%d %s"
          % (len(offenders), len(reads_after_intent), offenders[:5]))

    check("BENCH_ALL_FILLS_REACHED_A_LOCAL_OUTCOME", len(queue_waits) == FILLS,
          f"{len(queue_waits)}/{FILLS} fills produced an outcome")
    check("BENCH_40PCT_REACHED_THE_EXCHANGE", sent == expected_sent, f"sent={sent} expected={expected_sent}")
    check("BENCH_60PCT_BLOCKED_LOCALLY", blocked == len(blocked_coins),
          f"blocked={blocked} expected={len(blocked_coins)}")
    check("BENCH_QUEUE_WAIT_P90_UNDER_500MS", q90 is not None and q90 <= 500, f"p90={q90}")
    check("BENCH_FILL_TO_ACK_P90_UNDER_2S", a90 is not None and a90 <= 2000, f"p90={a90}")
    check("BENCH_ZERO_INFO_READS_BETWEEN_INTENT_AND_ORDER", not offenders,
          f"{len(offenders)} sent fills read info after the intent: {offenders[:5]}")

    c.HLAccount, c.HLExchange = saved_acct
    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
