"""Sender-lease holding for test fixtures - v3, using the Core's OWN documented seam.

CC-1 R60(2) option (d), rebuilt. History of this file, because the wrong versions were shipped:

  v1  locked `<state_dir>/engine-global.lock` and tried to satisfy the gate with an OS lock.
      Wrong twice: the Core uses a FIXED machine-wide path, and `_global_sender_lease_held()`
      inspects the Core's module state, not the lock's state. Refused by execution, never adopted.
  v2  monkeypatched `_global_instance_lock_path` to a temp file. Unnecessary, and `held INSIDE`
      came back False. Never adopted.
  v3  THIS ONE. The Core already provides the seam: `_global_instance_lock_path()` honours
      `HL_LIVE_GLOBAL_LOCK_FILE` (Core:16421), so no monkeypatch is needed and none is used.
      We point that variable at a temp file and call the Core's OWN
      `acquire_global_instance_lock()`, so all module state is set by Core code. Release goes
      through the Core's own `release_global_instance_lock()`.

WHY THIS DOES NOT WEAKEN THE PRODUCTION RULE
The machine-wide key stays the default and stays machine-wide. A test sets an env var for its own
process only; the live engine's lock is never opened, so "never two engines at once" is untouched.
"""
from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path

__all__ = ["hold_lease", "lease_is_held", "machine_lock_path", "LeaseRefused"]

_ENV = "HL_LIVE_GLOBAL_LOCK_FILE"


class LeaseRefused(RuntimeError):
    """Raised rather than silently continuing - a no-op here hides the very bug we are fixing."""


def _core():
    import HL_Live_Copy_Service_Core as core  # noqa: WPS433
    return core


def machine_lock_path() -> Path:
    """The real machine-wide lock path, computed WITHOUT the test override. Never opened here."""
    saved = os.environ.pop(_ENV, None)
    try:
        return _core()._global_instance_lock_path()
    finally:
        if saved is not None:
            os.environ[_ENV] = saved


@contextlib.contextmanager
def hold_lease():
    """Hold a sender lease on a temp lock file via the Core's own acquire/release."""
    core = _core()
    tmpdir = Path(tempfile.mkdtemp(prefix="lease_", dir=r"C:\tmp"))
    fake = tmpdir / "engine-global.lock"
    saved = os.environ.get(_ENV)
    os.environ[_ENV] = str(fake)
    try:
        try:
            core.acquire_global_instance_lock(tmpdir)
        except Exception as exc:  # noqa: BLE001
            raise LeaseRefused(f"Core refused the temp lease at {fake}: {exc}") from exc
        yield fake
    finally:
        try:
            core.release_global_instance_lock()
        except Exception:  # noqa: BLE001
            pass
        if saved is None:
            os.environ.pop(_ENV, None)
        else:
            os.environ[_ENV] = saved


def lease_is_held() -> bool:
    """True if this process holds a sender lease, read the way the GATE reads it.

    At 522b206 there is no `_global_sender_lease_held()`; the physical call checks the module
    globals directly at Core:5744:
        if not (_GLOBAL_INSTANCE_LOCK_OWNED and _GLOBAL_INSTANCE_LOCK is not None ...)
    So this mirrors that exact predicate. An earlier version called a function that no longer
    exists and swallowed the AttributeError, which reported False for a lease that WAS held.
    """
    core = _core()
    return bool(getattr(core, "_GLOBAL_INSTANCE_LOCK_OWNED", False)) and getattr(core, "_GLOBAL_INSTANCE_LOCK", None) is not None
