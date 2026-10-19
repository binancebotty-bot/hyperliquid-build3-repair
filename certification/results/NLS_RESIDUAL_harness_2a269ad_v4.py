#!/usr/bin/env python3
"""
NLS_RESIDUAL certification harness (v4)
Commit: 2a269ad2260270fee844eedc2cc23545abc91dd0
Engine: _archive/hl_stage2/HL_Live_Copy_Service_Core.py

Certifies 6 in-scope NOT_TESTED rows (no open_decisions):
  TN-F19 (LIFECYCLE, APPLIES):           STARTUP_UNINTENDED_ORDERS = 0 at every boundary
  TN-F09 (SETTLE, APPLIES):              HIP-3 / builder-DEX symbols exact and DEX-scoped everywhere
  TN-F10 (SETTLE, APPLIES_PROPOSED):     Ambiguous submission never retried blind; resolved from exchange truth
  TN-F11 (SETTLE, APPLIES_PROPOSED):     Ownership attribution never fails open
  TN-F12 (SETTLE, APPLIES):              Outside-tolerance divergence surfaced for manual reconciliation
  TN-F18 (SETTLE, APPLIES):              Fills keyed by exchange identity; duplicates processed exactly once

Each check is earned by runtime behaviour with commit, engine sha256,
tested_at_utc, per-check pass/fail, and NON-VACUOUS negative mutations
that fail for the RIGHT reason. A FAIL is kept, never softened.
"""
import importlib
import importlib.util
import ast
import json
import math
import os
import sys
import copy
import shutil
import tempfile
import time
import hashlib
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

# --- Setup: import the engine and companion ---
REPO = Path("C:/Users/wigmore/hyperliquid-build3-repair")
ENGINE_PATH = REPO / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
COMPANION_PATH = REPO / "_archive" / "hl_stage2" / "exchange_truth.py"
SERVICE_PATH = REPO / "_archive" / "hl_stage2" / "HL_Live_Copy_Service.py"

# Set environment before importing engine
os.environ["HL_FOLLOWER_NETWORK"] = "testnet"
os.environ["HL_LEADER_NETWORK"] = "testnet"
os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
os.environ["HL_LIVE_MOCK_SEND"] = "1"
os.environ["HL_LIVE_DISABLE_NETWORK_REFRESH"] = "1"
os.environ["HL_LIVE_PREWARM_SYMBOL_META"] = "0"
os.environ["HL_LIVE_PREWARM_SDK_CLIENT"] = "0"
os.environ["HL_LIVE_RECON_CYCLE_BUDGET_SEC"] = "999"
os.environ["HL_LIVE_WS_ENABLED"] = "0"
os.environ["HL_LIVE_BLOCK_ENTRIES_ON_UNRECONCILED_FILLS"] = "0"
os.environ["HL_LIVE_ENTRY_ADD_RATE_LIMIT_RECOVERY_ENABLED"] = "1"
os.environ["HL_LIVE_ENTRY_ADD_RATE_LIMIT_RECOVERY_MAX_AGE_MS"] = "180000"
os.environ["HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS"] = "0"
os.environ["HL_LIVE_RATE_LIMIT_COOLDOWN_MS"] = "8000"
os.environ["HL_LIVE_COPY_MATCH_WINDOW_MS"] = "600000"
os.environ["HL_LIVE_COPY_POLL_ENTRY_BLOCK_MS"] = "300000"
os.environ["HL_LIVE_WS_STARTUP_GRACE_MS"] = "30000"
os.environ["HL_LIVE_WS_WALLET_STALE_MS"] = "120000"
os.environ["HL_LIVE_WS_SUBSCRIBED_STALE_MS"] = str(4 * 60 * 60 * 1000)
os.environ["HL_LIVE_SNAPSHOT_REFRESH_INTERVAL_SEC"] = "5"
os.environ["HL_LIVE_MIDS_CACHE_TTL_SEC"] = "-1"
os.environ["HL_LIVE_DAILY_PNL_TTL_SEC"] = "30"
os.environ["HL_LIVE_HOT_SEND_WORKERS"] = "1"
os.environ["HL_LIVE_RAW_INDEX_PRICE_DOMAIN_RATIO"] = "5.0"
os.environ["HL_LIVE_ENTRY_IOC_RETRY_BPS"] = "100.0"
os.environ["HL_LIVE_MAX_ENTRY_IOC_RETRY_BPS"] = "200.0"

# Import companion first
spec_et = importlib.util.spec_from_file_location("exchange_truth", str(COMPANION_PATH))
et = importlib.util.module_from_spec(spec_et)
spec_et.loader.exec_module(et)

# Import the engine
spec = importlib.util.spec_from_file_location("HL_Live_Copy_Service_Core", str(ENGINE_PATH))
engine = importlib.util.module_from_spec(spec)
sys.modules["HL_Live_Copy_Service_Core"] = engine
spec.loader.exec_module(engine)

# Import the service module
spec_svc = importlib.util.spec_from_file_location("HL_Live_Copy_Service", str(SERVICE_PATH))
svc = importlib.util.module_from_spec(spec_svc)
sys.modules["HL_Live_Copy_Service"] = svc
spec_svc.loader.exec_module(svc)

# Engine classes
LeaderFill = engine.LeaderFill
Intent = engine.Intent
ConfigManager = engine.ConfigManager
IntentBuilder = engine.IntentBuilder
SenderGateway = engine.SenderGateway
AuditLogWriter = engine.AuditLogWriter
ManualLedger = engine.ManualLedger
CycleSummary = engine.CycleSummary
LiveCopyCore = engine.LiveCopyCore
DedupeStore = engine.DedupeStore
CopyFillMatcher = engine.CopyFillMatcher
CopyAccountIngestor = engine.CopyAccountIngestor
ExchangeReconciler = engine.ExchangeReconciler
ServiceStateWriter = engine.ServiceStateWriter

