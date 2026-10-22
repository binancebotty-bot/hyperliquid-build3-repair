#!/usr/bin/env python3
"""Audit append never drops a row: failed writes spill without blocking the caller,
later rows stay behind pending spills, and replay remains crash-safe. A failed append must NOT
stop the REPLAY_DEFERRED retry from being queued.

Run (from _archive/hl_stage2):
    HL_LIVE_ENV_FILE=/nonexistent python -u test_core_audit_append_never_drops.py
"""
from __future__ import annotations

import os, sys, tempfile, time, threading
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

tmp = Path(tempfile.mkdtemp(prefix="auditndd_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(tmp),
    "HL_LIVE_ENV_FILE": "/nonexistent",
})
import HL_Live_Copy_Service_Core as c  # noqa: E402

# Keep existing crash/replay scenarios deterministic; the dedicated background scenario enables the real scheduler.
c._CSV_APPEND_RETRIES = 0  # this file pins the no-retry contract (one attempt, no sleep); retries are covered by test_core_append_permission_retry.py
real_schedule_audit_flush = c._schedule_audit_flush
c._schedule_audit_flush = lambda *args: None

R = []

def check(n: str, ok: bool, d: str = "") -> None:
    R.append((n, bool(ok)))
    print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + d) if (d and not ok) else ""))

real_open = Path.open


# --- helper: patch Path.open to fail for a specific path in "a" (append) mode --------

class AppendFail:
    """Patches Path.open to raise *fail_exc* for *target* opened in mode "a",
    for the first *n_fail* attempts.  Counts every append-mode open of *target*."""
    def __init__(self, target: Path, n_fail: int, fail_exc: BaseException = PermissionError(13, "simulated sharing violation")):
        self.target = target
        self.n_fail = n_fail
        self.fail_exc = fail_exc
        self.count = 0
    def install(self) -> None:
        af = self
        _orig = real_open
        if hasattr(c, "_close_audit_handle"):
            c._close_audit_handle(self.target)
        def fake(self_path, *a, **k):
            f = _orig(self_path, *a, **k)
            if self_path == af.target and a and a[0] == "a":
                af.count += 1
                if af.count <= af.n_fail:
                    f.close()
                    raise af.fail_exc
            return f
        Path.open = fake
    def restore(self) -> None:
        Path.open = real_open


# --- Scenario 1: transient failure spills without blocking the caller --------------

fields1 = ["event", "status", "leader_fill_id"]
p1 = tmp / "append_only" / "test_retry.csv"
# establish header + first row
c.append_csv(p1, fields1, {"event": "E", "status": "S0", "leader_fill_id": "F0"})
af1 = AppendFail(p1, n_fail=2)
af1.install()
real_sleep = c.time.sleep
sleep_calls = []
c.time.sleep = lambda seconds: sleep_calls.append(seconds)
raised1 = False
ret1 = None
t0 = time.monotonic()
try:
    ret1 = c.append_csv(p1, fields1, {"event": "E", "status": "S1", "leader_fill_id": "F1"})
except Exception as exc:
    raised1 = True
t1 = time.monotonic()
c.time.sleep = real_sleep
af1.restore()
rows1 = c.read_csv_rows(p1)

check("APPEND_FAILURE_NO_RAISE", not raised1, f"raised={raised1}")
check("APPEND_FAILURE_SPILLS", ret1 is False and len(c.read_csv_rows(c._fallback_path(p1))) == 1, f"ret={ret1!r}")
check("APPEND_FAILURE_ONE_ATTEMPT", af1.count == 1, f"attempts={af1.count} expected=1")
check("APPEND_FAILURE_DOES_NOT_SLEEP", not sleep_calls, f"sleep calls={sleep_calls}")
check("APPEND_FAILURE_ROW_PRESERVED", len(rows1) == 1 and rows1[0]["leader_fill_id"] == "F0", str(rows1))
check("APPEND_AFTER_SPILL_STAYS_QUEUED",
      c.append_csv(p1, fields1, {"event": "E", "status": "S2", "leader_fill_id": "F2"}) is False,
      "later rows must not overtake a durable spill")
check("SPILL_ROWS_KEEP_APPEND_ORDER",
      [r["leader_fill_id"] for r in c.read_csv_rows(c._fallback_path(p1))] == ["F1", "F2"],
      str(c.read_csv_rows(c._fallback_path(p1))))
