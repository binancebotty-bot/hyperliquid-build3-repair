#!/usr/bin/env python3
"""Replay throughput (run 6f): the intent audit row is written outside the send lock; every allowed intent ends in a row.

Test (1) append_order_intent runs with the send lock NOT held; (2) the row is written before send_if_allowed runs
Test (3) send_if_allowed raising leaves a BLOCKED_SEND_EXCEPTION terminal row and returns SEND_EXCEPTION
Test (4) another worker can take the send lock while a slow audit append is in progress

Run: python test_core_intent_outside_lock.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="outlock_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                   "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MOCK_SEND": "1"})
import HL_Live_Copy_Service_Core as c

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


LEADER, FOLLOWER = "0x" + "a" * 40, "0x" + "c" * 40
c.USER_WALLET = FOLLOWER
c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": 100.0}
c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
EXP = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}
c.EXPOSURE_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP)
c.LEADER_FETCHER = c.EXPOSURE_FETCHER
c.atomic_write_json(c.LIVE_CONFIG_FILE, {
    "auto_send_enabled": False, "global_controls": {"min_notional": 1},
    "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100}}})
core = c.LiveCopyCore(source_csv=tmp / "none.csv")
core._hot_stop_event.set()
for t in core._hot_threads:
    t.join(timeout=2)

order = []
held_during_append = []
real_append = core.audit.append_order_intent
other_got_lock = []


def slow_append(intent):
    held_during_append.append(core._send_lock.locked())
    order.append("append")

    def other():
        got = core._send_lock.acquire(blocking=False)
        other_got_lock.append(got)
        if got:
            core._send_lock.release()
    th = threading.Thread(target=other)
    th.start()
    th.join()
    time.sleep(0.05)
    return real_append(intent)


core.audit.append_order_intent = slow_append
real_send = core.sender.send_if_allowed
core.sender.send_if_allowed = lambda i, r="": (order.append("send"), real_send(i, r))[1]

now = c.utc_now_ms()
f1 = c.LeaderFill("ol-1", LEADER, "BTC", "BUY", 100.0, 1.0, now, "WS_CAPTURED", 0, {"oid": "9", "dir": "Open Long"})
core._process_leader_fill(f1, None, "")
check("append_runs_without_send_lock", held_during_append == [False], str(held_during_append))
check("row_written_before_send", order[:2] == ["append", "send"], str(order))
check("other_worker_can_take_lock_during_append", other_got_lock == [True], str(other_got_lock))

# a send that raises still ends in a terminal row
def boom(intent, reason=""):
    raise RuntimeError("boom in send")


core.sender.send_if_allowed = boom
f2 = c.LeaderFill("ol-2", LEADER, "BTC", "BUY", 100.0, 1.0, now + 1, "WS_CAPTURED", 0, {"oid": "10", "dir": "Open Long"})
ok, status, intent = core._process_leader_fill(f2, None, "")
rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("leader_fill_id") == "ol-2"] if hasattr(c, "RECONCILIATION_CSV") else []
check("exception_returns_send_exception", (not ok) and status == "SEND_EXCEPTION", status)
check("exception_leaves_terminal_row", any("BLOCKED_SEND_EXCEPTION" in str(r) for r in rows), str(rows)[:300])

core.stop()
failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
