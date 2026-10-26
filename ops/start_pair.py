#!/usr/bin/env python3
"""Start the pair - engine and UI - from ONE checkout into ONE state dir, hidden, proven.

Why this is in the repo: the restart procedure used to live only in a scratch directory, so every session
rediscovered it and the audit-dir pointer was forgotten. Boss's standing rule is that the repo is in order at all
times. Sanitised: no key values, no hard-wired checkout paths - both the checkout and the state dir are arguments.

What it guarantees, in order:
  1. the checkout is a real pair checkout and (if given) the expected SHA is the one on disk;
  2. nothing is already running on that state dir or on the UI port - the proof stop_pair leaves behind;
  3. <stack>/CURRENT_AUDIT_DIR names this run, so a separate process (hl_monitor) cannot read a stale directory;
  4. engine and UI start console-less (pythonw), from the SAME checkout, one identity block printed at the end.

It does NOT seed a fresh state dir and it does NOT arm sending: both are separate ordered steps in
ops/PAIR_START_RUNBOOK.md. A fresh dir without seeding is the 2026-10-25 runaway, so refuse rather than guess.

    ops/start_pair.py --checkout <build-checkout> --state <stack>/runNN/state_YYYYMMDD \n                      [--expect-sha abc1234] [--ui-port 8031] [--dry-run]

Exit codes: 0 started (or a clean dry run), 1 refused, 2 bad arguments.
"""
import argparse
import re
import json
import os
import subprocess
import sys
import time
from pathlib import Path

OPS = Path(__file__).resolve().parent
sys.path.insert(0, str(OPS))
import stop_pair as SP  # reuse its pids()/listener() rather than re-deriving "is it running"

PY_ENGINE = os.environ.get("HL_PY_ENGINE") or r"C:/Users/wigmore/AppData/Local/Programs/Python/Python311/pythonw.exe"
PY_PLAIN = os.environ.get("HL_PY_PLAIN") or r"C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe"
UI_PORT = 8031
# pythonw is GUI-subsystem and has no console, so the detached flag alone is both sufficient and correct. Never OR
# the no-window flag into it: MSDN says that flag is IGNORED when the detached one is set, so the hide bit becomes
# dead code that reads like protection.
DETACHED_ONLY = 0x00000008


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def refuse(msg):
    print("REFUSED: %s" % msg, file=sys.stderr)
    return 1


def engine_path(checkout):
    return checkout / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"


def stack_root(state):
    """<stack>/runNN/state_YYYYMMDD -> <stack>"""
    return state.parent.parent