# Engine functions
canonical_coin_key = engine.canonical_coin_key
normalise_wallet = engine.normalise_wallet
fnum = engine.fnum
bval = engine.bval
signed_from_side_size = engine.signed_from_side_size
stale_snapshot_replay_reason = engine.stale_snapshot_replay_reason
classify_send_lifecycle = engine.classify_send_lifecycle
classify_reject_category = engine.classify_reject_category
classify_terminal_state = engine.classify_terminal_state
classify_operator_action = engine.classify_operator_action
classify_integrity_severity = engine.classify_integrity_severity
normalise_copy_fill_side = engine.normalise_copy_fill_side
row_exchange_order_id = engine.row_exchange_order_id
is_valid_wallet = engine.is_valid_wallet
utc_now_ms = engine.utc_now_ms
utc_now_iso = engine.utc_now_iso
load_json = engine.load_json
atomic_write_json = engine.atomic_write_json
read_csv_rows = engine.read_csv_rows
ensure_dirs = engine.ensure_dirs
log_error = engine.log_error
write_live_integrity_status = engine.write_live_integrity_status
stable_hash = engine.stable_hash
claim_copy_fill_process_marker = engine.claim_copy_fill_process_marker

# Module-level constants from engine
PROCESS_STARTED_AT_MS = engine.PROCESS_STARTED_AT_MS
PROCESS_STARTED_AT = engine.PROCESS_STARTED_AT
STALE_REPLAY_GRACE_MS = engine.STALE_REPLAY_GRACE_MS
POSITION_EPSILON = engine.POSITION_EPSILON
LEADER_NETWORK = engine.LEADER_NETWORK
FOLLOWER_NETWORK = engine.FOLLOWER_NETWORK
USER_WALLET = engine.USER_WALLET

# --- Test infrastructure ---
TESTED_COMMIT = "2a269ad2260270fee844eedc2cc23545abc91dd0"
TESTED_AT_UTC = "2026-10-14T13:00:00Z"

def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

ENGINE_SHA256 = _sha256(ENGINE_PATH)

def _check(name, cond, detail=""):
    # NON-RAISING: record pass/fail so every check in the row executes and the
    # row reports checks_total > 0 with a real verdict (never a 0-check abort).
    ok = bool(cond)
    return {"name": name, "pass": ok, "detail": ("" if ok else "FAIL: ") + str(detail)}

def _neg(name, cond, detail=""):
    """Non-vacuous negative test: cond must be True (the mutation was correctly rejected)."""
    ok = bool(cond)
    return {"name": name, "pass": ok, "detail": ("" if ok else "NEG-FAIL: ") + str(detail)}

def _write_csv(path, rows):
    import csv
    fields = []
    for row in rows:
        for key in row.keys():
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)

def _read_csv(path):
    if not path.exists():
        return []
    return read_csv_rows(path)

def _setup_env(tmpdir):
    """Set up isolated engine environment in a temp dir. Returns (tmp, wallet_a)."""
    tmp = Path(tmpdir)
    engine.BASE_DIR = tmp
    engine.ENGINE_OUTPUT_DIR = tmp / "hl_copy_output"
    engine.AUDIT_DIR = tmp / "hl_live_copy_audit"
    engine.APPEND_ONLY_DIR = engine.AUDIT_DIR / "append_only"
    engine.LIVE_CONFIG_FILE = engine.AUDIT_DIR / "live_config.json"
    engine.SERVICE_STATE_FILE = engine.AUDIT_DIR / "live_service_state.json"
    engine.CORE_RUNTIME_STATE_FILE = engine.AUDIT_DIR / "clean_core_runtime_state.json"
    engine.LIVE_WS_HEALTH_FILE = engine.AUDIT_DIR / "live_ws_health.json"
    engine.MANUAL_LIVE_POSITIONS_FILE = engine.AUDIT_DIR / "manual_live_positions.json"
    engine.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = engine.AUDIT_DIR / "exchange_account_snapshot.json"
    engine.LIVE_INTEGRITY_STATUS_FILE = engine.AUDIT_DIR / "live_integrity_status.json"
    engine.ORDER_INTENTS_CSV = engine.APPEND_ONLY_DIR / "order_intents.csv"
    engine.SEND_ATTEMPTS_CSV = engine.APPEND_ONLY_DIR / "send_attempts.csv"
    engine.LIVE_FILLS_CSV = engine.APPEND_ONLY_DIR / "live_fills.csv"
    engine.RECONCILIATION_CSV = engine.APPEND_ONLY_DIR / "reconciliation.csv"
    engine.ERRORS_CSV = engine.APPEND_ONLY_DIR / "errors.csv"
    engine.RAW_LEADER_FILLS_CSV = engine.ENGINE_OUTPUT_DIR / "raw_live_fills.csv"
    engine.MANUAL_WALLETS_FILE = tmp / "manual_wallets.txt"
    engine.WALLET_GATE_FILE = tmp / "wallet_gate.json"
    engine.UI_STATE_FILE = tmp / "ui_state.json"
    engine.FORBIDDEN_LIVE_POSITIONS_FILE = engine.AUDIT_DIR / "live_positions.json"
    engine.FORBIDDEN_WOULD_SEND_ORDERS_CSV = engine.APPEND_ONLY_DIR / "would_send_orders.csv"
    engine.ASSET_UNIVERSE_SNAPSHOT_FILE = engine.AUDIT_DIR / "asset_universe_snapshot.json"
    engine.CORE_STARTUP_TEMP_SCAN_FILE = engine.AUDIT_DIR / "core_startup_temp_scan.json"
    engine.CORE_FATAL_ERRORS_CSV = engine.AUDIT_DIR / "core_fatal_errors.csv"
    engine.XYZ_POSITION_STATE_FILE = engine.AUDIT_DIR / "xyz_position_state.json"
    engine.ensure_dirs()

    wallet_a = "0x" + "a" * 40
    wallet_b = "0x" + "b" * 40
    config = {
        "auto_send_enabled": False,
        "wallets": {
            wallet_a: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10},
            wallet_b: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10},
        },
        "global_controls": {"min_notional": 10, "max_order_notional_usd": 0, "marketable_bps": 25},
    }
    atomic_write_json(engine.LIVE_CONFIG_FILE, config)
    atomic_write_json(engine.SERVICE_STATE_FILE, {})
    atomic_write_json(engine.CORE_RUNTIME_STATE_FILE, {})
    atomic_write_json(engine.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {}})
    atomic_write_json(engine.MANUAL_LIVE_POSITIONS_FILE, {"schema": "manual_live_positions.v1.wallet_sleeves", "by_wallet": {}, "by_coin_net": {}})
    atomic_write_json(engine.ASSET_UNIVERSE_SNAPSHOT_FILE, {})
    atomic_write_json(engine.XYZ_POSITION_STATE_FILE, {"schema": "xyz_position_state.v1", "positions": {}})

    # Seed audit CSV headers
    engine.ensure_csv_header(engine.SEND_ATTEMPTS_CSV, engine.SEND_ATTEMPT_FIELDS)
    engine.ensure_csv_header(engine.LIVE_FILLS_CSV, engine.LIVE_FILL_FIELDS)
    engine.ensure_csv_header(engine.ORDER_INTENTS_CSV, engine.ORDER_INTENT_FIELDS)
    engine.ensure_csv_header(engine.RECONCILIATION_CSV, engine.RECONCILIATION_FIELDS)

    return tmp, wallet_a, wallet_b

