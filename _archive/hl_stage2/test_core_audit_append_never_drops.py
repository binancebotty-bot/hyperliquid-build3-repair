#!/usr/bin/env python3
"""Audit append never drops a row: retry+backoff on transient failure, spill to an
append-only fallback file that is replayed later, and a failed append must NOT
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

# Config for the test scenarios: short retry count and short backoff.
RETRIES = 3
BACKOFF = 0.02  # seconds; short enough for fast CI, long enough to measure

tmp = Path(tempfile.mkdtemp(prefix="auditndd_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(tmp),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LIVE_APPEND_RETRIES": str(RETRIES),
    "HL_LIVE_APPEND_BACKOFF_SEC": str(BACKOFF),
})
import HL_Live_Copy_Service_Core as c  # noqa: E402

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


# --- Scenario 1: retry with backoff, then succeed ----------------------------------

fields1 = ["event", "status", "leader_fill_id"]
p1 = tmp / "append_only" / "test_retry.csv"
# establish header + first row
c.append_csv(p1, fields1, {"event": "E", "status": "S0", "leader_fill_id": "F0"})
af1 = AppendFail(p1, n_fail=2)
af1.install()
raised1 = False
ret1 = None
t0 = time.monotonic()
try:
    ret1 = c.append_csv(p1, fields1, {"event": "E", "status": "S1", "leader_fill_id": "F1"})
except Exception as exc:
    raised1 = True
t1 = time.monotonic()
af1.restore()
rows1 = c.read_csv_rows(p1)

check("APPEND_RETRIES_NO_RAISE", not raised1, f"raised={raised1}")
check("APPEND_RETRIES_RETURNS_TRUE", ret1 is True, f"ret={ret1!r}")  # #5 contract: success -> True
check("APPEND_RETRIES_ATTEMPTS", af1.count == RETRIES, f"attempts={af1.count} expected={RETRIES}")
check("APPEND_RETRIES_BACKOFF_TAKEN", (t1 - t0) > BACKOFF * 2,
      f"elapsed={t1 - t0:.4f}s backoff*2={BACKOFF * 2:.4f}s")
check("APPEND_RETRIES_ROW_PRESERVED",
      len(rows1) == 2 and rows1[1]["leader_fill_id"] == "F1", str(rows1))
print("MEASURE::retry_attempts=%d backoff_per_attempt=%.4fs total_elapsed=%.4fs" % (af1.count, BACKOFF, t1 - t0))

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

# --- Scenario 7: summary --------------------------------------------------------

print("MEASURE::retry_count=%d backoff_seconds=%.4f fallback_dir=%s" % (
    RETRIES, BACKOFF, str(getattr(c, "FALLBACK_DIR", None))))

failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
