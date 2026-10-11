# J1 - disk-full robustness: observed behaviour and a proposed patch (main 5e88e89)

Test: `_archive/hl_stage2/test_core_disk_full.py` (15 checks, real code paths, a fake exchange that COUNTS calls).
Failure injected at `pathlib.Path.open` (a real failing write) and, for the JSON writes, `Core.os.replace`, so the
engine sees exactly what a full disk (ENOSPC) or a transient PermissionError gives it.

    HL_LIVE_ENV_FILE=/nonexistent python -u test_core_disk_full.py

## Two-run control (instrument, not product)
My FIRST run reported 11 failures. That was the INSTRUMENT: `pathlib.Path.open = <bound method>` passes the MODE
string as the first argument (a bound method is not bound by the descriptor protocol when assigned to a class
attribute), so every write in the test died with `AttributeError(str has no attribute name)`. Installing the patch as
a plain function and re-running gave the 5 real findings below. Nothing in the first run was an engine fault.

## Results on main 5e88e89 - 15 checks, 5 FAIL (5 findings)
PASS (already robust, worth keeping):
  A1 no order is sent when the order_intents row cannot be written
  A4 the next fill still runs after the failure
  B1 no exchange call when the pending_send row cannot be written
  B2 that case returns the fail-closed `SEND_NOT_ATTEMPTED_AUDIT_WRITE_FAILED` (T1a works)
  C1 the order really was attempted (1 exchange call) before the reconciliation failure
  C3 replaying the same leader fill sends NO second order (dedupe holds)
  C4 the lost audit trail is not silent: `build_live_integrity_status()` = RED, `audit_proof_missing` = 1
  D1 the JSON write failure is recorded, D2 the per-cycle caller guards `write_live_integrity_status`, D3 the next call still works

FINDINGS (each verified in the source):
  1. A2 `self.audit.append_order_intent(intent)` is NOT wrapped (Core ~8800). On ENOSPC the OSError propagates out of
     `_process_leader_fill`; on run_cycle's sync path (Core ~9491, also unguarded) that aborts the whole cycle.
     Observed: `OSError(28, 'No space left on device')`.
  2. A3 no loud record: the failure wrote nothing (errors.csv rows=0). On the WS-hot path the per-fill wrapper does
     `log_error("ws_hot_send", ...)`, but `log_error` itself appends to the SAME full disk, so on a genuinely full disk
     there is no durable error record at all.
  3. B3 final status row: the order IS sent (1 exchange call) and then writing its terminal row raises
     `OSError(28)` out of `send_if_allowed` (Core ~6594, unwrapped) - the caller gets an exception instead of a status.
     The pending_send row survives (good), the terminal outcome is lost.
  4. C2 the reconciliation append after a send (Core ~6596) is unwrapped: the same OSError escapes `send_if_allowed`
     after the order is already out.
  5. D4 `run_cycle`'s `finally` calls `self.state_writer.write(summary, self.dedupe, self.cfg)` (Core ~9517) with no
     guard: a failing state-JSON write escapes run_cycle (its sibling guard's `log_error` would fail too, see 2).

## Proposed patch (engine thread applies it; no Core edit was made here)
`DISK_FULL_PATCH_PROPOSAL.diff` - 5 edits, `git apply --check` clean, 58 insertions / 30 deletions:
  E1 `log_error` never raises: the append is wrapped; on failure it writes one stderr line.
  E2 the order-intent append is wrapped: no order is sent, a `SEND_NOT_ATTEMPTED_AUDIT_WRITE_FAILED` reconciliation
     row is attempted, the fill unit returns instead of raising.
  E3 the post-send `append_send_attempt` is wrapped (the order is already out; never raise).
  E5 the post-send `append_reconciliation` is wrapped the same way.
  E4 run_cycle's `finally` guards the state write.
Proof: applied to a copy of the release, the same test goes from 5 FAILED to **TOTAL=15 FAILED=0**, and the patched
file compiles. Both states are reproducible (unpatched 5 FAIL, patched 0 FAIL).

Model: Hermes deepseek-flash (this session), all parts. Graphify: `graphify update .` then queries for the audit-write
functions located `append_csv` L1112, `AuditLogWriter` L3100, `build_live_integrity_status` L1584 and the send path.
Offline only: no engine, no network, no orders, no keys read or printed.
