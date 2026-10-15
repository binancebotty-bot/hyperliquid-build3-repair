#!/usr/bin/env python3
"""Offline: outage_classify and run_report read CSV fields over the 128 KB default (Q22 crash)."""
import sys, tempfile
from pathlib import Path
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here)); sys.path.insert(0, str(here.parents[1] / "tools"))
import outage_classify as oc
import run_report  # noqa: F401  (import sets the limit)
d = Path(tempfile.mkdtemp()); f = d / "order_intents.csv"
f.write_text("a,b\n1," + "x" * 200000 + "\n")
ok = len(list(oc._rows(f))[0]["b"]) == 200000
print("RESULT::csv_field_limit_%s" % ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
