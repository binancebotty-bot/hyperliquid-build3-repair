#!/usr/bin/env python3
"""Per-gate send stamps (ownership gate, liquidation parity, wire validation, margin mode, pending-send row) are columns
of send_attempts.csv, appended at the END so an older file is migrated with its rows kept.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_send_stage_stamps2.py"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="stamps2_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_WS_ENABLED": "0"})
import HL_Live_Copy_Service_Core as c  # noqa: E402

RESULTS = []
NEW = ["ownership_gate_started_ms", "ownership_gate_finished_ms", "liq_parity_started_ms", "liq_parity_finished_ms",
       "wire_validated_ms", "margin_mode_started_ms", "margin_mode_finished_ms", "pending_send_done_ms"]


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


check("T1_NEW_COLUMNS_IN_ATTEMPT_FIELDS_AT_END", c.SEND_ATTEMPT_FIELDS[-len(NEW):] == NEW, str(c.SEND_ATTEMPT_FIELDS[-9:]))
check("T2_NEW_COLUMNS_IN_TIMING_FIELDS_AT_END", c.SEND_TIMING_FIELDS[-len(NEW):] == NEW)
old = [f for f in c.SEND_ATTEMPT_FIELDS if f not in NEW]
p = c.SEND_ATTEMPTS_CSV
p.parent.mkdir(parents=True, exist_ok=True)
with p.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=old)
    w.writeheader()
    w.writerow({"attempt_id": "a1", "coin": "BTC", "status": "ORDER_FILLED"})
c.append_csv(p, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "a2", "coin": "ETH", "margin_mode_started_ms": 5, "pending_send_done_ms": 9})
rows = list(csv.DictReader(p.open(encoding="utf-8")))
check("T3_OLD_FILE_MIGRATED_ROWS_KEPT", [r["attempt_id"] for r in rows] == ["a1", "a2"] and rows[0]["coin"] == "BTC", str(rows)[:200])
check("T4_NEW_STAMPS_WRITTEN", rows[1]["margin_mode_started_ms"] == "5" and rows[1]["pending_send_done_ms"] == "9")
failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
