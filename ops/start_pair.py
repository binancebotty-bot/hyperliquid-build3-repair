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
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
# pythonw with redirected stdio: CREATE_NO_WINDOW, not DETACHED_PROCESS.
UI_PORT = 8031
# The Core's pythonw uses DETACHED_PROCESS. The UI separately uses pythonw,
# CREATE_NO_WINDOW and redirected stdio; do not combine both creation flags.
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


SETTLE_S = 6.0          # the engine gets this long to prove it is alive before the UI is spawned
UI_WAIT_S = 60.0        # how long the UI gets to answer
STOP_WAIT_S = 10.0      # terminate, then this long, then kill


def pid_alive(pid):
    import psutil
    try:
        return psutil.Process(int(pid)).is_running()
    except Exception:
        return False


def acquire_lock(lock):
    """Exclusive start lock -> ('ok', fd) or ('held', holder-pid). A lock whose pid is dead is stale, not a blocker."""
    for _ in range(2):
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            return 'ok', fd
        except FileExistsError:
            try:
                other = int(lock.read_text(encoding='utf-8').strip() or 0)
            except (OSError, ValueError):
                other = 0
            if other and pid_alive(other):
                return 'held', other
            try:
                lock.unlink()
            except OSError:
                return 'held', other
    return 'held', 0


def release_lock(lock, fd):
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        lock.unlink()
    except OSError:
        pass


def read_pointer(pointer):
    """('absent','') | ('ok',text) | ('unreadable',reason).

    A directory or a denied path is unreadable, never absent: deleting it destroys a pointer this run cannot restore.
    """
    if not pointer.exists() and not pointer.is_symlink():
        return 'absent', ''
    try:
        return 'ok', pointer.read_text(encoding='utf-8-sig').strip()
    except OSError as exc:
        return 'unreadable', '%s: %s' % (type(exc).__name__, exc)


def reaped(proc, wait):
    """Popen.wait(timeout) IS the reap; polling and returning leaves the child unreaped."""
    try:
        proc.wait(timeout=wait)
        return True
    except Exception:
        return False


def stop_proc(proc, wait=None):
    """terminate -> wait -> kill -> wait -> 'terminated'|'killed'|'already_exited'|'unreaped'|'none'."""
    if proc is None:
        return 'none'
    if proc.poll() is not None:
        return 'already_exited'
    wait = STOP_WAIT_S if wait is None else wait
    try:
        proc.terminate()
    except Exception:
        pass
    if reaped(proc, wait):
        return 'terminated'
    try:
        proc.kill()
    except Exception:
        pass
    if reaped(proc, wait):
        return 'killed'
    return 'unreaped'          # the final wait ran; the process survived both signals


def state_identity(state):
    """(mtime_ns, size) of the UI state file BEFORE the launch, or None if it was absent."""
    try:
        st = (state / 'live_service_state.json').stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def ui_proven(ui, engine, port, state, before):
    """Up = both alive AND (our pid holds the port, or the state file is provably NEWER than before).

    `before` is state_identity() taken before the spawn. A file that already existed only proves the UI when its
    mtime strictly advances: a preserved or future timestamp would otherwise certify a hung UI.
    """
    if ui.poll() is not None or engine.poll() is not None:
        return False
    if SP.listener(port) == ui.pid:
        return True
    # NOT the state file: live_service_state.json is written by the ENGINE, so a fresh mtime proves the engine is
    # alive, never that the UI is. A uvicorn that never binds the port would be certified "up" by the engine's own
    # heartbeat. The listener PID is the only proof the UI owns this launch.
    return False


def already_running(state, port):
    """The refusal message if this dir or port is taken, else None. Read-only, so a dry run can call it too."""
    running = SP.pids(state)
    if running:
        return ("engine already running for %s: pids %s - stop it with ops/stop_pair.py --all"
                % (state, list(running)))
    if SP.listener(port):
        return "something is already listening on %d - stop the UI first" % port
    return None


def spawn_engine(engine_file, env):
    return subprocess.Popen(
        [PY_ENGINE, str(engine_file), "--ws", "--loop", "--interval", "10", "--poll-live", "--poll-copy"],
        cwd=str(engine_file.parent), env=env,
        creationflags=DETACHED_ONLY, close_fds=True)     # DETACHED_PROCESS only - never with CREATE_NO_WINDOW


def spawn_ui(port, engine_file, env):
    # Windows console python + detached handles crashes before uvicorn binds.
    # Preserve the 3-argument interface used by the launch runbook/tests.
    log_path = Path(env["HL_LIVE_AUDIT_DIR"]) / "ui_launch.log"
    with log_path.open("wb") as log:
        return subprocess.Popen(
            [PY_ENGINE, "-m", "uvicorn", "HL_Copy_App_SSOT:app", "--host", "127.0.0.1",
             "--port", str(port), "--no-access-log"],
            cwd=str(engine_file.parent), env=env, stdin=subprocess.DEVNULL,
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=CREATE_NO_WINDOW, close_fds=True)


