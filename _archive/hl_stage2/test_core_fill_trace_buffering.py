#!/usr/bin/env python3
"""Offline 30k-fill trace buffering and rotation proof."""
import json
import os
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

N = 30_000
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="fill_trace_buffer_") as temp:
    tmp = Path(temp)
    os.environ["HL_LIVE_ENV_FILE"] = str(tmp / "missing.env")
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp / "audit")
    sys.path.insert(0, str(ROOT))
    import HL_Live_Copy_Service_Core as C

    C.CORE_RUNTIME_STATE_FILE = tmp / "core_state.json"
    C.TRACE_MAX_BYTES_FILL = 32_000_000
    trace = tmp / "fill_trace.jsonl"
    trace.write_text('{"seed":"' + ("x" * (30 * 1024 * 1024 - 12)) + '"}\n', encoding="utf-8")
    core = object.__new__(C.LiveCopyCore)
    core._fill_trace_condition = threading.Condition()
    core._fill_trace_buffer = deque(maxlen=C.FILL_TRACE_QUEUE_MAX)
    core._fill_trace_dropped = 0
    core._fill_trace_writer_done = False
    core._fill_trace_writer = threading.Thread(target=core._fill_trace_writer_loop, daemon=True)
    core._fill_trace_writer.start()
    for i in range(N):
        core._fill_trace("catchup_net_zero", None, {"id": f"synthetic-{i:05d}"})
    core._fill_trace("cycle_end", None, {"cycle_id": "synthetic-catchup"})
    # Deterministic wait (was: a 10 s poll, then join(timeout=5), which raced the writer under load and could read a
    # partly written trace). Tell the writer to finish, then wait for it to exit: it returns only after the queue is empty.
    with core._fill_trace_condition:
        core._fill_trace_writer_done = True
        core._fill_trace_condition.notify_all()
    core._fill_trace_writer.join(timeout=300)
    assert not core._fill_trace_writer.is_alive(), "fill trace writer did not finish"
    # Chronological order. Rotation is x.jsonl -> x.jsonl.1 (newest rotated) -> ... -> x.jsonl.N (oldest), and the live file is
    # the newest. The old sort put the live file FIRST, so whether a rotation happened mid-run (it depends on batch timing)
    # decided pass or fail. That was the flake.
    rotated = sorted(trace.parent.glob("fill_trace.jsonl.*"), key=lambda p: -int(p.name.rsplit(".", 1)[1]))
    paths = rotated + [trace]
    records = [json.loads(line) for path in paths for line in path.read_text(encoding="utf-8").splitlines()]
    ids = [r["id"] for r in records if str(r.get("id", "")).startswith("synthetic-")]
    ok = len(ids) == N and ids == [f"synthetic-{i:05d}" for i in range(N)] and records[-1]["k"] == "cycle_end"
    print(f"RESULT::FILL_TRACE_30K_30MIB_{'PASS' if ok else 'FAIL'} rows={len(records)} drops={sum(r.get('count', 0) for r in records if r.get('k') == 'fill_trace_drop')}")
    raise SystemExit(0 if ok else 1)
