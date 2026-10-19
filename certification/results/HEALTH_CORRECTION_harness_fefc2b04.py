#!/usr/bin/env python3
"""
HEALTH_CORRECTION_harness_fefc2b04.py

Runtime-outcome harness for the 5 offending HEALTH checks that were
source-substring assertions in HEALTH_fa9d9f55ff.json.

Each check is EARNED by a runtime outcome, not a source substring.
Non-vacuous negative tests are included per row.

Tested commit: fefc2b04261c734bb32c767d2cc4a91095e65843
Engine: _archive/hl_stage2/HL_Live_Copy_Service_Core.py
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Add the engine directory to the path
ENGINE_DIR = Path(__file__).resolve().parent.parent.parent / "_archive" / "hl_stage2"
sys.path.insert(0, str(ENGINE_DIR))

# Import the engine module
import importlib.util
spec = importlib.util.spec_from_file_location(
    "HL_Live_Copy_Service_Core",
    ENGINE_DIR / "HL_Live_Copy_Service_Core.py"
)
engine = importlib.util.module_from_spec(spec)
sys.modules["HL_Live_Copy_Service_Core"] = engine
spec.loader.exec_module(engine)


def setup_env(tmp: Path):
    """Set up engine global paths to point into a temp directory."""
    engine.AUDIT_DIR = tmp / "audit"
    engine.APPEND_ONLY_DIR = engine.AUDIT_DIR / "append_only"
    engine.CORE_RUNTIME_STATE_FILE = engine.AUDIT_DIR / "clean_core_runtime_state.json"
    engine.LIVE_CONFIG_FILE = engine.AUDIT_DIR / "live_config_file.json"
    engine.SERVICE_STATE_FILE = engine.AUDIT_DIR / "live_service_state.json"
    engine.LIVE_WS_HEALTH_FILE = engine.AUDIT_DIR / "live_ws_health.json"
    engine.MANUAL_LIVE_POSITIONS_FILE = engine.AUDIT_DIR / "manual_live_positions.json"
    engine.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = engine.AUDIT_DIR / "exchange_account_snapshot.json"
    engine.LIVE_INTEGRITY_STATUS_FILE = engine.AUDIT_DIR / "live_integrity_status.json"
    engine.ORDER_INTENTS_CSV = engine.APPEND_ONLY_DIR / "order_intents.csv"
    engine.SEND_ATTEMPTS_CSV = engine.APPEND_ONLY_DIR / "send_attempts.csv"
    engine.LIVE_FILLS_CSV = engine.APPEND_ONLY_DIR / "live_fills.csv"
    engine.RECONCILIATION_CSV = engine.APPEND_ONLY_DIR / "reconciliation.csv"
    engine.ERRORS_CSV = engine.APPEND_ONLY_DIR / "errors.csv"
    engine.RAW_LEADER_FILLS_CSV = tmp / "raw_live_fills.csv"
    engine.MANUAL_WALLETS_FILE = tmp / "manual_wallets.txt"
    engine.WALLET_GATE_FILE = tmp / "wallet_gate.json"
    engine.UI_STATE_FILE = tmp / "ui_state.json"
    engine.FORBIDDEN_LIVE_POSITIONS_FILE = engine.AUDIT_DIR / "live_positions.json"
    engine.FORBIDDEN_WOULD_SEND_ORDERS_CSV = engine.APPEND_ONLY_DIR / "would_send_orders.csv"
    engine.ensure_dirs()


def write_config(wallet_a, auto_send=False):
    """Write a minimal live config."""
    engine.atomic_write_json(engine.LIVE_CONFIG_FILE, {
        "auto_send_enabled": auto_send,
        "wallets": {
            wallet_a: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10},
        },
        "global_controls": {"min_notional": 10, "max_order_notional_usd": 0, "marketable_bps": 25},
    })


def run_check(name, fn):
    """Run a check function and return (pass, detail)."""
    try:
        detail = fn()
        return True, detail
    except AssertionError as e:
        return False, f"ASSERT: {e}"
    except Exception as e:
        return False, f"ERROR: {type(e).__name__}: {e}"


# ============================================================
# CHECK 1: HEALTH-002:AGE_IN_WRITE_PATH
# Was: "last_copy_poll_age_ms referenced in source: True"
# Now: Verify last_copy_poll_age_ms is written to SERVICE_STATE_FILE at runtime
# ============================================================

def check_age_in_write_path_positive():
    """Positive: after a cycle, last_copy_poll_age_ms is present in SERVICE_STATE_FILE."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        setup_env(tmp)
        wallet_a = "0x" + "a" * 40
        write_config(wallet_a, auto_send=False)
        
        # Set last_copy_poll_ms to a known past time
        past_ms = engine.utc_now_ms() - 120000  # 2 minutes ago
        engine.atomic_write_json(engine.CORE_RUNTIME_STATE_FILE, {
            "last_copy_poll_ms": past_ms,
        })
        
        core = engine.LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        summary = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
        
        # Read SERVICE_STATE_FILE and verify last_copy_poll_age_ms is present and > 0
        state = engine.load_json(engine.SERVICE_STATE_FILE, {})
        age = state.get("last_copy_poll_age_ms")
        assert age is not None, "last_copy_poll_age_ms not found in SERVICE_STATE_FILE"
        assert isinstance(age, (int, float)), f"last_copy_poll_age_ms is not numeric: {type(age)}"
        assert age > 0, f"last_copy_poll_age_ms should be > 0, got {age}"
        
        return f"last_copy_poll_age_ms={age} present in SERVICE_STATE_FILE"


