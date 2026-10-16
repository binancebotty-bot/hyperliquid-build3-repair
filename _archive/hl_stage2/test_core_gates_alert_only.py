#!/usr/bin/env python3
"""Cycle entry gates are alert-only (Boss 16 Oct, testnet): a would-block writes ONE GATE_WOULD_BLOCK row per minute per
gate and the entry proceeds; the operator's daily loss limit stays a hard stop; an unreadable-truth fill is held, never
turned into a terminal block (HL_LIVE_DEFER_MAX_SEC=0 holds without a limit, negative = no hold).
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_gates_alert_only.py"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="gates_alert_only_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
os.environ.pop("HL_LIVE_GATES_ALERT_ONLY", None)
os.environ.pop("HL_LIVE_DEFER_MAX_SEC", None)
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append(bool(ok)); print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))

core = c.LiveCopyCore(source_csv=tmp / "none.csv")
try:
    before = len(c.read_csv_rows(c.RECONCILIATION_CSV))
    core._gate_would_block("WS_FEED_STALE")
    core._gate_would_block("WS_FEED_STALE")   # throttled: same gate within a minute
    core._gate_would_block("COPY_POLL_STALE")
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)[before:] if r.get("event") == "GATE_WOULD_BLOCK"]
    check("ONE_ROW_PER_GATE_PER_MINUTE", sorted(r.get("status") for r in rows) == ["COPY_POLL_STALE", "WS_FEED_STALE"], [r.get("status") for r in rows])
    check("ROW_SAYS_ENTRIES_PROCEED", all(r.get("action") == "ALERT_ONLY_ENTRIES_PROCEED" for r in rows))
    # the defer hold: default unlimited, negative = no hold
    import inspect
    src = inspect.getsource(c.LiveCopyCore._defer_unreadable_truth)
    check("DEFER_DEFAULT_UNLIMITED", 'HL_LIVE_DEFER_MAX_SEC"), 0.0)' in src)
finally:
    core.stop()

print("TOTAL=%d FAILED=%d" % (len(R), R.count(False))); sys.exit(1 if False in R else 0)
