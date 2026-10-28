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
import re
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
    excluded_runtime_locks: list[str] = []

    def ignore_runtime_locks(directory: str, names: list[str]) -> set[str]:
        skipped: set[str] = set()
        for name in names:
            if not name.lower().endswith(".lock"):
                continue
            path = Path(directory) / name
            if path.is_dir():
                raise HotfixError("state backup refuses to omit a lock-named directory")
            skipped.add(name)
            excluded_runtime_locks.append(path.relative_to(state).as_posix())
        return skipped

    # The running Core holds instance.lock exclusively; copying it can fail on Windows.
    # Never open, release, remove or force-copy an engine liveness lock.
    shutil.copytree(state, target, copy_function=shutil.copy2,
                    ignore=ignore_runtime_locks)
    if not (target / "PAIR_START_ANCHOR.json").is_file():
        raise HotfixError("state backup did not preserve the pair anchor")
    atomic_json(target / "backup_manifest.json", {
        "source_state_dir": str(state),
        "excluded_runtime_locks": sorted(excluded_runtime_locks),
        "exclusion_reason": "active runtime lock files are deliberately not copied",
    })
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


LEADER_FILL_RETENTION_CEILING = 10_000  # Hyperliquid userFillsByTime exposes only the latest 10,000 per wallet.


def api_leader_fills(start_ms: int, end_ms: int, wallets: list[str],
                     fetcher=None, endpoint: str = "https://api.hyperliquid.xyz/info",
                     require_retention_proof: bool = False) -> dict[tuple[str, str], dict[str, Any]]:
    """Independent leader-network source, not the follower/Core ledger.

    Pages overlap at the last millisecond and dedupe by (wallet, tid), NEVER hash.
    A full page with no timestamp advance or incomplete API reply fails closed;
    silently skipping fills in one hot millisecond is forbidden. The 10,000-fill
    retention ceiling is per-wallet, not per-page. For proof queries that have no
    fills, require independent latest-fill evidence instead of interpreting an
    old/truncated window's empty page as a confirmed zero.
    """
    if fetcher is None:
        import urllib.request
        def fetcher(payload):
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read())
    if end_ms < start_ms:
        raise HotfixError("invalid leader replay window")
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    for wallet in wallets:
        wallet = str(wallet).lower()
        cursor = max(0, int(start_ms))
        wallet_unique = 0
        for _page_no in range(300):
            payload = {"type": "userFillsByTime", "user": wallet, "startTime": cursor,
                       "endTime": int(end_ms), "aggregateByTime": False}
            try:
                batch = fetcher(payload)
            except Exception as exc:
                raise HotfixError("independent leader-fill API unavailable") from exc
            if not isinstance(batch, list) or len(batch) > 2000:
                raise HotfixError("leader-fill API returned an invalid/capped reply")
            times = []
            for row in batch:
                if not isinstance(row, dict) or row.get("tid") is None:
                    raise HotfixError("leader-fill API row missing unique tid")
                t = leader_fill_time(row)
                if t <= 0 or t < cursor or t > end_ms:
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
                if existing is None:
                    wallet_unique += 1
                    if wallet_unique >= LEADER_FILL_RETENTION_CEILING:
                        raise HotfixError("coverage ambiguous: retention ceiling reached (wallet %s, %d unique fills)"
                                          % (wallet, LEADER_FILL_RETENTION_CEILING))
            if times != sorted(times):
                raise HotfixError("leader-fill API pages are not chronological; cannot prove completeness")
            if len(batch) < 2000:
                break
            if not times or max(times) <= cursor:
                raise HotfixError("leader-fill API 2000-row cap prevents complete millisecond pagination")
            cursor = max(times)  # inclusive: retain every subfill sharing the last ms
        else:
            raise HotfixError("leader-fill API pagination budget exhausted")
        if require_retention_proof and wallet_unique == 0:
            # A short/empty historical time-window page is not an API completeness signal.
            # The separate recent-fills endpoint supplies a positive witness that this
            # wallet's *latest* known fill predates the requested lower bound.
            try:
                recent = fetcher({"type": "userFills", "user": wallet, "aggregateByTime": False})
            except Exception as exc:
                raise HotfixError("zero-fill window lacks positive retention evidence") from exc
            if (not isinstance(recent, list) or not recent or len(recent) > 2000
                    or any(not isinstance(row, dict) or leader_fill_time(row) <= 0
                           or leader_fill_time(row) >= start_ms for row in recent)):
                raise HotfixError("zero-fill window lacks positive retention evidence")
    return seen



