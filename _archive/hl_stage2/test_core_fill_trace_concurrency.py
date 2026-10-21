#!/usr/bin/env python3
"""Prove 64 producers do not wait on file I/O and retain every row."""
import json
import os
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

PRODUCERS = 64
PER_PRODUCER = 500
ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="fill_trace_concurrency_") as temp:
    tmp = Path(temp)
    os.environ["HL_LIVE_ENV_FILE"] = str(tmp / "missing.env")
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp / "audit")
    sys.path.insert(0, str(ROOT))
    import HL_Live_Copy_Service_Core as C

    C.CORE_RUNTIME_STATE_FILE = tmp / "core_state.json"
    core = object.__new__(C.LiveCopyCore)
    core._fill_trace_condition = threading.Condition()
    core._fill_trace_buffer = deque(maxlen=C.FILL_TRACE_QUEUE_MAX)
    core._fill_trace_dropped = 0
    core._fill_trace_writer_done = False
    core._fill_trace_writer = threading.Thread(target=core._fill_trace_writer_loop, daemon=True)
    core._fill_trace_writer.start()
    barrier = threading.Barrier(PRODUCERS)

    def producer(index):
        barrier.wait()
        for row in range(PER_PRODUCER):
            core._fill_trace("producer", None, {"producer": index, "row": row})

    threads = [threading.Thread(target=producer, args=(i,)) for i in range(PRODUCERS)]
    started = time.perf_counter()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - started
    with core._fill_trace_condition:
        while core._fill_trace_buffer:
            core._fill_trace_condition.wait(timeout=0.05)
        core._fill_trace_writer_done = True
        core._fill_trace_condition.notify()
    core._fill_trace_writer.join(timeout=5)
    path = tmp / "fill_trace.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    rows = {(r.get("producer"), r.get("row")) for r in records if r.get("k") == "producer"}
    drops = sum(int(r.get("count", 0)) for r in records if r.get("k") == "fill_trace_drop")
    expected = {(producer, row) for producer in range(PRODUCERS) for row in range(PER_PRODUCER)}
    ok = rows == expected and drops == 0 and not core._fill_trace_writer.is_alive()
    print(f"RESULT::FILL_TRACE_64_PRODUCER_{'PASS' if ok else 'FAIL'} rows={len(rows)} drops={drops} elapsed_ms={elapsed * 1000:.1f}")
    raise SystemExit(0 if ok else 1)
