#!/usr/bin/env python3
"""A one-shot append-open failure must retain and retry the detached trace batch."""
import builtins
import collections
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="fill_trace_retry_") as temp:
    tmp = Path(temp)
    os.environ["HL_LIVE_ENV_FILE"] = str(tmp / "missing.env")
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp / "audit")
    sys.path.insert(0, str(ROOT))
    import HL_Live_Copy_Service_Core as C

    C.CORE_RUNTIME_STATE_FILE = tmp / "core_state.json"
    C.log_error = lambda *_args: None
    path = tmp / "fill_trace.jsonl"
    core = object.__new__(C.LiveCopyCore)
    core._fill_trace_condition = threading.Condition()
    core._fill_trace_buffer = collections.deque(maxlen=C.FILL_TRACE_QUEUE_MAX)
    core._fill_trace_dropped = 2
    core._fill_trace_writer_done = False
    original_open = builtins.open
    failures = {"open": True, "partial": True}

    class PartialWriteThenFail:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def tell(self):
            return self.handle.tell()

        def seek(self, *args):
            return self.handle.seek(*args)

        def truncate(self, *args):
            return self.handle.truncate(*args)

        def writelines(self, lines):
            self.handle.writelines(lines[:1])
            self.handle.flush()
            raise OSError("injected partial append failure")

        def flush(self):
            return self.handle.flush()

    def injected_open(file, mode="r", *args, **kwargs):
        if Path(file) == path and mode == "a" and failures["open"]:
            failures["open"] = False
            raise OSError("injected one-shot append-open failure")
        if Path(file) == path and mode == "a" and failures["partial"]:
            failures["partial"] = False
            return PartialWriteThenFail(original_open(file, mode, *args, **kwargs))
        return original_open(file, mode, *args, **kwargs)

    builtins.open = injected_open
    core._fill_trace_buffer.append('{"k":"queued","seq":1}\n')
    core._fill_trace_writer = threading.Thread(target=core._fill_trace_writer_loop, daemon=True)
    core._fill_trace_writer.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if path.exists() and path.stat().st_size and not core._fill_trace_buffer:
            break
        time.sleep(0.01)
    with core._fill_trace_condition:
        core._fill_trace_writer_done = True
        core._fill_trace_condition.notify()
    core._fill_trace_writer.join(timeout=2)
    builtins.open = original_open
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []
    ok = (not failures["open"] and not failures["partial"] and not core._fill_trace_writer.is_alive()
          and [r.get("seq") for r in records if r.get("k") == "queued"] == [1]
          and [r.get("count") for r in records if r.get("k") == "fill_trace_drop"] == [2])
    print(f"RESULT::FILL_TRACE_APPEND_RETRY_{'PASS' if ok else 'FAIL'} rows={records}")
    raise SystemExit(0 if ok else 1)
