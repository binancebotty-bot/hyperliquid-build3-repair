"""Explicit, visible send-arming for test fixtures.  CC-1 R53(4), CH-8.

WHY THIS EXISTS
A triage of 89 failing cases across 17 files found that **54 of them failed because the
fixture never armed the engine**: the scratch config carried `"auto_send_enabled": False`,
so production correctly refused to send and the test read the refusal as a failure.  Those
files were not testing the product badly; they were testing a disarmed engine by accident.

THE RULE THIS ENFORCES
Arming is a DECISION, not a default.  A test that needs the engine to send must say so at
the point where it matters, and the call must be greppable.  A test that needs the engine
DISARMED - because refusing IS the behaviour under test - must also be able to say so, and
must not be silently armed by a shared helper.

Deliberately NOT provided: a default-on arm-on-import, an autouse fixture, or anything that
changes behaviour for tests that never call this module.  A helper that quietly turned
sending on everywhere would be worse than the status quo, because the suite would start
arming in exactly the cases where a refusal is the assertion.

USAGE
    from arm_fixture import arm_sends, disarm_sends, is_armed

    arm_sends(cfg_path)          # or arm_sends(state_dir) - both resolve the same file
    assert is_armed(cfg_path)    # cheap precondition; raises if the file is not armed

Test-only.  This module must never be imported by production code, and it refuses to touch
a config that looks live rather than scratch.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = ["arm_sends", "disarm_sends", "is_armed", "ArmingRefused"]

# A config outside one of these roots is treated as live/operator state and refused, because
# arming a real config would flip live copying.  Tests run from temp dirs and worktrees.
_SCRATCH_MARKERS = ("tmp", "temp", "scratch", "oc_wt_", "worktree", "pytest-", "reg_")


class ArmingRefused(RuntimeError):
    """Raised rather than quietly doing nothing - a silent no-op here would hide the bug."""


def _cfg_path(target) -> Path:
    p = Path(target)
    if p.is_dir():
        p = p / "live_config.json"
    if not p.exists():
        raise ArmingRefused(f"{p} does not exist; a fixture must create its config before arming it")
    if not any(m.lower() in str(p).lower() for m in _SCRATCH_MARKERS):
        raise ArmingRefused(
            f"{p} does not look like scratch state (no marker in {_SCRATCH_MARKERS}); "
            "refusing to arm something that may be live config"
        )
    return p


def _set(target, value: bool) -> Path:
    p = _cfg_path(target)
    data = json.loads(p.read_text(encoding="utf-8") or "{}")
    data["auto_send_enabled"] = bool(value)
    tmp = p.with_suffix(p.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, p)
    return p


def arm_sends(target) -> Path:
    """Arm the engine to actually send.  Returns the config path that was armed."""
    return _set(target, True)


def disarm_sends(target) -> Path:
    """Explicitly disarm, for fixtures where a refusal is the behaviour under test."""
    return _set(target, False)


def is_armed(target) -> bool:
    """True if the config will let the engine send.  Cheap precondition, no side effects."""
    p = Path(target)
    if p.is_dir():
        p = p / "live_config.json"
    try:
        return bool(json.loads(p.read_text(encoding="utf-8") or "{}").get("auto_send_enabled"))
    except (OSError, ValueError):
        return False
