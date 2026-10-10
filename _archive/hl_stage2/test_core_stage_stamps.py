#!/usr/bin/env python3
"""PR 1 stage stamps: stamp_fill is first-write-wins and never raises; the timing dict of a send attempt carries
the stamps; an old-header send_attempts.csv is migrated (rows kept, new columns appended at the END).
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_stage_stamps.py"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="stamps_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_WS_ENABLED": "0"})
import HL_Live_Copy_Service_Core as c  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


fill = c.LeaderFill("f1", "0x" + "a" * 40, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "WS_CAPTURED")
c.stamp_fill(fill, "enqueued_ms")
first = fill.raw["_stamps"]["enqueued_ms"]
import time  # noqa: E402
time.sleep(0.01)
c.stamp_fill(fill, "enqueued_ms")
check("S1_STAMP_IS_FIRST_WRITE_WINS", fill.raw["_stamps"]["enqueued_ms"] == first)
c.stamp_fill(object(), "x")
c.stamp_fill(None, "x")
check("S2_STAMP_NEVER_RAISES", True)

for k in ("picked_up_ms", "process_started_ms", "prewarm_done_ms", "lock_acquired_ms", "intent_written_ms"):
    c.stamp_fill(fill, k)
intent = c.Intent(intent_id="i1", fill=fill, copy_side="BUY", copy_size=1.0, copy_notional=100.0, wallet_mode="LIVE",
                  copy_mode="fixed", decision="ENTRY_ALLOWED", reason="", sleeve_id="s", position_id="",
                  position_direction_before="FLAT", wallet_position_before=0.0, coin_net_before=0.0,
                  reduce_only_intended=False, reduce_only_sent_planned=False, created_at_ms=c.utc_now_ms())
timing = c.SenderGateway._base_timing(intent)
check("S3_TIMING_CARRIES_ALL_STAMPS", all(k in timing for k in c.STAGE_STAMP_KEYS), str(sorted(timing)))

check("S4_NEW_COLUMNS_AT_THE_END", c.SEND_ATTEMPT_FIELDS[-len(c.STAGE_STAMP_KEYS):] == list(c.STAGE_STAMP_KEYS))
check("S5_TIMING_FIELDS_INCLUDE_STAMPS", all(k in c.SEND_TIMING_FIELDS for k in c.STAGE_STAMP_KEYS))

old_fields = [f for f in c.SEND_ATTEMPT_FIELDS if f not in c.STAGE_STAMP_KEYS]
path = tmp / "old_send_attempts.csv"
with path.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=old_fields)
    w.writeheader()
    w.writerow({"attempt_id": "a1", "coin": "BTC", "status": "ORDER_FILLED"})
c.append_csv(path, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "a2", "coin": "ETH", "status": "ORDER_FILLED",
                                          "enqueued_ms": 123})
rows = list(csv.DictReader(path.open(newline="", encoding="utf-8-sig")))
check("S6_OLD_HEADER_MIGRATED_ROWS_KEPT", [r["attempt_id"] for r in rows] == ["a1", "a2"] and rows[0]["coin"] == "BTC"
      and rows[0]["enqueued_ms"] == "" and rows[1]["enqueued_ms"] == "123")
header = next(csv.reader(path.open(newline="", encoding="utf-8-sig")))
check("S7_HEADER_ENDS_WITH_STAMPS", header[-len(c.STAGE_STAMP_KEYS):] == list(c.STAGE_STAMP_KEYS))

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