def check_age_in_write_path_negative():
    """Negative: with no prior last_copy_poll_ms, age is 0 in state."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        setup_env(tmp)
        wallet_a = "0x" + "a" * 40
        write_config(wallet_a, auto_send=False)
        
        # No last_copy_poll_ms in state
        engine.atomic_write_json(engine.CORE_RUNTIME_STATE_FILE, {})
        
        core = engine.LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        summary = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
        
        state = engine.load_json(engine.SERVICE_STATE_FILE, {})
        age = state.get("last_copy_poll_age_ms")
        assert age == 0, f"last_copy_poll_age_ms should be 0 with no prior poll, got {age}"
        
        return f"last_copy_poll_age_ms={age} (correctly zero with no prior poll)"


# ============================================================
# CHECK 2: HEALTH-002:NEG:AGE_THRESHOLD_COMPARISON_EXISTS
# Was: "threshold comparison in source: True"
# Now: Verify the age threshold comparison actually fires at runtime
# ============================================================

def check_age_threshold_positive():
    """Positive: when age > COPY_POLL_ENTRY_BLOCK_MS, COPY_POLL_STALE gate fires."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        setup_env(tmp)
        wallet_a = "0x" + "a" * 40
        write_config(wallet_a, auto_send=False)
        
        # Set a very small threshold (1ms)
        os.environ["HL_LIVE_COPY_POLL_ENTRY_BLOCK_MS"] = "1"
        
        # Set last_copy_poll_ms to 1 second ago (clearly > 1ms)
        past_ms = engine.utc_now_ms() - 1000
        engine.atomic_write_json(engine.CORE_RUNTIME_STATE_FILE, {
            "last_copy_poll_ms": past_ms,
        })
        
        core = engine.LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        summary = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
        
        # The gate should have fired: _entry_sends_blocked_reason should be "COPY_POLL_STALE"
        block_reason = core._entry_sends_blocked_reason
        assert block_reason == "COPY_POLL_STALE", f"Expected COPY_POLL_STALE, got {block_reason}"
        
        return f"gate fired: _entry_sends_blocked_reason={block_reason}"


def check_age_threshold_negative():
    """Negative: when age < COPY_POLL_ENTRY_BLOCK_MS, COPY_POLL_STALE does not fire."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        setup_env(tmp)
        wallet_a = "0x" + "a" * 40
        write_config(wallet_a, auto_send=False)
        
        # Set a very large threshold (1 hour)
        os.environ["HL_LIVE_COPY_POLL_ENTRY_BLOCK_MS"] = "3600000"
        
        # Set last_copy_poll_ms to 1 second ago (clearly < 1 hour)
        past_ms = engine.utc_now_ms() - 1000
        engine.atomic_write_json(engine.CORE_RUNTIME_STATE_FILE, {
            "last_copy_poll_ms": past_ms,
        })
        
        core = engine.LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        summary = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
        
        # The gate should NOT have fired
        block_reason = core._entry_sends_blocked_reason
        assert block_reason != "COPY_POLL_STALE", f"COPY_POLL_STALE should not fire, got {block_reason}"
        
        return f"gate not fired: _entry_sends_blocked_reason={block_reason!r} (correct)"


# ============================================================
# CHECK 3: HEALTH-003:SEND_BLOCK_REASON_IN_STATE
# Was: "send_block_reason in source: True"
# Now: Verify send_block_reason is present in SERVICE_STATE_FILE at runtime
# ============================================================

def check_send_block_reason_positive():
    """Positive: with auto_send disabled, send_block_reason=MASTER_REAL_ORDERS_OFF in state."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        setup_env(tmp)
        wallet_a = "0x" + "a" * 40
        write_config(wallet_a, auto_send=False)
        
        core = engine.LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        summary = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
        
        state = engine.load_json(engine.SERVICE_STATE_FILE, {})
        reason = state.get("send_block_reason")
        assert reason is not None, "send_block_reason not found in SERVICE_STATE_FILE"
        assert reason == "MASTER_REAL_ORDERS_OFF", f"Expected MASTER_REAL_ORDERS_OFF, got {reason}"
        
        return f"send_block_reason={reason} present in SERVICE_STATE_FILE"