spill_rows_reader = c._spill_rows
spill_scans = []
c._spill_rows = lambda *args: (spill_scans.append(args[0]) or spill_rows_reader(*args))
for i in range(3, 13):
    c.append_csv(p1, fields1, {"event": "E", "status": "S%d" % i, "leader_fill_id": "F%d" % i})
c._spill_rows = spill_rows_reader
check("SPILL_QUEUE_AVOIDS_RESCANNING_OLD_ROWS", not spill_scans, "rescans=%d" % len(spill_scans))
check("SPILL_REPLAY_RESTORES_ORDER",
      c.replay_audit_fallback(p1, fields1) == 12
      and [r["leader_fill_id"] for r in c.read_csv_rows(p1)] == ["F%d" % i for i in range(13)],
      str(c.read_csv_rows(p1)))

# --- Scenario 1a: a row arriving during replay cannot be erased by cleanup --------

p_race = tmp / "append_only" / "test_replay_enqueue_race.csv"
c.append_csv(p_race, fields1, {"event": "E", "status": "S0", "leader_fill_id": "F_RACE0"})
af_race = AppendFail(p_race, n_fail=1000)
af_race.install()
c.append_csv(p_race, fields1, {"event": "E", "status": "S1", "leader_fill_id": "F_RACE1"})
af_race.restore()
orig_append_race = c.append_csv
injected_race_row = False


def append_with_new_spill_during_replay(path, fields, row, **kwargs):
    global injected_race_row
    if path == p_race and row.get("leader_fill_id") == "F_RACE1" and not injected_race_row:
        injected_race_row = True
        orig_append_race(path, fields, {"event": "E", "status": "S2", "leader_fill_id": "F_RACE2"})
    return orig_append_race(path, fields, row, **kwargs)


c.append_csv = append_with_new_spill_during_replay
try:
    c.replay_audit_fallback(p_race, fields1)
finally:
    c.append_csv = orig_append_race
check("REPLAY_ENQUEUE_RACE_ROW_RETAINED",
      any(r.get("leader_fill_id") == "F_RACE2" for r in c.read_csv_rows(c._fallback_path(p_race))),
      str(c.read_csv_rows(c._fallback_path(p_race))))
check("REPLAY_ENQUEUE_RACE_ALL_ROWS_RECOVERED",
      c.replay_audit_fallback(p_race, fields1) == 1
      and [r.get("leader_fill_id") for r in c.read_csv_rows(p_race)] == ["F_RACE0", "F_RACE1", "F_RACE2"],
      str(c.read_csv_rows(p_race)))

# --- Scenario 1b: a recovered append path is flushed without restarting -----------

p_bg = tmp / "append_only" / "test_background_flush.csv"
c.append_csv(p_bg, fields1, {"event": "E", "status": "S0", "leader_fill_id": "F_BG0"})
af_bg = AppendFail(p_bg, n_fail=1000)
af_bg.install()
c._schedule_audit_flush = real_schedule_audit_flush
check("BACKGROUND_TEST_APPEND_SPILLS", c.append_csv(p_bg, fields1, {"event": "E", "status": "S1", "leader_fill_id": "F_BG1"}) is False)
check("BACKGROUND_FLUSHER_SINGLE_WORKER",
      sum(t.name == "audit-spill-flusher" for t in threading.enumerate()) == 1,
      "flusher threads=%d" % sum(t.name == "audit-spill-flusher" for t in threading.enumerate()))
af_bg.restore()
deadline = time.monotonic() + 3.0
while time.monotonic() < deadline:
    if [r.get("leader_fill_id") for r in c.read_csv_rows(p_bg)] == ["F_BG0", "F_BG1"]:
        break
    threading.Event().wait(0.02)
check("BACKGROUND_FLUSH_REPLAYS_AFTER_RECOVERY",
      [r.get("leader_fill_id") for r in c.read_csv_rows(p_bg)] == ["F_BG0", "F_BG1"],
      str(c.read_csv_rows(p_bg)))
check("BACKGROUND_FLUSH_CLEARS_SPILL",
      not c._fallback_path(p_bg).exists() or not c.read_csv_rows(c._fallback_path(p_bg)),
      str(c.read_csv_rows(c._fallback_path(p_bg)) if c._fallback_path(p_bg).exists() else []))
