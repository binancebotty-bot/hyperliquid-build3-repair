#!/usr/bin/env python3
"""A failed or short audit append must not leave a half-written row behind (the next append would glue onto it)."""
import errno
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
R = []


def check(n, c_, d=""):
    R.append((n, bool(c_)))
    print("RESULT::%s_%s%s" % (n, "PASS" if c_ else "FAIL", (" | " + d) if (d and not c_) else ""))


tmp = Path(tempfile.mkdtemp(prefix="appendtrunc_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
import HL_Live_Copy_Service_Core as c

fields = ["a", "b"]
p = tmp / "t.csv"
c.append_csv(p, fields, {"a": "1", "b": "2"})
good = p.read_bytes()

real_open = Path.open


class PartialThenFull:
    def __init__(self, f):
        self.f = f

    def __enter__(self):
        self.f.__enter__()
        return self

    def __exit__(self, *a):
        return self.f.__exit__(*a)

    def write(self, s):
        self.f.write(s[: max(1, len(s) // 2)])
        self.f.flush()
        raise OSError(errno.ENOSPC, "No space left on device")

    def flush(self):
        self.f.flush()


def fake_open(self, *a, **k):
    f = real_open(self, *a, **k)
    return PartialThenFull(f) if self == p and a and a[0] == "a" else f


Path.open = fake_open
raised = False
try:
    c.append_csv(p, fields, {"a": "3", "b": "4"})
except OSError:
    raised = True
finally:
    Path.open = real_open
check("APPEND_FAILURE_STILL_RAISES", raised)
check("APPEND_FAILURE_LEAVES_NO_HALF_ROW", p.read_bytes() == good, repr(p.read_bytes()[-20:]))
c.append_csv(p, fields, {"a": "5", "b": "6"})
rows = list(c.read_csv_rows(p))
check("NEXT_APPEND_IS_A_CLEAN_ROW", [r["a"] for r in rows] == ["1", "5"], str(rows))
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