_LEADER_INFO_ENDPOINTS = {
    "mainnet": "https://api.hyperliquid.xyz/info",
    "testnet": "https://api.hyperliquid-testnet.xyz/info",
}


def leader_api_url(state: Path, env: dict[str, str]) -> str:
    """Bind the export to the independently stamped leader network for this state."""
    stamp = read_json(state / "network.json")
    leader = str(stamp.get("leader") or "").strip().lower()
    if leader not in _LEADER_INFO_ENDPOINTS:
        raise HotfixError("state leader network is missing or unsupported")
    requested = str(env.get("HL_LEADER_NETWORK") or leader).strip().lower()
    if requested != leader:
        raise HotfixError("launch leader network disagrees with state network stamp")
    return _LEADER_INFO_ENDPOINTS[leader]


def api_source_capability(wallets: list[str], endpoint: str) -> None:
    """BEFORE STOP: read-only API health check, not gap coverage proof."""
    if not wallets or any(not re.fullmatch(r"0x[0-9a-f]{40}", str(w).lower()) for w in wallets):
        raise HotfixError("leader API capability requires exact valid LIVE/CLO wallet addresses")
    now = int(time.time() * 1000)
    api_leader_fills(now, now, wallets, endpoint=endpoint)


def export_api_source(wallets: list[str], stop_ms: int, first_cycle_ms: int,
                      target_sha: str, endpoint: str) -> tuple[Path, dict[str, Any]]:
    """Fetch after first healthy cycle; atomic independent source, outside audited state."""
    if stop_ms <= 0 or first_cycle_ms < stop_ms or not wallets:
        raise HotfixError("invalid API gap export window or leader set")
    # Query through the present, not just the earlier first-cycle timestamp. If
    # more than 10,000 recent fills have displaced the gap, that cap is observable
    # and blocks. Filter to the actual gap only AFTER proving the full retained tail.
    coverage_end_ms = int(time.time() * 1000)
    if coverage_end_ms < first_cycle_ms:
        raise HotfixError("leader-fill API export clock predates first healthy cycle")
    retained_tail = api_leader_fills(
        stop_ms, coverage_end_ms, wallets, endpoint=endpoint,
        require_retention_proof=True)
    seen = {key: row for key, row in retained_tail.items()
            if leader_fill_time(row) <= first_cycle_ms}
    name = "%s_source_%s_%d_%d.csv" % (LAST_SWAP.stem, target_sha[:12], stop_ms, first_cycle_ms)
    path = LAST_SWAP.with_name(name)
    fields = ("leader_fill_id", "user", "coin", "side", "px", "sz", "time", "tid", "hash")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for (wallet, tid), raw in sorted(seen.items(), key=lambda item: (
                    leader_fill_time(item[1]), item[0][0], item[0][1])):
                at = leader_fill_time(raw)
                coin = str(raw.get("coin") or "").strip()
                side = str(raw.get("side") or raw.get("dir") or "").strip()
                px = _num(raw.get("px"), "api.px")
                sz = _num(raw.get("sz"), "api.sz")
                if not coin or not side or px <= 0 or sz <= 0:
                    raise HotfixError("leader-fill API row lacks usable coin/side/size/price")
                _canonical_side(side)
                writer.writerow({"leader_fill_id": wallet + ":" + tid, "user": wallet,
                                 "coin": coin, "side": side, "px": raw["px"], "sz": raw["sz"],
                                 "time": at, "tid": tid, "hash": str(raw.get("hash") or "")})
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, {"api_verified": True, "source_path": str(path), "source_sha256": digest,
                  "wallets": sorted(set(str(w).lower() for w in wallets)),
                  "start_ms": stop_ms, "end_ms": first_cycle_ms,
                  "coverage_end_ms": coverage_end_ms,
                  "retention_ceiling": LEADER_FILL_RETENTION_CEILING,
                  "total_fills": len(seen),
                  "endpoint": endpoint, "fetched_at": datetime.now(timezone.utc).isoformat()}


