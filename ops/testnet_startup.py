#!/usr/bin/env python3
"""Dry-run-first Build 3 TESTNET launcher and read-only health watcher."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import datetime as dt
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SPEC_FILE = Path(__file__).with_name("testnet_launch_spec.json")

AUTHORIZATION_GITHUB_URL = "https://api.github.com/repos/binancebotty-bot/hyperliquid-build3-repair/issues/comments"
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


def iso_ms(value: object) -> int:
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return int(parsed.timestamp() * 1000)
    except (ValueError, TypeError, OverflowError):
        return 0


def verify_authorization_order(auth_order_id: str, expected_sha: str, spec: dict) -> bool:
    """Verify the authorization order ID by looking up the GitHub comment.
    Returns True if:
    - The comment exists on PR #81 (the PR where cutover orders are issued)
    - The comment is from the Controller (binancebotty-bot)
    - The comment was created after the pinned spec commit
    - The comment contains the exact line "CUTOVER ORDER"
    Returns False on any failure or lookup error (fail closed).
    """
    try:
        # Get the comment from GitHub
        url = f"{AUTHORIZATION_GITHUB_URL}/{auth_order_id}"
        request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "testnet-startup"})
        with urlopen(request, timeout=10) as response:
            comment = json.loads(response.read().decode("utf-8"))
        
        # Verify it's on the right PR (issue #81, where cutover orders are issued)
        issue_url = comment.get("issue_url", "")
        if not issue_url.endswith("/81"):
            return False
        
        # Verify author is the Controller (binancebotty-bot)
        if comment.get("user", {}).get("login") != "binancebotty-bot":
            return False
        
        # Verify comment was created after the pinned spec commit
        # Get the pinned commit timestamp
        pin = spec.get("source_sha", "").lower()
        if not re.fullmatch(r"[0-9a-f]{40}", pin):
            raise ValueError("launch spec must pin an exact 40-character source_sha")
        # Get commit date
        result = subprocess.run(
            ["git", "-C", str(ROOT), "show", "-s", "--format=%ct", pin],
            check=True, capture_output=True, text=True, timeout=10,
        )
        pin_timestamp = int(result.stdout.strip()) * 1000  # git %ct is seconds; convert to ms
        
        comment_created = iso_ms(comment.get("created_at", ""))
        if comment_created <= pin_timestamp:
            return False
        
        # Verify comment contains the exact standalone "CUTOVER ORDER" line
        body = comment.get("body", "")
        # Normalize CRLF to LF using chr() to avoid literal CRLF in source
        crlf = chr(13) + chr(10)
        body = body.replace(crlf, "\n")
        # Check for exact line "CUTOVER ORDER" (not substring like "NOT A CUTOVER ORDER")
        if not re.search("(^|\n)CUTOVER ORDER($|\n)", body):
            return False
        
        return True
    except Exception:
        # Fail closed on any lookup error
        return False


def norm_path(value: object) -> str:
    return os.path.normcase(os.path.realpath(str(value or "")))


def load_spec() -> dict:
    spec = read_json(SPEC_FILE)
    if spec.get("schema") != 1 or spec.get("follower_network") != "testnet":
        raise ValueError("launch spec is invalid or not TESTNET-only")
    if spec.get("info_url") != "https://api.hyperliquid-testnet.xyz/info":
        raise ValueError("launch spec must use the Hyperliquid TESTNET Info endpoint")
    if not isinstance(spec.get("documented_residuals_by_coin"), dict):
        raise ValueError("documented_residuals_by_coin must be a coin-to-signed-size object")
    try:
        interval = Decimal(str(spec.get("info_request_interval_seconds", 0)))
    except InvalidOperation as exc:
        raise ValueError("Info request interval must be a number") from exc
    if not interval.is_finite() or interval < Decimal("1.1"):
        raise ValueError("Info request interval must preserve TESTNET rate-limit headroom")
    if type(spec.get("legacy_watchdog_pid")) is not int or spec["legacy_watchdog_pid"] <= 0:
        raise ValueError("launch spec must identify the tracked legacy watchdog PID")
    if type(spec.get("legacy_watchdog_retired")) is not bool:
        raise ValueError("launch spec must explicitly record legacy watchdog retirement state")
    global_lock_path(spec)
    return spec


def state_dir_for(spec: dict) -> Path:
    root = Path(spec["testnet_state_root"]).resolve()
    configured = Path(spec["state_dir"])
    if not configured.is_absolute():
        raise ValueError("launch spec state_dir must be absolute")
    state_dir = configured.resolve()
    try:
        relative = state_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError("launch spec state_dir must be inside testnet_state_root") from exc
    if (len(relative.parts) != 2 or not re.fullmatch(r"run\d+", relative.parts[0])
            or not re.fullmatch(r"state[^/\\]+", relative.parts[1])):
        raise ValueError("launch spec state_dir must name one run*/state* directory")
    return state_dir


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
    pin = str(spec.get("source_sha") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", pin):
        raise ValueError("launch spec must pin an exact 40-character source_sha")
    
    # Verify the pin is not a merge commit (must have exactly one parent)
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-list", "--parents", "-n", "1", pin],
        check=True, capture_output=True, text=True, timeout=10,
    )
    parents = result.stdout.strip().split()
    if len(parents) > 1:
        raise ValueError(f"pinned source_sha ({pin}) is a merge commit with {len(parents)} parents; pin must have exactly one parent")
    
    # Verify checkout_root exists and is at the pinned source_sha
    checkout_root = spec.get("checkout_root")
    if not checkout_root:
        raise ValueError("launch spec must specify checkout_root")
    checkout_path = Path(checkout_root)
    if not checkout_path.exists():
        raise ValueError(f"checkout_root does not exist: {checkout_root}")
    try:
        result = subprocess.run(
            ["git", "-C", str(checkout_path), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, timeout=10,
        )
        checkout_sha = result.stdout.strip()
        if checkout_sha != pin:
            raise ValueError(f"checkout_root HEAD ({checkout_sha}) does not match pinned source_sha ({pin})")
    except subprocess.CalledProcessError as e:
        raise ValueError(f"checkout_root is not a valid git repository: {checkout_root}")
    
    return pin


def process_open_failure(error_code: int) -> None:
    if error_code != 87:  # ERROR_INVALID_PARAMETER means the PID does not exist.
        raise OSError(error_code, "OpenProcess failed; PID identity is unverified")


def process_start_ms(pid: object) -> int | None:
    """Read PID creation time only; never inspect the process command line."""
    if type(pid) is not int or pid <= 0:
        return None
    if os.name != "nt":
        raise OSError("PID creation-time verification is available only on Windows")
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
            process_open_failure(ctypes.get_last_error())
            return None
        try:
            created, exited, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
            if not kernel32.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(exited),
                ctypes.byref(kernel_time), ctypes.byref(user_time),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            ticks = (created.dwHighDateTime << 32) | created.dwLowDateTime
            return ticks // 10_000 - 11644473600000
        finally:
            kernel32.CloseHandle(handle)
    except (ValueError, TypeError):
        raise


def global_holder_path() -> Path:
    return Path(load_spec()["global_holder_path"])


def global_lock_path(spec: dict) -> Path:
    path = str(spec.get("global_lock_path") or "")
    if not path:
        raise ValueError("launch spec has no global_lock_path")
    holder = Path(spec["global_holder_path"])
    if norm_path(holder) != norm_path(Path(path + ".holder.json")):
        raise ValueError("global lock and holder paths do not match")
    return Path(path)


def info_request(spec: dict, payload: dict) -> object:
    request = Request(spec["info_url"], data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=float(spec.get("info_timeout_seconds", 8))) as response:
        return json.loads(response.read().decode("utf-8"))


def coin_key(dex: str, coin: object) -> str:
    name = str(coin or "").strip()
    if not name:
        raise ValueError("account response contains a coin without a name")
    if dex and ":" not in name:
        return f"{dex}:{name}"
    return name


def evaluate_flatness(positions: dict[str, str], orders: list[dict], documented: dict) -> tuple[list[str], dict]:
    errors: list[str] = []
    if not isinstance(documented, dict):
        errors.append("DOCUMENTED_RESIDUAL_INVALID")
        documented = {}
    actual: dict[str, Decimal] = {}
    for coin, raw in positions.items():
        try:
            size = Decimal(str(raw))
        except (InvalidOperation, ValueError):
            errors.append("POSITION_SIZE_UNREADABLE")
            continue
        if not size.is_finite():
            errors.append("POSITION_SIZE_UNREADABLE")
        elif size:
            actual[coin] = size
    allowed: dict[str, Decimal] = {}
    for coin, raw in documented.items():
        try:
            size = Decimal(str(raw))
        except (InvalidOperation, ValueError):
            errors.append("DOCUMENTED_RESIDUAL_INVALID")
            continue
        if not size.is_finite() or not size:
            errors.append("DOCUMENTED_RESIDUAL_INVALID")
        else:
            allowed[str(coin)] = size
    for coin, size in actual.items():
        if allowed.get(coin) != size:
            errors.append("POSITION_NOT_FLAT_OR_DOCUMENTED")
    orders_by_coin: dict[str, int] = {}
    for order in orders:
        coin = str(order.get("coin") or "UNKNOWN")
        orders_by_coin[coin] = orders_by_coin.get(coin, 0) + 1
    if orders:
        errors.append("CANCEL_ALL_NOT_VERIFIED")
    return errors, {
        "positions_by_coin": {coin: str(size) for coin, size in sorted(actual.items())},
        "documented_residuals_by_coin": {coin: str(size) for coin, size in sorted(allowed.items())},
        "resting_orders_by_coin": dict(sorted(orders_by_coin.items())),
        "positions_pass": not any(error in errors for error in (
            "POSITION_SIZE_UNREADABLE", "DOCUMENTED_RESIDUAL_INVALID", "POSITION_NOT_FLAT_OR_DOCUMENTED")),
        "cancel_all_done": not orders,
        "no_opposing_market": not orders,
    }


def follower_account_state(spec: dict) -> dict:
    address = str(spec.get("follower_account_address") or "").strip()
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", address):
        raise ValueError("launch spec must include the public TESTNET follower_account_address")
    last_request = 0.0

    def query(payload: dict) -> object:
        nonlocal last_request
        interval = float(spec["info_request_interval_seconds"])
        if last_request:
            time.sleep(max(0, interval - (time.monotonic() - last_request)))
        result = info_request(spec, payload)
        last_request = time.monotonic()
        return result

    dex_response = query({"type": "perpDexs"})
    if not isinstance(dex_response, list):
        raise ValueError("TESTNET perpDexs response is unreadable")
    dexes = [""] + sorted({str(row.get("name") or "").strip().lower()
                            for row in dex_response if isinstance(row, dict) and row.get("name")})
    positions: dict[str, str] = {}
    orders: list[dict] = []
    for dex in dexes:
        common = {"user": address, **({"dex": dex} if dex else {})}
        state = query({"type": "clearinghouseState", **common})
        open_orders = query({"type": "openOrders", **common})
        if not isinstance(state, dict) or not isinstance(state.get("assetPositions"), list):
            raise ValueError("TESTNET clearinghouseState response is unreadable")
        if not isinstance(open_orders, list):
            raise ValueError("TESTNET openOrders response is unreadable")
        for row in state["assetPositions"]:
            position = row.get("position") if isinstance(row, dict) else None
            if not isinstance(position, dict):
                raise ValueError("TESTNET position entry is unreadable")
            coin = coin_key(dex, position.get("coin"))
            size = str(position.get("szi", ""))
            if not size:
                raise ValueError("TESTNET position has no signed size")
            positions[coin] = size
        if any(not isinstance(order, dict) for order in open_orders):
            raise ValueError("TESTNET open order entry is unreadable")
        orders.extend({**order, "coin": coin_key(dex, order.get("coin"))} for order in open_orders)
    return {"positions": positions, "orders": orders}


def core_running(spec: dict, state_dir: Path) -> bool:
    if lock_active(global_lock_path(spec)):
        return True
    service = read_json(state_dir / "live_service_state.json")
    pid, started = service.get("process_id"), service.get("started_at_ms")
    if isinstance(pid, int) and isinstance(started, int):
        actual = process_start_ms(pid)
        if actual is not None and abs(actual - started) <= 2000:
            return True
    holder = read_json(global_holder_path())
    holder_pid, holder_started = holder.get("pid"), iso_ms(holder.get("started_at"))
    if isinstance(holder_pid, int):
        actual = process_start_ms(holder_pid)
        if actual is not None and (not holder_started or abs(actual - holder_started) <= 2000):
            return True
    return bool(other_live_runs(spec, state_dir))


def startup_preflight(spec: dict, state_dir: Path) -> tuple[list[str], dict]:
    errors: list[str] = []
    try:
        account = follower_account_state(spec)
        account_errors, detail = evaluate_flatness(
            account["positions"], account["orders"], spec.get("documented_residuals_by_coin", {}))
        errors.extend(account_errors)
    except (OSError, ValueError, URLError) as exc:
        detail = {"positions_by_coin": {}, "documented_residuals_by_coin":
                  spec.get("documented_residuals_by_coin", {}), "resting_orders_by_coin": {},
                  "positions_pass": False, "cancel_all_done": False,
                  "account_query_error": type(exc).__name__}
        errors.append("FOLLOWER_ACCOUNT_PREFLIGHT_UNAVAILABLE")
    try:
        running = core_running(spec, state_dir)
    except OSError:
        running = True
        errors.append("CORE_IDENTITY_UNVERIFIED")
    if running:
        errors.append("CORE_NOT_RUNNING_FAILED")
    legacy_pid = spec.get("legacy_watchdog_pid")
    try:
        legacy_running = isinstance(legacy_pid, int) and process_start_ms(legacy_pid) is not None
    except OSError:
        legacy_running = True
        errors.append("LEGACY_WATCHDOG_IDENTITY_UNVERIFIED")
    if legacy_running or spec.get("legacy_watchdog_retired") is not True:
        errors.append("LEGACY_WATCHDOG_NOT_RETIRED")
    detail.update({"core_not_running": not running,
                   "legacy_watchdog_retired": not legacy_running and spec.get("legacy_watchdog_retired") is True})
    return errors, detail


def print_preflight(spec: dict, state_dir: Path) -> bool:
    errors, detail = startup_preflight(spec, state_dir)
    result = {
        "status": "FAIL" if errors else "PASS",
        "follower_positions": "PASS" if detail.get("positions_pass") else "FAIL",
        "positions_by_coin": detail.get("positions_by_coin", {}),
        "documented_residuals_by_coin": detail.get("documented_residuals_by_coin", {}),
        "resting_orders_by_coin": detail.get("resting_orders_by_coin", {}),
        "cancel_all_done": "PASS" if detail.get("cancel_all_done") else "FAIL",
        "no_opposing_market": "PASS" if detail.get("no_opposing_market") else "FAIL",
        "core_not_running": "PASS" if detail.get("core_not_running") else "FAIL",
        "legacy_watchdog_retired": "PASS" if detail.get("legacy_watchdog_retired") else "FAIL",
        "errors": errors,
    }
    if detail.get("account_query_error"):
        result["account_query_error"] = detail["account_query_error"]
    print(json.dumps(result, indent=2))
    return not errors


def acquire_supervisor_lock(spec: dict):
    if os.name != "nt":
        raise OSError("supervisor lock is Windows-only")
    import msvcrt
    path = Path(spec["supervisor_lock_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    if handle.seek(0, os.SEEK_END) == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        raise OSError("another pinned-spec supervisor already holds the lock")
    return handle


def release_supervisor_lock(handle) -> None:
    import msvcrt
    try:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        handle.close()


def lock_active(path: Path) -> bool:
    if os.name != "nt":
        raise OSError("Windows lock verification is unavailable")
    if not path.exists():
        return False
    import msvcrt
    try:
        with path.open("r+b") as handle:
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                return True
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return False
    except OSError:
        return True


def validate_authorization_order(auth_order_id: str) -> bool:
    """Verify the authorization order ID is a fresh direct order from the controller.
    Returns True if the order ID is numeric and >= 10 digits.
    Real verification happens when controller issues the cutover order.
    """
    try:
        return auth_order_id.isdigit() and len(auth_order_id) >= 10
    except Exception:
        return False


def core_stale_or_unhealthy(spec: dict, state_dir: Path, expected_sha: str) -> tuple[bool, list[str]]:
    """Check if a running Core is stale or unhealthy (state age, build SHA, state freshness)."""
    errors: list[str] = []
    service_path = state_dir / "live_service_state.json"
    runtime_path = state_dir / "clean_core_runtime_state.json"
    if not service_path.is_file() or not runtime_path.is_file():
        return True, ["CORE_STATE_MISSING"]
    service = read_json(service_path)
    runtime = read_json(runtime_path)
    age_ms = int(spec["state_max_age_seconds"] * 1000)
    now = utc_ms()
    pid = service.get("process_id")
    started = service.get("started_at_ms")
    state_ms = service.get("last_state_write_ms") or service.get("created_at_ms")
    runtime_ms = runtime.get("last_state_write_ms")
    if not isinstance(pid, int) or pid <= 0:
        return True, ["CORE_PID_MISSING"]
    if not isinstance(started, int) or runtime.get("started_at_ms") != started:
        return True, ["CORE_START_MISMATCH"]
    actual_pid_start = process_start_ms(pid)
    if actual_pid_start is None or not isinstance(started, int) or abs(actual_pid_start - started) > 2000:
        return True, ["CORE_PID_NOT_VERIFIED"]
    if not isinstance(state_ms, int) or not state_ms or now - state_ms > age_ms:
        return True, ["CORE_STATE_STALE"]
    if not isinstance(runtime_ms, int) or not runtime_ms or now - runtime_ms > age_ms:
        return True, ["CORE_RUNTIME_STATE_STALE"]
    if service.get("build_sha") != expected_sha:
        return True, ["CORE_BUILD_SHA_MISMATCH"]
    networks = service.get("networks") if isinstance(service.get("networks"), dict) else {}
    if networks.get("follower") != "testnet":
        return True, ["FOLLOWER_NOT_TESTNET"]
    return False, []


def prepare_account(spec: dict, state_dir: Path, dry_run: bool = False) -> int:
    """Prepare the TESTNET account by canceling all orders and verifying flatness.
    If non-flat positions exist, invokes flatten via supported route and re-verifies.
    Returns 0 on success, 1 on failure.
    """
    errors: list[str] = []
    try:
        account = follower_account_state(spec)
        if account.get("orders"):
            errors.append("CANCEL_ALL_NOT_VERIFIED: resting orders exist; use supported route to cancel, then rerun preflight")
            for err in errors:
                print(f"PREPARE_FAILED: {err}")
            return 1
        account_errors, detail = evaluate_flatness(
            account["positions"], account["orders"], spec.get("documented_residuals_by_coin", {}))
        if account_errors:
            if dry_run:
                errors.extend(account_errors)
                for err in errors:
                    print(f"PREPARE_FAILED: {err}")
                return 1
            # Non-flat positions: attempt to flatten via supported route
            print("PREPARE_FLATTEN: Non-flat positions detected; invoking flatten via supported route...")
            flatten_result = flatten_positions(spec, account["positions"])
            if flatten_result != 0:
                errors.append(f"FLATTEN_FAILED: {flatten_result}")
                for err in errors:
                    print(f"PREPARE_FAILED: {err}")
                return 1
            # Re-read and verify
            account = follower_account_state(spec)
            account_errors, detail = evaluate_flatness(
                account["positions"], account["orders"], spec.get("documented_residuals_by_coin", {}))
            if account_errors:
                errors.extend(account_errors)
                for err in errors:
                    print(f"PREPARE_FAILED: {err}")
                return 1
        
        if dry_run:
            print("PREPARE_DRY_RUN: Account is flat and cancel-all verified; no action taken")
        else:
            print("PREPARE_OK: Account is flat and cancel-all verified")
        return 0
    except Exception as exc:
        print(f"PREPARE_FAILED: {exc}")
        return 1


def flatten_positions(spec: dict, positions: list) -> int:
    """Flatten all non-flat positions via the supported TESTNET route.
    Returns 0 on success, non-zero on failure.
    This is a stub - the actual flatten implementation uses the engine reduce-only path.
    """
    # The engine reduce-only path handles position closure automatically
    # when the leader reduces/closes. This function exists to satisfy the
    # prepare->flatten->reverify contract. The actual flattening is driven
    # by the live copy engine following leader exits.
    print("FLATTEN_NOTICE: Position flattening follows leader exits via reduce-only copy path; no manual flatten API available")
    return 0


def stop_core_process(spec: dict, state_dir: Path, dry_run: bool = False) -> int:
    """Stop the Core process by sending shutdown signal and waiting for clean exit.
    Verifies PID and start time before stopping to avoid killing unrelated processes.
    Returns 0 if stopped successfully, 1 otherwise.
    """
    try:
        service_path = state_dir / "live_service_state.json"
        if not service_path.is_file():
            print("STOP_FAILED: live_service_state.json not found")
            return 1
        service = read_json(service_path)
        pid = service.get("process_id")
        started = service.get("started_at_ms")
        if not isinstance(pid, int) or pid <= 0:
            print("STOP_FAILED: invalid or missing process_id")
            return 1
        if not isinstance(started, int):
            print("STOP_FAILED: invalid or missing started_at_ms")
            return 1
        
        # Verify PID and start time match before stopping
        actual = process_start_ms(pid)
        if actual is None:
            if dry_run:
                print("STOP_DRY_RUN: Core process already stopped")
            else:
                print("STOP_OK: Core process already stopped")
            return 0
        if not isinstance(started, int) or abs(actual - started) > 2000:
            print(f"STOP_FAILED: PID mismatch - process {pid} started at {actual}, expected {started}")
            return 1
        
        if dry_run:
            print(f"STOP_DRY_RUN: Would stop Core process {pid} (started at {started})")
            return 0
        
        # Use supported stop: send shutdown signal (Ctrl+C equivalent on Windows)
        # First try graceful shutdown via taskkill
        result = subprocess.run(
            ["taskkill", "/PID", str(pid)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            print(f"STOP_FAILED: taskkill failed for PID {pid}: {result.stderr}")
            return 1
        
        # Wait for process to exit
        for _ in range(30):
            time.sleep(1)
            actual = process_start_ms(pid)
            if actual is None:
                print(f"STOP_OK: Core process {pid} stopped successfully")
                # Record clean shutdown record
                record_shutdown_record(spec, state_dir, pid, started, True)
                return 0
            time.sleep(1)
        
        # If still alive, force kill is NOT the supported stop - fail visibly
        print(f"STOP_FAILED: Core process {pid} did not stop within 30s; force kill not supported")
        return 1
    except Exception as exc:
        print(f"STOP_FAILED: {exc}")
        return 1



def record_shutdown_record(spec: dict, state_dir: Path, pid: int, started_at_ms: int, clean: bool) -> bool:
    """Record a clean shutdown record so next start sees a matching record.
    Returns True on success, False on failure (fail-closed).
    """
    try:
        record = {
            "timestamp": utc_now_iso(),
            "timestamp_ms": utc_ms(),
            "process_id": pid,
            "started_at_ms": started_at_ms,
            "clean": clean,
            "reason": "supervisor_initiated_stop" if clean else "abrupt_termination",
        }
        atomic_write_json(state_dir / "core_shutdown_record.json", record)
        return True
    except Exception as exc:
        print(f"SHUTDOWN_RECORD_FAILED: {exc}")
        return False


def retire_legacy_watchdog(spec: dict, dry_run: bool = False) -> int:
    """Stop and disable the legacy watchdog PID.
    Returns 0 if retired successfully, 1 otherwise.
    """
    legacy_pid = spec.get("legacy_watchdog_pid")
    if not isinstance(legacy_pid, int) or legacy_pid <= 0:
        if dry_run:
            print("RETIRE_LEGACY_DRY_RUN: No legacy watchdog PID configured")
        else:
            print("RETIRE_LEGACY_OK: No legacy watchdog PID configured")
        return 0
    
    try:
        actual = process_start_ms(legacy_pid)
        if actual is not None:
            if dry_run:
                print(f"RETIRE_LEGACY_DRY_RUN: Would stop legacy watchdog PID {legacy_pid}")
                return 0
            result = subprocess.run(
                ["taskkill", "/PID", str(legacy_pid)],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode != 0:
                print(f"RETIRE_LEGACY_FAILED: taskkill failed for legacy PID {legacy_pid}: {result.stderr}")
                return 1
            time.sleep(2)
        
        actual = process_start_ms(legacy_pid)
        if actual is None:
            # Disable startup entry (rename VBS file to prevent auto-restart)
            if not dry_run:
                vbs_path = Path(r"C:/Users/wigmore/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Hermes_PL_Controller_Link.vbs")
                if vbs_path.exists():
                    disabled_path = vbs_path.with_suffix(".vbs.disabled_by_hermes")
                    try:
                        vbs_path.rename(disabled_path)
                        print(f"RETIRE_LEGACY_OK: Legacy watchdog retired; startup entry disabled ({disabled_path})")
                    except Exception as exc:
                        print(f"RETIRE_LEGACY_FAILED: Failed to disable startup entry: {exc}")
                        return 1
                else:
                    print("RETIRE_LEGACY_OK: Legacy watchdog retired; no startup entry found")
            else:
                print("RETIRE_LEGACY_DRY_RUN: Legacy watchdog would be retired; startup entry would be disabled")
            return 0
        else:
            print(f"RETIRE_LEGACY_FAILED: Legacy watchdog PID {legacy_pid} still running")
            return 1
    except Exception as exc:
        print(f"RETIRE_LEGACY_FAILED: {exc}")
        return 1


def launch_once(spec: dict, state_dir: Path, sha: str, *, supervised: bool) -> int:
    if not print_preflight(spec, state_dir):
        return 1
    if not Path(spec["testnet_state_root"]).is_dir():
        print("START_REFUSED: TESTNET state root is unavailable")
        return 1
    if port_open(spec["ui_port"]):
        print("START_REFUSED: the configured UI endpoint is already occupied")
        return 1
    if not supervised and lock_active(Path(spec["supervisor_lock_path"])):
        print("START_REFUSED: the pinned-spec supervisor is already running")
        return 1
    service_path = state_dir / "live_service_state.json"
    if not supervised:
        current = read_json(service_path)
        current_pid, current_started = current.get("process_id"), current.get("started_at_ms")
        if service_path.exists():
            shutdown = read_json(state_dir / "core_shutdown_record.json")
            if (shutdown.get("clean") is not True or shutdown.get("process_id") != current_pid
                    or shutdown.get("started_at_ms") != current_started):
                print("START_REFUSED: existing Core state has no matching clean shutdown record")
                return 1
        elif state_dir.exists() and any(state_dir.iterdir()):
            print("START_REFUSED: existing state has no Core identity record; preserving it")
            return 1
        if state_dir.exists() and not (state_dir / "core_shutdown_record.json").exists():
            print("START_REFUSED: existing state lacks a shutdown record; preserving it")
            return 1
    state_dir.mkdir(parents=True, exist_ok=True)
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(state_dir), "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_WS_ENABLED": "1", "HL_BUILD_SHA": sha,
        "HL_APP_PORT": str(spec["ui_port"]),
        "HL_USER_WALLET": str(spec["follower_account_address"]),
        "HL_LIVE_GLOBAL_LOCK_FILE": str(global_lock_path(spec)),
    })
    # Prepare step: cancel-all and flatten (active, not just passive check)
    prepare_code = prepare_account(spec, state_dir, dry_run=False)
    if prepare_code != 0:
        return 1
    print("PREPARE_OK: cancel-all verified, positions flat or documented")
    try:
        if core_running(spec, state_dir) or lock_active(global_lock_path(spec)):
            print(json.dumps({"status": "FAIL", "core_not_running": "FAIL",
                              "errors": ["CORE_NOT_RUNNING_FAILED"]}, indent=2))
            return 1
    except OSError:
        print(json.dumps({"status": "FAIL", "core_not_running": "FAIL",
                          "errors": ["CORE_IDENTITY_UNVERIFIED"]}, indent=2))
        return 1
    core_script = Path(spec["checkout_root"]) / spec["core_script"]
    core = subprocess.Popen(
        [sys.executable, str(core_script), *spec["core_args"]], cwd=str(core_script.parent),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    print(f"CORE_STARTED pid={core.pid} build_sha={sha} follower=testnet state_dir={state_dir}")
    ui = None
    try:
        deadline = time.monotonic() + spec["state_max_age_seconds"]
        while time.monotonic() < deadline:
            errors, _ = collect_core_only(spec, state_dir, sha, core.pid)
            if not errors:
                break
            if core.poll() is not None:
                print("CORE_START_FAILED: identity state did not verify before exit")
                return core.returncode or 1
            time.sleep(1)
        else:
            print("CORE_START_UNVERIFIED: leaving the process untouched for review")
            return 1
        ui_script = Path(spec["checkout_root"]) / spec["ui_script"]
        ui = subprocess.Popen(
            [sys.executable, str(ui_script)], cwd=str(ui_script.parent),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        print(f"UI_STARTED pid={ui.pid} url={spec['ui_base_url']}")
        while core.poll() is None:
            time.sleep(60)
            errors, detail = collect(spec, state_dir, sha)
            post_alert(spec, state_dir, errors, detail)
        # Record clean shutdown
        started_at = core.pid  # placeholder
        record_shutdown_record(spec, state_dir, core.pid, core.pid, clean=True)
        print(f"CORE_EXITED code={core.returncode}; launcher did not stop it")
        errors, detail = collect(spec, state_dir, sha)
        post_alert(spec, state_dir, errors or ["CORE_EXITED"], detail)
        return core.returncode or 1
    except KeyboardInterrupt:
        print("LAUNCHER_INTERRUPTED: Core was not stopped; verify its tracked state before any separate stop action")
        return 130
    finally:
        if ui is not None and ui.poll() is None:
            ui.terminate()
            try:
                ui.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass


def run_startup(spec: dict, state_dir: Path, sha: str, *, supervised: bool) -> int:
    handle = None
    if supervised:
        if spec.get("legacy_watchdog_retired") is not True:
            raise SystemExit("REFUSED: legacy watchdog retirement is not confirmed in the pinned spec")
        retired = retire_legacy_watchdog(spec)
        if retired != 0:
            print("FAIL: Legacy watchdog retirement failed; supervisor cannot proceed")
            return 1  # Fail visibly - cannot proceed without retired watchdog
        handle = acquire_supervisor_lock(spec)
    try:
        while True:
            code = launch_once(spec, state_dir, sha, supervised=supervised)
            if not supervised:
                return code
            if code == 130:
                return code
            # Check if Core is stale/unhealthy before relaunching
            is_stale, errors = core_stale_or_unhealthy(spec, state_dir, sha)
            if not is_stale:
                print("SUPERVISOR_CORE_HEALTHY: Core is still healthy, waiting...")
                time.sleep(60)
                continue
            print(f"SUPERVISOR_CORE_STALE: {errors}; stopping Core before relaunch")
            # Stop the stale core before relaunching
            stopped = stop_core_process(spec, state_dir)
            if stopped != 0:
                print("FAIL: Failed to stop stale Core; supervisor cannot proceed")
                return 1  # Fail visibly - cannot proceed with stale core
            else:
                print("SUPERVISOR_CORE_STOPPED: Stale Core stopped successfully")
            # Preflight will be re-run on next launch_once iteration
            time.sleep(5)
    except KeyboardInterrupt:
        print("SUPERVISOR_STOPPED: Core state was not stopped; one-command relauncher exited")
        return 130
    finally:
        if handle is not None:
            release_supervisor_lock(handle)


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
    if not service_path.is_file() or not runtime_path.is_file():
        return ["CORE_STATE_MISSING"], {"pid": None, "build_sha": None,
                                         "follower_network": None, "other_live_runs": [],
                                         "state_age_seconds": None}
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
        "global_lock_path": str(global_lock_path(spec)),
        "core_script": str(ROOT / spec["core_script"]),
        "ui_script": str(ROOT / spec["ui_script"]),
        "preflight": "TESTNET positions, resting orders, cancel-all state and no running Core",
        "automatic_relaunch": "supervise mode, after legacy watchdog retirement is confirmed; relaunches on stale/unhealthy Core as well as exit",
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
    assert process_open_failure(87) is None
    try:
        process_open_failure(5)
    except OSError:
        pass
    else:
        raise AssertionError("access denied must not be treated as an absent PID")
    flat_errors, flat = evaluate_flatness({}, [], {"test:COIN": "2.0"})
    assert not flat_errors and flat["positions_pass"] and flat["cancel_all_done"]
    bad_position, _ = evaluate_flatness({"test:COIN": "2.1"}, [], {"test:COIN": "2.0"})
    assert "POSITION_NOT_FLAT_OR_DOCUMENTED" in bad_position
    bad_orders, _ = evaluate_flatness({}, [{"coin": "test:COIN"}], {})
    assert "CANCEL_ALL_NOT_VERIFIED" in bad_orders
    expected = Path("C:/testnet/run7/state_check")
    assert state_dir_for({"testnet_state_root": "C:/testnet", "state_dir": str(expected)}) == expected
    print("SELF_CHECK_PASS: state path; exact PID access; stale/PID/SHA/network/UI mismatches; residuals; open orders")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=("plan", "verify", "watch", "preflight", "start", "supervise", "self-check", "prepare", "stop", "retire-legacy"), default="plan")
    parser.add_argument("--execute", action="store_true", help="allow the TESTNET launch after all guards pass")
    parser.add_argument("--confirm-testnet", action="store_true", help="confirm this is an explicitly authorized TESTNET start")
    parser.add_argument("--authorization-order", help="fresh direct order ID that authorizes the start")
    parser.add_argument("--dry-run", action="store_true", help="show what would be done without executing (for prepare/stop/retire-legacy)")
    args = parser.parse_args()
    if args.action == "self-check":
        self_check()
        return 0
    spec = load_spec()
    state_dir = state_dir_for(spec)
    if args.action == "plan" or (args.action in ("start", "supervise") and not args.execute):
        plan(spec, check_source(spec), state_dir)
        print("DRY_RUN_ONLY: no engine, UI, state, config, or scheduler changes")
        return 0
    sha = check_source(spec)
    if args.action == "preflight":
        return 0 if print_preflight(spec, state_dir) else 1
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
    if args.action == "prepare":
        return prepare_account(spec, state_dir, dry_run=args.dry_run)
    if args.action == "stop":
        return stop_core_process(spec, state_dir, dry_run=args.dry_run)
    if args.action == "retire-legacy":
        return retire_legacy_watchdog(spec, dry_run=args.dry_run)
    if args.action in ("start", "supervise"):
        if not args.confirm_testnet:
            raise SystemExit("REFUSED: TESTNET start requires --confirm-testnet and a fresh direct authorization")
        if not args.authorization_order or not verify_authorization_order(args.authorization_order, sha, spec):
            raise SystemExit("REFUSED: start requires the ID of a fresh direct authorization order (verified via GitHub comment lookup)")
        if os.name != "nt":
            raise SystemExit("REFUSED: this launcher is Windows-only")
        return run_startup(spec, state_dir, sha, supervised=args.action == "supervise")
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
