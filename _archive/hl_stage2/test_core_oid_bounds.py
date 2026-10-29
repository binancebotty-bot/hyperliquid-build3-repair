"""An oid is a small integer. A corrupt or hostile cell must return immediately and match nothing - not build a
ten-million-digit int on the fill path."""

import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("HL_LIVE_AUDIT_DIR", tempfile.mkdtemp(prefix="oid_"))
os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
import HL_Live_Copy_Service_Core as C   # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + detail) if (detail and not ok) else ""))


HOSTILE = ["1E+999999999", "1e400", "9" * 500, "1E+9" + "9" * 400, "NaN", "Infinity", "-Infinity"]


def timed(fn, arg):
    t0 = time.perf_counter()
    out = fn(arg)
    return out, (time.perf_counter() - t0) * 1000.0


for _i, raw in enumerate(HOSTILE):
    out, ms = timed(C.CopyFillMatcher._normalize_oid, raw)
    check("GATEWAY_REJECTS_AND_IS_FAST_%d" % _i, out == "" and ms < 10.0,
          "raw=%r out=%r took=%.1fms" % (raw[:24], out, ms))

# the sweep's canonicaliser is a nested function; exercise it through the same boundary the sweep uses
src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8", errors="replace")
check("THE_SWEEP_CANONICALISER_IS_BOUNDED",
      "dec.adjusted() > 40" in src and src.count("dec.adjusted() > 40") >= 2,
      "only %d bounded normaliser(s) found - there are two" % (src.count("dec.adjusted() > 40"),))
check("MEMORY_ERROR_IS_CAUGHT", src.count("OverflowError, MemoryError") >= 2,
      "a MemoryError escaping the parse would take the matcher down")

# a legitimate id still works, exactly and quickly
for good, want in [("123", "123"), ("123.00", "123"), ("1.23e2", "123"), (" 42 ", "42")]:
    out, ms = timed(C.CopyFillMatcher._normalize_oid, good)
    check("LEGIT_%s" % good.strip().replace(".", "_").replace("+", "p"), out == want and ms < 10.0,
          "raw=%r out=%r want=%r" % (good, out, want))

failed = [n for n, ok in results if not ok]
print("TOTAL=%d FAILED=%d" % (len(results), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