def source_gap_fills(source: Path, stop_ms: int, first_cycle_ms: int) -> dict[str, int]:
    if not source.is_file():
        raise HotfixError("local raw leader-fill source is unavailable; cannot prove replay coverage")
    fills: dict[str, int] = {}
    for row in csv_rows(source):
        at = leader_fill_time(row)
        if stop_ms <= at <= first_cycle_ms:
            fills[leader_fill_id(row)] = at
    return fills


def cursor_map(state: Path) -> dict[str, int]:
    runtime = read_json(state / "clean_core_runtime_state.json")
    cursors = runtime.get("last_leader_poll_cursor_ms")
    if isinstance(cursors, dict):
        return {str(k).lower(): int(v) for k, v in cursors.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return {}



def poll_coverage(state: Path, wallets: list[str], stop_ms: int, first_cycle_ms: int,
                  source_rows: list[dict[str, str]], cursors: dict[str, int]) -> None:
    """Prove completed per-wallet polls; last-fill cursor is NOT a poll timestamp.

    Core emits a trace record for each userFillsByTime request. POLL_OK means
    a short (possibly empty) last page; new=0 confirms no unhandled fills for
    a quiet leader. A subsequent poll may start after stop_ms when cursor_in
    already covers it; this is still positive poll coverage. Only truncated
    wallet prefixes are stored; collisions fail.
    """
    prefixes: dict[str, str] = {}
    for wallet in wallets:
        prefix = wallet[:10].lower()
        if prefix in prefixes and prefixes[prefix] != wallet:
            raise HotfixError("leader poll coverage ambiguous wallet prefixes: %s, %s" %
                              (prefixes[prefix], wallet))
        prefixes[prefix] = wallet
    records: dict[str, dict[str, Any]] = {}
    path = state / "leader_poll_trace.jsonl"
    if path.is_file():
        # Bounded recent trace read; missing/rotated evidence fails closed.
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - 1024 * 1024))
            if size > 1024 * 1024:
                fh.readline()  # discard one partial line
            for line in fh:
                try:
                    rec = json.loads(line)
                except (UnicodeError, ValueError):
                    continue
                if not isinstance(rec, dict) or rec.get("kind") != "poll":
                    continue
                wallet = prefixes.get(str(rec.get("wallet") or "").lower())
                if not wallet or csv_int(rec.get("ts"), "leader_poll_trace.ts") < stop_ms:
                    continue
                if (csv_int(rec.get("end_ms"), "leader_poll_trace.end_ms") >= first_cycle_ms
                        and (csv_int(rec.get("start_ms"), "leader_poll_trace.start_ms") <= stop_ms
                             or csv_int(rec.get("cursor_in"), "leader_poll_trace.cursor_in") >= stop_ms)):
                    records[wallet] = rec
    newest: dict[str, int] = {}
    for row in source_rows:
        wallet = str(row.get("user") or row.get("wallet") or "").lower()
        if wallet in wallets:
            newest[wallet] = max(newest.get(wallet, 0), leader_fill_time(row))
    failures: list[str] = []
    for wallet in wallets:
        rec = records.get(wallet)
        if rec is None:
            failures.append(wallet + "(no completed poll spanning gap)")
        elif rec.get("status") != "POLL_OK":
            failures.append(wallet + "(poll status=%s)" % rec.get("status"))
        elif wallet not in newest and csv_int(rec.get("new"), "leader_poll_trace.new") != 0:
            failures.append(wallet + "(no positive empty/new=0 poll evidence)")
        elif wallet in newest and cursors.get(wallet, 0) < newest[wallet]:
            failures.append(wallet + "(fill cursor=%d<newest fill=%d)" %
                            (cursors.get(wallet, 0), newest[wallet]))
    if failures:
        raise HotfixError("leader poll coverage not caught up: " + ", ".join(failures))


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


BUCKET_TOLERANCE = 1e-6
BUCKET_WIDTH_MS = 60_000          # normal: (wallet, coin, side, minute)
BUCKET_WIDTH_WIDE_MS = 300_000    # widened when provenance is ingest-time only


_SIDE_MAP = {"B": "BUY", "A": "SELL", "BUY": "BUY", "SELL": "SELL"}

# Direction strings as Core's LeaderFillIngestor.parse_fill understands them. Closing a long
# is a SELL and closing a short is a BUY, so the close forms invert the open forms.
_SIDE_DIRECTION = {
    "OPEN LONG": "BUY", "CLOSE SHORT": "BUY",
    "OPEN SHORT": "SELL", "CLOSE LONG": "SELL",
}