c._schedule_audit_flush = lambda *args: None

# --- Scenario 2: spill to append-only fallback on persistent failure --------------

p2 = tmp / "append_only" / "test_spill.csv"
c.append_csv(p2, fields1, {"event": "E", "status": "S0", "leader_fill_id": "F0"})
size_before = p2.stat().st_size
af2 = AppendFail(p2, n_fail=1000)
af2.install()
raised2 = False
try:
    c.append_csv(p2, fields1, {"event": "E", "status": "S_spill", "leader_fill_id": "F_SPILL"})
except Exception:
    raised2 = True
af2.restore()

fallback_p = getattr(c, "FALLBACK_DIR", None) / "test_spill.csv.spill" if getattr(c, "FALLBACK_DIR", None) else None
spilled_rows = c.read_csv_rows(fallback_p) if fallback_p and fallback_p.exists() else []

check("APPEND_SPILL_NO_RAISE", not raised2, f"raised={raised2}")
check("APPEND_SPILL_ROW_IN_FALLBACK", len(spilled_rows) == 1 and spilled_rows[0]["leader_fill_id"] == "F_SPILL", str(spilled_rows))
check("APPEND_SPILL_MAIN_FILE_UNCHANGED", p2.stat().st_size == size_before,
      f"size={p2.stat().st_size} before={size_before}")
check("APPEND_SPILL_FAILURES_RECORDED", c.audit_write_failure_count() >= 1,
      f"failures={c.audit_write_failure_count()}")

# --- Scenario 3: failed append must not stop REPLAY_DEFERRED retry being queued ---

# Build a minimal mock core that exercises _terminal_after_exception with a real AuditLogWriter.
fill = c.LeaderFill("FILL_DEFERRED", "0x" + "a" * 40, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "WS_CAPTURED")
core = SimpleNamespace(
    audit=c.AuditLogWriter(),
    _deferred_lock=threading.Lock(),
    _deferred={},
    _idem_lock=threading.Lock(),
    _idem_accepted=set(),
    _past_send_keys=set(),
    _deferred_thread=SimpleNamespace(is_alive=lambda: True),  # don't spawn the real thread
    dedupe=SimpleNamespace(_lock=threading.RLock(), processed=set()),
)
core._rows_for_held_siblings = lambda fill, state: None  # no merged siblings in this fill
core._guard_key = c.LiveCopyCore._guard_key

# Make every append to RECONCILIATION_CSV fail (spill only, no raise after fix)
af3 = AppendFail(c.RECONCILIATION_CSV, n_fail=1000)
af3.install()
raised3 = False
try:
    c.LiveCopyCore._terminal_after_exception(core, fill, RuntimeError("boom: simulated process error"))
except Exception as exc:
    raised3 = True
af3.restore()

deferred_queued = fill.leader_fill_id in core._deferred or c.LiveCopyCore._guard_key(fill) in core._deferred

check("DEFERRED_APPEND_NO_RAISE", not raised3, f"raised={raised3}")
check("DEFERRED_RETRY_QUEUED", deferred_queued, str(core._deferred))

# Verify the REPLAY_DEFERRED row was spilled (not lost) into the fallback
fallback_recon = getattr(c, "FALLBACK_DIR", None) / "reconciliation.csv.spill" if getattr(c, "FALLBACK_DIR", None) else None
recon_spilled = c.read_csv_rows(fallback_recon) if fallback_recon and fallback_recon.exists() else []
check("DEFERRED_SPILLED_ROW_PRESERVED",
      len(recon_spilled) >= 1 and any(r.get("leader_fill_id") == "FILL_DEFERRED" for r in recon_spilled), str(recon_spilled))

# --- Scenario 4: spilled row replayed into the real audit file ---------------------