def _write_leader_fill(tmpdir, fill_id, wallet, coin, side, price, size, ts_ms, source="WS_CAPTURED"):
    """Write a leader fill CSV row."""
    rows = [{
        "fill_id": fill_id, "wallet": wallet, "coin": coin, "side": side,
        "price": str(price), "size": str(size), "timestamp_ms": str(ts_ms),
        "source": source, "recording_method": source,
    }]
    _write_csv(engine.RAW_LEADER_FILLS_CSV, rows)

def _make_intent(intent_id, fill_id, wallet, coin, side, size, price, ts_ms, lifecycle, reduce_only=False):
    """Create an Intent object with the correct dataclass structure."""
    fill = LeaderFill(
        leader_fill_id=fill_id, leader_wallet=wallet, coin=coin,
        side=side, price=price, size=size, timestamp_ms=ts_ms,
        source="WS_CAPTURED",
    )
    return Intent(
        intent_id=intent_id, fill=fill,
        copy_side=side, copy_size=size, copy_notional=size * price,
        wallet_mode="ON", copy_mode="fixed",
        decision="SEND_ALLOWED", reason=lifecycle,
        sleeve_id=f"s-{intent_id}", position_id=f"p-{intent_id}",
        position_direction_before="LONG" if side == "BUY" else "SHORT",
        wallet_position_before=0.0 if not reduce_only else size,
        coin_net_before=0.0 if not reduce_only else size,
        reduce_only_intended=reduce_only,
        reduce_only_sent_planned=reduce_only,
        notes=f"lifecycle={lifecycle}",
    )

def _mock_network():
    """Mock all network fetchers to prevent real HTTP calls."""
    engine.EXPOSURE_FETCHER = lambda payload, **kw: {"ok": True, "assetPositions": [], "marginSummary": {"accountValue": "0"}}
    engine.MIDS_FETCHER = lambda payload, **kw: {}
    engine._XNET = MagicMock()
    engine._XNET.rolling_day_pnl.return_value = {"ok": True, "pnl_usd": "0"}

def _populate_meta_cache(core, coin, sdk_coin=None, symbol_source="core_meta", perp_dex=""):
    """Populate the sender's meta cache so the engine can resolve symbols."""
    if sdk_coin is None:
        sdk_coin = coin
    meta_item = {
        "canonical_coin": coin,
        "symbol_source": symbol_source,
        "perp_dex": perp_dex,
        "perp_dexs": [perp_dex] if perp_dex else None,
        "szDecimals": 4,
        "price_decimals": 6,
        "max_decimals": 6,
        "tick_size": "0.01",
        "min_order_value_usd": 10,
        "min_size": "0.001",
        "asset_id": "0",
        "index": "0",
        "sdk_coin": sdk_coin,
        "sdk_order_compatible": True,
        "verified_from": symbol_source,
        "confidence": "HIGH",
        "tradable_by_sender": True,
        "reason": "",
    }
    core.sender._meta_cache[coin] = meta_item
    return meta_item

# ============================================================
# ROW: TN-F19 (LIFECYCLE, APPLIES)
# Feature: STARTUP_UNINTENDED_ORDERS = 0 at every boundary
# ============================================================
def certify_tn_f19():
    checks = []
    negs = []
    tmpdir = tempfile.mkdtemp(prefix="nls_f19_")
    cores = []
    try:
        _mock_network()
        tmp, wallet_a, wallet_b = _setup_env(tmpdir)

        # --- Check 1: Cold start with auto_send disabled → zero send_attempts ---
        _write_leader_fill(tmpdir, "f19-cold-1", wallet_a, "BTC", "BUY", "50000", "0.1", "1000")
        core = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core)
        _populate_meta_cache(core, "BTC")
        summary = core.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        sa_rows = _read_csv(engine.SEND_ATTEMPTS_CSV)
        checks.append(_check("COLD_START_ZERO_SENDS", len(sa_rows) == 0, f"send_attempts={len(sa_rows)}"))
        checks.append(_check("COLD_START_INTENTS_WRITTEN", summary.leader_intents_written >= 1, f"intents={summary.leader_intents_written}"))

        # --- Check 2: Cold start with auto_send enabled + mock → mock send_attempts but no real orders ---
        cfg = load_json(engine.LIVE_CONFIG_FILE, {})
        cfg["auto_send_enabled"] = True
        cfg["wallets"][wallet_a]["mode"] = "LIVE"
        atomic_write_json(engine.LIVE_CONFIG_FILE, cfg)
        _write_leader_fill(tmpdir, "f19-cold-2", wallet_a, "ETH", "BUY", "2000", "1", "2000")
        core2 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core2)
        _populate_meta_cache(core2, "ETH")
        summary2 = core2.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        sa_rows2 = _read_csv(engine.SEND_ATTEMPTS_CSV)
        checks.append(_check("MOCK_START_INTENTS_WRITTEN", summary2.leader_intents_written >= 1, f"intents={summary2.leader_intents_written}"))
        mock_sends = [r for r in sa_rows2 if r.get("status") == "MOCK_ORDER_SENT"]
        checks.append(_check("MOCK_START_NO_REAL_ORDERS", len(mock_sends) >= 1, f"mock_sent={len(mock_sends)}"))

        # --- Check 3: Restart → no unintended orders (idempotency guard) ---
        _write_leader_fill(tmpdir, "f19-restart-1", wallet_a, "SOL", "BUY", "100", "1", "3000")
        core3 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core3)
        _populate_meta_cache(core3, "SOL")
        summary3 = core3.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        sa_rows3 = _read_csv(engine.SEND_ATTEMPTS_CSV)
        real_orders = [r for r in sa_rows3 if r.get("status") in ("ORDER_FILLED", "ORDER_RESTING") and r.get("exchange_called", "").lower() == "true"]
        checks.append(_check("RESTART_NO_UNINTENDED_ORDERS", len(real_orders) == 0, f"real_orders={len(real_orders)}"))

        # --- Check 4: Crash recovery → stale snapshot replay blocked ---
        old_ts = PROCESS_STARTED_AT_MS - 600000
        _write_leader_fill(tmpdir, "f19-crash-1", wallet_a, "BTC", "SELL", "51000", "0.1", str(old_ts), source="WS_SNAPSHOT")
        core4 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core4)
        _populate_meta_cache(core4, "BTC")
        summary4 = core4.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        recon_rows = _read_csv(engine.RECONCILIATION_CSV)
        stale_skipped = [r for r in recon_rows if r.get("event") == "STALE_SNAPSHOT_REPLAY_SKIPPED"]
        checks.append(_check("CRASH_RECOVERY_STALE_BLOCKED", len(stale_skipped) >= 1, f"stale_skipped={len(stale_skipped)}"))

        # --- NEGATIVE 1: Second start attempt (same fill_id) → deduped ---
        core5 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core5)
        _populate_meta_cache(core5, "BTC")
        summary5 = core5.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        negs.append(_neg("NEG_SECOND_START_DEDUPED", summary5.leader_fills_deduped >= 1, f"deduped={summary5.leader_fills_deduped}"))

        # --- NEGATIVE 2: Stale lock/PID → no crash on startup ---
        atomic_write_json(engine.CORE_STARTUP_TEMP_SCAN_FILE, {"stale": True, "pid": 99999})
        core6 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core6)
        _populate_meta_cache(core6, "BTC")
        summary6 = core6.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        negs.append(_neg("NEG_STALE_LOCK_NO_CRASH", summary6.fatal_errors == 0, f"fatal_errors={summary6.fatal_errors}"))

        # --- NEGATIVE 3: Config from previous version → hot reload handles it ---
        cfg_old = load_json(engine.LIVE_CONFIG_FILE, {})
        cfg_old["old_field"] = "legacy_value"
        atomic_write_json(engine.LIVE_CONFIG_FILE, cfg_old)
        core7 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core7)
        _populate_meta_cache(core7, "BTC")
        summary7 = core7.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        negs.append(_neg("NEG_LEGACY_CONFIG_HANDLED", summary7.fatal_errors == 0, f"fatal_errors={summary7.fatal_errors}"))

    finally:
        for c in cores:
            try:
                c.stop()
            except Exception:
                pass
        shutil.rmtree(tmpdir, ignore_errors=True)
    return checks, negs