def _canonical_side(side: Any) -> str:
    """Canonicalise Hyperliquid API side tokens and Core side tokens to one alphabet.

    The raw leader-fill ledger carries Hyperliquid API values B/A (and sometimes direction
    strings), while the Core writes LeaderFill.side as BUY/SELL. Both must land in the same
    bucket key or every real fill fails reconciliation despite a perfect replay. Direction
    strings map exactly as Core parse_fill does. An unknown or empty token is REJECTED: letting
    two unknowns compare equal would pass coverage without proving anything.
    """
    raw = str(side or "").strip()
    token = raw.upper()
    if token in _SIDE_MAP:
        return _SIDE_MAP[token]
    for phrase, canonical in _SIDE_DIRECTION.items():
        if phrase in token:
            return canonical
    if not token:
        raise HotfixError("empty side token; cannot prove coverage on an absent side")
    raise HotfixError("unknown side token %r; refusing to let unknowns match" % raw)


def _replay_timeout_message(last_bucket_failure: str | None) -> str:
    """Terminal replay failure must name the last failed bucket, not just say it timed out."""
    base = "attached replay watch timed out"
    if last_bucket_failure:
        return "%s; last failed bucket: %s; the pair remains up for operator review" % (
            base, last_bucket_failure.strip()[:300])
    return base + "; the pair remains up for operator review"


def _num(value: Any, field: str = "value") -> float:
    """Parse a financial number strictly. Invalid, missing or non-finite input is a failure.

    Coercing unparseable input to 0.0 let a row with unreadable px/sz match an intent with
    unreadable leader_notional and pass coverage as 0 == 0. Financial fields must never be
    silently treated as genuine zero notional.
    """
    if value is None:
        raise HotfixError("%s is missing; cannot prove coverage on an absent financial field" % field)
    text = str(value).strip()
    if not text:
        raise HotfixError("%s is empty; cannot prove coverage on an absent financial field" % field)
    try:
        number = float(text)
    except (TypeError, ValueError):
        raise HotfixError("%s is not numeric (%r); cannot prove coverage" % (field, text))
    if number != number or number in (float("inf"), float("-inf")):
        raise HotfixError("%s is not finite (%r); cannot prove coverage" % (field, text))
    return number


