#!/usr/bin/env python3
"""RED-only SET-009 ruling contract checks; run directly with the project venv."""
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"
os.environ.pop("HL_LIVE_GATES_ALERT_ONLY", None)
import HL_Live_Copy_Service_Core as core

SOURCE = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8")
RESULTS = []

def check(clause, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"RESULT::{clause}_{'PASS' if ok else 'FAIL'}" + (f" | {detail}" if detail else ""))

# Gate contract must load, validate age and status instead of treating missing/stale data as matched.
gate_start = SOURCE.find("# Gate 4:")
gate_end = SOURCE.find("# Gate 5:", gate_start)
gate = SOURCE[gate_start:gate_end]
checks = {
    "CLAUSE_1_STALE_STATUS_BLOCKS_ENTRY_AT_REPO_DEFAULT": "DIVERGENCE_STATUS_STALE" in gate and "HL_LIVE_GATES_ALERT_ONLY" not in gate,
    "CLAUSE_2_MISSING_STATUS_BLOCKS_ENTRY_AT_REPO_DEFAULT": "DIVERGENCE_STATUS_MISSING" in gate,
    "CLAUSE_3_UNREADABLE_CORRUPT_STATUS_BLOCKS_ENTRY_AT_REPO_DEFAULT": "DIVERGENCE_STATUS_UNREADABLE" in gate,
    "CLAUSE_4_FRESH_MANUAL_MISMATCH_BLOCKS_ENTRY": "exchange_manual_mismatch" in gate,
}
for clause, ok in checks.items():
    check(clause, ok, "Gate 4 must enforce this independently of alert-only configuration")

# Send path must exempt closes from the stale-status entry gate while still reaching its decision.
send_start = SOURCE.find("def send_if_allowed")
send = SOURCE[send_start:send_start + 18000]
check("CLAUSE_5_STALE_STATUS_NEVER_BLOCKS_REDUCE_ONLY_CLOSE_AND_REACHES_SEND_DECISION",
      "DIVERGENCE_STATUS_STALE" not in send or re.search(r"reduce_only[\s\S]{0,600}DIVERGENCE_STATUS_STALE", send) is not None,
      "close exemption must be explicit at send decision")

class Intent:
    notes = ""
    reason = ""
    wallet_position_before = 0
    copy_side = "SELL"
    copy_size = 1
    position_direction_before = "FLAT"
    before = 0

classified = core.classify_send_lifecycle(Intent())
check("CLAUSE_6_FLAT_REDUCE_ONLY_ZERO_BEFORE_CLASSIFIED_AS_CLOSE_NOT_ENTRY",
      classified in {"REDUCE", "EXIT"}, f"classified={classified}")

check("CLAUSE_7_STALE_CONDITION_MACHINE_VISIBLE_IN_ERRORS_OR_SUMMARY",
      bool(re.search(r"errors\.csv|summary\.[A-Za-z_]*divergence|summary\.[A-Za-z_]*stale", SOURCE, re.I)),
      "must expose stale condition in errors.csv row and/or summary field")

print("TOTAL=%d FAILED=%d" % (len(RESULTS), RESULTS.count(False)))
sys.exit(1 if False in RESULTS else 0)
