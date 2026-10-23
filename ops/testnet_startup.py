#!/usr/bin/env python3
"""Dry-run-first Build 3 TESTNET launcher and read-only health watcher."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SPEC_FILE = Path(__file__).with_name("testnet_launch_spec.json")
def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def utc_ms() -> int:
    return int(time.time() * 1000)


def iso_ms(value: object) -> int:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return int(parsed.timestamp() * 1000)
    except (ValueError, TypeError, OverflowError):
        return 0


def norm_path(value: object) -> str:
    return os.path.normcase(os.path.realpath(str(value or "")))


def load_spec() -> dict:
    spec = read_json(SPEC_FILE)
    if spec.get("schema") != 1 or spec.get("follower_network") != "testnet":
        raise ValueError("launch spec is invalid or not TESTNET-only")
    return spec


def state_dir_for(spec: dict) -> Path:
    return (ROOT / spec["state_dir"]).resolve()


def other_live_runs(spec: dict, expected_dir: Path) -> list[dict]:
    root = Path(spec["testnet_state_root"])
    live: list[dict] = []
    if not root.is_dir():
        return live
    for path in root.glob("run*/state*/live_service_state.json"):
        if norm_path(path.parent) == norm_path(expected_dir):
            continue
        state = read_json(path)
        pid = state.get("process_id")
        started = state.get("started_at_ms")
        actual = process_start_ms(pid)
        if isinstance(pid, int) and isinstance(started, int) and actual is not None and abs(actual - started) <= 2000:
            live.append({"pid": pid, "run": path.parent.parent.name, "state_dir": norm_path(path.parent)})
    return live


def git_sha() -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip()


def check_source(spec: dict) -> str:
    sha = git_sha()
    subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", spec["source_base_sha"], sha],
        check=True, capture_output=True, timeout=10,
    )
    dirty = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain"],
        check=True, capture_output=True, text=True, timeout=10,
    ).stdout
    if dirty:
        raise ValueError("source checkout is not clean; refusing to launch an unpinned tree")
    return sha


def process_start_ms(pid: object) -> int | None:
    """Read PID creation time only; never inspect the process command line."""
    if os.name != "nt":
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = (wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4))
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return None
        try:
            created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
            if not kernel32.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(exited),
                ctypes.byref(kernel_time), ctypes.byref(user_time),
            ):
                return None
            ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
            return ticks // 10_000 - 11644473600000
        finally:
            kernel32.CloseHandle(handle)
    except (OSError, ValueError, TypeError):
        return None


def global_holder_path() -> Path:
    return Path(load_spec()["global_holder_path"])


def fetch_ui(base_url: str, timeout: float = 2.0) -> dict:
    try:
        with urlopen(base_url.rstrip("/") + "/api/state", timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, URLError):
        return {}


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def evaluate(service: dict, runtime: dict, ui: dict, holder: dict, *, expected_sha: str,
             expected_dir: str, now_ms: int, max_age_ms: int,
             actual_pid_start_ms: int | None, other_live_pids: tuple[int, ...] = ()) -> list[str]:
    errors: list[str] = []
    pid = service.get("process_id")
    started = service.get("started_at_ms")
    state_ms = service.get("last_state_write_ms") or service.get("created_at_ms")
    if not isinstance(pid, int) or pid <= 0 or runtime.get("process_id") != pid:
        errors.append("CORE_PID_MISMATCH")
    if not isinstance(started, int) or runtime.get("started_at_ms") != started:
        errors.append("CORE_START_MISMATCH")
    if actual_pid_start_ms is None or not isinstance(started, int) or abs(actual_pid_start_ms - started) > 2000:
        errors.append("CORE_PID_NOT_VERIFIED")
    if not isinstance(state_ms, int) or not state_ms or now_ms - state_ms > max_age_ms:
        errors.append("CORE_STATE_STALE")
    runtime_ms = runtime.get("last_state_write_ms")
    if not isinstance(runtime_ms, int) or not runtime_ms or now_ms - runtime_ms > max_age_ms:
        errors.append("CORE_RUNTIME_STATE_STALE")
    if service.get("build_sha") != expected_sha:
        errors.append("CORE_BUILD_SHA_MISMATCH")
    expected_config = str(Path(expected_dir) / "live_config.json")
    if norm_path(service.get("config_path")) != norm_path(expected_config):
        errors.append("CORE_STATE_DIR_MISMATCH")
    networks = service.get("networks") if isinstance(service.get("networks"), dict) else {}
    if networks.get("follower") != "testnet":
        errors.append("FOLLOWER_NOT_TESTNET")
    holder_pid = holder.get("pid")
    holder_state = holder.get("state_dir")
    holder_started = iso_ms(holder.get("started_at"))
    if holder_pid != pid or norm_path(holder_state) != expected_dir or not started or abs(holder_started - started) > 2000:
        errors.append("GLOBAL_ENGINE_HOLDER_MISMATCH")
    if other_live_pids:
        errors.append("MULTIPLE_CORE_ENGINES")
    if ui.get("engine_process_id") != pid:
        errors.append("UI_PID_MISMATCH")
    if ui.get("engine_started_at_ms") != started:
        errors.append("UI_START_MISMATCH")
    if ui.get("engine_build_sha") != expected_sha:
        errors.append("UI_BUILD_SHA_MISMATCH")
    if norm_path(ui.get("audit_dir")) != expected_dir:
        errors.append("UI_AUDIT_DIR_MISMATCH")
    return errors


def collect(spec: dict, state_dir: Path, expected_sha: str) -> tuple[list[str], dict]:
    service_path = state_dir / "live_service_state.json"
    runtime_path = state_dir / "clean_core_runtime_state.json"
    service = read_json(service_path)
    runtime = read_json(runtime_path)
    holder = read_json(global_holder_path())
    others = other_live_runs(spec, state_dir)
    ui = fetch_ui(spec["ui_base_url"])
    age_ms = int(spec["state_max_age_seconds"] * 1000)
    errors = evaluate(
        service, runtime, ui, holder, expected_sha=expected_sha,
        expected_dir=norm_path(state_dir), now_ms=utc_ms(), max_age_ms=age_ms,
        actual_pid_start_ms=process_start_ms(service.get("process_id")),
        other_live_pids=tuple(row["pid"] for row in others),
    )
    if not Path(spec["testnet_state_root"]).is_dir():
        errors.append("TESTNET_STATE_ROOT_UNAVAILABLE")
    if not service_path.exists() or not runtime_path.exists():
        if "CORE_STATE_STALE" not in errors:
            errors.append("CORE_STATE_MISSING")
    else:
        for path, reason in ((service_path, "CORE_STATE_FILE_MTIME_STALE"),
                             (runtime_path, "CORE_RUNTIME_STATE_FILE_MTIME_STALE")):
            if utc_ms() - int(path.stat().st_mtime * 1000) > age_ms:
                errors.append(reason)
    return errors, {"pid": service.get("process_id"), "build_sha": service.get("build_sha"),
                    "follower_network": ((service.get("networks") or {}).get("follower")
                                         if isinstance(service.get("networks"), dict) else None),
                    "other_live_runs": [{"run": row["run"], "pid": row["pid"]} for row in others],
                    "state_age_seconds": round(max(0, utc_ms() - int(service_path.stat().st_mtime * 1000)) / 1000, 1)
                    if service_path.exists() else None}


def post_alert(spec: dict, state_dir: Path, errors: list[str], detail: dict) -> None:
    marker = state_dir / "startup_watchdog_alert.json"
    previous = read_json(marker)
    fingerprint = ",".join(sorted(set(errors)))
    if not errors:
        if previous.get("active"):
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({"active": False, "errors": [], "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}), encoding="utf-8")
        return
    if previous.get("active") and previous.get("fingerprint") == fingerprint:
        return
    gh = shutil.which("gh")
    if not gh:
        print("WATCHDOG_ALERT_NOT_POSTED: GitHub CLI unavailable; " + fingerprint)
        return
    body = ("TESTNET startup watchdog alert (alert-only; no restart attempted).\n\n"
            f"Errors: {fingerprint}\nPID: {detail.get('pid')}\nBuild SHA: {detail.get('build_sha')}\n"
            f"Follower network: {detail.get('follower_network')}\nState age seconds: {detail.get('state_age_seconds')}\n")
    result = subprocess.run(
        [gh, "issue", "comment", str(spec["issue_number"]), "--repo", spec["repository"], "--body", body],
        capture_output=True, text=True, timeout=20,
    )
    if result.returncode:
        print("WATCHDOG_ALERT_NOT_POSTED: GitHub CLI failed; " + fingerprint)
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"active": True, "fingerprint": fingerprint,
                                  "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}), encoding="utf-8")
    print("WATCHDOG_ALERT_POSTED: " + fingerprint)


def plan(spec: dict, sha: str, state_dir: Path) -> None:
    print(json.dumps({
        "mode": "DRY_RUN",
        "action": "START TESTNET core, wait for fresh state, then start loopback UI",
        "core_sha": sha,
        "follower_network": spec["follower_network"],
        "shared_state_dir": str(state_dir),
        "core_script": str(ROOT / spec["core_script"]),
        "ui_script": str(ROOT / spec["ui_script"]),
        "processes_started": 0,
        "runtime_or_config_changed": False,
    }, indent=2))


def self_check() -> None:
    now = utc_ms()
    directory = norm_path(ROOT / ".self-check-state")
    service = {"process_id": 42, "started_at_ms": now - 1000, "last_state_write_ms": now,
               "build_sha": "abc", "networks": {"follower": "testnet"},
               "config_path": str(Path(directory) / "live_config.json")}
    runtime = {"process_id": 42, "started_at_ms": now - 1000, "last_state_write_ms": now}
    ui = {"engine_process_id": 42, "engine_started_at_ms": now - 1000,
          "engine_build_sha": "abc", "audit_dir": directory}
    holder = {"pid": 42, "started_at": dt.datetime.fromtimestamp((now - 1000) / 1000, dt.timezone.utc).isoformat(),
              "state_dir": directory}
    args = dict(expected_sha="abc", expected_dir=directory, now_ms=now, max_age_ms=30_000,
                actual_pid_start_ms=now - 1000)
    assert not evaluate(service, runtime, ui, holder, **args)
    stale = evaluate({**service, "last_state_write_ms": now - 31_000}, runtime, ui, holder, **args)
    assert "CORE_STATE_STALE" in stale
    assert "CORE_RUNTIME_STATE_STALE" in evaluate(service, {**runtime, "last_state_write_ms": now - 31_000}, ui, holder, **args)
    assert "UI_PID_MISMATCH" in evaluate(service, runtime, {**ui, "engine_process_id": 43}, holder, **args)
    assert "UI_BUILD_SHA_MISMATCH" in evaluate(service, runtime, {**ui, "engine_build_sha": "old"}, holder, **args)
    assert "UI_AUDIT_DIR_MISMATCH" in evaluate(service, runtime, {**ui, "audit_dir": directory + "-old"}, holder, **args)
    assert "CORE_STATE_DIR_MISMATCH" in evaluate(service, runtime, ui, holder, **{**args, "expected_dir": directory + "-old"})
    assert "FOLLOWER_NOT_TESTNET" in evaluate({**service, "networks": {"follower": "mainnet"}}, runtime, ui, holder, **args)
    assert "GLOBAL_ENGINE_HOLDER_MISMATCH" in evaluate(service, runtime, ui, {**holder, "pid": 43}, **args)
    assert "CORE_PID_NOT_VERIFIED" in evaluate(service, runtime, ui, holder, **{**args, "actual_pid_start_ms": None})
    assert "MULTIPLE_CORE_ENGINES" in evaluate(service, runtime, ui, holder, **{**args, "other_live_pids": (43,)})
    print("SELF_CHECK_PASS: healthy identity; stale state; PID/SHA/old-UI-folder mismatch; wrong network; extra Core; missing/dead PID")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=("plan", "verify", "watch", "start", "self-check"), default="plan")
    parser.add_argument("--execute", action="store_true", help="allow the TESTNET launch after all guards pass")
    parser.add_argument("--confirm-testnet", action="store_true", help="confirm this is an explicitly authorized TESTNET start")
    parser.add_argument("--authorization-order", help="fresh direct order ID that authorizes the start")
    args = parser.parse_args()
    if args.action == "self-check":
        self_check()
        return 0
    spec = load_spec()
    state_dir = state_dir_for(spec)
    if args.action == "plan" or (args.action == "start" and not args.execute):
        plan(spec, check_source(spec), state_dir)
        print("DRY_RUN_ONLY: no engine, UI, state, config, or scheduler changes")
        return 0
    sha = check_source(spec)
    if args.action == "verify":
        errors, detail = collect(spec, state_dir, sha)
        print(json.dumps({"status": "FAIL" if errors else "PASS", "errors": errors, **detail}, indent=2))
        return 1 if errors else 0
    if args.action == "watch":
        try:
            while True:
                errors, detail = collect(spec, state_dir, sha)
                print(json.dumps({"status": "FAIL" if errors else "PASS", "errors": errors, **detail}, indent=2))
                post_alert(spec, state_dir, errors, detail)
                time.sleep(60)
        except KeyboardInterrupt:
            print("WATCH_STOPPED: no Core or UI process was started or stopped")
            return 0
    if args.action == "start":
        if not args.confirm_testnet:
            raise SystemExit("REFUSED: start requires --confirm-testnet and a fresh direct authorization")
        if not args.authorization_order or not args.authorization_order.isdigit():
            raise SystemExit("REFUSED: start requires the ID of a fresh direct authorization order")
        if os.name != "nt":
            raise SystemExit("REFUSED: this launcher is Windows-only")
        holder = read_json(global_holder_path())
        if holder and process_start_ms(holder.get("pid")) is not None:
            raise SystemExit("REFUSED: a tracked engine process is already running; no restart is attempted")
        if not Path(spec["testnet_state_root"]).is_dir():
            raise SystemExit("REFUSED: TESTNET state root is unavailable; cannot count other runs")
        service_path = state_dir / "live_service_state.json"
        current = read_json(service_path)
        current_pid = current.get("process_id")
        current_started = current.get("started_at_ms")
        if isinstance(current_pid, int) and isinstance(current_started, int):
            actual = process_start_ms(current_pid)
            if actual is not None and abs(actual - current_started) <= 2000:
                raise SystemExit("REFUSED: the configured state directory already has a live Core; no restart is attempted")
        if service_path.exists():
            shutdown = read_json(state_dir / "core_shutdown_record.json")
            if (shutdown.get("clean") is not True or shutdown.get("process_id") != current_pid
                    or shutdown.get("started_at_ms") != current_started):
                raise SystemExit("REFUSED: existing Core state has no matching clean shutdown record")
        elif state_dir.exists() and any(state_dir.iterdir()):
            raise SystemExit("REFUSED: existing state directory has no Core identity record; preserve it for review")
        others = other_live_runs(spec, state_dir)
        if others:
            summary = ",".join(f"{row['run']}:{row['pid']}" for row in others)
            raise SystemExit("REFUSED: another TESTNET Core is live: " + summary)
        if state_dir.exists() and not (state_dir / "core_shutdown_record.json").exists():
            raise SystemExit("REFUSED: existing state lacks a shutdown record; preserve it for review")
        if port_open(spec["ui_port"]):
            raise SystemExit("REFUSED: /api/state already responds; refusing to start a second UI or serve another run")
        state_dir.mkdir(parents=True, exist_ok=True)
        os.environ.update({"HL_LIVE_AUDIT_DIR": str(state_dir), "HL_FOLLOWER_NETWORK": "testnet",
                           "HL_LIVE_WS_ENABLED": "1", "HL_BUILD_SHA": sha,
                           "HL_APP_PORT": str(spec["ui_port"])})
        core = subprocess.Popen([sys.executable, str(ROOT / spec["core_script"]), *spec["core_args"]],
                                cwd=str((ROOT / spec["core_script"]).parent))
        print(f"CORE_STARTED pid={core.pid} build_sha={sha} follower=testnet state_dir={state_dir}")
        try:
            deadline = time.monotonic() + spec["state_max_age_seconds"]
            while time.monotonic() < deadline:
                errors, detail = collect_core_only(spec, state_dir, sha, core.pid)
                if not errors:
                    break
                if core.poll() is not None:
                    raise RuntimeError("Core exited before identity state became fresh: " + ",".join(errors))
                time.sleep(1)
            else:
                raise RuntimeError("Core state did not verify within 30 seconds")
            ui = subprocess.Popen([sys.executable, str(ROOT / spec["ui_script"])], cwd=str((ROOT / spec["ui_script"]).parent),
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            print(f"UI_STARTED pid={ui.pid} url={spec['ui_base_url']}")
            deadline = time.monotonic() + spec["state_max_age_seconds"]
            while time.monotonic() < deadline:
                errors, detail = collect(spec, state_dir, sha)
                if not errors:
                    break
                if ui.poll() is not None:
                    break
                time.sleep(1)
            if errors:
                post_alert(spec, state_dir, errors, detail)
                print("UI_NOT_VERIFIED: alert posted if available; no automatic restart")
            while core.poll() is None:
                time.sleep(60)
                errors, detail = collect(spec, state_dir, sha)
                post_alert(spec, state_dir, errors, detail)
            print(f"CORE_EXITED code={core.returncode}; no automatic restart")
            errors, detail = collect(spec, state_dir, sha)
            post_alert(spec, state_dir, errors or ["CORE_EXITED"], detail)
            return core.returncode or 0
        except KeyboardInterrupt:
            print("STOP_REQUESTED: Ctrl+C delivered to the foreground TESTNET launcher/Core; no force-kill")
            try:
                core.wait(timeout=15)
            except subprocess.TimeoutExpired:
                print("STOP_NOT_CONFIRMED: Core remains running; do not terminate it forcibly")
                return 2
            return 0
        finally:
            if "ui" in locals() and ui.poll() is None:
                ui.terminate()
                try:
                    ui.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
    return 0


def collect_core_only(spec: dict, state_dir: Path, sha: str, expected_pid: int) -> tuple[list[str], dict]:
    service_path = state_dir / "live_service_state.json"
    runtime_path = state_dir / "clean_core_runtime_state.json"
    service = read_json(service_path)
    runtime = read_json(runtime_path)
    age_ms = int(spec["state_max_age_seconds"] * 1000)
    now = utc_ms()
    errors = evaluate_core(service, runtime, expected_pid, sha, norm_path(state_dir), now, age_ms,
                           process_start_ms(expected_pid))
    for path, reason in ((service_path, "CORE_STATE_FILE_MISSING"),
                         (runtime_path, "CORE_RUNTIME_STATE_FILE_MISSING")):
        try:
            if now - int(path.stat().st_mtime * 1000) > age_ms:
                errors.append(reason.replace("MISSING", "FILE_MTIME_STALE"))
        except OSError:
            errors.append(reason)
    return errors, {"pid": service.get("process_id"), "build_sha": service.get("build_sha")}


def evaluate_core(service: dict, runtime: dict, pid: int, sha: str, state_dir: str,
                  now_ms: int, max_age_ms: int, actual_pid_start_ms: int | None) -> list[str]:
    errors = []
    started = service.get("started_at_ms")
    if service.get("process_id") != pid or runtime.get("process_id") != pid:
        errors.append("CORE_PID_MISMATCH")
    if not isinstance(started, int) or runtime.get("started_at_ms") != started:
        errors.append("CORE_START_MISMATCH")
    if actual_pid_start_ms is None or not isinstance(started, int) or abs(actual_pid_start_ms - started) > 2000:
        errors.append("CORE_PID_NOT_VERIFIED")
    state_ms = service.get("last_state_write_ms") or service.get("created_at_ms")
    if not isinstance(state_ms, int) or now_ms - state_ms > max_age_ms:
        errors.append("CORE_STATE_STALE")
    if service.get("build_sha") != sha:
        errors.append("CORE_BUILD_SHA_MISMATCH")
    networks = service.get("networks") if isinstance(service.get("networks"), dict) else {}
    if networks.get("follower") != "testnet":
        errors.append("FOLLOWER_NOT_TESTNET")
    if norm_path(service.get("config_path", "")).casefold() != (state_dir + os.sep + "live_config.json").casefold():
        errors.append("CORE_STATE_DIR_MISMATCH")
    holder = read_json(global_holder_path())
    if holder.get("pid") != pid or norm_path(holder.get("state_dir")) != state_dir:
        errors.append("GLOBAL_ENGINE_HOLDER_MISMATCH")
    if other_live_runs(spec, Path(state_dir)):
        errors.append("MULTIPLE_CORE_ENGINES")
    return errors


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
        print("STARTUP_REFUSED: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
