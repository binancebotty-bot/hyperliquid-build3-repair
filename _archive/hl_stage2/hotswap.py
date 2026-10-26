#!/usr/bin/env python3
"""Hot-swap seam for ALLOWLISTED sibling modules of the live copy engine.

A swap is requested by dropping HOTSWAP_REQUEST.json into the engine audit dir. The engine's
--loop cycle calls tick(AUDIT_DIR) at the top of every cycle, right beside the STOP_REQUESTED
sentinel check: one exists() when nothing is requested.

Nothing is imported, reloaded or swapped unless the request names an ALLOWLISTED module and the
artifact bytes hash to the sha256 the request declares. Every refusal is named, appended to
hotswap.log next to the request, and leaves the OLD code running: this module never raises.

The install never touches the live module object: it REBINDS the importer's module-level name
with one assignment (the setter the importer registers) and repoints sys.modules, so a direct
importer re-resolving the name also gets the new code.

The guard is shared for calls and exclusive for the swap: a call bumps a counter under a short
lock (never held across the network call), so concurrent calls never exclude each other; a swap
blocks new entries, waits for the counter to drain, installs, then clears. A swap that cannot
drain within GUARD_SWAP_TIMEOUT_SEC is refused REFUSED_BUSY and changes nothing - not the live
code and not HOTSWAP_STATE.json.

The published identity is the digest VERIFIED before installation, recorded at install and at
rollback: mutating or deleting the artifact afterwards cannot make it describe code that is not
running.
"""
from __future__ import annotations

import hashlib
import os
import importlib.util
import json
import sys
import threading
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

# A swap waits this long for in-flight calls to drain, then refuses REFUSED_BUSY: a hung call must
# never freeze the cycle loop.
GUARD_SWAP_TIMEOUT_SEC = 5.0

_sha_cache: Dict[str, Any] = {}
_installed_sha: Dict[str, str] = {}  # VERIFIED digest of the code actually running, per module
_setters: Dict[str, Any] = {}  # name -> the importer's one-assignment rebind
_current: Dict[str, Any] = {}  # name -> the module reference registered as current


class _Guard:
    """Reader/writer gate: any number of calls hold it, one swap takes it exclusively.

    The COUNTER is held for the whole call - that is what a swap waits on - while the condition
    lock that guards the increment/decrement is brief and never held across the call itself.
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._active = 0
        self._swapping = False
        # set once a swap holds the exclusive flag (it may still be draining): lets a test wait for
        # "the swap has begun" without sleeping.
        self.swap_entered = threading.Event()

    def __enter__(self) -> "_Guard":
        with self._cond:
            while self._swapping:  # a swap is installing: enter only once it is done
                self._cond.wait()
            self._active += 1
        return self

    def __exit__(self, *_exc: Any) -> None:
        with self._cond:
            self._active -= 1
            self._cond.notify_all()

    def acquire_exclusive(self, timeout: float) -> bool:
        """Refuse new holders, wait for the active count to drain. False and no change on timeout."""
        deadline = time.monotonic() + max(0.0, timeout)
        with self._cond:
            self._swapping = True  # first: no new holder may enter from here on
            self.swap_entered.set()
            while self._active:
                left = deadline - time.monotonic()
                if left <= 0:
                    self._swapping = False
                    self._cond.notify_all()
                    return False
                self._cond.wait(left)
            return True

    def release_exclusive(self) -> None:
        with self._cond:
            self._swapping = False
            self._cond.notify_all()

    def active(self) -> int:
        with self._cond:
            return self._active


_GUARD = _Guard()


def guard() -> _Guard:
    """Hold this around a use of a swappable module; a swap cannot straddle the block."""
    return _GUARD


class _GuardedModule:
    """Module proxy that holds the shared guard for the whole of every call into the module.

    The proxy stores the module NAME, not the module: the callable is resolved inside the guard, so
    a swap completing between an attribute access and the call cannot leave that call running the
    OLD code while the new module is already live.
    """

    __slots__ = ("_name", "_fallback")

    def __init__(self, module: Any) -> None:
        object.__setattr__(self, "_name", str(getattr(module, "__name__", "")))
        object.__setattr__(self, "_fallback", module)

    def _live(self) -> Any:
        name = object.__getattribute__(self, "_name")
        mod = sys.modules.get(name)
        if mod is None:
            mod = _current.get(name)
        return mod if mod is not None else object.__getattribute__(self, "_fallback")

    def __getattr__(self, item: str) -> Any:
        value = getattr(self._live(), item)
        if isinstance(value, type) or not callable(value):
            return value  # exception classes and constants pass straight through
        name = object.__getattribute__(self, "_name")

        def _call(*args: Any, **kwargs: Any) -> Any:
            with _GUARD:  # lookup AND call under one hold: a swap waits for both
                target = sys.modules.get(name) or _current.get(name)
                if target is None:
                    target = object.__getattribute__(self, "_fallback")
                return getattr(target, item)(*args, **kwargs)

        return _call

    def __setattr__(self, item: str, value: Any) -> None:
        setattr(self._live(), item, value)


def guarded(module: Any) -> _GuardedModule:
    _current[str(getattr(module, "__name__", ""))] = module  # the registered current reference
    return _GuardedModule(module)


def register_setter(name: str, setter: Any) -> None:
    """The importer's one-assignment rebind, called with the new module under the exclusive turn."""
    _setters[name] = setter


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


