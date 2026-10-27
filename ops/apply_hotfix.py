#!/usr/bin/env python3
"""Swap the running Core/UI pair to another clean Build 3 checkout on the same state.

This tool preserves state and the launch environment. It never seeds, clears, or reclaims a
state directory. It is deliberately fail-closed when the pair identity or proof inputs are
ambiguous. Use --dry-run to run every pre-stop check without writing or stopping anything.
"""
from __future__ import annotations

import argparse
import csv
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OPS = Path(__file__).resolve().parent
sys.path.insert(0, str(OPS))
import stop_pair as SP  # reuse the existing graceful stop, pid, listener, and UI identity checks

TARGET = "HL_Live_Copy_Service_Core.py"
UI_MODULE = "HL_Copy_App_SSOT:app"
LAUNCH_ENV = Path.home() / ".hermes" / "state" / "core_launch_env.json"
LAST_SWAP = Path.home() / ".hermes" / "state" / "apply_hotfix_last.json"
MAX_GAP_MS = 20_000
REPLAY_TIMEOUT_S = 30 * 60
POLL_S = 1.0
REPLAY_WATCH_S = 30.0  # observe the new pair after the first healthy cycle


class HotfixError(RuntimeError):
    pass


def refuse(message: str) -> int:
    print("BLOCKED: " + message, file=sys.stderr)
    return 1


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise HotfixError("cannot read required JSON file " + path.name) from exc
    if not isinstance(value, dict):
        raise HotfixError(path.name + " must contain a JSON object")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None,
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise HotfixError("git check failed: " + args[0])
    return result.stdout.strip()


def checkout_info(path: Path, require_clean: bool = True) -> tuple[Path, str]:
    root = Path(git(["-C", str(path), "rev-parse", "--show-toplevel"])).resolve()
    sha = git(["-C", str(root), "rev-parse", "--verify", "HEAD"])
    if len(sha) != 40:
        raise HotfixError("checkout did not resolve to a full commit SHA")
    if require_clean:
        changes = git(["-C", str(root), "status", "--porcelain", "--untracked-files=all"])
        source_changes = [line for line in changes.splitlines()
                          if not line[3:].replace("\\", "/").startswith("graphify-out/")]
        if source_changes:
            raise HotfixError("build checkout has uncommitted source changes")
    return root, sha


def resolve_build(spec: str) -> tuple[Path, str]:
    candidate = Path(spec).expanduser()
    if candidate.is_dir():
        root, sha = checkout_info(candidate)
    else:
        wanted = spec.lower().strip()
        if len(wanted) < 7 or any(c not in "0123456789abcdef" for c in wanted):
            raise HotfixError("supply a checkout path or at least seven SHA characters")
        root_repo = Path(git(["-C", str(OPS.parent), "rev-parse", "--show-toplevel"])).resolve()
        worktrees = git(["-C", str(root_repo), "worktree", "list", "--porcelain"])
        paths: list[Path] = []
        current: Path | None = None
        for line in worktrees.splitlines():
            if line.startswith("worktree "):
                current = Path(line[9:])
            elif line.startswith("HEAD ") and current is not None and line[5:].lower().startswith(wanted):
                paths.append(current)
        if len(paths) != 1:
            raise HotfixError("SHA must resolve to exactly one existing worktree")
        root, sha = checkout_info(paths[0])
        if not sha.startswith(wanted):
            raise HotfixError("worktree SHA changed during resolution")
    engine = root / "_archive" / "hl_stage2" / TARGET
    if not engine.is_file() or not (root / "ops" / "start_pair.py").is_file():
        raise HotfixError("target is not a complete pair checkout")
    return root, sha


