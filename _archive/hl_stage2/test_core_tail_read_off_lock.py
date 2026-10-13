#!/usr/bin/env python3
"""read_csv_tail_rows (the integrity status reads the newest 24 MB of four audit files every 5 s) no longer reads those bytes while
holding the shared file lock, so audit appends from the send path do not queue behind it (Q19: file_lock_wait 147 s in 2 h, waits up
to 0.9 s). Results are unchanged.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_tail_read_off_lock.py
"""
from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="tailoff_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_WS_ENABLED": "0"})
import HL_Live_Copy_Service_Core as c  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


F = ["a", "b"]
p = tmp / "t.csv"
for i in range(2000):
    c.append_csv(p, F, {"a": i, "b": "x" * 40})

full = c.read_csv_tail_rows(p, 0)
check("T1_WHOLE_FILE", len(full) == 2000 and full[0]["a"] == "0" and full[-1]["a"] == "1999", str(len(full)))
small = c.read_csv_tail_rows(p, 5000)
check("T2_TAIL_WHOLE_ROWS_AND_HEADER", 0 < len(small) < 2000 and small[-1]["a"] == "1999" and all(r["b"] == "x" * 40 for r in small), str(len(small)))
check("T3_MISSING_FILE_EMPTY", c.read_csv_tail_rows(tmp / "none.csv", 100) == [])
e = tmp / "e.csv"
e.write_bytes(b"")
check("T4_EMPTY_FILE_EMPTY", c.read_csv_tail_rows(e, 100) == [])

# the lock must be free while the bytes are read
held = []
real_open = Path.open


class Probe:
    def __init__(self, fh): self._fh = fh
    def __getattr__(self, n): return getattr(self._fh, n)
    def read(self, *a):
        held.append(c.FILE_LOCK._is_owned())
        return self._fh.read(*a)
    def __enter__(self): return self
    def __exit__(self, *a): return self._fh.__exit__(*a)


def probing_open(self, mode="r", *a, **k):
    fh = real_open(self, mode, *a, **k)
    return Probe(fh) if self == p and "b" in mode else fh


Path.open = probing_open
try:
    c.read_csv_tail_rows(p, 5000)
    c.read_csv_tail_rows(p, 0)
finally:
    Path.open = real_open
check("T5_LOCK_NOT_HELD_DURING_READ", held and not any(held), str(held))

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
