#!/usr/bin/env python3
"""Offline synthetic queue benchmark; never constructs a sender or makes exchange calls.

Run manually from this directory with a sanitized environment. The fake process boundary
models one 958 ms send per planned wallet/coin order; real merged-row persistence remains
covered by test_core_merged_rows.py.
"""
from __future__ import annotations

import os
import queue
import sys
import tempfile
import threading
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def percentile(samples, p):
    ordered = sorted(samples)
    return ordered[max(0, min(len(ordered) - 1, int((len(ordered) * p + 0.999999)) - 1))]


def build_core(c, workers):
    core = object.__new__(c.LiveCopyCore)
    core.cfg = SimpleNamespace(
        copy_mode=lambda _wallet: "fixed",
        max_order_notional=lambda: 1_000_000.0,
        marketable_bps=lambda: 0.0,
    )
    core.intent_builder = SimpleNamespace(_copy_notional=lambda _wallet, _fill: 12.0)
    core.ledger = SimpleNamespace(
        classify_leader_side_for_wallet=lambda _wallet, _coin, side: ("EXIT" if side == "SELL" else "ENTRY", False)
    )
    core.hot_send_workers = workers
    core._hot_queues = [queue.Queue(maxsize=50_000) for _ in range(workers)]
    core._hot_queue = core._hot_queues[0]
    core._prio_queues = [queue.Queue(maxsize=50_000) for _ in range(workers)]
    core._hot_stop_event = threading.Event()
    core._idem_lock = threading.Lock()
    core._idem_accepted = set()
    core._queued_lock = threading.Lock()
    core._queued_keys = set()
    core._pending_ts = {}
    core._pending_seen = {}
    core._pending_rowed = set()
    core._coin_lane = {}
    core._coin_locks = {}
    core._coin_locks_guard = threading.Lock()
    core._deferred = {}
    core._entry_sends_blocked_reason = ""
    core._inflight = {}
    core._stuck_dumped = set()
    core._past_send_keys = set()
    return core


def run_profile(c, wallets, coins, workers, inner, service_sec):
    os.environ["HL_LIVE_HOT_INNER"] = str(inner)
    core = build_core(c, workers)
    queued_at = {}
    peak_depth = 0
    base_ms = 1_800_000_000_000
    fills = []
    for wi, wallet in enumerate(wallets):
        for ci, coin in enumerate(coins):
            fills.append(c.LeaderFill(
                f"w{wi:02d}-c{ci:02d}-base", wallet, coin, "BUY", 100.0, 1.0,
                base_ms + len(fills), "WS_CAPTURED", base_ms + len(fills), {"dir": "Open Long"},
            ))
    # Add 200 more same-direction fills to twenty wallet/coin pairs; all 500 ids must survive.
    for extra in range(200):
        wi, ci = divmod(extra % 20, 2)
        fills.append(c.LeaderFill(
            f"w{wi:02d}-c{ci:02d}-extra{extra:03d}", wallets[wi], coins[ci], "BUY", 100.0, 1.0,
            base_ms + len(fills), "WS_CAPTURED", base_ms + len(fills), {"dir": "Open Long"},
        ))

    for fill in fills:
        queued_at[fill.leader_fill_id] = time.perf_counter()
        if not core._dispatch_fill(fill):
            raise AssertionError("synthetic dispatch rejected a fill")
        peak_depth = max(peak_depth, core.hot_backlog())

    starts, replies, audited_ids, orders = {}, {}, [], []
    active_by_coin = Counter()
    overlap = []
    lock = threading.Lock()

    def fake_process(fill, _summary=None, _reason=""):
        ids = [fill.leader_fill_id, *[str(x) for x in (fill.raw or {}).get("merged_fill_ids", [])]]
        with lock:
            active_by_coin[fill.coin] += 1
            if active_by_coin[fill.coin] > 1:
                overlap.append(fill.coin)
            for fid in ids:
                starts[fid] = time.perf_counter()
            orders.append((fill.coin, fill.leader_fill_id))
            with core._idem_lock:
                core._idem_accepted.update(ids)
        time.sleep(service_sec)  # mocked exchange latency; no exchange/client object exists
        completed = time.perf_counter()
        with lock:
            for fid in ids:
                replies[fid] = completed
                audited_ids.append(fid)  # fake one durable-row obligation per source fill
            active_by_coin[fill.coin] -= 1
        return True, "MOCK_SENT", None

    core._process_leader_fill_inner = fake_process
    threads = [threading.Thread(target=core._hot_send_loop, args=(idx,), daemon=True)
               for idx in range(workers)]
    for thread in threads:
        thread.start()
    for q in core._hot_queues:
        q.join()
    core._hot_stop_event.set()
    for thread in threads:
        thread.join(timeout=2.0)

    expected_ids = {fill.leader_fill_id for fill in fills}
    counts = Counter(audited_ids)
    if set(counts) != expected_ids or any(n != 1 for n in counts.values()):
        raise AssertionError(f"fake per-fill coverage mismatch: ids={len(counts)} rows={len(audited_ids)}")
    if len(orders) != 300:
        raise AssertionError(f"expected 300 wallet/coin orders, got {len(orders)}")
    if overlap or core._queued_keys or any(q.qsize() for q in core._hot_queues):
        raise AssertionError(f"queue/coin invariant failed: overlap={len(overlap)} queued={len(core._queued_keys)}")

    starts_latency = [starts[fid] - queued_at[fid] for fid in expected_ids]
    replies_latency = [replies[fid] - queued_at[fid] for fid in expected_ids]
    return {
        "workers": workers, "inner": inner, "fills": len(fills), "orders": len(orders),
        "queue_peak": peak_depth, "audit_ids": len(counts),
        "start_p50_s": percentile(starts_latency, 0.50),
        "start_p99_s": percentile(starts_latency, 0.99),
        "reply_p50_s": percentile(replies_latency, 0.50),
        "reply_p99_s": percentile(replies_latency, 0.99),
        "no_same_coin_overlap": not overlap,
    }


