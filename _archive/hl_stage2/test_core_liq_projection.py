#!/usr/bin/env python3
"""Cross-margin liquidation projection (Hyperliquid formula) used by the parity gate.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_liq_projection.py"""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.update({"HL_LIVE_AUDIT_DIR": tempfile.mkdtemp(), "HL_LIVE_ENV_FILE": "/nonexistent"})
import HL_Live_Copy_Service_Core as c
R = []
def check(n, ok, d=""):
    R.append(bool(ok)); print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))
p = c.project_liquidation_px
x = p(100.0, 0.0, 0.0, 1.0, 100.0, 10.0)
check("LONG_1X_NEVER_LIQUIDATES", x is not None and abs(x) < 1e-9, x)
x = p(100.0 / 3, 0.0, 0.0, 1.0, 100.0, 10.0)
check("LONG_3X_LIQ_ABOUT_70", x is not None and abs(x - 70.175) < 0.05, x)
y = p(100.0 / 3, 0.0, 0.0, -1.0, 100.0, 10.0)
check("SHORT_3X_LIQ_ABOVE_MARK", y is not None and 125 < y < 135, y)
z = p(100.0 / 3, 0.0, 1.0, 2.0, 100.0, 10.0)
check("ADDING_MOVES_LIQ_CLOSER", z is not None and z > x, (x, z))
check("FLAT_AFTER_IS_NONE", p(100.0, 0.0, 1.0, 0.0, 100.0, 10.0) is None)
check("BAD_INPUT_IS_NONE", p(100.0, 0.0, 0.0, 1.0, 0.0, 10.0) is None and p(100.0, 0.0, 0.0, 1.0, 100.0, 0.0) is None)
print("TOTAL=%d FAILED=%d" % (len(R), R.count(False))); sys.exit(1 if False in R else 0)