def main(argv=None):
    ap = argparse.ArgumentParser(description="start the pair from one checkout into one state dir")
    ap.add_argument("--checkout", required=True, help="the build checkout (contains _archive/hl_stage2)")
    ap.add_argument("--state", required=True, help="the state dir for this run")
    ap.add_argument("--expect-sha", default="", help="refuse unless the checkout is at this commit")
    ap.add_argument("--ui-port", type=int, default=UI_PORT, help="UI port (default 8031)")
    ap.add_argument("--dry-run", action="store_true", help="validate and print the plan; start nothing")
    args = ap.parse_args(argv)

    checkout = Path(args.checkout).expanduser()
    state = Path(args.state).expanduser()

    # 1. the checkout must be a pair checkout
    if not engine_path(checkout).exists():
        return refuse("no engine at %s - not a pair checkout" % engine_path(checkout))
    if not (checkout / "ops" / "stop_pair.py").exists():
        return refuse("%s has no ops/stop_pair.py - not a pair checkout" % checkout)

    sha = subprocess.run(["git", "-C", str(checkout), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    if args.expect_sha:
        want = args.expect_sha.strip()
        if not sha:
            return refuse("cannot read a commit from %s - is it a git checkout? an unreadable sha cannot be pinned"
                          % checkout)
        if len(want) < 7:
            return refuse("--expect-sha must be at least 7 characters, got %r (a short prefix certifies nothing)" % want)
        if not (want.startswith(sha) or sha.startswith(want[:len(sha)])):
            return refuse("checkout is at %s, expected %s" % (sha or "?", want))

    # the pointer lives at <stack>/CURRENT_AUDIT_DIR, so the shape of --state decides where it is written
    if not (re.fullmatch(r"state_\d{8}", state.name) and re.fullmatch(r"run\d+", state.parent.name)):
        return refuse("--state must look like <stack>/runNN/state_YYYYMMDD, got %s - the pointer path derives "
                      "from it and a wrong depth writes it where the monitor never looks" % state)
    # a fresh dir must be SEEDED, and live_config.json is not the proof: the seeder writes the leader cursor, and
    # an absent or zero cursor is exactly the 2026-10-25 replay condition.
    seeded = (state / "live_config.json").exists()
    if not state.exists():
        return refuse("%s does not exist - create it, seed it, then start (see PAIR_START_RUNBOOK section 3)"
                      % state)
    if not seeded:
        return refuse("%s has no live_config.json - seed it first; an unseeded dir replays history "
                      "as live intents (the 2026-10-25 runaway)" % state)
    cursor_file = state / "clean_core_runtime_state.json"
    if not cursor_file.exists():
        return refuse("%s has no clean_core_runtime_state.json - live_config alone is not a seed; run "
                      "ops/seed_pair_state.py (an absent cursor replays the retention window)" % state)
    try:
        raw_cursor = json.loads(cursor_file.read_text(encoding='utf-8-sig')).get('last_leader_poll_cursor_ms')
        if isinstance(raw_cursor, dict):                      # per-wallet map: any positive cursor proves seeding
            cursor = max([int(v) for v in raw_cursor.values() if str(v).lstrip('-').isdigit()] or [0])
        else:
            cursor = int(raw_cursor or 0)
    except Exception as exc:
        return refuse("cannot read the leader cursor from %s: %r" % (cursor_file, exc))
    _age_ms = int(time.time() * 1000) - cursor
    if cursor > 0 and _age_ms > 100 * 60 * 1000:
        return refuse("the leader cursor in %s is %d ms old, older than the 100-minute retention window - a copied "
                      "state dir passes a positive-cursor check and still replays history; re-seed rather than force"
                      % (cursor_file, _age_ms))
    if cursor <= 0:
        return refuse("the leader cursor in %s is %r - an unseeded/zero cursor replays the retention window "
                      "as live intents (the 2026-10-25 runaway); re-seed rather than force" % (cursor_file, cursor))

    # 2. nothing may already be running for this dir or on the UI port
    running = SP.pids(state)
    if running:
        return refuse("engine already running for %s: pids %s - stop it with ops/stop_pair.py --all"
                      % (state, list(running)))
    if SP.listener(args.ui_port):
        return refuse("something is already listening on %d - stop the UI first" % args.ui_port)

    # 3. the pointer this run owns
    pointer = stack_root(state) / "CURRENT_AUDIT_DIR"
    plan = {
        "checkout": str(checkout), "sha": sha, "state": str(state),
        "engine": str(engine_path(checkout)), "ui_port": args.ui_port, "pointer": str(pointer),
    }
    try:
        previous_pointer = pointer.read_text(encoding="utf-8-sig").strip() if pointer.exists() else ""
    except OSError:
        previous_pointer = ""

    if args.dry_run:
        print(json.dumps({"dry_run": True, "would_start": plan}, indent=2))
        return 0


    env = dict(os.environ)
    env["HL_LIVE_AUDIT_DIR"] = str(state)
    for k in list(env):
        if k.startswith("PYTHON"):
            env.pop(k)          # a stray PYTHONPATH/PYTHONHOME makes the 3.14 UI exit instantly and silently
    engine = subprocess.Popen(
        [PY_ENGINE, str(engine_path(checkout)), "--ws", "--loop", "--interval", "10",
         "--poll-live", "--poll-copy"],
        cwd=str(engine_path(checkout).parent), env=env,
        creationflags=DETACHED_ONLY, close_fds=True)     # DETACHED_PROCESS only - never with CREATE_NO_WINDOW
    time.sleep(6.0)
    if engine.poll() is not None:
        return refuse("the engine exited immediately (rc=%s) - read its log, nothing was armed" % engine.returncode)

    ui = subprocess.Popen(
        [PY_PLAIN, "-m", "uvicorn", "HL_Copy_App_SSOT:app", "--host", "127.0.0.1",
         "--port", str(args.ui_port), "--no-access-log"],
        cwd=str(engine_path(checkout).parent), env=env,
        creationflags=DETACHED_ONLY, close_fds=True)

    deadline = time.time() + 60
    while time.time() < deadline and not (SP.listener(args.ui_port) and (state / "live_service_state.json").exists()):
        time.sleep(1.0)

    up = bool(SP.listener(args.ui_port)) and engine.poll() is None
    if up:
        # proven: only now does the pointer move. Written through a temp file, so a kill mid-write cannot leave an
        # empty CURRENT_AUDIT_DIR behind.
        _tmp = pointer.with_name(pointer.name + '.tmp')
        _tmp.write_text(str(state) + chr(10), encoding='utf-8')
        os.replace(str(_tmp), str(pointer))
    else:
        # A failed start must leave NOTHING running: a detached engine with no pointer is invisible to the monitor and
        # blocks the next start with "engine already running".
        for _proc in (ui, engine):
            try:
                if _proc is not None and _proc.poll() is None:
                    _proc.terminate()
            except Exception:
                pass
        try:
            if previous_pointer and previous_pointer != str(state):
                pointer.write_text(previous_pointer + chr(10), encoding='utf-8')   # revert: the run that was live
            elif pointer.exists() and not previous_pointer:
                pointer.unlink()
        except Exception:
            pass
    print(json.dumps({
        "pair": "STARTED" if up else "UI_NOT_LISTENING",
        "sha": sha, "state": str(state), "engine_pid": engine.pid, "ui_pid": ui.pid,
        "ui_port": args.ui_port, "listener": bool(SP.listener(args.ui_port)),
        "pointer": str(pointer), "started_at": utc(),
        "sends": "OFF unless live_config says otherwise - arming is a separate logged step",
    }, indent=2))
    return 0 if up else 1


if __name__ == "__main__":
    sys.exit(main())
