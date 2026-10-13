#!/usr/bin/env python3
"""The pending_send row (send_attempts.csv, written before every order) waits only for send_attempts users: a holder of the shared
audit-file lock (JSON replace, another CSV's scan) no longer delays it (Q19: pending_send 250-1150 ms, file_lock_wait up to 0.9 s).
A slow append names the code that held the lock in lock_contention.jsonl.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_send_lock_isolation.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="sendlock_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_WS_ENABLED": "0", "HL_LIVE_LOCK_DIAG_SEC": "0.1"})
import HL_Live_Copy_Service_Core as c  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


check("L1_SEND_FILE_HAS_OWN_LOCK", c._lock_for(c.SEND_ATTEMPTS_CSV) is c.SEND_FILE_LOCK and c._lock_for(c.ORDER_INTENTS_CSV) is c.FILE_LOCK)

c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "warm"})
c.append_csv(c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS, {"intent_id": "warm"})

holding = threading.Event()
release = threading.Event()


def hold_shared_lock():
    with c.FILE_LOCK:
        holding.set()
        release.wait(5)


def slow_shared_lock_holder_for_diag():
    hold_shared_lock()


t = threading.Thread(target=slow_shared_lock_holder_for_diag, name="holder")
t.start()
holding.wait(2)
t0 = time.monotonic()
c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "pending1", "status": "pending_send"})
dt = time.monotonic() - t0
check("L2_SEND_ROW_NOT_BLOCKED_BY_SHARED_LOCK", dt < 0.1, "%.3f s" % dt)
rows = c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
check("L3_ROW_WRITTEN", rows and rows[-1]["attempt_id"] == "pending1", str(rows[-1:]))

# another file still waits for the shared lock, and the wait is diagnosed with the holder's code
done = []
w = threading.Thread(target=lambda: (c.append_csv(c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS, {"intent_id": "i1"}), done.append(1)))
w.start()
time.sleep(0.4)
check("L4_OTHER_FILE_STILL_SERIALISED", not done)
release.set()
t.join(); w.join(5)
check("L5_OTHER_FILE_COMPLETES", done == [1])
diag = tmp / "lock_contention.jsonl"
lines = [json.loads(x) for x in diag.read_text().splitlines()] if diag.exists() else []
holder = [th for l in lines for th in l["threads"] if th["thread"] == "holder"]
check("L6_DIAG_NAMES_HOLDER_CODE", lines and holder and any("hold_shared_lock" in f for f in holder[0]["stack"]), str(lines[:1]))
check("L7_DIAG_HAS_PATH_AND_WAIT", lines and lines[0]["path"] == "order_intents.csv" and lines[0]["waited_ms"] >= 100, str(lines[:1]))

# tail/full reads and the send-cache see the row
tail = c.read_csv_tail_rows(c.SEND_ATTEMPTS_CSV, 0)
check("L8_TAIL_READ_SEES_ROWS", [r["attempt_id"] for r in tail][-1] == "pending1")
failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
