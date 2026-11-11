#!/usr/bin/env python3
"""Boot/logon auto-start for the Core+UI pair. Deterministic, refusing, and provable.

WHY THIS EXISTS
The pair died at ~23:26Z on 2026-10-28 and nothing brought it back: the restart procedure lived in a
scratch dir and no scheduled task owned it (C7-DIR-154/155/181). This is the single boot entry point,
and it refuses rather than guessing in every case the runbook says to refuse.

CONTRACT
  * pinned checkout AND pinned SHA - a checkout not at the pinned commit is refused, never started;
  * pinned state dir (default run19/state_20261027) - seeding is start_pair.py's job and its refusals
    are honoured verbatim, because an unseeded dir replays the retention window as live intents;
  * REFUSE if an engine already holds a lock, either the machine-wide global lock
    (<LOCALAPPDATA>/HL_Live_Copy_Service_Core/engine-global.lock + .holder.json) or the per-state
    <state>/instance.lock. A boot task that fires twice must not start a second pair;
  * every decision is appended to an identity log with its reason, so "why did boot do nothing" is
    answered from a file, not from memory;
  * --check / --dry-run starts NOTHING and prints what it would start and why it would refuse.

EXIT CODES  0 started or clean check  1 refused  2 bad arguments  3 start_pair.py failed
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_CHECKOUT = r"C:/tmp/v33_a1acc28"
DEFAULT_STATE = r"C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run19/state_20261027"
PINNED_SHA = "a1acc28c0cd9d3a6710783ed08a7b9401475c644"
UI_PORT = 8031
PY_PLAIN = os.environ.get("HL_PY_PLAIN") or r"C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe"
LOG = Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "HL_Live_Copy_Service_Core" / "boot_start_pair.log"


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log(entry):
    """Append-only identity log. Never truncates: the history of refusals IS the evidence."""
    entry["at"] = utc()
    entry["pid"] = os.getpid()
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
    except OSError:
        pass


def global_lock_path():
    override = str(os.getenv("HL_LIVE_GLOBAL_LOCK_FILE") or "").strip()
    if override:
        return Path(override)
    base = str(os.getenv("LOCALAPPDATA") or os.getenv("XDG_STATE_HOME") or tempfile.gettempdir())
    return Path(base) / "HL_Live_Copy_Service_Core" / "engine-global.lock"


def global_lock_held():
    """True when another process holds the engine's machine-wide byte-range lock.

    The engine holds it for its process lifetime, so the OS drops it when the engine dies: it can
    never go stale. We test by TRYING to take it and releasing immediately.
    """
    lock_path = global_lock_path()
    if not lock_path.exists():
        return False, None
    try:
        fh = open(lock_path, "a+")
    except OSError as exc:
        return True, "lock unreadable: %s: %s" % (type(exc).__name__, exc)
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0)
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                return False, None
            except OSError:
                pass
        else:
            import fcntl
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                return False, None
            except OSError:
                pass
        holder = lock_path.with_name(lock_path.name + ".holder.json")
        try:
            ident = json.loads(holder.read_text(encoding="utf-8-sig"))
        except Exception:
            ident = {"holder": "unknown"}
        return True, ident
    finally:
        try:
            fh.close()
        except OSError:
            pass


def state_lock_held(state):
    """The engine writes <state>/instance.lock. Refuse if a LIVE pid holds it; a dead pid is stale."""
    lock = Path(state) / "instance.lock"
    if not lock.exists():
        return False, None
    try:
        raw = lock.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        return True, "instance.lock unreadable: %s" % exc
    pid = None
    for token in raw.replace(",", " ").split():
        if token.isdigit():
            pid = int(token)
            break
    if pid is None:
        return False, "instance.lock present but carries no pid (%r) - treated as stale" % raw[:60]
    try:
        import psutil
        alive = psutil.Process(pid).is_running()
    except Exception:
        alive = False
    return (True, {"pid": pid}) if alive else (False, "stale instance.lock from dead pid %d" % pid)


def build(args):
    checkout = Path(args.checkout).expanduser()
    state = Path(args.state).expanduser()
    start_pair = checkout / "ops" / "start_pair.py"
    engine = checkout / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"

    plan = {
        "checkout": str(checkout), "state": str(state),
        "pinned_sha": PINNED_SHA, "ui_port": args.ui_port,
        "start_pair": str(start_pair), "engine": str(engine),
    }
    reasons = []

    if not start_pair.exists():
        reasons.append("no ops/start_pair.py at %s - not a pair checkout" % checkout)
    if not engine.exists():
        reasons.append("no engine at %s" % engine)

    try:
        sha = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as exc:
        sha = ""
        reasons.append("cannot read git HEAD: %s" % exc)
    plan["actual_sha"] = sha or None
    if sha and sha != PINNED_SHA:
        reasons.append("checkout is at %s, pinned build is %s" % (sha[:12], PINNED_SHA[:12]))
    elif not sha:
        reasons.append("checkout HEAD unreadable - an unreadable sha cannot be pinned")

    if not state.exists():
        reasons.append("state dir %s does not exist" % state)
    else:
        if not (state / "live_config.json").exists():
            reasons.append("state dir has no live_config.json - unseeded (2026-10-25 runaway shape)")
        if not (state / "clean_core_runtime_state.json").exists():
            reasons.append("state dir has no clean_core_runtime_state.json - no leader cursor, unseeded")

    gheld, gident = global_lock_held()
    if gheld:
        reasons.append("engine already holds the machine-wide global lock: %s" % json.dumps(gident)[:200])
    sheld, sident = state_lock_held(state)
    if sheld:
        reasons.append("engine already holds %s/instance.lock: %s" % (state, json.dumps(sident)[:120]))

    return plan, reasons


def main(argv=None):
    ap = argparse.ArgumentParser(description="boot/logon auto-start for the Core+UI pair")
    ap.add_argument("--checkout", default=DEFAULT_CHECKOUT)
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--ui-port", type=int, default=UI_PORT)
    ap.add_argument("--check", "--dry-run", dest="check", action="store_true",
                    help="start nothing; print what would start and why it would refuse")
    args = ap.parse_args(argv)

    plan, reasons = build(args)

    if reasons:
        payload = {"mode": "check" if args.check else "boot", "decision": "REFUSE",
                   "reasons": reasons, "plan": plan, "log": str(LOG)}
        log({"event": "boot_refused", "reasons": reasons, "plan": plan})
        print(json.dumps(payload, indent=2))
        return 1

    if args.check:
        payload = {"mode": "check", "decision": "WOULD_START", "reasons": [],
                   "plan": plan, "log": str(LOG)}
        log({"event": "boot_check_would_start", "plan": plan})
        print(json.dumps(payload, indent=2))
        return 0

    cmd = [PY_PLAIN, plan["start_pair"],
           "--checkout", plan["checkout"], "--state", plan["state"],
           "--expect-sha", PINNED_SHA, "--ui-port", str(args.ui_port)]
    log({"event": "boot_start_invoked", "cmd": cmd, "plan": plan})
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as exc:
        log({"event": "boot_start_error", "error": "%s: %s" % (type(exc).__name__, exc)})
        print(json.dumps({"decision": "ERROR", "error": str(exc), "cmd": cmd}, indent=2))
        return 3

    payload = {"decision": "STARTED" if proc.returncode == 0 else "START_FAILED",
               "start_pair_exit": proc.returncode,
               "stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:],
               "cmd": cmd, "log": str(LOG)}
    log({"event": "boot_start_result", "exit": proc.returncode,
         "stdout_tail": proc.stdout[-500:], "stderr_tail": proc.stderr[-500:]})
    print(json.dumps(payload, indent=2))
    return 0 if proc.returncode == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
