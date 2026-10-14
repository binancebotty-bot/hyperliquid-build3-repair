#!/usr/bin/env python3
"""
Independent static census for Build 3 invariants 6-9.
Does NOT import engine/UI code. Pure AST + text analysis.

Invariants:
  ENG-INV-06: No new engine/runtime around Build 3 (single process, single .order() site, no new deps)
  ENG-INV-07: Leader mutable state isolated by (wallet, coin)
  ENG-INV-08: Startup/recovery truth includes all perp DEX scopes (default + HIP-3/builder)
  ENG-INV-09: Exchange truth outranks local replay (manual follower-position file not authoritative)

Usage:
  python census_inv_06_09.py --engine-dir <path> [--mutate]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ── helpers ──────────────────────────────────────────────────────────────────

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def file_lines(path: Path) -> int:
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def all_py_files(engine_dir: Path) -> List[Path]:
    """All .py files under engine_dir, excluding _archive and test files."""
    result = []
    for p in sorted(engine_dir.rglob("*.py")):
        parts = set(p.parts)
        if "_archive" in parts:
            continue
        if "test_" in p.name or "_test" in p.name:
            continue
        result.append(p)
    return result


# ── ENG-INV-06: No new engine/runtime around Build 3 ─────────────────────────

def check_inv06(engine_dir: Path) -> Dict[str, Any]:
    """
    Checks:
      - Exactly one physical .order() call site in the Core engine
      - No subprocess/os.system/Popen spawns in the Core engine
      - No new third-party imports beyond stdlib + known engine deps
      - No new persistent store constructors (sqlite3.connect, etc.)
    """
    # Scope: the Core engine file only (not the UI/dry-run service)
    core_file = None
    for candidate in [
        engine_dir / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py",
        engine_dir / "HL_Live_Copy_Service_Core.py",
    ]:
        if candidate.exists():
            core_file = candidate
            break

    if core_file is None:
        return {
            "id": "ENG-INV-06",
            "result": "FAIL",
            "checks": {"core_file_found": False},
            "error": "Core engine file not found",
        }

    py_files = [core_file]

    order_call_sites: List[Dict[str, Any]] = []
    process_spawns: List[Dict[str, Any]] = []
    file_writers: List[Dict[str, Any]] = []
    third_party_imports: Dict[str, List[str]] = defaultdict(list)
    persistent_stores: List[Dict[str, Any]] = []

    # Known stdlib modules (including platform-specific ones used by the engine)
    STDLIB = {
        "argparse", "atexit", "csv", "hashlib", "json", "math", "os", "re",
        "queue", "signal", "sys", "threading", "time", "traceback",
        "dataclasses", "decimal", "datetime", "pathlib", "typing",
        "collections", "contextlib", "copy", "enum", "functools", "io",
        "itertools", "logging", "operator", "random", "shutil", "socket",
        "ssl", "string", "struct", "subprocess", "tempfile", "textwrap",
        "unittest", "urllib", "uuid", "warnings", "weakref", "zipfile",
        "zoneinfo", "http", "email", "base64", "binascii", "calendar",
        "concurrent", "ctypes", "difflib", "filecmp", "fnmatch", "getpass",
        "glob", "gzip", "heapq", "hmac", "html", "imp", "importlib", "inspect",
        "keyword", "linecache", "locale", "mimetypes", "msvcrt", "multiprocessing",
        "numbers", "platform", "pprint", "profile", "pstats", "pwd",
        "py_compile", "pyclbr", "pydoc", "quopri", "reprlib", "rlcompleter",
        "runpy", "sched", "secrets", "select", "selectors", "shelve",
        "shlex", "site", "smtplib", "sndhdr", "socketserver", "sre_compile",
        "sre_constants", "sre_parse", "stat", "statistics", "stringprep",
        "symtable", "sysconfig", "tabnanny", "tarfile", "telnetlib",
        "termios", "test", "this", "token", "tokenize", "trace",
        "tracemalloc", "tty", "turtle", "types", "unicodedata",
        "uu", "venv", "wave", "webbrowser", "wsgiref", "xdrlib",
        "xml", "xmlrpc", "zipimport", "zlib", "__future__", "builtins",
        "graphlib", "tomllib", "fcntl",
    }

    # Known engine-local modules (not third-party)
    ENGINE_LOCAL = {
        "exchange_truth", "convergence_shadow", "HL_Live_Copy_Service_Core",
        "HL_Live_Copy_Service", "HL_Copy_App_SSOT",
    }

    # Known allowed third-party deps for Build 3
    ALLOWED_THIRD_PARTY = {
        "requests", "websocket", "eth_account", "hyperliquid",
        "fastapi", "uvicorn", "pydantic", "starlette",
    }

    for fpath in py_files:
        rel = str(fpath.relative_to(engine_dir)) if engine_dir in fpath.parents else str(fpath)
        try:
            source = fpath.read_text(encoding="utf-8-sig", errors="replace")
            tree = ast.parse(source, filename=str(fpath))
        except (SyntaxError, Exception):
            continue

        for node in ast.walk(tree):
            # .order() call sites
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "order":
                    order_call_sites.append({
                        "file": rel,
                        "line": node.lineno,
                        "col": node.col_offset,
                    })

            # Process spawns
            if isinstance(node, ast.Call):
                func = node.func
                name = ""
                if isinstance(func, ast.Attribute):
                    name = func.attr
                elif isinstance(func, ast.Name):
                    name = func.id
                if name in ("Popen", "run", "call", "check_output", "check_call", "system", "spawn", "spawnl", "spawnv"):
                    # Check if it's subprocess.X or os.X
                    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                        mod = func.value.id
                        if mod in ("subprocess", "os", "multiprocessing"):
                            process_spawns.append({
                                "file": rel,
                                "line": node.lineno,
                                "call": f"{mod}.{name}",
                            })

            # File writers (open with 'w'/'a' mode, or write_text, or to_csv, etc.)
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute):
                    if func.attr in ("write_text", "write_bytes", "writelines"):
                        file_writers.append({
                            "file": rel,
                            "line": node.lineno,
                            "call": func.attr,
                        })
                    elif func.attr == "to_csv":
                        file_writers.append({
                            "file": rel,
                            "line": node.lineno,
                            "call": "to_csv",
                        })

            # Persistent stores
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "connect":
                    if isinstance(func.value, ast.Name) and func.value.id in ("sqlite3", "psycopg2", "pymysql", "redis"):
                        persistent_stores.append({
                            "file": rel,
                            "line": node.lineno,
                            "call": f"{func.value.id}.connect",
                        })

            # Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name.split(".")[0]
                    if mod not in STDLIB and mod not in ENGINE_LOCAL:
                        third_party_imports[mod].append(rel)
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    mod = node.module.split(".")[0]
                    if mod not in STDLIB and mod not in ENGINE_LOCAL:
                        third_party_imports[mod].append(rel)

    # Evaluate
    unexpected_third_party = {k: v for k, v in third_party_imports.items() if k not in ALLOWED_THIRD_PARTY}

    checks = {
        "single_order_call_site": len(order_call_sites) == 1,
        "no_process_spawns": len(process_spawns) == 0,
        "no_new_third_party_imports": len(unexpected_third_party) == 0,
        "no_persistent_store": len(persistent_stores) == 0,
    }

    passed = all(checks.values())

    return {
        "id": "ENG-INV-06",
        "result": "PASS" if passed else "FAIL",
        "checks": checks,
        "order_call_sites": order_call_sites,
        "process_spawns": process_spawns,
        "unexpected_third_party_imports": dict(unexpected_third_party),
        "persistent_stores": persistent_stores,
        "total_py_files_scanned": len(py_files),
        "allowed_third_party_found": {k: v for k, v in third_party_imports.items() if k in ALLOWED_THIRD_PARTY},
    }


# ── ENG-INV-07: Leader mutable state isolated by (wallet, coin) ─────────────

def check_inv07(engine_dir: Path) -> Dict[str, Any]:
    """
    Checks that leader mutable state is keyed by (wallet, coin):
      - sleeve_id() uses both wallet and coin
      - position_id() uses wallet, coin, direction, and intent
      - No global leader state that mixes wallets
      - The LeaderState class stores per-(wallet,coin) sleeves
    """
    # Find the Core engine file
    core_file = None
    for candidate in [
        engine_dir / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py",
        engine_dir / "HL_Live_Copy_Service_Core.py",
    ]:
        if candidate.exists():
            core_file = candidate
            break

    if core_file is None:
        return {
            "id": "ENG-INV-07",
            "result": "FAIL",
            "checks": {"core_file_found": False},
            "error": "Core engine file not found",
        }

    source = core_file.read_text(encoding="utf-8-sig", errors="replace")
    tree = ast.parse(source, filename=str(core_file))

    checks: Dict[str, bool] = {}
    details: Dict[str, Any] = {}

    # Check 1: sleeve_id function uses both wallet and coin
    sleeve_id_found = False
    sleeve_id_uses_wallet = False
    sleeve_id_uses_coin = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "sleeve_id":
            sleeve_id_found = True
            # Check arguments
            arg_names = [a.arg for a in node.args.args]
            sleeve_id_uses_wallet = "wallet" in arg_names
            sleeve_id_uses_coin = "coin" in arg_names
            # Check body for f-string or concatenation using both
            body_src = ast.get_source_segment(source, node) or ""
            uses_both_in_body = ("wallet" in body_src and "coin" in body_src)
            checks["sleeve_id_uses_wallet_and_coin"] = sleeve_id_uses_wallet and sleeve_id_uses_coin and uses_both_in_body
            details["sleeve_id_args"] = arg_names
            details["sleeve_id_body"] = body_src[:500]
            break
    checks["sleeve_id_function_exists"] = sleeve_id_found

    # Check 2: position_id function uses wallet, coin, direction
    position_id_found = False
    position_id_uses_all = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "position_id":
            position_id_found = True
            arg_names = [a.arg for a in node.args.args]
            body_src = ast.get_source_segment(source, node) or ""
            uses_all = all(k in body_src for k in ("wallet", "coin", "direction"))
            position_id_uses_all = uses_all
            checks["position_id_uses_wallet_coin_direction"] = uses_all
            details["position_id_args"] = arg_names
            break
    checks["position_id_function_exists"] = position_id_found

    # Check 3: ManualLedger class has per-(wallet,coin) sleeve storage
    # The actual class name in Build 3 is ManualLedger (stores leader sleeves by wallet+coin)
    # Data is stored as self.data["by_wallet"][wallet][coin] = sleeve dict
    manual_ledger_found = False
    manual_ledger_has_sleeves = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ManualLedger":
            manual_ledger_found = True
            class_src = ast.get_source_segment(source, node) or ""
            # Check for by_wallet nested dict pattern (setdefault("by_wallet",...) or data["by_wallet"])
            has_by_wallet_pattern = (
                'setdefault("by_wallet"' in class_src
                or "by_wallet" in class_src
            )
            # Check for nested wallet->coin dict (wallet_map = by_wallet.setdefault(w, {}))
            has_nested_wallet_coin = (
                "wallet_map" in class_src
                and "setdefault" in class_src
                and "by_wallet" in class_src
            )
            # Check for sleeve method that takes wallet and coin
            has_sleeve_method = False
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "sleeve":
                    arg_names = [a.arg for a in item.args.args]
                    if "wallet" in arg_names and "coin" in arg_names:
                        has_sleeve_method = True
                        details["sleeve_method_args"] = arg_names
            manual_ledger_has_sleeves = has_by_wallet_pattern and has_nested_wallet_coin and has_sleeve_method
            details["manual_ledger_has_by_wallet"] = has_by_wallet_pattern
            details["manual_ledger_has_nested_wallet_coin"] = has_nested_wallet_coin
            details["manual_ledger_has_sleeve_method"] = has_sleeve_method
            checks["manual_ledger_has_per_wallet_coin_sleeves"] = manual_ledger_has_sleeves
            break
    checks["manual_ledger_class_exists"] = manual_ledger_found

    # Check 4: No global mutable leader state (module-level dicts keyed only by coin)
    global_leader_dicts = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    name = target.id.lower()
                    if "leader" in name and ("state" in name or "position" in name or "sleeve" in name):
                        # Check if it's a Dict literal
                        if isinstance(node.value, ast.Dict):
                            global_leader_dicts.append({
                                "name": target.id,
                                "line": node.lineno,
                            })
    checks["no_global_leader_state_mixing_wallets"] = len(global_leader_dicts) == 0
    details["global_leader_dicts"] = global_leader_dicts

    # Check 5: sleeve() method takes wallet and coin
    sleeve_method_found = False
    sleeve_method_uses_both = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "sleeve":
            arg_names = [a.arg for a in node.args.args]
            sleeve_method_found = True
            sleeve_method_uses_both = "wallet" in arg_names and "coin" in arg_names
            checks["sleeve_method_takes_wallet_and_coin"] = sleeve_method_uses_both
            details["sleeve_method_args"] = arg_names
            break
    checks["sleeve_method_exists"] = sleeve_method_found

    passed = all(checks.values())

    return {
        "id": "ENG-INV-07",
        "result": "PASS" if passed else "FAIL",
        "checks": checks,
        "details": details,
        "core_file": str(core_file),
    }


# ── ENG-INV-08: Startup/recovery truth includes all perp DEX scopes ──────────

def check_inv08(engine_dir: Path) -> Dict[str, Any]:
    """
    Checks that startup/recovery truth includes all perp DEX scopes:
      - list_perp_dexes() enumerates default + HIP-3/builder DEXes
      - master_account_net() iterates over all dexes
      - master_exposure() iterates over all dexes
      - master_userfills_all_dexes() iterates over all dexes
      - Missing scope fails closed (returns ok=False)
    """
    # Find exchange_truth.py
    et_file = None
    for candidate in [
        engine_dir / "_archive" / "hl_stage2" / "exchange_truth.py",
        engine_dir / "exchange_truth.py",
    ]:
        if candidate.exists():
            et_file = candidate
            break

    if et_file is None:
        return {
            "id": "ENG-INV-08",
            "result": "FAIL",
            "checks": {"exchange_truth_file_found": False},
            "error": "exchange_truth.py not found",
        }

    source = et_file.read_text(encoding="utf-8-sig", errors="replace")
    tree = ast.parse(source, filename=str(et_file))

    checks: Dict[str, bool] = {}
    details: Dict[str, Any] = {}

    # Check 1: list_perp_dexes function exists and returns default + HIP-3
    list_dexes_found = False
    list_dexes_includes_default = False
    list_dexes_includes_hip3 = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "list_perp_dexes":
            list_dexes_found = True
            body_src = ast.get_source_segment(source, node) or ""
            list_dexes_includes_default = '""' in body_src or "names = ['']" in body_src or 'names = [""]' in body_src
            list_dexes_includes_hip3 = "perpDexs" in body_src or "dexes" in body_src
            details["list_perp_dexes_body"] = body_src[:800]
            break
    checks["list_perp_dexes_function_exists"] = list_dexes_found
    checks["list_perp_dexes_includes_default_scope"] = list_dexes_includes_default
    checks["list_perp_dexes_enumerates_all_scopes"] = list_dexes_includes_hip3

    # Check 2: master_account_net iterates over all dexes
    man_found = False
    man_iterates_dexes = False
    man_fails_closed = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "master_account_net":
            man_found = True
            body_src = ast.get_source_segment(source, node) or ""
            man_iterates_dexes = "for dex in" in body_src or "for dex in dexes" in body_src
            man_fails_closed = "SCOPE_UNAVAILABLE" in body_src or "ok.*False" in body_src
            details["master_account_net_body"] = body_src[:800]
            break
    checks["master_account_net_exists"] = man_found
    checks["master_account_net_iterates_all_dexes"] = man_iterates_dexes
    checks["master_account_net_fails_closed_on_missing_scope"] = man_fails_closed

    # Check 3: master_exposure iterates over all dexes
    me_found = False
    me_iterates_dexes = False
    me_fails_closed = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "master_exposure":
            me_found = True
            body_src = ast.get_source_segment(source, node) or ""
            me_iterates_dexes = "for dex in" in body_src
            me_fails_closed = "SCOPE_UNAVAILABLE" in body_src
            details["master_exposure_body"] = body_src[:800]
            break
    checks["master_exposure_exists"] = me_found
    checks["master_exposure_iterates_all_dexes"] = me_iterates_dexes
    checks["master_exposure_fails_closed_on_missing_scope"] = me_fails_closed

    # Check 4: master_userfills_all_dexes iterates over all dexes
    muf_found = False
    muf_iterates_dexes = False
    muf_fails_closed = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "master_userfills_all_dexes":
            muf_found = True
            body_src = ast.get_source_segment(source, node) or ""
            muf_iterates_dexes = "for dex in" in body_src
            muf_fails_closed = "TRUTH_UNAVAILABLE" in body_src
            details["master_userfills_all_dexes_body"] = body_src[:800]
            break
    checks["master_userfills_all_dexes_exists"] = muf_found
    checks["master_userfills_all_dexes_iterates_all_dexes"] = muf_iterates_dexes
    checks["master_userfills_all_dexes_fails_closed"] = muf_fails_closed

    # Check 5: The Core engine calls list_perp_dexes at startup
    core_file = None
    for candidate in [
        engine_dir / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py",
        engine_dir / "HL_Live_Copy_Service_Core.py",
    ]:
        if candidate.exists():
            core_file = candidate
            break
    if core_file:
        core_source = core_file.read_text(encoding="utf-8-sig", errors="replace")
        core_tree = ast.parse(core_source, filename=str(core_file))
        calls_list_dexes = False
        for node in ast.walk(core_tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id == "list_perp_dexes":
                    calls_list_dexes = True
                elif isinstance(func, ast.Attribute) and func.attr == "list_perp_dexes":
                    calls_list_dexes = True
        checks["core_calls_list_perp_dexes_at_startup"] = calls_list_dexes
    else:
        checks["core_calls_list_perp_dexes_at_startup"] = False

    passed = all(checks.values())

    return {
        "id": "ENG-INV-08",
        "result": "PASS" if passed else "FAIL",
        "checks": checks,
        "details": details,
        "exchange_truth_file": str(et_file),
    }


# ── ENG-INV-09: Exchange truth outranks local replay ─────────────────────────

def check_inv09(engine_dir: Path) -> Dict[str, Any]:
    """
    Checks that exchange truth outranks local replay:
      - manual_live_positions.json is NOT used as authoritative truth
      - Exchange truth (clearinghouseState, userFillsByTime) is the source of ACTUAL
      - The engine reads exchange truth for position/fill verification
      - Local files are only used for audit/reconciliation, not as trading authority
    """
    core_file = None
    for candidate in [
        engine_dir / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py",
        engine_dir / "HL_Live_Copy_Service_Core.py",
    ]:
        if candidate.exists():
            core_file = candidate
            break

    if core_file is None:
        return {
            "id": "ENG-INV-09",
            "result": "FAIL",
            "checks": {"core_file_found": False},
            "error": "Core engine file not found",
        }

    source = core_file.read_text(encoding="utf-8-sig", errors="replace")
    tree = ast.parse(source, filename=str(core_file))

    checks: Dict[str, bool] = {}
    details: Dict[str, Any] = {}

    # Check 1: manual_live_positions.json is defined as a file path but NOT read as authoritative truth
    # It should be written to (audit) but not used as the source of ACTUAL position
    manual_pos_reads = []
    manual_pos_writes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in ("read_text", "read_bytes", "json_load", "load"):
                # Check if reading manual_live_positions
                if isinstance(node.func, ast.Attribute):
                    # Check the value being read
                    if isinstance(node.func.value, ast.Name):
                        if "manual" in node.func.value.id.lower() and "position" in node.func.value.id.lower():
                            manual_pos_reads.append({"line": node.lineno, "var": node.func.value.id})
            if isinstance(func, ast.Attribute) and func.attr in ("write_text", "write_bytes", "json_dump", "dump"):
                if isinstance(node.func.value, ast.Name):
                    if "manual" in node.func.value.id.lower() and "position" in node.func.value.id.lower():
                        manual_pos_writes.append({"line": node.lineno, "var": node.func.value.id})

    # Check 2: The engine uses exchange truth (clearinghouseState, userFillsByTime) for ACTUAL
    uses_clearinghouse = "clearinghouseState" in source
    uses_userfills = "userFillsByTime" in source
    checks["engine_uses_clearinghouse_state_for_actual"] = uses_clearinghouse
    checks["engine_uses_userfills_for_settlement"] = uses_userfills

    # Check 3: The engine does NOT use manual_live_positions as authoritative for trading decisions
    # Look for patterns where manual positions are used in convergence/trading logic
    manual_in_trading = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if "manual" in node.id.lower() and "position" in node.id.lower():
                # Check if used in a trading context (convergence, order sizing, etc.)
                # This is a heuristic: if the variable name appears near convergence/order logic
                pass  # We'll check via source text analysis below

    # Text-based check: look for manual_live_positions being read and used in convergence
    lines = source.split("\n")
    manual_pos_var = None
    for i, line in enumerate(lines):
        if "MANUAL_LIVE_POSITIONS_FILE" in line and "=" in line:
            manual_pos_var = line.split("=")[0].strip()
            break

    if manual_pos_var:
        # Check if the variable is read (not just defined)
        read_pattern = re.compile(rf'{re.escape(manual_pos_var)}\s*\.\s*(read|load|open|exists)')
        write_pattern = re.compile(rf'{re.escape(manual_pos_var)}\s*\.\s*(write|dump|save|open)')
        is_read = bool(read_pattern.search(source))
        is_written = bool(write_pattern.search(source))
        details["manual_pos_var"] = manual_pos_var
        details["manual_pos_is_read"] = is_read
        details["manual_pos_is_written"] = is_written
        # The file should be written (audit) but NOT read as authoritative truth
        checks["manual_positions_not_read_as_authoritative"] = not is_read
    else:
        checks["manual_positions_not_read_as_authoritative"] = True  # Not used at all = not authoritative

    # Check 4: Exchange truth module is imported and used
    imports_exchange_truth = "exchange_truth" in source or "_XNET" in source
    checks["engine_imports_exchange_truth"] = imports_exchange_truth

    # Check 5: The engine uses master_account_net or master_exposure for ACTUAL position
    uses_master_net = "master_account_net" in source or "master_exposure" in source
    checks["engine_uses_master_exchange_truth"] = uses_master_net

    # Check 6: Settlement verification uses exchange truth
    # The Core engine uses ExchangeReconciler + _XNET.master_exposure for settlement
    uses_settlement_verification = (
        "resolve_settlement" in source
        or "master_userfills" in source
        or "ExchangeReconciler" in source
        or "_XNET.master_exposure" in source
        or "_XNET.master_account_net" in source
    )
    checks["engine_verifies_settlement_via_exchange"] = uses_settlement_verification

    passed = all(checks.values())

    return {
        "id": "ENG-INV-09",
        "result": "PASS" if passed else "FAIL",
        "checks": checks,
        "details": details,
        "core_file": str(core_file),
    }


# ── Mutation tests ───────────────────────────────────────────────────────────

def run_mutation_tests(engine_dir: Path, results: Dict[str, Any]) -> Dict[str, Any]:
    """
    For each invariant, create a mutated copy that breaks the invariant and verify the check FAILS.
    This proves the check is non-vacuous.
    """
    import tempfile
    import shutil

    mutations = {}

    # ── INV-06 mutation: add a second .order() call site ──
    with tempfile.TemporaryDirectory() as tmpdir:
        mutated = Path(tmpdir) / "mutated"
        shutil.copytree(engine_dir / "_archive" / "hl_stage2", mutated / "hl_stage2")
        core = mutated / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
        if core.exists():
            src = core.read_text(encoding="utf-8")
            # Add a second .order() call
            src += "\n\ndef _mutant_extra_order():\n    exchange.order({})  # MUTANT: second order site\n"
            core.write_text(src, encoding="utf-8")
            r = check_inv06(mutated)
            mutations["INV-06_second_order_site"] = {
                "mutation": "Added second .order() call site",
                "expected": "FAIL",
                "actual": r["result"],
                "non_vacuous": r["result"] == "FAIL",
            }

    # ── INV-07 mutation: remove wallet from sleeve_id ──
    with tempfile.TemporaryDirectory() as tmpdir:
        mutated = Path(tmpdir) / "mutated"
        shutil.copytree(engine_dir / "_archive" / "hl_stage2", mutated / "hl_stage2")
        core = mutated / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
        if core.exists():
            src = core.read_text(encoding="utf-8")
            # Mutate sleeve_id to only use coin (remove wallet)
            src = src.replace(
                'def sleeve_id(wallet: str, coin: str) -> str:\n    return f"{normalise_wallet(wallet)}::{canonical_coin_key(coin)}"',
                'def sleeve_id(wallet: str, coin: str) -> str:\n    return f"{canonical_coin_key(coin)}"  # MUTANT: removed wallet'
            )
            core.write_text(src, encoding="utf-8")
            r = check_inv07(mutated)
            mutations["INV-07_remove_wallet_from_sleeve_id"] = {
                "mutation": "Removed wallet from sleeve_id function",
                "expected": "FAIL",
                "actual": r["result"],
                "non_vacuous": r["result"] == "FAIL",
            }

    # ── INV-08 mutation: remove HIP-3 DEX enumeration ──
    with tempfile.TemporaryDirectory() as tmpdir:
        mutated = Path(tmpdir) / "mutated"
        shutil.copytree(engine_dir / "_archive" / "hl_stage2", mutated / "hl_stage2")
        et = mutated / "hl_stage2" / "exchange_truth.py"
        if et.exists():
            src = et.read_text(encoding="utf-8")
            # Mutate list_perp_dexes to only return default scope
            src = src.replace(
                'names = [""]',
                'names = [""]  # MUTANT: removed HIP-3 enumeration'
            )
            # Also remove the loop that adds HIP-3 dexes
            src = src.replace(
                'for item in (res["data"] if isinstance(res["data"], list) else []):',
                'for item in []:  # MUTANT: removed HIP-3 enumeration'
            )
            et.write_text(src, encoding="utf-8")
            r = check_inv08(mutated)
            mutations["INV-08_remove_hip3_enumeration"] = {
                "mutation": "Removed HIP-3/builder DEX enumeration from list_perp_dexes",
                "expected": "FAIL",
                "actual": r["result"],
                "non_vacuous": r["result"] == "FAIL",
            }

    # ── INV-09 mutation: make manual positions authoritative ──
    with tempfile.TemporaryDirectory() as tmpdir:
        mutated = Path(tmpdir) / "mutated"
        shutil.copytree(engine_dir / "_archive" / "hl_stage2", mutated / "hl_stage2")
        core = mutated / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
        if core.exists():
            src = core.read_text(encoding="utf-8")
            # Add a read of manual_live_positions as authoritative truth
            src += "\n\ndef _mutant_read_manual_positions():\n    with open(MANUAL_LIVE_POSITIONS_FILE) as f:\n        return json.load(f)  # MUTANT: manual positions as authoritative\n"
            core.write_text(src, encoding="utf-8")
            r = check_inv09(mutated)
            mutations["INV-09_manual_positions_authoritative"] = {
                "mutation": "Added manual_live_positions.json read as authoritative truth",
                "expected": "FAIL",
                "actual": r["result"],
                "non_vacuous": r["result"] == "FAIL",
            }

    return mutations


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build 3 invariants 6-9 static census")
    parser.add_argument("--engine-dir", required=True, help="Path to the engine root directory")
    parser.add_argument("--mutate", action="store_true", help="Run mutation tests")
    parser.add_argument("--output", default=None, help="Output JSON file path")
    args = parser.parse_args()

    engine_dir = Path(args.engine_dir).resolve()
    if not engine_dir.exists():
        print(f"ERROR: engine dir not found: {engine_dir}", file=sys.stderr)
        sys.exit(2)

    # Record commit info
    import subprocess
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(engine_dir), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        commit = "unknown"

    tested_at = datetime.now(timezone.utc).isoformat()

    # Run checks
    inv06 = check_inv06(engine_dir)
    inv07 = check_inv07(engine_dir)
    inv08 = check_inv08(engine_dir)
    inv09 = check_inv09(engine_dir)

    # File hashes for the key files
    file_hashes = {}
    for fpath in [
        engine_dir / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py",
        engine_dir / "_archive" / "hl_stage2" / "exchange_truth.py",
        engine_dir / "_archive" / "hl_stage2" / "convergence_shadow.py",
    ]:
        if fpath.exists():
            file_hashes[str(fpath.relative_to(engine_dir))] = {
                "sha256": sha256_file(fpath),
                "lines": file_lines(fpath),
            }

    results = {
        "tested_commit": commit,
        "tested_at_utc": tested_at,
        "engine_dir": str(engine_dir),
        "file_hashes": file_hashes,
        "invariants": {
            "ENG-INV-06": inv06,
            "ENG-INV-07": inv07,
            "ENG-INV-08": inv08,
            "ENG-INV-09": inv09,
        },
    }

    # Mutation tests
    if args.mutate:
        mutations = run_mutation_tests(engine_dir, results)
        results["mutation_tests"] = mutations

    # Output
    output_json = json.dumps(results, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"Results written to {args.output}")
    else:
        print(output_json)

    # Summary
    print("\n=== SUMMARY ===")
    for inv_id, inv_result in results["invariants"].items():
        print(f"  {inv_id}: {inv_result['result']}")
        for check_name, check_val in inv_result.get("checks", {}).items():
            status = "PASS" if check_val else "FAIL"
            print(f"    {status}: {check_name}")

    if args.mutate and "mutation_tests" in results:
        print("\n=== MUTATION TESTS (non-vacuity proof) ===")
        for mut_name, mut_result in results["mutation_tests"].items():
            status = "PASS" if mut_result["non_vacuous"] else "FAIL"
            print(f"  {status}: {mut_name} -> {mut_result['actual']} (expected {mut_result['expected']})")

    # Exit code
    all_pass = all(r["result"] == "PASS" for r in results["invariants"].values())
    if args.mutate:
        all_pass = all_pass and all(m["non_vacuous"] for m in results.get("mutation_tests", {}).values())
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