def precompile(build: Path) -> None:
    engine_dir = build / "_archive" / "hl_stage2"
    for path in (engine_dir / TARGET, engine_dir / "HL_Copy_App_SSOT.py",
                 build / "ops" / "start_pair.py", build / "ops" / "stop_pair.py"):
        if not path.is_file():
            raise HotfixError("precompile input missing: " + path.name)
        try:
            compile(path.read_bytes(), str(path), "exec")
        except (SyntaxError, UnicodeError) as exc:
            raise HotfixError("precompile failed: " + path.name) from exc


def launch_spec() -> tuple[dict[str, Any], dict[str, str], Path]:
    spec = read_json(LAUNCH_ENV)
    env = spec.get("env")
    if not isinstance(env, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in env.items()):
        raise HotfixError("core_launch_env.json needs an env object of string values")
    if "HL_LIVE_AUDIT_DIR" not in env:
        raise HotfixError("core_launch_env.json is missing the HL_LIVE_AUDIT_DIR key")
    state = Path(env["HL_LIVE_AUDIT_DIR"]).expanduser().resolve()
    if not state.is_dir() or not (state.name.startswith("state_") and state.parent.name.startswith("run")):
        raise HotfixError("launch environment does not identify an existing run/state directory")
    return spec, dict(env), state


def identity_record(state: Path) -> dict[str, Any]:
    for name in ("core_start_record.json", "live_service_state.json"):
        path = state / name
        if path.is_file():
            record = read_json(path)
            if record.get("pid") or record.get("process_id"):
                return record
    raise HotfixError("no current Core identity block exists in the state directory")


def process_build(script: str) -> tuple[Path, str]:
    path = Path(script).resolve()
    if path.name != TARGET or not path.is_file():
        raise HotfixError("Core identity script is missing or has the wrong name")
    return checkout_info(path.parent)


def ui_build(port: int) -> tuple[int, Path, str]:
    listener = SP.listener(port)
    if not listener:
        raise HotfixError("no tracked UI listener exists on the requested port")
    try:
        track = read_json(SP.TRACK)
        if int(track.get("pid") or 0) != int(listener) or int(track.get("port") or 0) != port:
            raise HotfixError("UI listener does not match the saved UI identity")
        import psutil
        process = psutil.Process(int(listener))
        if abs(process.create_time() - float(track.get("create_time") or 0)) > 0.001:
            raise HotfixError("UI pid was reused")
        root, sha = checkout_info(Path(process.cwd()))
    except HotfixError:
        raise
    except Exception as exc:
        raise HotfixError("cannot verify the tracked UI identity") from exc
    return int(listener), root, sha


def pointer_path(state: Path) -> Path:
    return state.parent.parent / "CURRENT_AUDIT_DIR"


def validate_pair(state: Path, port: int) -> tuple[dict[str, Any], Path, str, int]:
    identity = identity_record(state)
    engine_pid = int(identity.get("pid") or identity.get("process_id") or 0)
    script = str(identity.get("script") or "")
    if not engine_pid or not script:
        raise HotfixError("Core identity block must include pid and script")
    old_root, old_sha = process_build(script)
    pids = SP.pids(state)
    if pids != [engine_pid]:
        raise HotfixError("exactly one engine must match the state identity block")
    ui_pid, ui_root, ui_sha = ui_build(port)
    if old_root != ui_root or old_sha != ui_sha:
        raise HotfixError("Core and UI are not on the same build")
    pointer = pointer_path(state)
    if not pointer.is_file() or Path(pointer.read_text(encoding="utf-8-sig").strip()).resolve() != state:
        raise HotfixError("CURRENT_AUDIT_DIR does not name this exact state directory")
    return identity, old_root, old_sha, ui_pid


def without_engine_timestamps(value: Any, scope: str) -> Any:
    if isinstance(value, dict):
        ignored = set()
        if scope == "manual_live_positions.json":
            ignored = {"last_updated_at"}
        elif scope == "xyz_position_state.json":
            ignored = {"updated_at", "updated_at_ms"}
        return {k: without_engine_timestamps(v, scope) for k, v in value.items()
                if k not in ignored}
    if isinstance(value, list):
        return [without_engine_timestamps(item, scope) for item in value]
    return value


