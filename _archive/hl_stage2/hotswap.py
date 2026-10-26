#!/usr/bin/env python3
"""Hot-swap seam for ALLOWLISTED sibling modules of the live copy engine.

A swap is requested by dropping HOTSWAP_REQUEST.json into the engine audit dir. The engine's
--loop cycle calls tick(AUDIT_DIR) at the top of every cycle, right beside the STOP_REQUESTED
sentinel check: one exists() when nothing is requested.

Nothing is imported, reloaded or swapped unless the request names an ALLOWLISTED module and the
artifact bytes hash to the sha256 the request declares. Every refusal is named, appended to
hotswap.log next to the request, and leaves the OLD code running: this module never raises.

The install is a single `target.__dict__.update(...)` on the already-imported module object, so
every existing `_XNET.foo` call site keeps working with no edits. A call already holding the old
callable is unaffected; the next lookup sees the new one.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import types
from pathlib import Path
from typing import Any, Dict, Optional

REQUEST_FILE = "HOTSWAP_REQUEST.json"
STATE_FILE = "HOTSWAP_STATE.json"
LOG_FILE = "hotswap.log"

# Only these may ever be swapped. Widen deliberately; everything else is refused by name.
ALLOWLIST = frozenset({"exchange_truth"})

# Never swappable, even if the allowlist is widened later.
PROTECTED_MODULES = frozenset({
    "HL_Live_Copy_Service_Core",  # the engine itself
    "HL_Copy_App_SSOT",           # the UI
    "HL_Live_Copy_Service",       # the launcher
    "hotswap",
})
PROTECTED_SUBSTRINGS = ("gate", "send", "wallet", "secret", "key")

_STAGING_NAME = "_hotswap_staging"
_DROP_KEYS = ("__name__", "__loader__", "__spec__", "__package__", "__builtins__")
_sha_cache: Dict[str, Any] = {}


def _log(audit_dir: Any, event: str, module: Any, detail: Any = "") -> None:
    try:
        line = json.dumps({
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "event": event,
            "module": "" if module is None else str(module),
            "detail": str(detail)[:400],
        })
        with (Path(audit_dir) / LOG_FILE).open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _refuse(audit_dir: Any, code: str, module: Any, detail: Any = "") -> bool:
    _log(audit_dir, code, module, detail)
    return False


def _state_path(audit_dir: Any) -> Path:
    return Path(audit_dir) / STATE_FILE


def _read_state(audit_dir: Any) -> Dict[str, Any]:
    try:
        state = json.loads(_state_path(audit_dir).read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def _write_state(audit_dir: Any, state: Dict[str, Any]) -> None:
    try:
        _state_path(audit_dir).write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    except Exception:
        pass


def loaded_sha(name: str) -> str:
    """sha256 of the source file the module object is currently executing from.

    After a swap __file__ points at the installed artifact, so this is the loaded artifact's
    hash; before any swap it is the original file's hash. "" for a module that is not imported
    or whose file cannot be read.
    """
    module = sys.modules.get(name)
    path = getattr(module, "__file__", None) if module is not None else None
    if not path:
        return ""
    try:
        stat = Path(path).stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        hit = _sha_cache.get(name)
        if hit is not None and hit[0] == key:
            return hit[1]
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        _sha_cache[name] = (key, digest)
        return digest
    except Exception:
        return ""


def _name_allowed(audit_dir: Any, name: Any) -> bool:
    if not isinstance(name, str) or not name.isidentifier():
        return _refuse(audit_dir, "REFUSED_MALFORMED_REQUEST", name, "module name is not a python identifier")
    if name in PROTECTED_MODULES or any(s in name.lower() for s in PROTECTED_SUBSTRINGS):
        return _refuse(audit_dir, "REFUSED_PROTECTED_MODULE", name, "protected name, never swappable")
    if name not in ALLOWLIST:
        return _refuse(audit_dir, "REFUSED_NOT_ALLOWLISTED", name, "not in hotswap ALLOWLIST")
    return True


def _build(path: Path, raw: bytes) -> types.ModuleType:
    """Fully execute the artifact as a throwaway module. Raises on any import-time failure."""
    staging = types.ModuleType(_STAGING_NAME)
    staging.__file__ = str(path)
    exec(compile(raw, str(path), "exec"), staging.__dict__)
    return staging


def _install(target: types.ModuleType, staging: types.ModuleType, path: Path) -> None:
    """One atomic step: swap every name into the already-imported module object."""
    # shortcut: update() merges, so a name dropped from a new artifact keeps its OLD binding. That
    # merge is what leaves no window where the module lacks a name another thread may be calling.
    # Upgrade to a locked clear+update if an artifact ever renames a public function.
    patch = {k: v for k, v in staging.__dict__.items() if k not in _DROP_KEYS}
    patch["__file__"] = str(path)
    target.__dict__.update(patch)


def _keep_previous(audit_dir: Any, name: str, target: types.ModuleType) -> Optional[Dict[str, str]]:
    src = getattr(target, "__file__", None)
    if not src or not Path(src).is_file():
        return None
    try:
        raw = Path(src).read_bytes()
        dest = Path(audit_dir) / ("%s.hotswap_previous_%d.py" % (name, int(time.time() * 1000)))
        dest.write_bytes(raw)
    except Exception:
        return None
    return {"previous_path": str(dest), "previous_sha": hashlib.sha256(raw).hexdigest()}


def _load_bytes(audit_dir: Any, name: str, artifact: Any) -> Optional[bytes]:
    if not isinstance(artifact, str) or not artifact:
        _refuse(audit_dir, "REFUSED_MALFORMED_REQUEST", name, "artifact path missing")
        return None
    path = Path(artifact)
    if not path.is_absolute():
        _refuse(audit_dir, "REFUSED_ARTIFACT_UNREADABLE", name, "artifact path is not absolute: %s" % path)
        return None
    if not path.is_file():
        _refuse(audit_dir, "REFUSED_ARTIFACT_MISSING", name, str(path))
        return None
    try:
        return path.read_bytes()
    except Exception as exc:
        _refuse(audit_dir, "REFUSED_ARTIFACT_UNREADABLE", name, "%s: %s" % (type(exc).__name__, exc))
        return None


def _apply(audit_dir: Any, name: str, artifact: Any, expected: str) -> bool:
    target = sys.modules.get(name)
    if target is None:
        return _refuse(audit_dir, "REFUSED_MODULE_NOT_IMPORTED", name,
                       "module is not imported; refusing to import a new module for a swap")
    raw = _load_bytes(audit_dir, name, artifact)
    if raw is None:
        return False
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        return _refuse(audit_dir, "REFUSED_SHA_MISMATCH", name, "expected %s got %s" % (expected, actual))
    path = Path(artifact)
    try:
        staging = _build(path, raw)
    except BaseException as exc:  # a bad artifact must not kill the engine
        return _refuse(audit_dir, "REFUSED_IMPORT_RAISED", name, "%s: %s" % (type(exc).__name__, exc))
    previous = _keep_previous(audit_dir, name, target)
    if previous is None:
        return _refuse(audit_dir, "REFUSED_PREVIOUS_COPY_FAILED", name,
                       "could not keep the live source %r; no rollback available" % getattr(target, "__file__", None))
    _install(target, staging, path)
    _sha_cache.pop(name, None)
    state = _read_state(audit_dir)
    state[name] = {"installed_path": str(path), "installed_sha": actual, **previous}
    _write_state(audit_dir, state)
    _log(audit_dir, "APPLIED", name, actual)
    return True


def _rollback(audit_dir: Any, name: str, expected: str) -> bool:
    target = sys.modules.get(name)
    if target is None:
        return _refuse(audit_dir, "REFUSED_MODULE_NOT_IMPORTED", name, "module is not imported")
    entry = _read_state(audit_dir).get(name)
    if not isinstance(entry, dict) or not entry.get("previous_path"):
        return _refuse(audit_dir, "REFUSED_NO_PREVIOUS", name, "no previous artifact recorded for rollback")
    prev_path = Path(str(entry["previous_path"]))
    prev_sha = str(entry.get("previous_sha") or "")
    raw = _load_bytes(audit_dir, name, str(prev_path))
    if raw is None:
        return False
    actual = hashlib.sha256(raw).hexdigest()
    if not prev_sha or actual != prev_sha:
        return _refuse(audit_dir, "REFUSED_SHA_MISMATCH", name,
                       "previous artifact sha %s expected %s" % (actual, prev_sha))
    if expected and expected != actual:
        return _refuse(audit_dir, "REFUSED_SHA_MISMATCH", name, "request sha %s != previous %s" % (expected, actual))
    try:
        staging = _build(prev_path, raw)
    except BaseException as exc:
        return _refuse(audit_dir, "REFUSED_IMPORT_RAISED", name, "%s: %s" % (type(exc).__name__, exc))
    _install(target, staging, prev_path)
    _sha_cache.pop(name, None)
    state = _read_state(audit_dir)
    state[name] = {"installed_path": str(prev_path), "installed_sha": actual}
    _write_state(audit_dir, state)
    _log(audit_dir, "ROLLED_BACK", name, actual)
    return True


def _handle(audit_dir: Any, req_path: Path) -> bool:
    try:
        request = json.loads(req_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _refuse(audit_dir, "REFUSED_MALFORMED_REQUEST", "?", "%s: %s" % (type(exc).__name__, exc))
    if not isinstance(request, dict):
        return _refuse(audit_dir, "REFUSED_MALFORMED_REQUEST", "?", "request is not a JSON object")
    name = request.get("module")
    action = request.get("action") or "apply"
    artifact = request.get("artifact") or request.get("path")
    expected = str(request.get("sha256") or "").strip().lower()
    if action not in ("apply", "rollback"):
        return _refuse(audit_dir, "REFUSED_MALFORMED_REQUEST", name, "unknown action %r" % (action,))
    if expected and len(expected) != 64:
        return _refuse(audit_dir, "REFUSED_MALFORMED_REQUEST", name, "sha256 is not 64 hex chars")
    if action == "apply" and not expected:
        return _refuse(audit_dir, "REFUSED_MALFORMED_REQUEST", name, "apply needs the artifact sha256")
    if not _name_allowed(audit_dir, name):
        return False
    if action == "apply":
        return _apply(audit_dir, name, artifact, expected)
    return _rollback(audit_dir, name, expected)


def tick(audit_dir: Any) -> bool:
    """Consume at most one HOTSWAP_REQUEST.json. Never raises. True if a swap was applied."""
    req_path = None
    ok = False
    try:
        req_path = Path(audit_dir) / REQUEST_FILE
        if not req_path.exists():
            return False
        ok = _handle(audit_dir, req_path)
    except Exception as exc:
        _log(audit_dir, "REFUSED_UNEXPECTED", "?", "%s: %s" % (type(exc).__name__, exc))
        ok = False
    if req_path is not None:
        try:
            req_path.unlink()  # a consumed request never re-applies; the log keeps the verdict
        except Exception:
            pass
    return ok
