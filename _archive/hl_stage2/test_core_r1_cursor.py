#!/usr/bin/env python3
"""R1 outage-replay durability: the saved leader cursor never moves past a fill that is only in memory.

Test (1) a queued fill holds the cursor at its time; (2) it moves on once the fill is handled
Test (3) another leader's cursor is not held; (4) with nothing pending the cursor moves to the proposal
Test (5) a full-queue rejection leaves nothing pending
Test (6) simulated crash: cursor persisted at poll time is <= every unprocessed fill's time, so a restarted poll re-reads them

Run: python test_core_r1_cursor.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import queue
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40
B = "0x" + "b" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="r1cur_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_HOT_SEND_WORKERS": "2"})
    import HL_Live_Copy_Service_Core as c
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
        A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    core._hot_stop_event.clear()
    core.async_dispatch = True

    now = c.utc_now_ms()
    f1 = c.LeaderFill("r1a", A, "BTC", "BUY", 100.0, 1.0, now - 60000, "TEST", 0, {"oid": "1", "dir": "Open Long"})
    f2 = c.LeaderFill("r1b", A, "ETH", "BUY", 100.0, 1.0, now - 30000, "TEST", 0, {"oid": "2", "dir": "Open Long"})
    check("nothing_pending_cursor_moves", core.leader_cursor_next(A, now) == now)
    core._dispatch_fill(f1)
    core._dispatch_fill(f2)
    check("queued_fill_holds_cursor", core.leader_cursor_next(A, now) == now - 60000, str(core.leader_cursor_next(A, now)))
    check("other_leader_not_held", core.leader_cursor_next(B, now) == now)

    # a crash right now: the cursor that would be saved is not past any unprocessed fill
    saved = core.leader_cursor_next(A, now)
    check("crash_replay_rereads_all_unprocessed", all(f.timestamp_ms >= saved for f in (f1, f2)))

    # worker handles f1 only
    for q in core._hot_queues:
        got = []
        while not q.empty():
            got.append(q.get_nowait())
        for g in got:
            if g.leader_fill_id == "r1a":
                core._release_queued([g], q)
            else:
                q.put_nowait(g)
    check("cursor_advances_to_next_oldest", core.leader_cursor_next(A, now) == now - 30000, str(core.leader_cursor_next(A, now)))
    for q in core._hot_queues:
        got = []
        while not q.empty():
            got.append(q.get_nowait())
        if got:
            core._release_queued(got, q)
    check("handled_cursor_moves_on", core.leader_cursor_next(A, now) == now)

    for q in core._hot_queues:
        q.maxsize = 1
        try:
            q.put_nowait(f1)
        except queue.Full:
            pass
    f3 = c.LeaderFill("r1c", A, "SOL", "BUY", 100.0, 1.0, now - 5000, "TEST", 0, {"oid": "3", "dir": "Open Long"})
    ok = core._dispatch_fill(f3)
    check("full_queue_leaves_nothing_pending", ok is False and core.leader_cursor_next(A, now) == now, str(core._pending_ts))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