def _bucket(wallet: str, coin: str, side: str, at_ms: int, width_ms: int) -> tuple[str, str, str, int]:
    return (str(wallet or "").strip().lower(), str(coin or "").strip().upper(),
            _canonical_side(side), int(at_ms) // width_ms)


def bucket_reconciliation(state: Path, source: Path, stop_ms: int, first_cycle_ms: int) -> dict[str, Any]:
    """C7-DIR-22 ruling C: bucket-level coverage, the approved weaker proof.

    Exact fill-id equality cannot hold once historical ledger rows carry only a hash, so
    coverage is proved per (wallet, coin, side, interval): exact count equality in every
    bucket, notional equal within 1e-6 relative, and any difference is a FAIL that names
    the bucket. If any intent row lacks the additive leader_fill_timestamp_ms, provenance
    is ingest time and the buckets widen to five minutes - reported, never hidden.
    """
    if not source.is_file():
        raise HotfixError("local raw leader-fill source is unavailable; cannot prove replay coverage")
    source_rows = [r for r in csv_rows(source) if stop_ms <= leader_fill_time(r) <= first_cycle_ms]
    intents = csv_rows(state / "append_only" / "order_intents.csv")
    # P1-c / C7-DIR-43(3): judge intents on the SAME event-time window as source_rows, not
    # ingestion time. Both bounds are enforced for stamped rows: event_ms >= stop_ms excludes
    # a late-ingested pre-stop fill, and event_ms <= first_cycle_ms excludes post-first-cycle
    # ordinary trading. Ingest-only rows have no event stamp, so created_at_ms is the only
    # time available; they are bounded by the same [stop_ms, first_cycle_ms] window, which
    # limits post-cycle ordinary trading while stamped late-ingested in-window fills survive.
    new_intents: list[dict[str, str]] = []
    for r in intents:
        stamp = str(r.get("leader_fill_timestamp_ms") or "").strip()
        event_ms = (csv_int(stamp, "order_intents.leader_fill_timestamp_ms") if stamp
                    else csv_int(r.get("created_at_ms"), "order_intents.created_at_ms"))
        if stop_ms <= event_ms <= first_cycle_ms:
            new_intents.append(r)
    ingest_only = any(not str(r.get("leader_fill_timestamp_ms") or "").strip() for r in new_intents)
    width = BUCKET_WIDTH_WIDE_MS if ingest_only else BUCKET_WIDTH_MS
    left: dict[tuple[str, str, str, int], list[float]] = {}
    for r in source_rows:
        key = _bucket(str(r.get("user") or r.get("wallet") or ""), str(r.get("coin") or ""),
                      str(r.get("side") or r.get("dir") or ""), leader_fill_time(r), width)
        entry = left.setdefault(key, [0, 0.0])
        entry[0] += 1
        px = _num(r.get("px") or r.get("price"), "source.px")
        sz = _num(r.get("sz") or r.get("size"), "source.sz")
        entry[1] += abs(px * sz)
    right: dict[tuple[str, str, str, int], list[float]] = {}
    for r in new_intents:
        at = csv_int(r.get("leader_fill_timestamp_ms") or 0, "order_intents.leader_fill_timestamp_ms") \
            if str(r.get("leader_fill_timestamp_ms") or "").strip() else \
            csv_int(r.get("created_at_ms"), "order_intents.created_at_ms")
        key = _bucket(str(r.get("leader_wallet") or ""), str(r.get("coin") or ""),
                      str(r.get("leader_side") or ""), at, width)
        entry = right.setdefault(key, [0, 0.0])
        entry[0] += 1
        entry[1] += abs(_num(r.get("leader_notional"), "intent.leader_notional"))
    failures = []
    merged_buckets = 0
    for key in sorted(set(left) | set(right), key=lambda k: (k[0], k[1], k[2], k[3])):
        lc, ln = left.get(key, [0, 0.0])
        rc, rn = right.get(key, [0, 0.0])
        notional_ok = (not ln and not rn) or abs(ln - rn) / max(abs(ln), abs(rn), 1e-12) <= BUCKET_TOLERANCE
        if lc == rc:
            if not notional_ok:
                failures.append({"bucket": key, "source_notional": ln, "intent_notional": rn,
                                 "cause": "notional"})
            continue
        # A bucket with NO intent rows is never a merge: catch-up absorption can only ever
        # leave one surviving row, so zero intents against real source fills is always a
        # coverage gap - not even a zero-notional bucket may be excused this way.
        if rc == 0 and lc > 0:
            failures.append({"bucket": key, "source_count": lc, "intent_count": 0,
                             "cause": "count"})
            continue
        # Catch-up nets many leader fills into ONE intent row (raw["merged_fill_ids"]), so a
        # bucket can legitimately hold fewer intent rows than source fills. That is accepted
        # ONLY when the bucket's notional is conserved within tolerance and rows were only
        # absorbed (0 < intent_count < source_count); otherwise it is a real coverage gap.
        if 0 < rc < lc and notional_ok:
            merged_buckets += 1
            continue
        failures.append({"bucket": key, "source_count": lc, "intent_count": rc,
                         "source_notional": ln, "intent_notional": rn, "cause": "count"})
    if failures:
        raise HotfixError("bucket coverage FAIL: %s" % json.dumps(failures[:5], sort_keys=True)[:400])
    return {"label": "bucket-level coverage", "buckets": len(left), "width_ms": width,
            "source_fills": len(source_rows), "intent_rows": len(new_intents),
            "provenance": "ingest_time_widened" if ingest_only else "leader_fill_time",
            "failed_buckets": 0, "merged_buckets": merged_buckets}


def replay_proof(state: Path, baseline: dict[str, Any], sent_before: set[tuple[str, str]],
                 source: Path, stop_ms: int, first_cycle_ms: int, live_wallets: list[str],
                 source_evidence: dict[str, Any] | None = None) -> dict[str, int]:
    fills = source_gap_fills(source, stop_ms, first_cycle_ms)
    if source_evidence is not None:
        evidence = source_evidence
        if (evidence.get("api_verified") is not True
                or evidence.get("source_path") != str(source)
                or evidence.get("source_sha256") != hashlib.sha256(source.read_bytes()).hexdigest()
                or evidence.get("wallets") != sorted(set(w.lower() for w in live_wallets))
                or int(evidence.get("start_ms") or -1) != stop_ms
                or int(evidence.get("end_ms") or -1) != first_cycle_ms
                or int(evidence.get("total_fills") if evidence.get("total_fills") is not None else -1) != len(fills)):
            raise HotfixError("API source completeness metadata does not match replay window")
    elif not fills:
        # A local empty/header-only CSV is not evidence of a zero-fill gap.
        raise HotfixError("zero-fill gap requires completed leader API proof, not an empty CSV")
    buckets = bucket_reconciliation(state, source, stop_ms, first_cycle_ms)
    attempts = csv_rows(state / "append_only" / "send_attempts.csv")
    new_attempts = [r for r in attempts if csv_int(r.get("created_at_ms"), "send_attempts.created_at_ms") >= stop_ms]
    duplicates = [r for r in new_attempts if (str(r.get("wallet") or r.get("leader_wallet") or "").lower(),
                                                  str(r.get("leader_fill_id") or "")) in sent_before]
    if duplicates:
        raise HotfixError("a fill already sent before the swap received another send attempt")
    # Poll completion is proven separately from last-fill cursor progression.
    cursors = cursor_map(state)
    poll_coverage(state, live_wallets, stop_ms, first_cycle_ms,
                  [r for r in csv_rows(source)
                   if stop_ms <= leader_fill_time(r) <= first_cycle_ms], cursors)
    unresolved = unresolved_count(state)
    if unresolved:
        raise HotfixError("attached watch still reports unresolved rows")
    after = snapshot_state(state)
    for key in ("anchor_sha256", "anchor_t0_ms", "live_config_semantic_sha256",
                "manual_live_positions_sha256", "xyz_position_state_sha256", "user_owned_sha256"):
        if after[key] != baseline[key]:
            raise HotfixError("same-state invariant changed: " + key)
    return {"gap_fills": len(fills), "gap_intent_rows": buckets["intent_rows"],
            "duplicate_attempts": 0, "unresolved": unresolved,
            "cursors_caught_up": len(live_wallets),
            "proof_label": buckets["label"], "buckets": buckets["buckets"],
            "bucket_width_ms": buckets["width_ms"], "bucket_provenance": buckets["provenance"],
            "failed_buckets": buckets["failed_buckets"],
            "merged_buckets": buckets["merged_buckets"]}


def live_wallets(config: dict[str, Any]) -> list[str]:
    wallets = config.get("wallets") if isinstance(config.get("wallets"), dict) else {}
    return [str(name).lower() for name, value in wallets.items() if isinstance(value, dict)
            and str(value.get("mode") or "").upper().startswith(("LIVE", "CLO"))]


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text + "\n", encoding="utf-8")
    os.replace(temp, path)


