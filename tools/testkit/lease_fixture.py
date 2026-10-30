"""Explicit, visible SENDER-LEASE holding for test fixtures.  CC-1 R56(2), M2/I08.

WHY THIS EXISTS
The fence fix (gpt/coda2-sender-fence) requires the machine-wide sender lease at the physical
`exchange.order` call, refused as SEND_BLOCKED_NO_SENDER_LEASE.  That is correct behaviour.
It turned 14 test files from PASS to ASSERTION_FAIL - measured at ba04535 - because those
fixtures drive the sender without ever holding the lease.

The fix is TEST-SIDE and belongs in ONE place, not 14.  A fixture that intends to send opts in
here; a fixture that intends to prove the refusal deliberately does not.

THE RULE THIS ENFORCES
Holding the lease is a DECISION, visible at the call site.  There is no autouse fixture and no
import-time acquisition: a suite that silently held the lease everywhere would make the refusal
path untestable and would let a fixture send that was meant to be blocked.

USAGE
    from lease_fixture import hold_lease

    with hold_lease(state_dir):        # context manager: releases on exit, even on failure
        ...drive the sender...

    # or, for tests that must stay blocked:
    assert not lease_is_held(state_dir)

Opt-in files (they SEND and now need the lease):
    test_core_intent_durable_barrier.py, test_core_intent_write_behind.py,
    test_core_liq_parity.py, test_core_margin_mode_background.py,
    test_core_master_gate.py, test_core_missed_entry_rule.py,
    test_core_outage_defer.py, test_core_retry_send_integrity.py,
    test_core_rw12_eol_consistency.py, test_core_rw13_recovery_reconcile.py,
    test_core_rw14_snapshot_failclosed.py, test_core_rw7b_review_fixes.py,
    test_hotpath_replay_bench.py, test_j2_local_rejects.py,
    test_ui_account_tile_all_dexes.py

Deliberately WITHOUT the lease (they assert the refusal):
    test_core_c7_sender_fence.py  (C2/C4 exist to prove a second sender is refused)
    test_core_rw12_mode_at_send.py (M6 asserts a refusal, not a send)

Test-only.  Never imported by production code.  Refuses a non-scratch path for the same reason
the arming helper does: acquiring a lease on live state would interfere with a running engine.
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

__all__ = ["hold_lease", "lease_is_held", "LeaseRefused"]

_SCRATCH_MARKERS = ("tmp", "temp", "scratch", "oc_wt_", "worktree", "pytest-", "reg_")
_LOCK_NAME = "engine-global.lock"


class LeaseRefused(RuntimeError):
    """Raised rather than silently continuing - a no-op here would hide the very bug we are fixing."""


def _lock_path(state_dir) -> Path:
    p = Path(state_dir)
    if not any(m.lower() in str(p).lower() for m in _SCRATCH_MARKERS):
        raise LeaseRefused(
            f"{p} does not look like scratch state; refusing to take the sender lease on "
            "something that may be a live engine's state dir"
        )
    p.mkdir(parents=True, exist_ok=True)
    return p / _LOCK_NAME


@contextlib.contextmanager
def hold_lease(state_dir):
    """Hold the machine-wide sender lease for the duration of the block, then release it.

    Uses the same byte-range lock the engine uses (msvcrt LK_NBLCK / fcntl LOCK_EX|LOCK_NB) so a
    fixture holding it is refused by the same code path production uses - a fake would prove nothing.
    """
    path = _lock_path(state_dir)
    fh = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield path
        finally:
            try:
                if os.name == "nt":
                    import msvcrt

                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
    except OSError as exc:
        raise LeaseRefused(f"could not acquire the sender lease at {path}: {exc}") from exc
    finally:
        fh.close()


def lease_is_held(state_dir) -> bool:
    """True if some process currently holds the lease for this state dir."""
    try:
        path = _lock_path(state_dir)
    except LeaseRefused:
        return False
    fh = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            return False
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        fh.close()
