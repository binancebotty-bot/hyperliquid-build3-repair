#!/usr/bin/env python3
"""A failed or short audit append must not:
  (a) leave a half-written row behind (next append would glue onto it),
  (b) lose the row (it is spilled to the append-only fallback),
  (c) raise so the caller's control flow is disrupted.
The next append after a failure writes a clean row, and the spilled row is
replayed by replay_audit_fallback."""
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
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(tmp),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LIVE_APPEND_RETRIES": "2",       # short retry budget for fast test
    "HL_LIVE_APPEND_BACKOFF_SEC": "0.01",
})
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
ret = None
try:
    ret = c.append_csv(p, fields, {"a": "3", "b": "4"})
except OSError:
    raised = True
finally:
    Path.open = real_open

check("APPEND_FAILURE_NO_RAISE", not raised, "append_csv should never raise -- it spills")
check("APPEND_FAILURE_RETURNS_FALSE", ret is False, f"ret={ret!r}")
check("APPEND_FAILURE_LEAVES_NO_HALF_ROW", p.read_bytes() == good, repr(p.read_bytes()[-20:]))

# the failed row must have been spilled, not dropped
sp = c._fallback_path(p)
spilled = c.read_csv_rows(sp) if sp.exists() else []
check("APPEND_FAILURE_SPILLS_ROW",
      len(spilled) == 1 and spilled[0]["a"] == "3", str(spilled))

# next append writes a clean row
c.append_csv(p, fields, {"a": "5", "b": "6"})
rows = list(c.read_csv_rows(p))
check("NEXT_APPEND_IS_A_CLEAN_ROW", [r["a"] for r in rows] == ["1", "5"], str(rows))

# spilled row is replayed
replayed = c.replay_audit_fallback(p, fields)
rows_after = list(c.read_csv_rows(p))
check("SPILLED_ROW_REPLAYED",
      replayed == 1 and [r["a"] for r in rows_after] == ["1", "5", "3"], f"replayed={replayed} rows={rows_after}")
check("SPILL_FILE_CLEARED", not sp.exists() or len(c.read_csv_rows(sp)) == 0, str(sp))
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