# Windows system utilities (including git and process inspection) need the real
# parent process environment. Only the configured HL_* launch values may override
# the parent; never let a saved launch spec shadow Windows' executable lookup.
_CHILD_SYSTEM_KEYS = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "PATHEXT", "COMSPEC")


def child_env(launch_env: dict[str, str] | None = None) -> dict[str, str]:
    """Parent environment + explicit launch values; system keys always from parent."""
    merged = dict(os.environ)
    merged.update(launch_env or {})
    for key in _CHILD_SYSTEM_KEYS:
        # Remove any system-key alias in the saved launch spec, including a
        # differently cased spelling, before restoring the parent value.
        for saved_key in tuple(merged):
            if saved_key.upper() == key:
                merged.pop(saved_key)
        for parent_key, value in os.environ.items():
            if parent_key.upper() == key:
                merged[parent_key] = value
    return merged


def start_pair(build: Path, sha: str, state: Path, port: int, launch_env: dict[str, str]) -> dict[str, Any]:
    command = [sys.executable, str(build / "ops" / "start_pair.py"), "--checkout", str(build),
               "--state", str(state), "--expect-sha", sha, "--ui-port", str(port)]
    result = subprocess.run(command, capture_output=True, text=True, env=child_env(launch_env), timeout=120)
    if result.returncode:
        try:
            failure = json.loads(result.stdout)
        except (ValueError, TypeError):
            failure = {}
        if not isinstance(failure, dict):
            failure = {}
        reason = str(failure.get("pair") or "no identity report")[:100]
        ui_exit = failure.get("ui_exit_rc")
        child_log = str(failure.get("ui_launch_output") or "")[-4096:]
        detail = child_log or (result.stderr or result.stdout or "no child output")[-4096:]
        raise HotfixError("start_pair failed (%s; ui_exit_rc=%s): %s" %
                          (reason, ui_exit, detail))
    try:
        payload = json.loads(result.stdout)
    except Exception as exc:
        raise HotfixError("start_pair did not return its identity block; output: " +
                          str(result.stdout or "")[-2000:]) from exc
    if payload.get("pair") != "STARTED" or not payload.get("engine_pid") or not payload.get("ui_pid"):
        raise HotfixError("start_pair did not prove a complete pair; report: " +
                          str(payload)[:2000])
    return payload