def digest_json(path: Path, scope: str) -> str:
    if not path.exists():
        return "ABSENT"
    value = read_json(path)
    normalized = without_engine_timestamps(value, scope)
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def user_owned_digest(config: dict[str, Any]) -> str:
    wallets = config.get("wallets") if isinstance(config.get("wallets"), dict) else {}
    owned = {}
    for name, wallet in wallets.items():
        if not isinstance(wallet, dict):
            continue
        mode = str(wallet.get("mode") or wallet.get("copy_mode") or "").strip().upper().replace("_", "-")
        if mode in {"USER", "USER-OWNED"}:
            owned[str(name)] = wallet
    raw = json.dumps(owned, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def snapshot_state(state: Path) -> dict[str, Any]:
    anchor_path = state / "PAIR_START_ANCHOR.json"
    config_path = state / "live_config.json"
    if not anchor_path.is_file() or not config_path.is_file():
        raise HotfixError("PAIR_START_ANCHOR.json and live_config.json are required")
    anchor_bytes = anchor_path.read_bytes()
    anchor = read_json(anchor_path)
    t0 = int(anchor.get("t0_ms") or 0)
    if t0 <= 0:
        raise HotfixError("PAIR_START_ANCHOR.json has no positive t0_ms")
    config = read_json(config_path)
    return {
        "anchor_sha256": hashlib.sha256(anchor_bytes).hexdigest(),
        "anchor_t0_ms": t0,
        "live_config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "live_config_semantic_sha256": digest_json(config_path, "live_config.json"),
        "manual_live_positions_sha256": digest_json(state / "manual_live_positions.json", "manual_live_positions.json"),
        "xyz_position_state_sha256": digest_json(state / "xyz_position_state.json", "xyz_position_state.json"),
        "user_owned_sha256": user_owned_digest(config),
    }


def reject_symlinks(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise HotfixError("state backup refuses symlinks")


def backup_state(state: Path) -> Path:
    reject_symlinks(state)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    target = state.parent.parent / "hotfix_backups" / (state.parent.name + "_" + stamp)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise HotfixError("unique backup path already exists")
    shutil.copytree(state, target, copy_function=shutil.copy2)
    if not (target / "PAIR_START_ANCHOR.json").is_file():
        raise HotfixError("state backup did not preserve the pair anchor")
    return target


def csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as stream:
        return list(csv.DictReader(stream))


def sent_keys(state: Path) -> set[tuple[str, str]]:
    rows = csv_rows(state / "append_only" / "send_attempts.csv")
    return {(str(r.get("wallet") or r.get("leader_wallet") or "").lower(),
             str(r.get("leader_fill_id") or "")) for r in rows if r.get("leader_fill_id")}


def leader_fill_id(row: dict[str, str]) -> str:
    for key in ("leader_fill_id", "fill_id", "hash", "tid", "oid"):
        if row.get(key):
            return str(row[key])
    wallet = row.get("user") or row.get("wallet") or ""
    parts = [wallet, row.get("coin"), row.get("side", row.get("dir")),
             row.get("px", row.get("price")), row.get("sz", row.get("size")),
             row.get("time", row.get("timestamp_ms")), row.get("startPosition", "")]
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:32]


def leader_fill_time(row: dict[str, str]) -> int:
    for key in ("time", "timestamp_ms", "timestamp"):
        try:
            value = int(float(row.get(key) or 0))
            if value:
                return value
        except ValueError:
            pass
    return 0


def csv_int(value: str | None, field: str) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError, OverflowError) as exc:
        raise HotfixError("invalid numeric proof field: " + field) from exc