def check_send_block_reason_negative():
    """Negative: with auto_send enabled, send_block_reason is empty string."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        setup_env(tmp)
        wallet_a = "0x" + "a" * 40
        write_config(wallet_a, auto_send=True)
        
        core = engine.LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        summary = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
        
        state = engine.load_json(engine.SERVICE_STATE_FILE, {})
        reason = state.get("send_block_reason")
        assert reason == "", f"send_block_reason should be empty with auto_send enabled, got {reason!r}"
        
        return f"send_block_reason={reason!r} (correctly empty with auto_send enabled)"


# ============================================================
# CHECK 4: HEALTH-004:NETWORK_ERRORS_COUNTER
# Was: "network_errors in source: True"
# Now: Verify network_errors counter increments at runtime on poll failure
# ============================================================

class FailingIngestor:
    """Mock ingestor that always returns an error status."""
    def poll_hyperliquid_fills(self, wallet, start_ms, end_ms=None):
        return [], "POLL_FAILED"


def check_network_errors_positive():
    """Positive: when poll_live fails, network_errors increments."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        setup_env(tmp)
        wallet_a = "0x" + "a" * 40
        write_config(wallet_a, auto_send=False)
        
        core = engine.LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        core.ingestor = FailingIngestor()
        summary = core.run_cycle(use_source_csv=False, poll_live=True, poll_copy=False, reconcile_exchange=False)
        
        assert summary.network_errors > 0, f"network_errors should be > 0, got {summary.network_errors}"
        
        # Also verify it's in the state file
        state = engine.load_json(engine.SERVICE_STATE_FILE, {})
        state_errors = state.get("network_errors")
        assert state_errors is not None, "network_errors not found in SERVICE_STATE_FILE"
        assert state_errors > 0, f"network_errors in state should be > 0, got {state_errors}"
        
        return f"network_errors={summary.network_errors} (incremented on poll failure)"


class SuccessIngestor:
    """Mock ingestor that always returns success."""
    def poll_hyperliquid_fills(self, wallet, start_ms, end_ms=None):
        return [], "POLL_OK"


def check_network_errors_negative():
    """Negative: when poll_live succeeds, network_errors stays 0."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        setup_env(tmp)
        wallet_a = "0x" + "a" * 40
        write_config(wallet_a, auto_send=False)
        
        core = engine.LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        core.ingestor = SuccessIngestor()
        summary = core.run_cycle(use_source_csv=False, poll_live=True, poll_copy=False, reconcile_exchange=False)
        
        assert summary.network_errors == 0, f"network_errors should be 0, got {summary.network_errors}"
        
        return f"network_errors={summary.network_errors} (correctly zero on poll success)"


# ============================================================
# CHECK 5: TN-F15:FRESHNESS_BUDGET_EXISTS
# Was: "COPY_POLL_ENTRY_BLOCK_MS in source: True"
# Now: Verify the freshness budget gate fires at runtime
# ============================================================

def check_freshness_budget_positive():
    """Positive: when age > COPY_POLL_ENTRY_BLOCK_MS, the freshness gate fires."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        setup_env(tmp)
        wallet_a = "0x" + "a" * 40
        write_config(wallet_a, auto_send=False)
        
        # Set a very small budget (1ms)
        os.environ["HL_LIVE_COPY_POLL_ENTRY_BLOCK_MS"] = "1"
        
        # Set last_copy_poll_ms to 5 seconds ago (clearly > 1ms)
        past_ms = engine.utc_now_ms() - 5000
        engine.atomic_write_json(engine.CORE_RUNTIME_STATE_FILE, {
            "last_copy_poll_ms": past_ms,
        })
        
        core = engine.LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        summary = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
        
        # The freshness gate should have fired
        block_reason = core._entry_sends_blocked_reason
        assert block_reason == "COPY_POLL_STALE", f"Expected COPY_POLL_STALE, got {block_reason}"
        
        return f"freshness gate fired: _entry_sends_blocked_reason={block_reason}"