def stop_pair(state: Path, port: int, launch_env: dict[str, str] | None = None) -> dict[str, Any]:
    request_ms = int(time.time() * 1000)
    result = subprocess.run([sys.executable, str(OPS / "stop_pair.py"), "--all", "--port", str(port)],
                            capture_output=True, text=True, env=child_env(launch_env), timeout=120)
    if result.returncode:
        raise HotfixError("stop_pair did not prove a clean stop: " +
                          str(result.stderr or result.stdout or "no child output")[-2000:])
    record = read_json(state / "core_shutdown_record.json")
    if (record.get("reason") != "stop_sentinel" or record.get("clean") is not True
            or int(record.get("timestamp_ms") or 0) < request_ms - 500):
        raise HotfixError("shutdown record does not prove this clean stop")
    if SP.pids(state) or SP.listener(port):
        raise HotfixError("post-stop identity check failed: pair state ambiguous; check whether pair is down and use --rollback only after operator verification")
    return record


def tracked_start_ui(port: int, launch_env: dict[str, str] | None = None) -> None:
    result = subprocess.run([sys.executable, str(OPS / "stop_pair.py"), "--track-ui", "--port", str(port)],
                            capture_output=True, text=True, env=child_env(launch_env), timeout=20)
    if result.returncode:
        raise HotfixError("could not record the new UI identity: " +
                          str(result.stderr or result.stdout or "no child output")[-2000:])


def prove_restored_pair(state: Path, port: int, started: dict[str, Any],
                        requested_ms: int, expected_root: Path,
                        expected_sha: str) -> None:
    """Rollback is proved by the old live pair and fresh Core heartbeat, not a spawn ack."""
    engine_pid, ui_pid = int(started.get("engine_pid") or 0), int(started.get("ui_pid") or 0)
    if not engine_pid or not ui_pid:
        raise HotfixError("rollback proof: missing engine/UI pid")
    deadline = time.monotonic() + 45.0
    while time.monotonic() < deadline:
        identity, root, sha, tracked_ui = validate_pair(state, port)
        if (int(identity.get("pid") or identity.get("process_id") or 0) != engine_pid
                or tracked_ui != ui_pid or SP.listener(port) != ui_pid
                or root != expected_root or sha != expected_sha):
            raise HotfixError("rollback proof: old engine/UI pid, listener or SHA mismatch")
        if first_healthy_cycle(state, engine_pid, requested_ms) is not None:
            return
        time.sleep(0.5)
    raise HotfixError("rollback proof: old pair has no fresh healthy Core heartbeat")


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