def main():
    with tempfile.TemporaryDirectory(prefix="queue_burst_offline_") as tmp:
        os.environ.update({
            "HL_LEADER_NETWORK": "testnet",
            "HL_FOLLOWER_NETWORK": "testnet",
            "HL_LIVE_AUDIT_DIR": tmp,
            "HL_LIVE_ENV_FILE": str(Path(tmp) / "no-env-file"),
            "HL_LIVE_WS_ENABLED": "0",
            "HL_LIVE_AUTO_SEND_ENABLED": "0",
            "HL_LIVE_EARLY_PREWARM": "0",
            "HL_LIVE_PREWARM_SYMBOL_META": "0",
            "HL_LIVE_PREWARM_SDK_CLIENT": "0",
            "HL_LIVE_FOREIGN_WS_SCAN": "0",
            "HL_LIVE_HOT_BATCH_MAX": "500",
        })
        import HL_Live_Copy_Service_Core as c

        wallets = [f"0x{i:040x}" for i in range(1, 11)]
        coins = [f"TESTCOIN{i:02d}" for i in range(30)]
        for repeat in range(1, 4):
            for workers, inner in ((4, 6), (4, 8)):
                result = run_profile(c, wallets, coins, workers, inner, 0.958)
                result["repeat"] = repeat
                print("BENCH::" + " ".join(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}"
                                           for k, v in result.items()))

        # The existing planner must still prioritize a close/reduction ahead of an entry.
        core = build_core(c, 4)
        close = c.LeaderFill("close-first", wallets[0], coins[0], "SELL", 100.0, 1.0,
                             1_800_000_000_002, "TEST", 0, {"dir": "Close Long"})
        entry = c.LeaderFill("entry-second", wallets[0], coins[1], "BUY", 100.0, 1.0,
                             1_800_000_000_001, "TEST", 0, {"dir": "Open Long"})
        if [f.leader_fill_id for f in core._plan_batch([entry, close])] != ["close-first", "entry-second"]:
            raise AssertionError("exit priority changed")
        print("RESULT::exit_priority_PASS")


if __name__ == "__main__":
    main()