def api_leader_fills(start_ms: int, end_ms: int, wallets: list[str],
                     fetcher=None) -> dict[tuple[str, str], dict[str, Any]]:
    """Independent mainnet source, not the follower/Core ledger.

    Pages overlap at the last millisecond and dedupe by (wallet, tid), NEVER hash.
    A full page with no timestamp advance or incomplete API reply fails closed;
    silently skipping fills in one hot millisecond is forbidden.
    """
    if fetcher is None:
        import urllib.request
        def fetcher(payload):
            request = urllib.request.Request(
                "https://api.hyperliquid.xyz/info",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read())
    if end_ms < start_ms:
        raise HotfixError("invalid mainnet replay window")
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for wallet in wallets:
        wallet = str(wallet).lower()
        cursor = max(0, int(start_ms))
        for _page_no in range(300):
            payload = {"type": "userFillsByTime", "user": wallet, "startTime": cursor,
                       "endTime": int(end_ms), "aggregateByTime": False}
            try:
                batch = fetcher(payload)
            except Exception as exc:
                raise HotfixError("independent mainnet leader-fill API unavailable") from exc
            if not isinstance(batch, list) or len(batch) > 2000:
                raise HotfixError("leader-fill API returned an invalid/capped reply")
            times = []
            for row in batch:
                if not isinstance(row, dict) or row.get("tid") is None:
                    raise HotfixError("leader-fill API row missing unique tid")
                t = leader_fill_time(row)
                if t < cursor or t > end_ms:
                    raise HotfixError("leader-fill API returned a timestamp outside the requested page")
                times.append(t)
                tid = str(row["tid"])
                key = (wallet, tid)
                existing = seen.get(key)
                if existing is not None and any(
                        str(existing.get(k)) != str(row.get(k))
                        for k in ("coin", "side", "time", "px", "sz")):
                    raise HotfixError("leader-fill API reused tid with conflicting contents")
                seen[key] = dict(row, user=wallet)
            if times != sorted(times):
                raise HotfixError("leader-fill API pages are not chronological; cannot prove completeness")
            if len(batch) < 2000:
                break
            if not times or max(times) <= cursor:
                raise HotfixError("leader-fill API 2000-row cap prevents complete millisecond pagination")
            cursor = max(times)  # inclusive: retain every subfill sharing the last ms
        else:
            raise HotfixError("leader-fill API pagination budget exhausted")
    return seen


def prove_api_to_ledger(api_fills: dict[tuple[str, str], dict[str, Any]],
                        intents: list[dict[str, str]], start_ms: int, end_ms: int) -> None:
    """Join on (wallet, tid) only. No hash/composite fallback may claim PASS.

    The current Core does NOT write leader_tid into order_intents.csv, so a
    nonempty window must be blocked pending an authorised ledger schema change.
    This is intentional: multiple executions can share hash, price and time.
    """
    ledger_ids: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in intents:
        created = csv_int(row.get("created_at_ms"), "order_intents.created_at_ms")
        if not start_ms <= created <= end_ms:
            continue
        tid = str(row.get("leader_tid") or "").strip()
        if not tid:
            continue
        wallet = str(row.get("leader_wallet") or "").lower()
        ledger_ids.setdefault((wallet, tid), []).append(row)
    for key, raw in api_fills.items():
        matches = [row for row in ledger_ids.get(key, []) if (
            csv_int(row.get("created_at_ms"), "order_intents.created_at_ms")
            >= leader_fill_time(raw)
            and csv_int(row.get("leader_fill_timestamp_ms"),
                        "order_intents.leader_fill_timestamp_ms") == leader_fill_time(raw))]
        if len(matches) != 1 or not str(matches[0].get("leader_fill_id") or ""):
            raise HotfixError(
                "API tid cannot be proven in the ledger (missing, duplicate or late row); "
                "Core must persist leader_tid and leader_fill_timestamp_ms per source fill "
                "including merged sibling fills before an API-backed swap can be certified")