replayed = 0
fb_dir = getattr(c, "FALLBACK_DIR", None)
if hasattr(c, "replay_audit_fallback") and fb_dir is not None:
    p4 = tmp / "append_only" / "test_replay.csv"
    c.append_csv(p4, fields1, {"event": "E", "status": "S_init", "leader_fill_id": "F_init"})
    af4 = AppendFail(p4, n_fail=1000)
    af4.install()
    try:
        c.append_csv(p4, fields1, {"event": "E", "status": "S_replay", "leader_fill_id": "F_replay"})
    except Exception:
        pass
    af4.restore()
    fb4 = fb_dir / "test_replay.csv.spill"
    check("REPLAY_HAS_FALLBACK", fb4.exists() and len(c.read_csv_rows(fb4)) >= 1, str(fb4))
    replayed = c.replay_audit_fallback(p4, fields1)
    rows4 = c.read_csv_rows(p4)
    check("REPLAY_ROW_IN_MAIN_FILE",
          any(r.get("leader_fill_id") == "F_replay" for r in rows4), str(rows4))
    check("REPLAY_ROW_COUNT_RECONCILES",
        len([r for r in rows4 if r.get("leader_fill_id") in ("F_init", "F_replay")]) == 2, str(len(rows4)))
    check("REPLAY_FALLBACK_EMPTIED",
          not fb4.exists() or len(c.read_csv_rows(fb4)) == 0, str(fb4))
else:
    check("REPLAY_AVAILABLE", False, "replay_audit_fallback not present on this base")

# --- Scenario 5: replay_audit_fallback must NOT touch unrelated spill files (#6) ---

if hasattr(c, "replay_audit_fallback"):
    pa = tmp / "append_only" / "isolation_a.csv"
    pb = tmp / "append_only" / "isolation_b.csv"
    for pf in (pa, pb):
        c.append_csv(pf, fields1, {"event": "E", "status": "S0", "leader_fill_id": "init"})
    # spill a row into each fallback
    for pf in (pa, pb):
        af_iso = AppendFail(pf, n_fail=1000)
        af_iso.install()
        try:
            c.append_csv(pf, fields1, {"event": "E", "status": "S_spill", "leader_fill_id": pf.stem})
        except Exception:
            pass
        af_iso.restore()
    fa = c._fallback_path(pa)
    fb = c._fallback_path(pb)
    ca_before = fb.stat().st_size if fb.exists() else 0
    replayed_a = c.replay_audit_fallback(pa, fields1)
    cb_after = fb.stat().st_size if fb.exists() else 0
    check("REPLAY_ISOLATION_RETURNS_COUNT", replayed_a == 1, f"replayed_a={replayed_a}")
    check("REPLAY_ISOLATION_UNRELATED_UNTOUCHED",
          cb_after == ca_before, f"b_before={ca_before} b_after={cb_after}")
    check("REPLAY_ISOLATION_TARGET_CLEARED",
          not fa.exists() or len(c.read_csv_rows(fa)) == 0, str(fa))
else:
    check("REPLAY_ISOLATION_AVAILABLE", False, "replay_audit_fallback not present")

# --- Scenario 6 (respill): append still fails during replay, row stays in spill --
if hasattr(c, "replay_audit_fallback"):
    p6 = tmp / "append_only" / "test_respill.csv"
    c.append_csv(p6, fields1, {"event": "E", "status": "S_init", "leader_fill_id": "F_init"})
    af6 = AppendFail(p6, n_fail=1000)
    af6.install()
    try:
        c.append_csv(p6, fields1, {"event": "E", "status": "S_spill", "leader_fill_id": "F_respill"})
    except Exception:
        pass
    af6.restore()
    fb6 = c._fallback_path(p6)
    check("RESPILL_HAS_SPILLED_ROW", fb6.exists() and len(c.read_csv_rows(fb6)) == 1, str(fb6))
    main_size_before = p6.stat().st_size
    # replay while the main-file append STILL fails -- must not lose the row
    af6b = AppendFail(p6, n_fail=1000)
    af6b.install()
    replayed6 = c.replay_audit_fallback(p6, fields1)
    af6b.restore()
    check("RESPILL_REPLAY_COUNT_ZERO", replayed6 == 0, f"replayed={replayed6}")
    check("RESPILL_ROW_STILL_IN_FALLBACK",
          fb6.exists() and len(c.read_csv_rows(fb6)) == 1, str(fb6))
    check("RESPILL_MAIN_FILE_UNCHANGED",
          p6.stat().st_size == main_size_before, f"size={p6.stat().st_size} before={main_size_before}")
    # now the append path is healed -- replay succeeds
    replayed6b = c.replay_audit_fallback(p6, fields1)
    rows6 = c.read_csv_rows(p6)
    check("RESPILL_REPLAYED_AFTER_RESTORE",
          replayed6b == 1 and any(r["leader_fill_id"] == "F_respill" for r in rows6),
          f"replayed={replayed6b} rows={rows6}")
    check("RESPILL_FALLBACK_CLEARED",
          not fb6.exists() or len(c.read_csv_rows(fb6)) == 0, str(fb6))