def check_freshness_budget_negative():
    """Negative: when age < COPY_POLL_ENTRY_BLOCK_MS, the freshness gate does not fire."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        setup_env(tmp)
        wallet_a = "0x" + "a" * 40
        write_config(wallet_a, auto_send=False)
        
        # Set a very large budget (2 hours)
        os.environ["HL_LIVE_COPY_POLL_ENTRY_BLOCK_MS"] = "7200000"
        
        # Set last_copy_poll_ms to 5 seconds ago (clearly < 2 hours)
        past_ms = engine.utc_now_ms() - 5000
        engine.atomic_write_json(engine.CORE_RUNTIME_STATE_FILE, {
            "last_copy_poll_ms": past_ms,
        })
        
        core = engine.LiveCopyCore(source_csv=engine.RAW_LEADER_FILLS_CSV)
        summary = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
        
        # The freshness gate should NOT have fired
        block_reason = core._entry_sends_blocked_reason
        assert block_reason != "COPY_POLL_STALE", f"COPY_POLL_STALE should not fire, got {block_reason}"
        
        return f"freshness gate not fired: _entry_sends_blocked_reason={block_reason!r} (correct)"


# ============================================================
# MAIN
# ============================================================

def main():
    checks = [
        # HEALTH-002:AGE_IN_WRITE_PATH
        ("HEALTH-002:AGE_IN_WRITE_PATH", check_age_in_write_path_positive),
        ("HEALTH-002:NEG:AGE_IN_WRITE_PATH_ZERO_WITHOUT_PRIOR", check_age_in_write_path_negative),
        # HEALTH-002:NEG:AGE_THRESHOLD_COMPARISON_EXISTS
        ("HEALTH-002:NEG:AGE_THRESHOLD_COMPARISON_FIRES", check_age_threshold_positive),
        ("HEALTH-002:NEG:AGE_THRESHOLD_COMPARISON_NOT_FIRES", check_age_threshold_negative),
        # HEALTH-003:SEND_BLOCK_REASON_IN_STATE
        ("HEALTH-003:SEND_BLOCK_REASON_IN_STATE", check_send_block_reason_positive),
        ("HEALTH-003:NEG:SEND_BLOCK_REASON_EMPTY_WHEN_ENABLED", check_send_block_reason_negative),
        # HEALTH-004:NETWORK_ERRORS_COUNTER
        ("HEALTH-004:NETWORK_ERRORS_COUNTER_INCREMENTS", check_network_errors_positive),
        ("HEALTH-004:NEG:NETWORK_ERRORS_ZERO_ON_SUCCESS", check_network_errors_negative),
        # TN-F15:FRESHNESS_BUDGET_EXISTS
        ("TN-F15:FRESHNESS_BUDGET_GATE_FIRES", check_freshness_budget_positive),
        ("TN-F15:NEG:FRESHNESS_BUDGET_GATE_NOT_FIRES", check_freshness_budget_negative),
    ]
    
    results = []
    passed = 0
    failed = 0
    
    for name, fn in checks:
        ok, detail = run_check(name, fn)
        results.append({
            "name": name,
            "pass": ok,
            "detail": detail,
        })
        if ok:
            passed += 1
            print(f"PASS: {name} :: {detail}")
        else:
            failed += 1
            print(f"FAIL: {name} :: {detail}")
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} PASS, {failed} FAIL out of {len(checks)} checks")
    print(f"{'='*60}")
    
    # Write results to JSON
    output = {
        "harness": "HEALTH_CORRECTION_harness_fefc2b04.py",
        "tested_commit": "fefc2b04261c734bb32c767d2cc4a91095e65843",
        "engine_sha256": "2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405",
        "total_checks": len(checks),
        "passed": passed,
        "failed": failed,
        "checks": results,
    }
    
    output_path = Path(__file__).resolve().parent / "HEALTH_CORRECTION_fefc2b04.json"
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nResults written to: {output_path}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