def source_gap_fills(source: Path, stop_ms: int, first_cycle_ms: int) -> dict[str, int]:
    if not source.is_file():
        raise HotfixError("local raw leader-fill source is unavailable; cannot prove replay coverage")
    fills: dict[str, int] = {}
    for row in csv_rows(source):
        at = leader_fill_time(row)
        if stop_ms <= at <= first_cycle_ms:
            fid = str(row.get("leader_fill_id") or "").strip()
            if not fid or fid in fills:
                raise HotfixError("explicit source CSV must have unique leader_fill_id per fill")
            fills[fid] = at
    return fills


def cursor_map(state: Path) -> dict[str, int]:
    runtime = read_json(state / "clean_core_runtime_state.json")
    cursors = runtime.get("last_leader_poll_cursor_ms")
    if isinstance(cursors, dict):
        return {str(k).lower(): int(v) for k, v in cursors.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return {}


def unresolved_count(state: Path) -> int:
    status_path = state / "live_integrity_status.json"
    if not status_path.is_file():
        raise HotfixError("live_integrity_status.json is unavailable")
    status = read_json(status_path)
    checks = [status.get("hard_copy_invariant", {}).get("historical_unresolved_active_red_count", 0),
              status.get("counts", {}).get("open_late_fill_incidents", 0)]
    for value in checks:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise HotfixError("unresolved proof counter is not numeric")
    return int(sum(checks))


def first_healthy_cycle(state: Path, wanted_pid: int, after_ms: int) -> tuple[int, dict[str, Any]] | None:
    service = state / "live_service_state.json"
    if not service.is_file():
        return None
    record = read_json(service)
    at = int(record.get("created_at_ms") or 0)
    if int(record.get("process_id") or record.get("pid") or 0) != wanted_pid or at < after_ms:
        return None
    if record.get("ok") is not True:
        return None
    if int(record.get("fatal_errors") or 0) != 0 or int(record.get("network_errors") or 0) != 0:
        return None
    return at, record


def replay_proof(state: Path, baseline: dict[str, Any], sent_before: set[tuple[str, str]],
                 source: Path | None, stop_ms: int, first_cycle_ms: int, live_wallets: list[str]) -> dict[str, int]:
    api_fills = None if source is not None else api_leader_fills(
        stop_ms - 60_000, first_cycle_ms, live_wallets)
    fills = (source_gap_fills(source, stop_ms, first_cycle_ms) if source is not None
             else {wallet + ":" + tid: leader_fill_time(raw)
                   for (wallet, tid), raw in api_fills.items()})
    intents = csv_rows(state / "append_only" / "order_intents.csv")
    if api_fills is not None:
        prove_api_to_ledger(api_fills, intents, stop_ms - 60_000, first_cycle_ms)
    new_intents = [r for r in intents if csv_int(r.get("created_at_ms"), "order_intents.created_at_ms") >= stop_ms]
    intent_fill_ids = {str(r.get("leader_fill_id") or "") for r in new_intents}
    missing_rows = sorted(set(fills) - intent_fill_ids) if source is not None else []
    if missing_rows:
        raise HotfixError("gap replay is missing order_intents rows")
    attempts = csv_rows(state / "append_only" / "send_attempts.csv")
    new_attempts = [r for r in attempts if csv_int(r.get("created_at_ms"), "send_attempts.created_at_ms") >= stop_ms]
    duplicates = [r for r in new_attempts if (str(r.get("wallet") or r.get("leader_wallet") or "").lower(),
                                                  str(r.get("leader_fill_id") or "")) in sent_before]
    if duplicates:
        raise HotfixError("a fill already sent before the swap received another send attempt")
    cursors = cursor_map(state)
    required_ms = max(stop_ms, first_cycle_ms)
    if any(cursors.get(wallet, 0) < required_ms for wallet in live_wallets):
        raise HotfixError("leader poll cursors have not caught up to the swap gap")
    unresolved = unresolved_count(state)
    if unresolved:
        raise HotfixError("attached watch still reports unresolved rows")
    after = snapshot_state(state)
    for key in ("anchor_sha256", "anchor_t0_ms", "live_config_semantic_sha256",
                "manual_live_positions_sha256", "xyz_position_state_sha256", "user_owned_sha256"):
        if after[key] != baseline[key]:
            raise HotfixError("same-state invariant changed: " + key)
    return {"gap_fills": len(fills), "gap_intent_rows": len(new_intents),
            "duplicate_attempts": 0, "unresolved": unresolved,
            "cursors_caught_up": len(live_wallets)}


def live_wallets(config: dict[str, Any]) -> list[str]:
    wallets = config.get("wallets") if isinstance(config.get("wallets"), dict) else {}
    return [str(name).lower() for name, value in wallets.items() if isinstance(value, dict)
            and str(value.get("mode") or "").upper().startswith(("LIVE", "CLO"))]


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text + "\n", encoding="utf-8")
    os.replace(temp, path)