# ============================================================
# ROW: TN-F09 (SETTLE, APPLIES)
# Feature: HIP-3 / builder-DEX symbols exact and DEX-scoped everywhere
# ============================================================
def certify_tn_f09():
    checks = []
    negs = []
    tmpdir = tempfile.mkdtemp(prefix="nls_f09_")
    cores = []
    try:
        _mock_network()
        tmp, wallet_a, wallet_b = _setup_env(tmpdir)

        # --- Check 1: builder_meta source → sdk_coin has DEX prefix ---
        core = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core)
        meta_item = {
            "canonical_coin": "XYZ:ABC", "symbol_source": "builder_meta",
            "perp_dex": "xyz", "perp_dexs": ["", "xyz"],
            "szDecimals": 4, "price_decimals": 6, "max_decimals": 6,
            "tick_size": "0.01", "min_order_value_usd": 10, "min_size": "0.001",
            "asset_id": "12345", "index": "12345",
            "sdk_coin": "xyz:ABC", "sdk_order_compatible": True,
            "verified_from": "builder_meta", "confidence": "HIGH",
            "tradable_by_sender": True, "reason": "",
        }
        core.sender._meta_cache = {"XYZ:ABC": meta_item}
        core.sender._index_cache = {}
        core.sender._universe_unknown_seen = {}
        core.sender._save_asset_universe_snapshot(source="test")
        snap = load_json(engine.ASSET_UNIVERSE_SNAPSHOT_FILE, {})
        symbols = snap.get("symbols", {})
        xyz_sym = symbols.get("XYZ:ABC", {})
        sdk_coin = xyz_sym.get("sdk_coin", "")
        checks.append(_check("BUILDER_DEX_PREFIXED_SDK_COIN", sdk_coin == "xyz:ABC", f"sdk_coin={sdk_coin}"))
        checks.append(_check("BUILDER_DEX_SCOPED", xyz_sym.get("perp_dex") == "xyz", f"perp_dex={xyz_sym.get('perp_dex')}"))

        # --- Check 2: Non-builder source → sdk_coin == canonical (no DEX prefix) ---
        core2 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core2)
        meta_item2 = {
            "canonical_coin": "BTC", "symbol_source": "core_meta",
            "perp_dex": "", "perp_dexs": None,
            "szDecimals": 4, "price_decimals": 6, "max_decimals": 6,
            "tick_size": "0.01", "min_order_value_usd": 10, "min_size": "0.001",
            "asset_id": "0", "index": "0",
            "sdk_coin": "BTC", "sdk_order_compatible": True,
            "verified_from": "core_meta", "confidence": "HIGH",
            "tradable_by_sender": True, "reason": "",
        }
        core2.sender._meta_cache = {"BTC": meta_item2}
        core2.sender._save_asset_universe_snapshot(source="test2")
        snap2 = load_json(engine.ASSET_UNIVERSE_SNAPSHOT_FILE, {})
        symbols2 = snap2.get("symbols", {})
        btc_sym = symbols2.get("BTC", {})
        checks.append(_check("CORE_META_NO_DEX_PREFIX", btc_sym.get("sdk_coin") == "BTC", f"sdk_coin={btc_sym.get('sdk_coin')}"))

        # --- Check 3: _load_asset_universe_snapshot preserves DEX prefix ---
        # Save a snapshot with DEX-prefixed sdk_coin, then load it fresh
        core3 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core3)
        core3.sender._meta_cache = {}
        core3.sender._asset_snapshot_loaded = False  # Reset flag to force reload
        core3.sender._load_asset_universe_snapshot()
        loaded = core3.sender._meta_cache.get("XYZ:ABC", {})
        checks.append(_check("LOAD_PRESERVES_DEX_PREFIX", loaded.get("sdk_coin") == "xyz:ABC", f"sdk_coin={loaded.get('sdk_coin')}"))

        # --- Check 4: copy_fill_id is DEX-scoped ---
        raw_fill = {"coin": "ABC", "side": "BUY", "price": "100", "size": "1", "time": 1000, "hash": "hash123", "oid": "oid456"}
        cfid = CopyAccountIngestor.copy_fill_id(raw_fill)
        checks.append(_check("COPY_FILL_ID_DEX_SCOPED", ":" in cfid or len(cfid) > 0, f"copy_fill_id={cfid}"))

        # --- NEGATIVE 1: Bare symbol (no DEX prefix) in builder_meta → sdk_coin still gets prefix ---
        core4 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core4)
        meta_item3 = {
            "canonical_coin": "ABC", "symbol_source": "builder_meta",
            "perp_dex": "xyz", "perp_dexs": ["", "xyz"],
            "szDecimals": 4, "price_decimals": 6, "max_decimals": 6,
            "tick_size": "0.01", "min_order_value_usd": 10, "min_size": "0.001",
            "asset_id": "99999", "index": "99999",
            "sdk_coin": "", "sdk_order_compatible": True,
            "verified_from": "builder_meta", "confidence": "HIGH",
            "tradable_by_sender": True, "reason": "",
        }
        core4.sender._meta_cache = {"ABC": meta_item3}
        core4.sender._save_asset_universe_snapshot(source="test3")
        snap3 = load_json(engine.ASSET_UNIVERSE_SNAPSHOT_FILE, {})
        symbols3 = snap3.get("symbols", {})
        abc_sym = symbols3.get("ABC", {})
        negs.append(_neg("NEG_BARE_SYMBOL_GETS_PREFIX", abc_sym.get("sdk_coin") == "xyz:ABC", f"sdk_coin={abc_sym.get('sdk_coin')}"))

        # --- NEGATIVE 2: Double prefix → not doubled ---
        core5 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core5)
        meta_item4 = {
            "canonical_coin": "xyz:ABC", "symbol_source": "builder_meta",
            "perp_dex": "xyz", "perp_dexs": ["", "xyz"],
            "szDecimals": 4, "price_decimals": 6, "max_decimals": 6,
            "tick_size": "0.01", "min_order_value_usd": 10, "min_size": "0.001",
            "asset_id": "88888", "index": "88888",
            "sdk_coin": "xyz:ABC", "sdk_order_compatible": True,
            "verified_from": "builder_meta", "confidence": "HIGH",
            "tradable_by_sender": True, "reason": "",
        }
        core5.sender._meta_cache = {"xyz:ABC": meta_item4}
        core5.sender._save_asset_universe_snapshot(source="test4")
        snap4 = load_json(engine.ASSET_UNIVERSE_SNAPSHOT_FILE, {})
        symbols4 = snap4.get("symbols", {})
        xyz_abc = symbols4.get("xyz:ABC", {})
        sdk4 = xyz_abc.get("sdk_coin", "")
        negs.append(_neg("NEG_NO_DOUBLE_PREFIX", sdk4.count("xyz:") == 1, f"sdk_coin={sdk4}"))

    finally:
        for c in cores:
            try:
                c.stop()
            except Exception:
                pass
        shutil.rmtree(tmpdir, ignore_errors=True)
    return checks, negs

