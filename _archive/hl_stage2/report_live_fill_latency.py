"""Read p50/p90 durations from proc_end rows in an engine fill_trace.jsonl."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


STAGES = (
    ("leader_fill_to_enqueue_ms", "leader_fill_ms", "enqueue_ms"),
    ("enqueue_to_pickup_ms", "enqueue_ms", "pickup_ms"),
    ("pickup_to_lane_start_ms", "pickup_ms", "lane_start_ms"),
    ("lane_start_to_reply_ms", "lane_start_ms", "reply_ms"),
    ("leader_fill_to_reply_ms", "leader_fill_ms", "reply_ms"),
)


def _timestamp(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        return None
    return float(value)


def summarize(path: Path) -> tuple[dict[str, list[float]], dict[str, int]]:
    values = {name: [] for name, _, _ in STAGES}
    counts = {"proc_end_rows": 0, "rows_with_reply": 0, "missing_stage_rows": 0, "malformed_json_lines": 0}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                counts["malformed_json_lines"] += 1
                continue
            if not isinstance(row, dict) or row.get("k") != "proc_end":
                continue
            counts["proc_end_rows"] += 1
            stamps = row.get("stage_stamps")
            if not isinstance(stamps, dict):
                counts["missing_stage_rows"] += 1
                continue
            parsed = {key: _timestamp(stamps.get(key)) for _, start, end in STAGES for key in (start, end)}
            if parsed.get("reply_ms") is not None:
                counts["rows_with_reply"] += 1
            ordered = [parsed[key] for key in ("leader_fill_ms", "enqueue_ms", "pickup_ms", "lane_start_ms", "reply_ms")]
            if any(value is None for value in ordered) or any(b < a for a, b in zip(ordered, ordered[1:])):
                counts["missing_stage_rows"] += 1
            for name, start, end in STAGES:
                a, b = parsed[start], parsed[end]
                if a is not None and b is not None and b >= a:
                    values[name].append(b - a)
    return values, counts


def percentile(samples: list[float], q: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    return ordered[math.ceil(q * len(ordered)) - 1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fill_trace", type=Path, help="local fill_trace.jsonl path")
    args = parser.parse_args()
    try:
        values, counts = summarize(args.fill_trace)
    except OSError as exc:
        parser.error(f"cannot read fill trace: {exc}")
        return 2
    print("TRACE " + " ".join(f"{key}={value}" for key, value in counts.items()))
    for name, _, _ in STAGES:
        samples = values[name]
        p50, p90 = percentile(samples, 0.50), percentile(samples, 0.90)
        if p50 is None:
            print(f"{name} n=0 p50_ms=NA p90_ms=NA")
        else:
            print(f"{name} n={len(samples)} p50_ms={p50:g} p90_ms={p90:g}")
    if not values["leader_fill_to_reply_ms"]:
        print("LATENCY_RESULT::INCONCLUSIVE_NO_COMPLETE_STAGE_ROWS")
    else:
        print(f"LATENCY_RESULT::READY rows={len(values['leader_fill_to_reply_ms'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