def start_pair(build: Path, sha: str, state: Path, port: int, launch_env: dict[str, str]) -> dict[str, Any]:
    command = [sys.executable, str(build / "ops" / "start_pair.py"), "--checkout", str(build),
               "--state", str(state), "--expect-sha", sha, "--ui-port", str(port)]
    result = subprocess.run(command, capture_output=True, text=True, env=launch_env, timeout=120)
    if result.returncode:
        raise HotfixError("start_pair failed; captured output withheld")
    try:
        payload = json.loads(result.stdout)
    except Exception as exc:
        raise HotfixError("start_pair did not return its identity block") from exc
    if payload.get("pair") != "STARTED" or not payload.get("engine_pid"):
        raise HotfixError("start_pair did not prove a complete pair")
    return payload


def stop_pair(state: Path, port: int) -> dict[str, Any]:
    request_ms = int(time.time() * 1000)
    result = subprocess.run([sys.executable, str(OPS / "stop_pair.py"), "--all", "--port", str(port)],
                            capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise HotfixError("stop_pair did not prove a clean stop; captured output withheld")
    record = read_json(state / "core_shutdown_record.json")
    if (record.get("reason") != "stop_sentinel" or record.get("clean") is not True
            or int(record.get("timestamp_ms") or 0) < request_ms - 500):
        raise HotfixError("shutdown record does not prove this clean stop")
    if SP.pids(state) or SP.listener(port):
        raise HotfixError("post-stop identity check failed: pair state ambiguous; check whether pair is down and use --rollback only after operator verification")
    return record


def tracked_start_ui(port: int) -> None:
    result = subprocess.run([sys.executable, str(OPS / "stop_pair.py"), "--track-ui", "--port", str(port)],
                            capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise HotfixError("could not record the new UI identity; output withheld")


def rewrite_launch_spec(spec: dict[str, Any], build: Path, sha: str, state: Path) -> None:
    # Preserve env entries unchanged; only their names are printed in the proof.
    spec["cwd"] = str(build / "_archive" / "hl_stage2")
    spec["script"] = str(build / "_archive" / "hl_stage2" / TARGET)
    spec["build_sha"] = sha
    if Path(spec["env"]["HL_LIVE_AUDIT_DIR"]).expanduser().resolve() != state:
        raise HotfixError("launch state changed during the swap")
    atomic_json(LAUNCH_ENV, spec)


def save_swap_record(old_root: Path, old_sha: str, new_root: Path, new_sha: str,
                     state: Path, port: int, backup: Path) -> None:
    atomic_json(LAST_SWAP, {"previous_checkout": str(old_root), "previous_sha": old_sha,
                            "current_checkout": str(new_root), "current_sha": new_sha,
                            "state_dir": str(state), "ui_port": port,
                            "state_backup": str(backup),
                            "saved_at": datetime.now(timezone.utc).isoformat()})


def perform_swap(target: Path, target_sha: str, port: int, dry_run: bool) -> int:
    spec, env, state = launch_spec()
    identity, old_root, old_sha, _old_ui_pid = validate_pair(state, port)
    if old_sha == target_sha:
        raise HotfixError("target build is already running")
    new_root, checked_sha = checkout_info(target)
    if new_root != target or checked_sha != target_sha:
        raise HotfixError("target build changed after resolution")
    precompile(new_root)
    baseline = snapshot_state(state)
    config = read_json(state / "live_config.json")
    wallets = live_wallets(config)
    if not wallets:
        raise HotfixError("no LIVE/CLO leader wallets are configured; cannot prove polling catch-up")
    source_spec = env.get("HL_LIVE_SOURCE_FILLS")
    default_source = old_root / "_archive" / "hl_stage2" / "hl_copy_output" / "raw_live_fills.csv"
    source = Path(source_spec).expanduser() if source_spec else None
    if source is not None and not source.is_file():
        raise HotfixError("explicit HL_LIVE_SOURCE_FILLS override does not exist")
    # The default on-disk path is inside hl_copy_output, but WS+poll-live
    # does not populate it; without an override the API is authoritative.
    print("REPLAY SOURCE: %s" % (str(source) if source is not None
                                 else "mainnet API (default CSV path: %s)" % default_source))
    keys = ",".join(sorted(env))
    print("PREFLIGHT: one Core + tracked UI; identity, SHA, state, anchor, config, ledger and env-key checks passed")
    print("ENV KEYS (values withheld): " + keys)
    print("BUILD: %s -> %s" % (old_sha, target_sha))
    print("STATE: same directory; no seeding or clearing")
    print("PRECOMPILE: engine, UI, start_pair.py, stop_pair.py passed")
    print("STATE SHA: PAIR_START_ANCHOR=%s live_config_semantic=%s USER/ledger invariants captured"
          % (baseline["anchor_sha256"], baseline["live_config_semantic_sha256"]))
    if dry_run:
        print("DRY RUN: no backup, state write, stop, or start performed")
        return 0

    backup = backup_state(state)
    sent_before = sent_keys(state)
    # Recheck after the potentially long pre-stop backup; no change is allowed before the stop.
    current_identity, current_root, current_sha, _ = validate_pair(state, port)
    if (int(current_identity.get("pid") or current_identity.get("process_id") or 0)
            != int(identity.get("pid") or identity.get("process_id") or 0)
            or current_root != old_root or current_sha != old_sha
            or snapshot_state(state) != baseline):
        raise HotfixError("pre-stop identity or state changed during staging")

    original_spec = copy.deepcopy(spec)
    # Do not touch either process after an unproven/ambiguous stop. Restart is safe
    # only once stop_pair has positively established that both old processes exited.
    stop_pair(state, port)
    try:
        old_pair_down_ms = int(time.time() * 1000)
        rewrite_launch_spec(spec, new_root, target_sha, state)
        atomic_text(pointer_path(state), str(state))
        start_info = start_pair(new_root, target_sha, state, port, dict(env))
        tracked_start_ui(port)
        engine_pid = int(start_info["engine_pid"])
        deadline = time.monotonic() + REPLAY_TIMEOUT_S
        first_cycle: tuple[int, dict[str, Any]] | None = None
        healthy_observed_at: float | None = None
        proof: dict[str, int] | None = None
        while time.monotonic() < deadline:
            first_cycle = first_healthy_cycle(state, engine_pid, old_pair_down_ms)
            if first_cycle is not None:
                if healthy_observed_at is None:
                    healthy_observed_at = time.monotonic()
                if time.monotonic() - healthy_observed_at < REPLAY_WATCH_S:
                    time.sleep(POLL_S)
                    continue
                try:
                    proof = replay_proof(state, baseline, sent_before, source, old_pair_down_ms,
                                         max(first_cycle[0], int(time.time() * 1000)), wallets)
                    break
                except HotfixError as exc:
                    # A lagging poll/copy cycle is expected during the attached watch; invariant drift is not.
                    if "not caught up" not in str(exc) and "unresolved rows" not in str(exc) and "missing order_intents" not in str(exc):
                        raise
            time.sleep(POLL_S)
        if first_cycle is None or proof is None:
            raise HotfixError("attached replay watch timed out; the pair remains up for operator review")
        gap_ms = first_cycle[0] - old_pair_down_ms
        print("PROOF TABLE")
        print("  same_state_dir              PASS")
        print("  pair_start_anchor_sha/t0    PASS (%s / %d)" % (baseline["anchor_sha256"], baseline["anchor_t0_ms"]))
        print("  live_config_semantic_sha    PASS (%s; ignored timestamp fields: none)" % baseline["live_config_semantic_sha256"])
        print("  sleeve_ledger_sha            PASS (ignored: manual_live_positions.last_updated_at; xyz_position_state.updated_at, updated_at_ms)")
        print("  USER-OWNED sleeves           PASS (content digest unchanged)")
        print("  one_engine + tracked_UI      PASS")
        print("  old_pair_down_ms             %d" % old_pair_down_ms)
        print("  first_healthy_cycle_ms       %d" % first_cycle[0])
        print("  deactivation_to_healthy_ms   %d / %d" % (gap_ms, MAX_GAP_MS))
        print("  missed_fills / intent_rows   %d / %d" % (proof["gap_fills"], proof["gap_intent_rows"]))
        print("  duplicate_attempts           %d" % proof["duplicate_attempts"])
        print("  UNRESOLVED                   %d" % proof["unresolved"])
        print("  poll_wallets_caught_up       %d" % proof["cursors_caught_up"])
        # Preserve explicit rollback target when the new build stays running (including gap failure).
        save_swap_record(old_root, old_sha, new_root, target_sha, state, port, backup)
        if gap_ms >= MAX_GAP_MS:
            print("FAIL: pair downtime must be under 20 seconds")
            return 1
        print("HOTFIX SWAP PASS: %s" % target_sha)
        print("STATE BACKUP: %s" % backup)
        return 0
    except Exception as swap_error:
        try:
            if SP.pids(state) or SP.listener(port):
                stop_pair(state, port)
            rewrite_launch_spec(copy.deepcopy(original_spec), old_root, old_sha, state)
            atomic_text(pointer_path(state), str(state))
            start_pair(old_root, old_sha, state, port, dict(original_spec["env"]))
            tracked_start_ui(port)
        except Exception as rollback_error:
            raise HotfixError("swap failed and previous pair could not be restored") from rollback_error
        raise HotfixError("swap failed; previous pair restored") from swap_error

def main() -> int:
    parser = argparse.ArgumentParser(description="Same-state Build 3 Core/UI hotfix swap")
    parser.add_argument("build_sha_or_worktree", nargs="?")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--ui-port", type=int, default=8031)
    args = parser.parse_args()
    try:
        if args.rollback:
            if args.build_sha_or_worktree:
                raise HotfixError("--rollback takes its target from the last successful swap record")
            prior = read_json(LAST_SWAP)
            target, sha = checkout_info(Path(prior.get("previous_checkout") or ""))
            if sha != prior.get("previous_sha"):
                raise HotfixError("previous build checkout no longer matches its recorded SHA")
            if str(Path(prior.get("state_dir") or "").resolve()) != str(launch_spec()[2]):
                raise HotfixError("rollback record belongs to a different state directory")
            port = int(prior.get("ui_port") or args.ui_port)
        else:
            if not args.build_sha_or_worktree:
                raise HotfixError("supply a build SHA or worktree path")
            target, sha = resolve_build(args.build_sha_or_worktree)
            port = args.ui_port
        return perform_swap(target, sha, port, args.dry_run)
    except (HotfixError, OSError, ValueError, subprocess.SubprocessError) as exc:
        return refuse(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