def _write_state_bytes(path: Path, blob: str) -> None:
    """tmp + fsync + os.replace: a crash mid-write leaves the OLD file whole, never a truncated map.

    write_text() could truncate the file and take every module's rollback pointer with it.
    """
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(blob)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _write_state(audit_dir: Any, state: Dict[str, Any]) -> bool:
    """True ONLY if the whole map was replaced. The result is explicit: a caller must never assume it."""
    try:
        _write_state_bytes(_state_path(audit_dir), json.dumps(state, indent=2, sort_keys=True))
    except Exception:
        return False
    return True


def _persist_state(audit_dir: Any, name: str, entry: Dict[str, Any]) -> bool:
    """Write the entry, re-read it and check it names the expected path and digest: the pointer must
    be durable BEFORE anything is installed."""
    state = _read_state(audit_dir)
    state[name] = entry
    if not _write_state(audit_dir, state):
        return False
    back = _read_state(audit_dir).get(name)
    if not isinstance(back, dict):
        return False
    # EVERY field the rollback depends on, not just path+sha: when a retry refreshes the previous-code
    # pointer for the SAME artifact, a failed write leaves an entry that still matches path+sha, and the
    # install would then proceed with a rollback pointer that was never updated (Codex 6408591328).
    for key in ("installed_path", "installed_sha", "previous_path", "previous_sha"):
        if key in entry and back.get(key) != entry[key]:
            return False
    return True


def loaded_sha(name: str) -> str:
    """Digest of the code the module object is executing.

    After a swap this is the digest VERIFIED before installation (recorded at install/rollback),
    so a mutated or deleted artifact cannot change what is reported. Before any swap it is the
    sha256 of the module's source file, memoised on (path, mtime, size). "" for a module that is
    not imported or whose file cannot be read.
    """
    recorded = _installed_sha.get(name)
    if recorded:
        return recorded
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


def _build(path: Path, raw: bytes, name: str) -> types.ModuleType:
    """Fully execute the artifact as a module that CARRIES THE TARGET'S IDENTITY.

    __name__, __file__, __spec__ and __loader__ all describe the target module, so code doing
    `from <target> import y`, logging __name__ or an importlib check behaves as it would on the real
    module. The staging dict is separate, so the live module is untouched until the rebind. Raises
    on any import-time failure.
    """
    staging = types.ModuleType(name)
    staging.__file__ = str(path)
    spec = importlib.util.spec_from_file_location(name, str(path))
    staging.__spec__ = spec
    staging.__loader__ = getattr(spec, "loader", None)
    staging.__package__ = ""
    exec(compile(raw, str(path), "exec"), staging.__dict__)
    return staging


def _install(audit_dir: Any, name: str, new_module: types.ModuleType, digest: str,
             entry: Optional[Dict[str, Any]]) -> bool:
    """Exclusive turn FIRST, then the durable state, then ONE rebind of the importer's name.

    Taking the exclusive turn before writing anything is what keeps a REFUSED_BUSY swap from
    leaving HOTSWAP_STATE.json describing an install that never happened.
    """
    setter = _setters.get(name)
    if setter is None:
        return _refuse(audit_dir, "REFUSED_NO_SETTER", name,
                       "importer registered no rebind setter; refusing a half swap")
    if not _GUARD.acquire_exclusive(GUARD_SWAP_TIMEOUT_SEC):
        return _refuse(audit_dir, "REFUSED_BUSY", name,
                       "a call stayed in flight for %.1fs; nothing installed" % GUARD_SWAP_TIMEOUT_SEC)
    _state_file = _state_path(audit_dir)
    try:
        _prior_state = _state_file.read_text(encoding="utf-8")
    except Exception:
        _prior_state = ""
    try:
        if entry is not None and not _persist_state(audit_dir, name, entry):
            return _refuse(audit_dir, "REFUSED_STATE_WRITE_FAILED", name,
                           "installed pointer not durable; nothing installed")
        setter(new_module)
        sys.modules[name] = new_module  # a direct importer re-resolving the name sees it too
        _installed_sha[name] = digest
    except Exception as exc:
        # the state named this artifact before the rebind happened: put the previous map back, so a
        # refused install never leaves a durable pointer to code that is not live.
        try:
            _write_state_bytes(_state_file, _prior_state)
        except Exception:
            pass
        return _refuse(audit_dir, "REFUSED_SETTER_RAISED", name, "%s: %s" % (type(exc).__name__, exc))
    finally:
        _GUARD.release_exclusive()
    return True


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
        staging = _build(path, raw, name)
    except BaseException as exc:  # a bad artifact must not kill the engine
        return _refuse(audit_dir, "REFUSED_IMPORT_RAISED", name, "%s: %s" % (type(exc).__name__, exc))
    previous = _keep_previous(audit_dir, name, target)
    if previous is None:
        return _refuse(audit_dir, "REFUSED_PREVIOUS_COPY_FAILED", name,
                       "could not keep the live source %r; no rollback available" % getattr(target, "__file__", None))
    entry = {"installed_path": str(path), "installed_sha": actual, **previous}
    if not _install(audit_dir, name, staging, actual, entry):
        return False
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
        staging = _build(prev_path, raw, name)
    except BaseException as exc:
        return _refuse(audit_dir, "REFUSED_IMPORT_RAISED", name, "%s: %s" % (type(exc).__name__, exc))
    # the state write happens INSIDE the exclusive turn (see _install), so a refused rollback leaves
    # HOTSWAP_STATE.json byte-identical and still naming what is actually live.
    if not _install(audit_dir, name, staging, actual,
                    {"installed_path": str(prev_path), "installed_sha": actual}):
        return False
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