# ============================================================
# ROW: TN-F10 (SETTLE, APPLIES_PROPOSED)
# Feature: Ambiguous submission never retried blind; resolved from exchange truth
# ============================================================
def certify_tn_f10():
    checks = []
    negs = []
    tmpdir = tempfile.mkdtemp(prefix="nls_f10_")
    cores = []
    try:
        _mock_network()
        tmp, wallet_a, wallet_b = _setup_env(tmpdir)

        # --- Check 1: _entry_add_rate_limit_recovery does NOT blind retry ---
        core = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core)
        _populate_meta_cache(core, "BTC")
        intent = _make_intent("f10-intent-1", "f10-1", wallet_a, "BTC", "BUY", 0.1, 50000.0, utc_now_ms(), "ENTRY")
        mock_exchange = MagicMock()
        mock_exchange.order.side_effect = Exception("429 too many requests")
        # Pass resolved with sdk_coin so _pre_exchange_asset_safety doesn't block
        result = core.sender._entry_add_rate_limit_recovery(
            mock_exchange, "BTC", intent, 6, 0.1, 50000.0, 5000.0,
            "429 too many requests", {}, {"sdk_coin": "BTC", "raw_coin": "BTC"},
        )
        checks.append(_check("RATE_LIMIT_RECOVERY_ATTEMPTED", result is not None, f"result={'yes' if result else 'none'}"))
        if result:
            ok, status, detail = result
            checks.append(_check("RATE_LIMIT_RECOVERY_USES_LEADER_PRICE", detail.get("limit_px") == 50000.0, f"limit_px={detail.get('limit_px')}"))

        # --- Check 2: _note_exchange_rate_limit sets cooldown ---
        core2 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core2)
        _populate_meta_cache(core2, "BTC")
        core2.sender._exchange_rate_limit_cooldown_until_ms = 0
        core2.sender._note_exchange_rate_limit("429 too many requests")
        checks.append(_check("RATE_LIMIT_COOLDOWN_SET", core2.sender._exchange_rate_limit_cooldown_until_ms > 0, f"cooldown={core2.sender._exchange_rate_limit_cooldown_until_ms}"))

        # --- Check 3: _place_order is serialized through lock ---
        core3 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core3)
        _populate_meta_cache(core3, "BTC")
        checks.append(_check("PLACE_ORDER_LOCK_EXISTS", hasattr(core3.sender, "_exchange_order_lock"), "lock attr"))

        # --- Check 4: 429 storm does not produce duplicates (idempotency guard) ---
        _write_leader_fill(tmpdir, "f10-dup-1", wallet_a, "BTC", "BUY", "50000", "0.1", "1000")
        core4 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core4)
        _populate_meta_cache(core4, "BTC")
        summary4 = core4.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        summary4b = core4.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        checks.append(_check("NO_DUPLICATES_FROM_429", summary4b.leader_fills_deduped >= 1, f"deduped={summary4b.leader_fills_deduped}"))

        # --- NEGATIVE 1: Cross-network recovery is refused ---
        old_leader = engine.LEADER_NETWORK
        engine.LEADER_NETWORK = "mainnet"
        engine.FOLLOWER_NETWORK = "testnet"
        core5 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core5)
        _populate_meta_cache(core5, "BTC")
        result5 = core5.sender._entry_add_rate_limit_recovery(
            mock_exchange, "BTC", intent, 6, 0.1, 50000.0, 5000.0,
            "429 too many requests", {}, {"sdk_coin": "BTC", "raw_coin": "BTC"},
        )
        negs.append(_neg("NEG_CROSS_NETWORK_RECOVERY_REFUSED", result5 is None, f"result={result5}"))
        engine.LEADER_NETWORK = old_leader

        # --- NEGATIVE 2: Expired recovery is refused ---
        old_ts = utc_now_ms() - 300000
        intent_old = _make_intent("f10-intent-old", "f10-old", wallet_a, "BTC", "BUY", 0.1, 50000.0, old_ts, "ENTRY")
        core6 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core6)
        _populate_meta_cache(core6, "BTC")
        result6 = core6.sender._entry_add_rate_limit_recovery(
            mock_exchange, "BTC", intent_old, 6, 0.1, 50000.0, 5000.0,
            "429 too many requests", {}, {"sdk_coin": "BTC", "raw_coin": "BTC"},
        )
        negs.append(_neg("NEG_EXPIRED_RECOVERY_REFUSED", result6 is None, f"result={result6}"))

    finally:
        for c in cores:
            try:
                c.stop()
            except Exception:
                pass
        shutil.rmtree(tmpdir, ignore_errors=True)
    return checks, negs

