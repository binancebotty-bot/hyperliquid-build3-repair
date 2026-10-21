#!/usr/bin/env python3
"""Offline 30k-fill trace catch-up; no engine or sender is started."""
import builtins
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

N = 30_000
SCRATCH_BYTES = 30 * 1024 * 1024
CONTROL_ONLY = "--baseline-control" in sys.argv[2:]
CORE_ROOT = (
    Path(sys.argv[1]).resolve()
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--")
    else Path(__file__).resolve().parent
)

with tempfile.TemporaryDirectory(prefix="fill_trace_buffer_") as temp:
    tmp = Path(temp)
    os.environ["HL_LIVE_ENV_FILE"] = str(tmp / "missing.env")
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp / "audit")
    sys.path.insert(0, str(CORE_ROOT))
    import HL_Live_Copy_Service_Core as C

    C.CORE_RUNTIME_STATE_FILE = str(tmp / "core_state.json")
    C.TRACE_MAX_BYTES_FILL = 32_000_000
    trace = tmp / "fill_trace.jsonl"
    prefix, suffix = '{"seed":"', '"}\n'
    seed = prefix + ("x" * (SCRATCH_BYTES - len(prefix) - len(suffix))) + suffix
    trace.write_text(seed, encoding="utf-8")

    core = object.__new__(C.LiveCopyCore)
    core._fill_trace_lock = threading.Lock()
    checks, lock_held, opens, sink_lines = [], [], [0], []
    real_open, real_rotate = builtins.open, C.rotate_trace_file

    class Sink:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def write(self, line):
            sink_lines.append(line)

        def writelines(self, lines):
            sink_lines.extend(lines)

    def tracked_open(*args, **kwargs):
        if str(args[0]).endswith("fill_trace.jsonl"):
            opens[0] += 1
            if CONTROL_ONLY:
                return Sink()
        return real_open(*args, **kwargs)

    def tracked_rotate(path, max_bytes, keep=0):
        checks.append(path)
        if core._fill_trace_lock.locked():
            lock_held.append(True)
        if not CONTROL_ONLY:
            return real_rotate(path, max_bytes, keep)

    C.open, C.rotate_trace_file = tracked_open, tracked_rotate
    for i in range(N):
        core._fill_trace("catchup_net_zero", None, {"id": "synthetic-%05d" % i})
    core._fill_trace("cycle_end", None, {"cycle_id": "synthetic-catchup"})

    if CONTROL_ONLY:
        records = [json.loads(line) for line in sink_lines]
    else:
        rotated = sorted(
            trace.parent.glob("fill_trace.jsonl.*"),
            key=lambda path: int(path.suffix[1:]),
            reverse=True,
        )
        paths = rotated + [trace]
        records = [
            json.loads(line)
            for path in paths
            for line in path.read_text(encoding="utf-8").splitlines()
        ]

    synthetic_ids = [
        row["id"] for row in records if str(row.get("id", "")).startswith("synthetic-")
    ]
    batch_size = getattr(C, "FILL_TRACE_BATCH_WRITES", 128)
    expected_checks = (N + 1) // batch_size
    expected_appends = (N + batch_size) // batch_size
    ok = (
        len(seed.encode("utf-8")) == SCRATCH_BYTES
        and len(records) == (N + 1 if CONTROL_ONLY else N + 2)
        and len(synthetic_ids) == N
        and synthetic_ids == ["synthetic-%05d" % i for i in range(N)]
        and records[-1].get("k") == "cycle_end"
        and len(checks) == expected_checks
        and not lock_held
        and opens[0] == expected_appends
    )
    if not CONTROL_ONLY:
        ok = ok and len(rotated) == 1 and records[0].get("seed", "").startswith("x")
    print(
        "RESULT::FILL_TRACE_30K_30MIB_%s rows=%d size_checks=%d appends=%d global_lock_held=%d"
        % ("PASS" if ok else "FAIL", len(records), len(checks), opens[0], len(lock_held))
    )
    sys.exit(0 if ok else 1)
