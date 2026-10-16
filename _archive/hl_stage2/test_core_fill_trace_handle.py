#!/usr/bin/env python3
"""Offline: _fill_trace keeps one append handle (no open/close per record) yet stays correct:
rows are on disk at once, rotation at the cap, a removed file is recreated, a changed state dir is followed."""
import json, os, sys, tempfile, threading, time
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as C

d1 = Path(tempfile.mkdtemp()); d2 = Path(tempfile.mkdtemp())
C.CORE_RUNTIME_STATE_FILE = d1 / "state.json"

class Fake:
    _fill_trace = C.LiveCopyCore._fill_trace

f = Fake()
fill = SimpleNamespace(leader_fill_id="id1", leader_wallet="0x" + "a" * 40, coin="BTC", timestamp_ms=1)
def rows(d):
    p = d / "fill_trace.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []

f._fill_trace("proc_start", fill); f._fill_trace("proc_end", fill, {"status_of": (True, "OK", None)})
r = rows(d1); assert [x["k"] for x in r] == ["proc_start", "proc_end"] and r[1]["status"] == "OK", r  # on disk at once

# threads: no row lost or torn
ts = [threading.Thread(target=lambda: [f._fill_trace("poll_dispatched", fill) for _ in range(200)]) for _ in range(8)]
[t.start() for t in ts]; [t.join() for t in ts]
assert len(rows(d1)) == 2 + 1600

# file removed by someone else: recreated within the 2 s re-check
(d1 / "fill_trace.jsonl").unlink(); time.sleep(2.2)
f._fill_trace("proc_start", fill); assert len(rows(d1)) == 1

# state dir changes: follows it
C.CORE_RUNTIME_STATE_FILE = d2 / "state.json"
f._fill_trace("proc_start", fill); assert len(rows(d2)) == 1 and len(rows(d1)) == 1

# rotation at the cap
C.TRACE_MAX_BYTES_FILL = 500
for _ in range(40): f._fill_trace("poll_dispatched", fill)
names = sorted(x.name for x in d2.iterdir())
assert "fill_trace.jsonl.1" in names, names
assert (d2 / "fill_trace.jsonl").stat().st_size <= 500 + 200
print("RESULT::fill_trace_handle_PASS | %s" % names)
