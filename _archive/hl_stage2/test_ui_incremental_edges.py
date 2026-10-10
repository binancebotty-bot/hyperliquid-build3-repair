#!/usr/bin/env python3
"""UI2 review fixes: tail rows never show a half-written row; truncate-then-regrow resets; snapshot is a copy.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_ui_incremental_edges.py"""
import os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"
import HL_Copy_App_SSOT as A
R = []
def check(n, ok):
    R.append(bool(ok)); print("RESULT::", n, "PASS" if ok else "FAIL")
d = Path(tempfile.mkdtemp()); p = d / "t.csv"
def rows(a, b): return "".join("r%d,v%d\n" % (i, i) for i in range(a, b))
p.write_text("id,val\n" + rows(0, 50))
r, t = A._read_csv_incremental(p, tail_bytes=100)
check("tail total", t == 50 and r and r[-1]["id"] == "r49")
with p.open("a") as f: f.write("r50,v5")  # half-written row
r, t = A._read_csv_incremental(p, tail_bytes=100)
check("partial row not shown", t == 50 and r[-1]["id"] == "r49" and all(x["val"] is not None for x in r))
with p.open("a") as f: f.write("0\n")
r, t = A._read_csv_incremental(p, tail_bytes=100)
check("completed row shown", t == 51 and r[-1]["id"] == "r50" and r[-1]["val"] == "v50")
# small file (size <= tail) path
r, t = A._read_csv_incremental(p, tail_bytes=10**6)
check("small file rows == total", len(r) == t == 51)
# truncate in place, regrow beyond old size
size = p.stat().st_size
with p.open("w") as f: f.write("id,val\n" + rows(1000, 1100))
assert p.stat().st_size > size
r, t = A._read_csv_incremental(p, tail_bytes=10**6)
check("truncate+regrow resets", t == 100 and r[0]["id"] == "r1000")
# full mode returns a snapshot
r, t = A._read_csv_incremental(p)
n = len(r)
with p.open("a") as f: f.write(rows(2000, 2005))
A._read_csv_incremental(p)
check("full snapshot not mutated", len(r) == n)
print("TOTAL=%d FAILED=%d" % (len(R), R.count(False))); sys.exit(1 if False in R else 0)