else:
    check("RESPILL_AVAILABLE", False, "replay_audit_fallback not present")

# --- Scenario 7: a row must not be reported as preserved if both stores fail ----

p7 = tmp / "append_only" / "test_spill_failure.csv"
c.append_csv(p7, fields1, {"event": "E", "status": "S0", "leader_fill_id": "F0"})
orig_spill = c._spill_row
c._spill_row = lambda *a, **k: False
af7 = AppendFail(p7, n_fail=1000)
af7.install()
raised7 = False
try:
    c.append_csv(p7, fields1, {"event": "E", "status": "S_lost", "leader_fill_id": "F_LOST"})
except OSError:
    raised7 = True
af7.restore()
c._spill_row = orig_spill
check("SPILL_FAILURE_RAISES", raised7,
      "append must fail closed when neither the live file nor fallback persisted the row")
check("SPILL_FAILURE_MAIN_UNCHANGED", len(c.read_csv_rows(p7)) == 1,
      str(c.read_csv_rows(p7)))

# --- Scenario 8: REPLAY_DEFERRED is queued before an undurable audit row raises --

fill8 = c.LeaderFill("FILL_UNDURABLE", "0x" + "b" * 40, "ETH", "BUY", 100.0, 1.0, c.utc_now_ms(), "WS_CAPTURED")
orig_spill8 = c._spill_row
c._spill_row = lambda *a, **k: False
af8 = AppendFail(c.RECONCILIATION_CSV, n_fail=1000)
af8.install()
raised8 = False
try:
    c.LiveCopyCore._terminal_after_exception(core, fill8, RuntimeError("simulated pre-send failure"))
except OSError:
    raised8 = True
af8.restore()
c._spill_row = orig_spill8
key8 = c.LiveCopyCore._guard_key(fill8)
check("DEFERRED_UNDURABLE_APPEND_RAISES", raised8, "expected hard persistence failure")
check("DEFERRED_QUEUED_BEFORE_RAISE", key8 in core._deferred,
      str(core._deferred))

# --- Scenario 9: crash after one replay append is idempotent on restart ----------

p9 = tmp / "append_only" / "test_replay_crash.csv"
c.append_csv(p9, fields1, {"event": "E", "status": "S_init", "leader_fill_id": "F_init"})
af9 = AppendFail(p9, n_fail=1000)
af9.install()
try:
    c.append_csv(p9, fields1, {"event": "E", "status": "S_spill", "leader_fill_id": "F_CRASH_REPLAY"})
except Exception:
    pass
try:
    c.append_csv(p9, fields1, {"event": "E", "status": "S_spill", "leader_fill_id": "F_CRASH_REPLAY_2"})
except Exception:
    pass
af9.restore()
fb9 = c._fallback_path(p9)
orig_append9 = c.append_csv
append_calls9 = 0
def crash_after_first_replay_append(path, fields, row, **kwargs):
    global append_calls9
    result = orig_append9(path, fields, row, **kwargs)
    append_calls9 += 1
    if path == p9 and append_calls9 == 1:
        raise KeyboardInterrupt("simulated process crash after durable append")
    return result
c.append_csv = crash_after_first_replay_append
crashed9 = False
try:
    c.replay_audit_fallback(p9, fields1)
except KeyboardInterrupt:
    crashed9 = True
finally:
    c.append_csv = orig_append9
check("REPLAY_CRASH_SIMULATED", crashed9)
check("REPLAY_CRASH_SPILL_RETAINED",
      fb9.exists() and any(r.get("leader_fill_id") == "F_CRASH_REPLAY" for r in c.read_csv_rows(fb9)),
      str(fb9))
rows9_after_crash = c.read_csv_rows(p9)
check("REPLAY_CRASH_FIRST_APPEND_DURABLE",
      sum(r.get("leader_fill_id") == "F_CRASH_REPLAY" for r in rows9_after_crash) == 1,
      str(rows9_after_crash))
