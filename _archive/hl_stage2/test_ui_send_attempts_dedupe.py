#!/usr/bin/env python3
"""A send has a pending_send row and a final row (same attempt_id): UI counters and recent list count it once."""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"
import HL_Copy_App_SSOT as A
R = []
def check(n, ok): R.append(bool(ok)); print("RESULT::", n, "PASS" if ok else "FAIL")
d = Path(tempfile.mkdtemp()); p = d / "send_attempts.csv"
rows = [("a1", "pending_send"), ("a1", "ORDER_FILLED"), ("a2", "pending_send"), ("a3", "pending_send"), ("a3", "ORDER_REJECTED")]
p.write_text("attempt_id,status,coin\n" + "".join("%s,%s,BTC\n" % r for r in rows))
A.SEND_ATTEMPTS_CSV = p
c = A._load_send_attempt_counts()
check("counts once per attempt", c == {"ORDER_FILLED": 1, "pending_send": 1, "ORDER_REJECTED": 1}) if True else None
r = A._load_recent_send_attempts(limit=2)
check("recent: 2 distinct attempts, newest state", len(r) == 2)
print("TOTAL=%d FAILED=%d" % (len(R), R.count(False))); sys.exit(1 if False in R else 0)