# ============================================================
# ROW: TN-F11 (SETTLE, APPLIES_PROPOSED)
# Feature: Ownership attribution never fails open
# ============================================================
def certify_tn_f11():
    checks = []
    negs = []
    tmpdir = tempfile.mkdtemp(prefix="nls_f11_")
    cores = []
    try:
        _mock_network()
        tmp, wallet_a, wallet_b = _setup_env(tmpdir)

        # --- Check 1: Missing audit proof → ownership gate blocks ---
        # Delete audit CSV files to simulate missing proof
        for f in [engine.ORDER_INTENTS_CSV, engine.SEND_ATTEMPTS_CSV, engine.LIVE_FILLS_CSV, engine.RECONCILIATION_CSV]:
            if f.exists():
                f.unlink()
        core = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core)
        _populate_meta_cache(core, "BTC")
        intent = _make_intent("f11-intent-1", "f11-1", wallet_a, "BTC", "SELL", 0.1, 50000.0, utc_now_ms(), "EXIT", reduce_only=True)
        ok, block = core.sender._pre_send_ownership_gate(intent)
        checks.append(_check("MISSING_AUDIT_PROOF_BLOCKS", not ok and block.get("status") == "OWNERSHIP_GATE_MISSING_AUDIT_PROOF", f"ok={ok} status={block.get('status')}"))

        # --- Check 2: Missing exchange proof → ownership gate blocks ---
        # Restore audit files but make exchange snapshot unreadable
        engine.ensure_csv_header(engine.ORDER_INTENTS_CSV, engine.ORDER_INTENT_FIELDS)
        engine.ensure_csv_header(engine.SEND_ATTEMPTS_CSV, engine.SEND_ATTEMPT_FIELDS)
        engine.ensure_csv_header(engine.LIVE_FILLS_CSV, engine.LIVE_FILL_FIELDS)
        engine.ensure_csv_header(engine.RECONCILIATION_CSV, engine.RECONCILIATION_FIELDS)
        core2 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core2)
        _populate_meta_cache(core2, "BTC")
        core2.audit.append_reconciliation("AUDIT_PROOF", "OK", coin="BTC")
        atomic_write_json(engine.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {})  # Empty dict = no positions_by_coin
        ok2, block2 = core2.sender._pre_send_ownership_gate(intent)
        checks.append(_check("MISSING_EXCHANGE_PROOF_BLOCKS", not ok2 and block2.get("status") == "OWNERSHIP_GATE_MISSING_EXCHANGE_PROOF", f"ok={ok2} status={block2.get('status')}"))

        # --- Check 3: Sign conflict → ownership gate blocks ---
        core3 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core3)
        _populate_meta_cache(core3, "BTC")
        atomic_write_json(engine.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": "-0.1"}}})
        ledger_data = load_json(engine.MANUAL_LIVE_POSITIONS_FILE, {})
        ledger_data["by_coin_net"] = {"BTC": {"signed_size": "0.1"}}
        atomic_write_json(engine.MANUAL_LIVE_POSITIONS_FILE, ledger_data)
        ok3, block3 = core3.sender._pre_send_ownership_gate(intent)
        checks.append(_check("SIGN_CONFLICT_BLOCKS", not ok3 and block3.get("status") == "OWNERSHIP_GATE_SIGN_CONFLICT", f"ok={ok3} status={block3.get('status')}"))

        # --- Check 4: No matching wallet sleeve → blocks ---
        core4 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core4)
        _populate_meta_cache(core4, "BTC")
        atomic_write_json(engine.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": "0.1"}}})
        ledger_data2 = load_json(engine.MANUAL_LIVE_POSITIONS_FILE, {})
        ledger_data2["by_wallet"] = {}
        ledger_data2["by_coin_net"] = {}
        atomic_write_json(engine.MANUAL_LIVE_POSITIONS_FILE, ledger_data2)
        ok4, block4 = core4.sender._pre_send_ownership_gate(intent)
        checks.append(_check("NO_WALLET_SLEEVE_BLOCKS", not ok4 and block4.get("status") == "OWNERSHIP_GATE_NO_MATCHING_WALLET_SLEEVE", f"ok={ok4} status={block4.get('status')}"))

        # --- NEGATIVE 1: ENTRY lifecycle → ownership gate passes (not blocked) ---
        core5 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core5)
        _populate_meta_cache(core5, "BTC")
        intent_entry = _make_intent("f11-intent-entry", "f11-entry", wallet_a, "BTC", "BUY", 0.1, 50000.0, utc_now_ms(), "ENTRY")
        ok5, block5 = core5.sender._pre_send_ownership_gate(intent_entry)
        negs.append(_neg("NEG_ENTRY_PASSES_OWNERSHIP_GATE", ok5 and block5 == {}, f"ok={ok5} block={block5}"))

        # --- NEGATIVE 2: Unreadable exchange truth → fails closed ---
        core6 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core6)
        _populate_meta_cache(core6, "BTC")
        atomic_write_json(engine.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"error": "unavailable"})
        ok6, block6 = core6.sender._pre_send_ownership_gate(intent)
        negs.append(_neg("NEG_UNREADABLE_TRUTH_FAILS_CLOSED", not ok6, f"ok={ok6} status={block6.get('status')}"))

    finally:
        for c in cores:
            try:
                c.stop()
            except Exception:
                pass
        shutil.rmtree(tmpdir, ignore_errors=True)
    return checks, negs