replayed9b = c.replay_audit_fallback(p9, fields1)
rows9_final = c.read_csv_rows(p9)
check("REPLAY_CRASH_RESTART_FINISHES_ONCE",
      replayed9b == 1
      and sum(r.get("leader_fill_id") == "F_CRASH_REPLAY" for r in rows9_final) == 1
      and sum(r.get("leader_fill_id") == "F_CRASH_REPLAY_2" for r in rows9_final) == 1,
      f"replayed={replayed9b} rows={rows9_final}")
check("REPLAY_CRASH_RESTART_CLEARS_SPILL",
      not fb9.exists() or not c.read_csv_rows(fb9), str(fb9))

# --- Scenario 9b: identical legitimate rows are distinct spill events ---------

p9b = tmp / "append_only" / "test_replay_identical.csv"
identical_row = {"event": "E", "status": "S_identical", "leader_fill_id": "F_identical"}
c.append_csv(p9b, fields1, identical_row)  # legitimate pre-existing row
for _ in range(2):
    af9b = AppendFail(p9b, n_fail=1000)
    af9b.install()
    try:
        c.append_csv(p9b, fields1, identical_row)
    except Exception:
        pass
    af9b.restore()
fb9b = c._fallback_path(p9b)
check("IDENTICAL_SPILL_ROWS_BOTH_PRESERVED",
      len(c.read_csv_rows(fb9b)) == 2, str(c.read_csv_rows(fb9b)))
orig_append9b = c.append_csv
append_calls9b = 0
def crash_after_first_identical_replay(path, fields, row, **kwargs):
    global append_calls9b
    result = orig_append9b(path, fields, row, **kwargs)
    append_calls9b += 1
    if path == p9b and append_calls9b == 1:
        raise KeyboardInterrupt("simulated crash after first identical replay append")
    return result
c.append_csv = crash_after_first_identical_replay
crashed9b = False
try:
    c.replay_audit_fallback(p9b, fields1)
except KeyboardInterrupt:
    crashed9b = True
finally:
    c.append_csv = orig_append9b
check("IDENTICAL_REPLAY_CRASH_SIMULATED", crashed9b)
check("IDENTICAL_REPLAY_CRASH_DURABLE_COUNT",
      sum(r == identical_row for r in c.read_csv_rows(p9b)) == 2,
      str(c.read_csv_rows(p9b)))
replayed9b = c.replay_audit_fallback(p9b, fields1)
rows9b = c.read_csv_rows(p9b)
check("IDENTICAL_REPLAY_RESTART_PRESERVES_ALL_THREE",
      replayed9b == 1 and sum(r == identical_row for r in rows9b) == 3,
      f"replayed={replayed9b} rows={rows9b}")
check("IDENTICAL_REPLAY_RESTART_CLEARS_SPILL",
      not fb9b.exists() or not c.read_csv_rows(fb9b), str(fb9b))

# --- Scenario 10: unresolved startup spill refuses to arm ----------------------

startup_path = c.SEND_ATTEMPTS_CSV
startup_spill = c._fallback_path(startup_path)
if startup_spill.exists():
    startup_spill.unlink()
c._spill_row(startup_path, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "STARTUP_PENDING", "leader_fill_id": "F_STARTUP"})
orig_append10 = c.append_csv
def fail_startup_replay(path, fields, row, **kwargs):
    if path == startup_path:
        return False
    return orig_append10(path, fields, row, **kwargs)
c.append_csv = fail_startup_replay
startup_refused = False
try:
    c.AuditLogWriter().replay_all_fallbacks()
except OSError:
    startup_refused = True
finally:
    c.append_csv = orig_append10
check("UNRESOLVED_SPILL_REFUSES_STARTUP", startup_refused)
check("UNRESOLVED_STARTUP_SPILL_RETAINED",
      startup_spill.exists() and any(r.get("attempt_id") == "STARTUP_PENDING" for r in c.read_csv_rows(startup_spill)),
      str(startup_spill))

# Resolve the test spill before checking errors.csv startup replay.
c.AuditLogWriter().replay_all_fallbacks()
check("RESOLVED_STARTUP_SPILL_CLEARED", not startup_spill.exists() or not c.read_csv_rows(startup_spill), str(startup_spill))