def ui_launch_failure_output(state):
    """Only the last 4 KiB of this attempt's UI log, and only on failure."""
    try:
        with (state / "ui_launch.log").open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            stream.seek(max(0, stream.tell() - 4096))
            return stream.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


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

    # 2. the pointer this run owns (read-only, so a dry run can report it)
    pointer = stack_root(state) / "CURRENT_AUDIT_DIR"
    pstate, previous_pointer = read_pointer(pointer)
    if pstate == 'unreadable':
        return refuse("the pointer %s is present but unreadable (%s) - left in place, because a run that "
                      "cannot read it cannot restore it" % (pointer, previous_pointer))
    plan = {
        "checkout": str(checkout), "sha": sha, "state": str(state),
        "engine": str(engine_path(checkout)), "ui_port": args.ui_port, "pointer": str(pointer),
        "pointer_state": pstate,
    }

    if args.dry_run:
        blocked = already_running(state, args.ui_port)      # nothing starts, but the refusals are still reported
        if blocked:
            return refuse(blocked)
        print(json.dumps({"dry_run": True, "would_start": plan}, indent=2))
        return 0

    # 3. one start at a time per stack. The lock is taken BEFORE the running-process and listener checks and held
    #    through start, proof and pointer publication: a launcher that waited its turn must re-check, or it starts a
    #    second pair on a dir that is already running.
    lock = stack_root(state) / ".start_pair.lock"
    got, lock_fd = acquire_lock(lock)
    if got != 'ok':
        return refuse("another start is in progress on %s (lock pid %s) - delete %s if that pid is gone"
                      % (stack_root(state), lock_fd or '?', lock))
    try:
        blocked = already_running(state, args.ui_port)     # re-checked HERE: a launcher that waited must see A's pair
        if blocked:
            return refuse(blocked)

        env = dict(os.environ)
        env["HL_LIVE_AUDIT_DIR"] = str(state)
        for k in list(env):
            if k.startswith("PYTHON"):
                env.pop(k)          # a stray PYTHONPATH/PYTHONHOME makes the 3.14 UI exit instantly and silently
        before = state_identity(state)          # recorded BEFORE the spawn: a stale file can never prove the UI
        engine = spawn_engine(engine_path(checkout), env)
        ui = None
        up = False
        engine_exited = None
        stopped = {}
        # everything after the first process starts is guarded: any exception (UI spawn, pointer write) reaps it
        try:
            time.sleep(SETTLE_S)
            if engine.poll() is not None:
                engine_exited = engine.returncode        # fall through: the report must still say what was reaped
            else:
                ui = spawn_ui(args.ui_port, engine_path(checkout), env)
                deadline = time.time() + UI_WAIT_S
                while time.time() < deadline and not ui_proven(ui, engine, args.ui_port, state, before):
                    time.sleep(1.0)
                up = ui_proven(ui, engine, args.ui_port, state, before)
                if up:
                    # proven: only now does the pointer move, through a temp file so a kill mid-write cannot
                    # leave it empty
                    _tmp = pointer.with_name(pointer.name + '.tmp')
                    _tmp.write_text(str(state) + chr(10), encoding='utf-8')
                    os.replace(str(_tmp), str(pointer))
        finally:
            if not up:
                stopped = {'ui': stop_proc(ui), 'engine': stop_proc(engine)}
                try:
                    if pstate == 'ok' and previous_pointer and previous_pointer != str(state):
                        pointer.write_text(previous_pointer + chr(10), encoding='utf-8')   # revert: the live run
                    elif pstate == 'absent' and pointer.exists():
                        pointer.unlink()
                except Exception as exc:
                    print("WARNING: could not restore the pointer %s: %r" % (pointer, exc), file=sys.stderr)
        print(json.dumps({
            "pair": "STARTED" if up else ("ENGINE_EXITED" if engine_exited is not None else "UI_NOT_LISTENING"),
            "sha": sha, "state": str(state), "engine_pid": engine.pid, "ui_pid": ui.pid if ui else None,
            "engine_exit_rc": engine_exited,
            "ui_exit_rc": ui.poll() if ui is not None else None,
            "ui_launch_output": ui_launch_failure_output(state) if ui is not None and not up else "",
            "ui_port": args.ui_port, "listener": bool(SP.listener(args.ui_port)),
            "pointer": str(pointer), "pointer_state": pstate, "started_at": utc(),
            "stopped_on_failure": stopped,
            "sends": "OFF unless live_config says otherwise - arming is a separate logged step",
        }, indent=2))
        return 0 if up else 1
    finally:
        release_lock(lock, lock_fd)


if __name__ == "__main__":
    sys.exit(main())
