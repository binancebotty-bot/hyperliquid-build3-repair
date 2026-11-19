#!/usr/bin/env python3
"""RED tests for SET-009: Ledger vs Exchange divergence detection.

Both polarities:
1. Exchange has position, ledger is flat (phantom position)
2. Ledger has position, exchange is flat (missing position)

Current code: compare_snapshot() logs to reconciliation CSV but doesn't block sends
or emit a structured alert with (coin, ledger_qty, exchange_qty, timestamp).
build_live_integrity_status() reports mismatch but is audit-only.

FIX: Added _extract_exchange_size helper and Gate 6 (LEDGER_EXCHANGE_DIVERGENCE)
that blocks sends when previous cycle's integrity status shows mismatch.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import HL_Live_Copy_Service_Core as c
from HL_Live_Copy_Service_Core import (
    ExchangeReconciler,
    ManualLedger,
    AuditLogWriter,
    build_live_integrity_status,
    write_live_integrity_status,
    atomic_write_json,
    MANUAL_LIVE_POSITIONS_FILE,
    EXCHANGE_ACCOUNT_SNAPSHOT_FILE,
    RECONCILIATION_CSV,
    LIVE_INTEGRITY_STATUS_FILE,
    POSITION_EPSILON,
    AUDIT_DIR,
    APPEND_ONLY_DIR,
    LIVE_CONFIG_FILE,
    SERVICE_STATE_FILE,
    CORE_RUNTIME_STATE_FILE,
)

RESULTS = []

def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    status = "PASS" if cond else "FAIL"
    suffix = f" | {detail}" if detail and not cond else ""
    print(f"RESULT::{name}_{status}{suffix}")

def setup_tmp() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="set009_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "mainnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
        "HL_LIVE_GATES_ALERT_ONLY": "0",
    })
    # Override global paths like the self-test does
    c.AUDIT_DIR = tmp / "hl_live_copy_audit_testnet"
    c.APPEND_ONLY_DIR = c.AUDIT_DIR / "append_only"
    c.LIVE_CONFIG_FILE = c.AUDIT_DIR / "live_config.json"
    c.SERVICE_STATE_FILE = c.AUDIT_DIR / "live_service_state.json"
    c.CORE_RUNTIME_STATE_FILE = c.AUDIT_DIR / "clean_core_runtime_state.json"
    c.MANUAL_LIVE_POSITIONS_FILE = c.AUDIT_DIR / "manual_live_positions.json"
    c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = c.AUDIT_DIR / "exchange_account_snapshot.json"
    c.RECONCILIATION_CSV = c.APPEND_ONLY_DIR / "reconciliation.csv"
    c.LIVE_INTEGRITY_STATUS_FILE = c.AUDIT_DIR / "live_integrity_status.json"
    c.ensure_dirs()
    c.USER_WALLET = "0x" + "c" * 40
    return tmp

def test_polarity_exchange_has_ledger_flat():
    """Polarity 1: Exchange reports a position the ledger lacks (phantom position)."""
    print("\n=== POLARITY 1: Exchange has position, ledger flat ===")
    tmp = setup_tmp()
    
    # Setup: ledger is empty (flat), exchange snapshot has BTC position
    # Write files FIRST, then create ledger so it loads the correct state
    atomic_write_json(c.MANUAL_LIVE_POSITIONS_FILE, {"by_wallet": {}, "by_coin_net": {}})
    snapshot = {"positions_by_coin": {"BTC": {"signed_size": 1.5}}}
    atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, snapshot)
    ledger = ManualLedger()
    audit = AuditLogWriter()
    
    # Run the reconciler with explicit snapshot
    recon = ExchangeReconciler(ledger, audit)
    status = recon.compare_snapshot(snapshot)
    
    # Check: mismatch is reported in reconciliation CSV
    recon_rows = c.read_csv_rows(c.RECONCILIATION_CSV)
    mismatch_rows = [r for r in recon_rows if r.get("status") == "LEDGER_EXCHANGE_NET_MISMATCH"]
    
    check("SET009_P1_mismatch_reported_in_recon_csv", 
          len(mismatch_rows) >= 1,
          f"found {len(mismatch_rows)} mismatch rows")
    
    row = mismatch_rows[0] if mismatch_rows else {}
    check("SET009_P1_mismatch_has_coin", row.get("coin") == "BTC", str(row.get("coin")))
    check("SET009_P1_mismatch_has_manual_net", "manual_net" in row, f"keys: {list(row.keys())}")
    check("SET009_P1_mismatch_has_exchange_net", "exchange_net" in row, f"keys: {list(row.keys())}")
    check("SET009_P1_mismatch_has_timestamp", "created_at" in row or "created_at_ms" in row, f"keys: {list(row.keys())}")
    
    # Verify values
    check("SET009_P1_manual_net_is_zero", float(row.get("manual_net", -1)) == 0.0, str(row.get("manual_net")))
    check("SET009_P1_exchange_net_is_1_5", abs(float(row.get("exchange_net", -1)) - 1.5) < 1e-9, str(row.get("exchange_net")))
    
    # Check: build_live_integrity_status reports the mismatch
    integ = build_live_integrity_status()
    check("SET009_P1_integrity_reports_mismatch",
      integ.get("counts", {}).get("exchange_manual_mismatch", 0) >= 1,
      f"counts: {integ.get('counts')}")
    
    pos_assign = integ.get("position_assignment", {})
    mismatches = pos_assign.get("exchange_manual_mismatches", [])
    check("SET009_P1_integrity_mismatch_detail_has_coin",
          any(m.get("coin") == "BTC" for m in mismatches), str(mismatches))
    m = mismatches[0] if mismatches else {}
    check("SET009_P1_integrity_mismatch_detail_has_exchange", "exchange" in m, str(m))
    check("SET009_P1_integrity_mismatch_detail_has_manual", "manual" in m, str(m))
    check("SET009_P1_integrity_mismatch_detail_has_delta", "delta" in m, str(m))

def test_polarity_ledger_has_exchange_flat():
    """Polarity 2: Ledger has a position the exchange lacks (missing position)."""
    print("\n=== POLARITY 2: Ledger has position, exchange flat ===")
    tmp = setup_tmp()
    
    # Setup: ledger has BTC position, exchange snapshot is empty
    # Write files FIRST, then create ledger
    atomic_write_json(c.MANUAL_LIVE_POSITIONS_FILE, {
        "by_wallet": {"0xwallet": {"BTC": {"signed_size": 2.0, "coin": "BTC"}}},
        "by_coin_net": {"BTC": {"signed_size": 2.0}}
    })
    snapshot = {"positions_by_coin": {}}
    atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, snapshot)
    ledger = ManualLedger()
    audit = AuditLogWriter()
    
    # Run the reconciler with explicit snapshot
    recon = ExchangeReconciler(ledger, audit)
    status = recon.compare_snapshot(snapshot)
    
    # Check: mismatch is reported
    recon_rows = c.read_csv_rows(c.RECONCILIATION_CSV)
    mismatch_rows = [r for r in recon_rows if r.get("status") == "LEDGER_EXCHANGE_NET_MISMATCH"]
    
    check("SET009_P2_mismatch_reported_in_recon_csv",
          len(mismatch_rows) >= 1,
          f"found {len(mismatch_rows)} mismatch rows")
    
    if mismatch_rows:
        row = mismatch_rows[0]
        check("SET009_P2_mismatch_has_coin", row.get("coin") == "BTC", str(row.get("coin")))
        check("SET009_P2_mismatch_has_manual_net", "manual_net" in row, f"keys: {list(row.keys())}")
        check("SET009_P2_mismatch_has_exchange_net", "exchange_net" in row, f"keys: {list(row.keys())}")
        
        check("SET009_P2_manual_net_is_2_0", abs(float(row.get("manual_net", -1)) - 2.0) < 1e-9, str(row.get("manual_net")))
        check("SET009_P2_exchange_net_is_zero", float(row.get("exchange_net", -1)) == 0.0, str(row.get("exchange_net")))
    
    # Check: build_live_integrity_status reports the mismatch
    integ = build_live_integrity_status()
    check("SET009_P2_integrity_reports_mismatch",
          integ.get("counts", {}).get("exchange_manual_mismatch", 0) >= 1,
          f"counts: {integ.get('counts')}")

def test_gate_blocks_sends_on_divergence():
    """Gate 6: LEDGER_EXCHANGE_DIVERGENCE blocks entry sends when previous cycle shows mismatch."""
    print("\n=== GATE 6: Divergence blocks sends ===")
    tmp = setup_tmp()
    
    # Setup: exchange has position, ledger flat
    atomic_write_json(c.MANUAL_LIVE_POSITIONS_FILE, {"by_wallet": {}, "by_coin_net": {}})
    snapshot = {"positions_by_coin": {"BTC": {"signed_size": 1.0}}}
    atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, snapshot)
    
    # Write a PREVIOUS cycle integrity status that shows the mismatch
    # This simulates the previous cycle having detected the divergence
    prev_integrity = {
        "created_at": "fresh",
        "created_at_ms": c.utc_now_ms(),
        "status": "RED",
        "counts": {
            "send_attempts": 0,
            "live_fills": 0,
            "reconciliation_rows": 1,
            "exchange_manual_mismatch": 1,
        },
        "position_assignment": {
            "status": "MISMATCH",
            "exchange_manual_mismatches": [
                {"coin": "BTC", "exchange": 1.0, "manual": 0.0, "delta": 1.0, "action": "ASSIGN_OR_REPAIR_PROVEN_POSITION"}
            ],
            "archived_manual_residuals": [],
        },
        "notes": "audit-only live integrity status; no ledger mutation",
    }
    atomic_write_json(c.LIVE_INTEGRITY_STATUS_FILE, prev_integrity)
    
    # Run a cycle - the gate should block entry sends
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.wallets = ["0xwallet"]
    core.cfg = c.ConfigManager()
    atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": {},
        "wallets": {"0xwallet": {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000}}
    })
    
    # Mock network to avoid live requests
    import requests
    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    
    summary = core.run_cycle(poll_live=False, poll_copy=False, reconcile_exchange=False)
    
    check("SET009_gate_blocks_on_divergence",
          core._entry_sends_blocked_reason == "LEDGER_EXCHANGE_DIVERGENCE",
          f"block_reason: {core._entry_sends_blocked_reason}")
    
    # Verify the cycle still runs ok (just blocks sends)
    check("SET009_cycle_runs_ok_despite_block", summary.ok is True, str(summary))

def test_no_block_when_matched():
    """No block when previous cycle shows matched positions."""
    print("\n=== NO BLOCK WHEN MATCHED ===")
    tmp = setup_tmp()
    
    # Setup: both ledger and exchange flat
    atomic_write_json(c.MANUAL_LIVE_POSITIONS_FILE, {"by_wallet": {}, "by_coin_net": {}})
    atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {}})
    
    # Write a PREVIOUS cycle integrity status that shows MATCHED
    prev_integrity = {
        "created_at": "fresh",
        "created_at_ms": c.utc_now_ms(),
        "status": "GREEN",
        "counts": {
            "send_attempts": 0,
            "live_fills": 0,
            "reconciliation_rows": 1,
            "exchange_manual_mismatch": 0,
        },
        "position_assignment": {
            "status": "MATCHED",
            "exchange_manual_mismatches": [],
            "archived_manual_residuals": [],
        },
        "notes": "audit-only live integrity status; no ledger mutation",
    }
    atomic_write_json(c.LIVE_INTEGRITY_STATUS_FILE, prev_integrity)
    
    # Run a cycle - should NOT be blocked by divergence gate
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.wallets = ["0xwallet"]
    core.cfg = c.ConfigManager()
    atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": {},
        "wallets": {"0xwallet": {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000}}
    })
    
    import requests
    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    
    summary = core.run_cycle(poll_live=False, poll_copy=False, reconcile_exchange=False)
    
    check("SET009_no_block_when_matched",
          core._entry_sends_blocked_reason != "LEDGER_EXCHANGE_DIVERGENCE",
          f"block_reason: {core._entry_sends_blocked_reason}")

def test_stale_status_holds_entries_but_not_closes():
    """Stale status is an entry hold with alert; close lifecycle remains allowed."""
    tmp = setup_tmp()
    atomic_write_json(c.LIVE_INTEGRITY_STATUS_FILE, {
        "created_at_ms": c.utc_now_ms() - 300_000,
        "counts": {"exchange_manual_mismatch": 1},
    })
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.wallets = ["0xwallet"]
    core.cfg = c.ConfigManager()
    atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {"0xwallet": {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000}}})
    import requests
    def offline(*a, **k): raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    summary = core.run_cycle(poll_live=False, poll_copy=False, reconcile_exchange=False)
    check("SET009_stale_mismatch_entry_blocked_with_stale_reason",
          core._entry_sends_blocked_reason == "LEDGER_STATUS_STALE", core._entry_sends_blocked_reason)
    check("SET009_stale_alert_counter_and_age_set",
          summary.integrity_status_stale and summary.integrity_status_age_ms >= 120_000
          and "integrity_status_stale" in c.CycleSummary.__dataclass_fields__,
          f"stale={summary.integrity_status_stale} age={summary.integrity_status_age_ms}")
    close = c.Intent("test-close", c.LeaderFill("close-fill", "0xwallet", "BTC", "SELL", 100.0, 1.0, c.utc_now_ms(), "TEST"),
        "SELL", 1.0, 100.0, "LIVE", "fixed", "EXIT_ALLOWED", "", "sleeve", "position", "LONG", 1.0,
        1.0, True, True, notes="lifecycle=EXIT")
    close_decision = core.sender.send_if_allowed(close, "LEDGER_STATUS_STALE")
    check("SET009_stale_close_reaches_send_decision",
          close_decision[1] != "ENTRY_BLOCKED_LEDGER_STATUS_STALE", str(close_decision))


def test_missing_status_holds_entries_and_alerts():
    """Missing status fails closed for entries and records the loud alert."""
    tmp = setup_tmp()
    if c.LIVE_INTEGRITY_STATUS_FILE.exists(): c.LIVE_INTEGRITY_STATUS_FILE.unlink()
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.wallets = ["0xwallet"]
    core.cfg = c.ConfigManager()
    atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {"0xwallet": {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000}}})
    import requests
    def offline(*a, **k): raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    summary = core.run_cycle(poll_live=False, poll_copy=False, reconcile_exchange=False)
    check("SET009_missing_status_entry_blocked_and_alerted",
          core._entry_sends_blocked_reason == "LEDGER_STATUS_STALE" and summary.integrity_status_stale
          and "integrity_status_stale" in c.CycleSummary.__dataclass_fields__,
          f"reason={core._entry_sends_blocked_reason} stale={summary.integrity_status_stale}")
    close = c.Intent("test-close", c.LeaderFill("close-fill", "0xwallet", "BTC", "SELL", 100.0, 1.0, c.utc_now_ms(), "TEST"),
        "SELL", 1.0, 100.0, "LIVE", "fixed", "EXIT_ALLOWED", "", "sleeve", "position", "LONG", 1.0,
        1.0, True, True, notes="lifecycle=EXIT")
    close_decision = core.sender.send_if_allowed(close, "LEDGER_STATUS_STALE")
    check("SET009_missing_status_close_passes",
          close_decision[1] != "ENTRY_BLOCKED_LEDGER_STATUS_STALE", str(close_decision))

def main():
    test_polarity_exchange_has_ledger_flat()
    test_polarity_ledger_has_exchange_flat()
    test_gate_blocks_sends_on_divergence()
    test_no_block_when_matched()
    test_stale_status_holds_entries_but_not_closes()
    test_missing_status_holds_entries_and_alerts()
    
    failed = [n for n, ok in RESULTS if not ok]
    print(f"\nTOTAL={len(RESULTS)} FAILED={len(failed)}")
    if failed:
        print("FAILED:", ", ".join(failed))
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