# A journal-only pending row is still a startup blocker if replay cannot finish.
c._spill_row(startup_path, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "SIDECAR_PENDING", "leader_fill_id": "F_SIDECAR"})
startup_spill.write_bytes(b"")
c.append_csv = fail_startup_replay
sidecar_startup_refused = False
try:
    c.AuditLogWriter().replay_all_fallbacks()
except OSError:
    sidecar_startup_refused = True
finally:
    c.append_csv = orig_append10
check("UNRESOLVED_SIDECAR_SPILL_REFUSES_STARTUP", sidecar_startup_refused)
check("UNRESOLVED_SIDECAR_ROW_RETAINED", c._spill_pending(startup_path))
c.AuditLogWriter().replay_all_fallbacks()
check("RESOLVED_SIDECAR_ROW_REPLAYED",
      any(r.get("attempt_id") == "SIDECAR_PENDING" for r in c.read_csv_rows(startup_path)))

# A failed journal cleanup also blocks startup before a fresh spill can reuse row indexes.
c._spill_row(startup_path, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "CLEAR_PENDING", "leader_fill_id": "F_CLEAR"})
startup_journal = c._spill_journal_path(startup_path)
orig_path_open = Path.open
def fail_journal_clear(path, *args, **kwargs):
    if path == startup_journal and args and args[0] == "wb":
        raise PermissionError("simulated journal cleanup failure")
    return orig_path_open(path, *args, **kwargs)
Path.open = fail_journal_clear
journal_cleanup_refused = False
try:
    c.AuditLogWriter().replay_all_fallbacks()
except OSError:
    journal_cleanup_refused = True
finally:
    Path.open = orig_path_open
check("UNCLEARED_REPLAY_JOURNAL_REFUSES_STARTUP", journal_cleanup_refused)
c.AuditLogWriter().replay_all_fallbacks()
check("JOURNAL_CLEANUP_RETRY_DOES_NOT_DUPLICATE",
      sum(r.get("attempt_id") == "CLEAR_PENDING" for r in c.read_csv_rows(startup_path)) == 1)

# --- Scenario 11: errors.csv spill is replayed and blocks startup if unresolved --

errors_path = c.ERRORS_CSV
errors_spill = c._fallback_path(errors_path)
if errors_spill.exists():
    errors_spill.unlink()
error_row = {
    "created_at": c.utc_now_iso(),
    "created_at_ms": c.utc_now_ms(),
    "context": "TEST_ERRORS_REPLAY",
    "error_type": "TestError",
    "message": "replayed after restart",
    "traceback": "",
}
c._spill_row(errors_path, c.ERROR_FIELDS, error_row)
c.AuditLogWriter().replay_all_fallbacks()
errors_rows = c.read_csv_rows(errors_path)
check("ERRORS_SPILL_REPLAYED_ON_STARTUP",
      any(r.get("context") == "TEST_ERRORS_REPLAY" and r.get("message") == "replayed after restart" for r in errors_rows),
      str(errors_rows))
check("ERRORS_SPILL_CLEARED_ON_STARTUP",
      not errors_spill.exists() or not c.read_csv_rows(errors_spill), str(errors_spill))

error_row2 = dict(error_row, created_at=c.utc_now_iso(), created_at_ms=c.utc_now_ms(), context="TEST_ERRORS_UNRESOLVED")
c._spill_row(errors_path, c.ERROR_FIELDS, error_row2)
orig_append11 = c.append_csv
def fail_errors_replay(path, fields, row, **kwargs):
    if path == errors_path:
        return False
    return orig_append11(path, fields, row, **kwargs)
c.append_csv = fail_errors_replay
errors_startup_refused = False
try:
    c.AuditLogWriter().replay_all_fallbacks()
except OSError:
    errors_startup_refused = True
finally:
    c.append_csv = orig_append11
check("UNRESOLVED_ERRORS_SPILL_REFUSES_STARTUP", errors_startup_refused)
check("UNRESOLVED_ERRORS_SPILL_RETAINED",
      errors_spill.exists() and any(r.get("context") == "TEST_ERRORS_UNRESOLVED" for r in c.read_csv_rows(errors_spill)),
      str(errors_spill))
c.AuditLogWriter().replay_all_fallbacks()

# --- Scenario 12: summary -------------------------------------------------------

print("MEASURE::append_elapsed=%.4fs fallback_dir=%s" % (t1 - t0, str(getattr(c, "FALLBACK_DIR", None))))

failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
