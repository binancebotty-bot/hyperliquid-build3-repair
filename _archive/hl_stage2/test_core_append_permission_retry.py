#!/usr/bin/env python3
"""append_csv retries a PermissionError (Windows handle held by another reader) a bounded number of times,
only after the partial row was cleanly truncated; exhausted attempts keep the loud failure + durable record + spill;
HL_LIVE_CSV_APPEND_RETRIES=0 preserves the old single-attempt behaviour."""
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


tmp = Path(tempfile.mkdtemp(prefix="appendperm_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
import HL_Live_Copy_Service_Core as c

c.AUDIT_WRITE_FAILURES_FILE.parent.mkdir(parents=True, exist_ok=True)  # journal dir (the append-only dir is otherwise created lazily)
fields = ["a", "b"]
real_open = Path.open
real_sleep = c.time.sleep
sleeps = []
c._schedule_audit_flush = lambda *a, **k: None  # no background replay: the spill is inspected and replayed explicitly
c.time.sleep = lambda s: sleeps.append(s)  # no real waiting; record the backoff schedule


class PartialThenDenied:
    """Writes half the row, flushes it to disk, then fails like a Windows sharing violation."""
    def __init__(self, f):
        self.f = f

    def write(self, s):
        self.f.write(s[: max(1, len(s) // 2)])
        self.f.flush()
        raise PermissionError(errno.EACCES, "Permission denied")

    def flush(self):
        self.f.flush()

    def fileno(self):
        return self.f.fileno()

    @property
    def closed(self):
        return self.f.closed

    def close(self):
        self.f.close()


def run(name, fail_times, retries, backoff_ms="40", path=None, **kw):
    """Append {"a": "x"} to a fresh file; the first `fail_times` opens write a partial row then raise PermissionError."""
    c._CSV_APPEND_RETRIES = retries
    c._CSV_APPEND_BACKOFF_SEC = float(backoff_ms) / 1000.0
    p = path or (tmp / (name + ".csv"))
    c.append_csv(p, fields, {"a": "1", "b": "2"})
    c._close_audit_handle(p)  # force a fresh open() for the append under test
    good = p.read_bytes()
    state = {"opens": 0, "sizes": []}

    def fake_open(self, *a, **k):
        f = real_open(self, *a, **k)
        if self == p and a and a[0] == "a":
            state["opens"] += 1
            state["sizes"].append(self.stat().st_size)  # size seen by each attempt: must always be the clean size
            if state["opens"] <= fail_times:
                return PartialThenDenied(f)
        return f

    sleeps.clear()
    c._AUDIT_WRITE_FAILURES["count"] = 0
    c._CSV_APPEND_RETRY_STATS["count"] = 0
    fails_before = c.audit_write_failure_count()
    Path.open = fake_open
    raised, ret = False, None
    try:
        ret = c.append_csv(p, fields, {"a": "3", "b": "4"}, **kw)
    except Exception:
        raised = True
    finally:
        Path.open = real_open
        c._close_audit_handle(p)
    return p, good, state, ret, raised, fails_before


# 1. succeeds on the 3rd attempt
p, good, st, ret, raised, fb = run("third", fail_times=2, retries=5, retry_permission=True)
rows = list(c.read_csv_rows(p))
check("SUCCEEDS_ON_THIRD_ATTEMPT", ret is True and not raised and st["opens"] == 3, f"ret={ret} opens={st['opens']}")
check("EVERY_ATTEMPT_STARTS_FROM_CLEAN_SIZE", set(st["sizes"]) == {len(good)}, str(st["sizes"]))
check("ROW_WRITTEN_ONCE_NO_PARTIAL", [r["a"] for r in rows] == ["1", "3"] and p.read_bytes().startswith(good), str(rows))
check("RETRY_COUNTER_AND_BACKOFF", c._CSV_APPEND_RETRY_STATS["count"] == 2 and sleeps == [0.04, 0.08], f"{c._CSV_APPEND_RETRY_STATS} {sleeps}")
check("NO_FAILURE_RECORDED_WHEN_RETRY_SUCCEEDS", c.audit_write_failure_count() == fb and not c._fallback_path(p).exists(), "")

# 2. attempts exhausted: loud failure + durable record + spill, partial truncated
p, good, st, ret, raised, fb = run("exhausted", fail_times=99, retries=3, retry_permission=True)
check("EXHAUSTED_ATTEMPT_COUNT", st["opens"] == 4, f"opens={st['opens']}")
check("EXHAUSTED_LEAVES_NO_PARTIAL_ROW", p.read_bytes() == good, repr(p.read_bytes()[-20:]))
check("EXHAUSTED_RECORDS_FAILURE", ret is False and c.audit_write_failure_count() > fb
      and "PermissionError" in c.AUDIT_WRITE_FAILURES_FILE.read_text(encoding="utf-8"), f"ret={ret} {c._AUDIT_WRITE_FAILURES}")
sp = c._fallback_path(p)
spilled = c.read_csv_rows(sp) if sp.exists() else []
check("EXHAUSTED_ROW_SPILLED", len(spilled) == 1 and spilled[0]["a"] == "3", str(spilled))
check("EXHAUSTED_RETRIES_COUNTED", c._CSV_APPEND_RETRY_STATS["count"] == 3 and sleeps == [0.04, 0.08, 0.16], f"{sleeps}")
c.replay_audit_fallback(p, fields)  # leave the spill replayed so later cases are independent

# 3. retries=0 preserves old behaviour: one attempt, no sleep, immediate failure record
p, good, st, ret, raised, fb = run("zero", fail_times=99, retries=0, retry_permission=True)
check("RETRIES_ZERO_SINGLE_ATTEMPT", st["opens"] == 1 and not sleeps and c._CSV_APPEND_RETRY_STATS["count"] == 0, f"opens={st['opens']} {sleeps}")
check("RETRIES_ZERO_OLD_FAILURE_PATH", ret is False and p.read_bytes() == good and c.audit_write_failure_count() > fb, f"ret={ret}")

# 3b. default call (no opt-in), and the send-lane files even with the opt-in absent, make one attempt and never sleep
for nm, pth in (("default", None), ("intents", c.ORDER_INTENTS_CSV), ("pending_send", c.SEND_ATTEMPTS_CSV)):
    p, good, st, ret, raised, fb = run("nosleep_" + nm, fail_times=99, retries=5, path=pth)
    check("NO_OPT_IN_%s_SINGLE_ATTEMPT_NO_SLEEP" % nm.upper(), st["opens"] == 1 and not sleeps and ret is False and p.read_bytes() == good,
          f"opens={st['opens']} sleeps={sleeps}")
    c.replay_audit_fallback(p, fields)
# reconciliation (opted in by its caller) retries
p, good, st, ret, raised, fb = run("recon", fail_times=2, retries=5, path=c.RECONCILIATION_CSV, retry_permission=True)
check("RECONCILIATION_RETRIES", ret is True and st["opens"] == 3 and sleeps == [0.04, 0.08], f"opens={st['opens']} {sleeps}")
_src = Path(c.__file__).read_text(encoding="utf-8")
check("RECON_CALLER_OPTS_IN", "append_csv(RECONCILIATION_CSV, RECONCILIATION_FIELDS, row, retry_permission=True)" in _src, "")
check("SEND_LANE_CALLERS_DO_NOT_OPT_IN", not any("retry_permission" in ln for ln in _src.splitlines() if "ORDER_INTENTS_CSV," in ln or "SEND_ATTEMPTS_CSV," in ln), "")

# 3c. concurrency: a reconciliation retry must not hold FILE_LOCK while it sleeps (order intents share that lock)
import threading
import time as _time

c._CSV_APPEND_RETRIES = 5
c._CSV_APPEND_BACKOFF_SEC = 0.04
pa = c.RECONCILIATION_CSV
pb = c.ORDER_INTENTS_CSV
c.append_csv(pa, fields, {"a": "1", "b": "2"})
c.append_csv(pb, fields, {"a": "1", "b": "2"})
c._close_audit_handle(pa)
c._close_audit_handle(pb)
a_sleeping, a_go = threading.Event(), threading.Event()
a_state = {"fails": 0}


def blocking_sleep(sec):
    a_sleeping.set()
    a_go.wait(10)  # A "sleeps" until released: far longer than B is allowed to take


def conc_open(self, *a, **k):
    f = real_open(self, *a, **k)
    if self == pa and a and a[0] == "a" and a_state["fails"] < 1:
        a_state["fails"] += 1
        return PartialThenDenied(f)
    return f


c.time.sleep = blocking_sleep
Path.open = conc_open
a_res = {}


def thread_a():
    a_res["ret"] = c.append_csv(pa, fields, {"a": "A", "b": "row"}, retry_permission=True)


ta = threading.Thread(target=thread_a)
ta.start()
got_sleep = a_sleeping.wait(5)
t0 = _time.monotonic()
b_ret = c.append_csv(pb, fields, {"a": "B", "b": "row"})  # same FILE_LOCK; must not wait for A's sleep
b_lat = _time.monotonic() - t0
b_done_while_a_sleeping = ta.is_alive() and not a_go.is_set()
a_go.set()
ta.join(10)
Path.open = real_open
c.time.sleep = lambda s: sleeps.append(s)
c._close_audit_handle(pa)
c._close_audit_handle(pb)
check("CONC_A_ENTERED_SLEEP", got_sleep, "")
check("CONC_B_NOT_BLOCKED_BY_A_SLEEP", b_ret is True and b_done_while_a_sleeping and b_lat < 1.0, f"ret={b_ret} lat={b_lat:.3f}")
rows_a = [r["a"] for r in c.read_csv_rows(pa)]
rows_b = [r["a"] for r in c.read_csv_rows(pb)]
check("CONC_A_ROW_LANDS_EXACTLY_ONCE", a_res.get("ret") is True and rows_a.count("A") == 1 and rows_a[-1] == "A", f"{a_res} {rows_a}")
check("CONC_B_ROW_LANDS_ONCE", rows_b.count("B") == 1 and rows_b[-1] == "B", str(rows_b))

# 3d. a caller already holding the lock (replay path, reentrant depth > 1) cannot be released: single attempt, old behaviour
sleeps.clear()
with c.FILE_LOCK:
    p, good, st, ret, raised, fb = run("reentrant", fail_times=99, retries=5, retry_permission=True)
check("REENTRANT_CALLER_NO_RETRY", st["opens"] == 1 and not sleeps and ret is False and p.read_bytes() == good,
      f"opens={st['opens']} sleeps={sleeps}")
c.replay_audit_fallback(p, fields)

# 4. backoff total is capped near 1s worst case even with a large retry count / base
p, good, st, ret, raised, fb = run("capped", fail_times=99, retries=50, backoff_ms="400", retry_permission=True)
check("BACKOFF_TOTAL_CAPPED", sum(sleeps) <= 1.0 + 1e-9 and sum(sleeps) > 0.9, f"{sleeps}")
c.replay_audit_fallback(p, fields)

# 5. non-PermissionError OSError (e.g. disk full) is NOT retried
c._CSV_APPEND_RETRIES = 5
p = tmp / "enospc.csv"
c.append_csv(p, fields, {"a": "1", "b": "2"})
c._close_audit_handle(p)
opens = []


def enospc_open(self, *a, **k):
    if self == p and a and a[0] == "a":
        opens.append(1)
        raise OSError(errno.ENOSPC, "No space left on device")
    return real_open(self, *a, **k)


sleeps.clear()
Path.open = enospc_open
try:
    ret = c.append_csv(p, fields, {"a": "3", "b": "4"})
finally:
    Path.open = real_open
check("ENOSPC_NOT_RETRIED", ret is False and len(opens) == 1 and not sleeps, f"opens={len(opens)} {sleeps}")

c.time.sleep = real_sleep
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
