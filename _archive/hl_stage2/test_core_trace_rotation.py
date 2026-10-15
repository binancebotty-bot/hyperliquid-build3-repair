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
print("RESULT::trace_rotation_%s | %s" % ("PASS" if ok else "FAIL", names))
sys.exit(0 if ok else 1)
