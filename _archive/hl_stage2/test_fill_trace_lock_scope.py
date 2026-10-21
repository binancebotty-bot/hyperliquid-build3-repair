#!/usr/bin/env python3
"""Lock-scope checks for the persistent fill-trace append handle."""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as C


def core_at(path: Path):
    core = object.__new__(C.LiveCopyCore)
    C.CORE_RUNTIME_STATE_FILE = str(path.parent / "runtime.json")
    return core


def records(path: Path):
    archived = sorted(path.parent.glob(path.name + ".*"), key=lambda p: int(p.suffix[1:]), reverse=True)
    files = archived + [path]
    rows = []
    for item in files:
        if item.exists():
            rows.extend(json.loads(line) for line in item.read_text(encoding="utf-8").splitlines())
    return rows


def close_core(core):
    if core is None:
        return
    state = core.__dict__.get("_fill_trace_state")
    if state and state.get("fh") is not None:
        state["fh"].close()


def t1():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "fill_trace.jsonl"
        old_max, old_keep = C.TRACE_MAX_BYTES_FILL, C.TRACE_KEEP_FILES
        C.TRACE_MAX_BYTES_FILL, C.TRACE_KEEP_FILES = 5000, 1000
        try:
            core = core_at(path)
            for seq in range(30000):
                core._fill_trace("test", None, {"seq": seq})
            got = [row["seq"] for row in records(path)]
            return got == list(range(30000))
        finally:
            close_core(locals().get("core"))
            C.TRACE_MAX_BYTES_FILL, C.TRACE_KEEP_FILES = old_max, old_keep


def t2():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "fill_trace.jsonl"
        old_max, old_rotate = C.TRACE_MAX_BYTES_FILL, C.rotate_trace_file
        entered, release = threading.Event(), threading.Event()
        C.TRACE_MAX_BYTES_FILL = 1

        def slow_rotate(*args, **kwargs):
            entered.set()
            release.wait(2)
            return old_rotate(*args, **kwargs)

        C.rotate_trace_file = slow_rotate
        try:
            core = core_at(path)
            first = threading.Thread(target=core._fill_trace, args=("test", None, {"seq": 0}))
            first.start()
            assert entered.wait(2)
            started = time.monotonic()
            core._fill_trace("test", None, {"seq": 1})
            latency_ms = (time.monotonic() - started) * 1000
            release.set()
            first.join(3)
            return latency_ms < 200 and not first.is_alive(), latency_ms
        finally:
            release.set()
            close_core(locals().get("core"))
            C.rotate_trace_file, C.TRACE_MAX_BYTES_FILL = old_rotate, old_max


def t3():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "fill_trace.jsonl"
        old_max, old_rotate = C.TRACE_MAX_BYTES_FILL, C.rotate_trace_file
        entered, release = threading.Event(), threading.Event()
        C.TRACE_MAX_BYTES_FILL = 1

        def slow_rotate(*args, **kwargs):
            entered.set()
            release.wait(2)
            return old_rotate(*args, **kwargs)

        C.rotate_trace_file = slow_rotate
        try:
            core = core_at(path)
            trace = threading.Thread(target=core._fill_trace, args=("test", None, {"seq": 0}))
            trace.start()
            assert entered.wait(2)
            status_done = threading.Event()
            status = threading.Thread(target=lambda: status_done.set())
            status.start()
            status.join(0.2)
            release.set()
            trace.join(3)
            return status_done.is_set() and not trace.is_alive()
        finally:
            release.set()
            close_core(locals().get("core"))
            C.rotate_trace_file, C.TRACE_MAX_BYTES_FILL = old_rotate, old_max


if __name__ == "__main__":
    ok1 = t1()
    ok2, latency = t2()
    ok3 = t3()
    print("RESULT::fill_trace_lock_scope_%s | T1=%s T2=%.1fms T3=%s" %
          ("PASS" if ok1 and ok2 and ok3 else "FAIL", ok1, latency, ok3))
    raise SystemExit(0 if ok1 and ok2 and ok3 else 1)
