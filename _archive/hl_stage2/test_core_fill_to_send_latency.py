#!/usr/bin/env python3
"""Fill-to-send latency is derived from the websocket receive and real-send timestamps and logged for the UI."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TMP = Path(tempfile.mkdtemp(prefix="fill_to_send_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(TMP),
    "HL_LIVE_ENV_FILE": str(TMP / "missing.env"),
    "HL_LIVE_WS_ENABLED": "0",
})
import HL_Live_Copy_Service_Core as c  # noqa: E402

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


start = 1_000
send = 2_750
written = 3_000
timing = c.SenderGateway._finish_timing({"ws_received_ms": start, "send_real_started_ms": send}, written)
check("F2S_DURATION_IS_RECEIVE_TO_REAL_SEND", timing.get("fill_to_send_ms") == 1_750,
      str(timing.get("fill_to_send_ms")))
check("F2S_SOURCE_TIMESTAMPS_RETAINED", timing.get("ws_received_ms") == start
      and timing.get("send_real_started_ms") == send)
check("F2S_DURATION_IS_IN_UI_READABLE_SEND_SCHEMA",
      "fill_to_send_ms" in c.SEND_TIMING_FIELDS and "fill_to_send_ms" in c.SEND_ATTEMPT_FIELDS)

c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
    "attempt_id": "latency-1",
    "ws_received_ms": start,
    "send_real_started_ms": send,
    "fill_to_send_ms": timing.get("fill_to_send_ms", ""),
})
rows = c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
row = next((r for r in rows if r.get("attempt_id") == "latency-1"), {})
check("F2S_DURATION_AND_TIMESTAMPS_ARE_LOGGED",
      row.get("ws_received_ms") == str(start)
      and row.get("send_real_started_ms") == str(send)
      and row.get("fill_to_send_ms") == "1750", str(row))

failed = [name for name, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