def save_swap_proof(proof: dict[str, Any], source_metadata: dict[str, Any] | None = None) -> Path:
    """Persist the coverage proof beside the swap record.

    The proof is written to its own file next to LAST_SWAP, so the accepted merge count and
    bucket metadata survive the run. It never touches audited state or any ledger.
    """
    target = LAST_SWAP.with_name(LAST_SWAP.stem + "_proof.json")
    atomic_json(target, {"proof": proof, "source": source_metadata or {},
                         "saved_at": datetime.now(timezone.utc).isoformat()})
    return target


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
    api_url = leader_api_url(state, env)
    # A header-only/stale local CSV is never sufficient. Probe external source BEFORE stop.
    api_source_capability(wallets, api_url)
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
    stop_pair(state, port, dict(env))
    try:
        old_pair_down_ms = int(time.time() * 1000)
        rewrite_launch_spec(spec, new_root, target_sha, state)
        atomic_text(pointer_path(state), str(state))
        start_info = start_pair(new_root, target_sha, state, port, dict(env))
        tracked_start_ui(port, dict(env))
        engine_pid = int(start_info["engine_pid"])
        deadline = time.monotonic() + REPLAY_TIMEOUT_S
        first_cycle: tuple[int, dict[str, Any]] | None = None
        proof: dict[str, int] | None = None
        source: Path | None = None
        source_meta: dict[str, Any] | None = None
        last_bucket_failure: str | None = None
        while time.monotonic() < deadline:
            if first_cycle is None:
                first_cycle = first_healthy_cycle(state, engine_pid, old_pair_down_ms)
            if first_cycle is not None:
                # Pin the first healthy timestamp and fetch exactly ONCE after that cycle.
                # Repeated retries only re-read the same proven source; no stale pre-stop CSV.
                if source is None:
                    source, source_meta = export_api_source(
                        wallets, old_pair_down_ms, first_cycle[0], target_sha, api_url)
                try:
                    proof = replay_proof(state, baseline, sent_before, source, old_pair_down_ms,
                                         first_cycle[0], wallets, source_meta)
                    break
                except HotfixError as exc:
                    # A lagging poll/copy cycle is expected during the attached watch; invariant drift is not.
                    # Bounded catch-up: a bucket can be short of intent rows only because the
                    # audit row has not flushed yet. That is transient and must be rechecked until
                    # the replay deadline; invariant drift and duplicate sends still fail at once
                    # because they raise different messages.
                    _msg = str(exc)
                    if "bucket coverage FAIL" in _msg:
                        # Remember the named bucket so a terminal timeout reports WHICH bucket
                        # never reconciled instead of a bare "watch timed out".
                        last_bucket_failure = _msg
                    _transient = ("not caught up" in _msg or "unresolved rows" in _msg
                                  or "missing order_intents" in _msg or "bucket coverage FAIL" in _msg)
                    if not _transient:
                        raise
                    print("REPLAY WATCH transient: " + _msg[:1500], flush=True)
            else:
                print("REPLAY WATCH transient: first healthy cycle pending (engine pid %d)" %
                      engine_pid, flush=True)
            time.sleep(POLL_S)
        if first_cycle is None or proof is None:
            raise HotfixError(_replay_timeout_message(last_bucket_failure))
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
        print("  merged_buckets               %d" % proof["merged_buckets"])
        print("  duplicate_attempts           %d" % proof["duplicate_attempts"])
        print("  UNRESOLVED                   %d" % proof["unresolved"])
        print("  poll_wallets_caught_up       %d" % proof["cursors_caught_up"])
        # Preserve explicit rollback target when the new build stays running (including gap failure).
        save_swap_record(old_root, old_sha, new_root, target_sha, state, port, backup)
        # C7-DIR-43(4): persist the coverage proof beside the swap record, untouched by state/ledgers.
        proof_path = save_swap_proof(proof, source_meta)
        print("  proof_file                   %s" % proof_path)
        print("  source_fills / wallets      %d / %d" % (source_meta["total_fills"], len(source_meta["wallets"])))
        if gap_ms >= MAX_GAP_MS:
            print("FAIL: pair downtime must be under 20 seconds")
            return 1
        print("HOTFIX SWAP PASS: %s" % target_sha)
        print("STATE BACKUP: %s" % backup)
        return 0
    except Exception as swap_error:
        try:
            if SP.pids(state) or SP.listener(port):
                stop_pair(state, port, dict(original_spec["env"]))
            rewrite_launch_spec(copy.deepcopy(original_spec), old_root, old_sha, state)
            atomic_text(pointer_path(state), str(state))
            restore_requested_ms = int(time.time() * 1000)
            restored = start_pair(old_root, old_sha, state, port, dict(original_spec["env"]))
            tracked_start_ui(port, dict(original_spec["env"]))
            prove_restored_pair(state, port, restored, restore_requested_ms, old_root, old_sha)
        except Exception as rollback_error:
            # A second failure must never erase the initiating failure: both
            # reasons are required for recovery decisions and operator diagnosis.
            raise HotfixError("swap failed (original: %s); previous pair NOT proven restored "
                              "(rollback: %s)" %
                              (str(swap_error)[-2000:], str(rollback_error)[-2000:])) from rollback_error
        # Preserve the last named bucket in the operator-visible rollback error.
        # Leave unrelated failure messages generic.
        detail = ("; " + str(swap_error)) if "last failed bucket:" in str(swap_error) else ""
        raise HotfixError("swap failed; previous pair restored" + detail) from swap_error

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
