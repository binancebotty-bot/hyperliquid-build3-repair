"""Synthetic-only check for local stage-latency summaries."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from report_live_fill_latency import STAGES, percentile, summarize


with tempfile.TemporaryDirectory(prefix="latency_report_") as tmp:
    trace = Path(tmp) / "fill_trace.jsonl"
    rows = [
        {"k": "proc_end", "stage_stamps": {"leader_fill_ms": 1_000, "enqueue_ms": 1_100,
         "pickup_ms": 1_300, "lane_start_ms": 1_400, "reply_ms": 1_700}},
        {"k": "proc_end", "stage_stamps": {"leader_fill_ms": 2_000, "enqueue_ms": 2_100,
         "pickup_ms": 2_200, "lane_start_ms": 2_300, "reply_ms": 2_500}},
        {"k": "proc_end", "stage_stamps": {"leader_fill_ms": 3_000, "enqueue_ms": 3_100,
         "pickup_ms": 3_200, "lane_start_ms": 3_300}},
        {"k": "proc_end", "status": "BLOCKED", "stage_stamps": {}},
        {"k": "other", "stage_stamps": {"leader_fill_ms": 1, "reply_ms": 2}},
    ]
    trace.write_text("\n".join(json.dumps(row) for row in rows) + "\nnot-json\n", encoding="utf-8")
    values, counts = summarize(trace)
    assert counts == {"proc_end_rows": 4, "rows_with_reply": 2, "missing_stage_rows": 2,
                      "malformed_json_lines": 1}, counts
    assert values["leader_fill_to_reply_ms"] == [700.0, 500.0], values
    assert percentile(values["leader_fill_to_reply_ms"], 0.50) == 500.0
    assert percentile(values["leader_fill_to_reply_ms"], 0.90) == 700.0
    assert len(values) == len(STAGES) == 5

print("PASS: synthetic p50/p90, incomplete rows, malformed input, and non-proc rows")
