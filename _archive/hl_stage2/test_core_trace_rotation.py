#!/usr/bin/env python3
"""Offline: rotate_trace_file keeps numbered history instead of overwriting a single .old."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as C

d = Path(tempfile.mkdtemp()); p = d / "t.jsonl"
for n in range(5):
    p.write_text("gen%d\n" % n * 10)
    C.rotate_trace_file(p, 10, keep=3)
names = sorted(x.name for x in d.iterdir())
ok = names == ["t.jsonl.1", "t.jsonl.2", "t.jsonl.3"] and "gen4" in (d / "t.jsonl.1").read_text() and "gen2" in (d / "t.jsonl.3").read_text()
C.rotate_trace_file(p, 10, keep=3)  # missing file: no raise
small = d / "s.jsonl"; small.write_text("x"); C.rotate_trace_file(small, 10)
ok = ok and small.exists() and not (d / "s.jsonl.1").exists()
old_state = C.CORE_RUNTIME_STATE_FILE
old_rotate = C.rotate_trace_file
try:
    C.CORE_RUNTIME_STATE_FILE = d / "state.json"
    checks = []
    C.rotate_trace_file = lambda *args, **kwargs: checks.append(args[0].name)
    core = object.__new__(C.LiveCopyCore)
    for _ in range(129):
        core._fill_trace("test", None)
        core._poll_trace({"kind": "test"})
    ok = ok and checks.count("fill_trace.jsonl") == 2 and checks.count("leader_poll_trace.jsonl") == 2
finally:
    C.CORE_RUNTIME_STATE_FILE = old_state
    C.rotate_trace_file = old_rotate
print("RESULT::trace_rotation_%s | %s" % ("PASS" if ok else "FAIL", names))
sys.exit(0 if ok else 1)