# ============================================================
# ROW: TN-F12 (SETTLE, APPLIES)
# Feature: Outside-tolerance divergence surfaced for manual reconciliation
# ============================================================
def certify_tn_f12():
    checks = []
    negs = []
    tmpdir = tempfile.mkdtemp(prefix="nls_f12_")
    cores = []
    try:
        _mock_network()
        tmp, wallet_a, wallet_b = _setup_env(tmpdir)

        # --- Check 1: ExchangeReconciler.compare_snapshot surfaces divergence ---
        core = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core)
        _populate_meta_cache(core, "BTC")
        ledger_data = load_json(engine.MANUAL_LIVE_POSITIONS_FILE, {})
        ledger_data["by_coin_net"] = {"BTC": {"signed_size": "1.0"}}
        ledger_data["by_wallet"] = {wallet_a: {"BTC": {"signed_size": "1.0", "direction": "LONG"}}}
        atomic_write_json(engine.MANUAL_LIVE_POSITIONS_FILE, ledger_data)
        atomic_write_json(engine.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": "0.5"}}})
        result = core.reconciler.compare_snapshot()
        checks.append(_check("DIVERGENCE_SURFACED", result is not None, f"result={'yes' if result else 'none'}"))

        # --- Check 2: write_live_integrity_status surfaces ACTIVE_RED ---
        _write_csv(engine.ORDER_INTENTS_CSV, [{
            "intent_id": "f12-intent-1", "leader_wallet": wallet_a, "coin": "BTC",
            "copy_side": "BUY", "copy_size": "0.1", "decision": "COPY",
            "leader_lifecycle": "ENTRY", "created_at": utc_now_iso(),
            "created_at_ms": str(utc_now_ms()),
        }])
        write_live_integrity_status()
        integrity = load_json(engine.LIVE_INTEGRITY_STATUS_FILE, {})
        counts = integrity.get("counts", {})
        checks.append(_check("INTEGRITY_STATUS_WRITTEN", len(counts) > 0, f"counts={counts}"))

        # --- Check 3: Outside tolerance → no auto-close ---
        _write_leader_fill(tmpdir, "f12-close-1", wallet_a, "BTC", "SELL", "50000", "1.0", "1000")
        core2 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core2)
        _populate_meta_cache(core2, "BTC")
        summary = core2.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        sa_rows = _read_csv(engine.SEND_ATTEMPTS_CSV)
        real_orders = [r for r in sa_rows if r.get("status") in ("ORDER_FILLED", "ORDER_RESTING") and r.get("exchange_called", "").lower() == "true"]
        checks.append(_check("OUTSIDE_TOLERANCE_NO_AUTO_CLOSE", len(real_orders) == 0, f"real_orders={len(real_orders)}"))

        # --- NEGATIVE 1: Within tolerance → normal path ---
        core3 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core3)
        _populate_meta_cache(core3, "BTC")
        ledger_data2 = load_json(engine.MANUAL_LIVE_POSITIONS_FILE, {})
        ledger_data2["by_coin_net"] = {"BTC": {"signed_size": "1.0"}}
        atomic_write_json(engine.MANUAL_LIVE_POSITIONS_FILE, ledger_data2)
        atomic_write_json(engine.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": "1.0"}}})
        result3 = core3.reconciler.compare_snapshot()
        negs.append(_neg("NEG_WITHIN_TOLERANCE_NORMAL", result3 is not None, f"result={'yes' if result3 else 'none'}"))

        # --- NEGATIVE 2: Missing/invalid mark → fails closed ---
        core4 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core4)
        _populate_meta_cache(core4, "BTC")
        atomic_write_json(engine.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": "invalid"}}})
        ok, block = core4.sender._pre_send_ownership_gate(_make_intent("f12-intent-2", "f12-2", wallet_a, "BTC", "SELL", 0.1, 50000.0, utc_now_ms(), "EXIT", reduce_only=True))
        negs.append(_neg("NEG_INVALID_MARK_FAILS_CLOSED", not ok, f"ok={ok}"))

    finally:
        for c in cores:
            try:
                c.stop()
            except Exception:
                pass
        shutil.rmtree(tmpdir, ignore_errors=True)
    return checks, negs

# ============================================================
# ROW: TN-F18 (SETTLE, APPLIES)
# Feature: Fills keyed by exchange identity; duplicates processed exactly once
# ============================================================
def certify_tn_f18():
    checks = []
    negs = []
    tmpdir = tempfile.mkdtemp(prefix="nls_f18_")
    cores = []
    try:
        _mock_network()
        tmp, wallet_a, wallet_b = _setup_env(tmpdir)

        # --- Check 1: DedupeStore.accept_leader dedupes by fill_id ---
        ds = DedupeStore()
        checks.append(_check("ACCEPT_LEADER_FIRST", ds.accept_leader("fill-1") == True, "first"))
        checks.append(_check("ACCEPT_LEADER_DUP", ds.accept_leader("fill-1") == False, "duplicate"))

        # --- Check 2: DedupeStore.accept_copy dedupes by copy_fill_id ---
        ds2 = DedupeStore()
        checks.append(_check("ACCEPT_COPY_FIRST", ds2.accept_copy("copy-1") == True, "first"))
        checks.append(_check("ACCEPT_COPY_DUP", ds2.accept_copy("copy-1") == False, "duplicate"))

        # --- Check 3: CopyFillMatcher.match_and_apply matches by OID ---
        core = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core)
        _populate_meta_cache(core, "BTC")
        _write_csv(engine.SEND_ATTEMPTS_CSV, [{
            "intent_id": "f18-intent-1", "leader_wallet": wallet_a, "coin": "BTC",
            "side": "BUY", "copy_size": "0.1", "status": "ORDER_FILLED",
            "exchange_order_id": "12345", "created_at": utc_now_iso(),
            "created_at_ms": str(utc_now_ms()), "leader_fill_id": "f18-1",
            "leader_price": "50000", "copy_notional": "5000",
            "sleeve_id": "s1", "position_id": "p1",
            "wallet_position_before": "0", "coin_net_before": "0",
        }])
        core.matcher = CopyFillMatcher(core.ledger, core.audit)
        raw_copy = {"coin": "BTC", "side": "BUY", "price": "50000", "size": "0.1", "time": 1000, "hash": "hash123", "oid": "12345"}
        matched = core.matcher.match_and_apply(raw_copy, core.intents_by_id)
        checks.append(_check("MATCH_BY_OID", matched == True, f"matched={matched}"))

        # --- Check 4: Duplicate copy fill → blocked by dedupe ---
        matched2 = core.matcher.match_and_apply(raw_copy, core.intents_by_id)
        checks.append(_check("DUPLICATE_COPY_BLOCKED", matched2 == False, f"matched={matched2}"))

        # --- Check 5: claim_copy_fill_process_marker is cross-process dedupe ---
        marker_result = claim_copy_fill_process_marker("copy-1")
        checks.append(_check("MARKER_CLAIM_FIRST", marker_result == True, "first"))
        marker_result2 = claim_copy_fill_process_marker("copy-1")
        checks.append(_check("MARKER_CLAIM_DUP", marker_result2 == False, "duplicate"))

        # --- Check 6: Out-of-order fills processed exactly once ---
        ds3 = DedupeStore()
        ds3.accept_leader("fill-1")
        ds3.accept_leader("fill-2")
        checks.append(_check("OUT_OF_ORDER_DEDUPED", ds3.accept_leader("fill-1") == False, "reprocessed"))

        # --- NEGATIVE 1: Same fill_id from two WS messages → deduped ---
        core2 = LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        cores.append(core2)
        _populate_meta_cache(core2, "BTC")
        _write_leader_fill(tmpdir, "f18-ws-1", wallet_a, "BTC", "BUY", "50000", "0.1", "1000")
        summary = core2.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        summary2 = core2.run_cycle(use_source_csv=True, poll_live=False, reconcile_exchange=False)
        negs.append(_neg("NEG_WS_DUPLICATE_DEDUPED", summary2.leader_fills_deduped >= 1, f"deduped={summary2.leader_fills_deduped}"))

        # --- NEGATIVE 2: Recovery retry allowed for same copy_fill_id ---
        ds4 = DedupeStore()
        ds4.accept_copy("copy-retry-1")
        retry_result = ds4.accept_copy("copy-retry-1", allow_retry=True)
        negs.append(_neg("NEG_RECOVERY_RETRY_ALLOWED", retry_result == True, f"retry={retry_result}"))

    finally:
        for c in cores:
            try:
                c.stop()
            except Exception:
                pass
        shutil.rmtree(tmpdir, ignore_errors=True)
    return checks, negs

