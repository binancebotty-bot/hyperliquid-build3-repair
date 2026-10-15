#!/usr/bin/env python3
"""Offline: the Core reads audit CSV history with a >128 KB field (Q23 startup crash) and survives a damaged row."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as C

d = Path(tempfile.mkdtemp()); f = d / "order_intents.csv"
f.write_text("a,b\n1,ok\n2," + "x" * 300000 + "\n3,ok\n")
rows = list(C.iter_audit_history(f))
ok1 = [r["a"] for r in rows] == ["1", "2", "3"] and len(rows[1]["b"]) == 300000
ok2 = C.csv.field_size_limit() >= 2**24
# a row the reader rejects (NUL byte is fine in py3.11+, so force the error with a tiny limit)
C.csv.field_size_limit(10)
before = C.CSV_BAD_ROWS
g = d / "g.csv"; g.write_text("a,b\n1,ok\n2," + "y" * 50 + "\n3,ok\n")
rows2 = list(C.iter_csv_rows(g))
C.csv.field_size_limit(2**31 - 1)
ok3 = [r["a"] for r in rows2] == ["1", "3"] and C.CSV_BAD_ROWS == before + 1
ok = ok1 and ok2 and ok3
print("RESULT::core_csv_field_limit_%s | %s %s %s" % ("PASS" if ok else "FAIL", ok1, ok2, ok3))
sys.exit(0 if ok else 1)