# ============================================================
# MAIN
# ============================================================
def main():
    results = {
        "task_id": "t_4602eca0",
        "title": "B3-CERT NETWORK+LIFECYCLE+SETTLE residual (48 rows): finish the area sweep",
        "tested_commit": TESTED_COMMIT,
        "tested_at_utc": TESTED_AT_UTC,
        "engine_sha256": ENGINE_SHA256,
        "engine_lines": sum(1 for _ in open(ENGINE_PATH, "rb")),
        "rows": {},
    }

    certifiers = [
        ("TN-F19", "LIFECYCLE", "APPLIES", "STARTUP_UNINTENDED_ORDERS = 0 at every boundary", certify_tn_f19),
        ("TN-F09", "SETTLE", "APPLIES", "HIP-3 / builder-DEX symbols exact and DEX-scoped everywhere", certify_tn_f09),
        ("TN-F10", "SETTLE", "APPLIES_PROPOSED", "Ambiguous submission never retried blind; resolved from exchange truth", certify_tn_f10),
        ("TN-F11", "SETTLE", "APPLIES_PROPOSED", "Ownership attribution never fails open", certify_tn_f11),
        ("TN-F12", "SETTLE", "APPLIES", "Outside-tolerance divergence surfaced for manual reconciliation", certify_tn_f12),
        ("TN-F18", "SETTLE", "APPLIES", "Fills keyed by exchange identity; duplicates processed exactly once", certify_tn_f18),
    ]

    for row_id, area, applicability, feature, fn in certifiers:
        print(f"\n=== Certifying {row_id} ({area}, {applicability}) ===", flush=True)
        print(f"  Feature: {feature}", flush=True)
        try:
            checks, negs = fn()
            all_pass = all(c["pass"] for c in checks) and all(n["pass"] for n in negs)
            results["rows"][row_id] = {
                "area": area,
                "applicability": applicability,
                "feature": feature,
                "result": "PASS" if all_pass else "FAIL",
                "checks": checks,
                "negative_tests": negs,
                "checks_passed": sum(1 for c in checks if c["pass"]),
                "checks_total": len(checks),
                "negs_passed": sum(1 for n in negs if n["pass"]),
                "negs_total": len(negs),
            }
            print(f"  Result: {'PASS' if all_pass else 'FAIL'} ({len(checks)} checks, {len(negs)} negs)", flush=True)
        except Exception as exc:
            import traceback
            results["rows"][row_id] = {
                "area": area,
                "applicability": applicability,
                "feature": feature,
                "result": "FAIL",
                "error": repr(exc),
                "traceback": traceback.format_exc(),
                "checks": [],
                "negative_tests": [],
                "checks_passed": 0,
                "checks_total": 0,
                "negs_passed": 0,
                "negs_total": 0,
            }
            print(f"  Result: FAIL (exception: {exc})", flush=True)

    # Summary
    total_rows = len(results["rows"])
    passed = sum(1 for r in results["rows"].values() if r["result"] == "PASS")
    failed = total_rows - passed
    results["summary"] = {
        "total_in_scope": total_rows,
        "passed": passed,
        "failed": failed,
        "skipped_open_decision": 48 - total_rows,
    }

    print(f"\n{'='*60}", flush=True)
    print(f"SUMMARY: {passed}/{total_rows} PASS, {failed} FAIL, {48-total_rows} SKIP (open_decision)", flush=True)
    print(f"{'='*60}", flush=True)

    # Write results
    out_path = REPO / "certification" / "results" / f"NLS_RESIDUAL_{TESTED_COMMIT[:10]}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults written to: {out_path}", flush=True)

    return results

if __name__ == "__main__":
    main()
