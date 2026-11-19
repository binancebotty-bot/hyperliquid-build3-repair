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

def _alert_only(value) -> None:
    """Set the entry-gate mode explicitly, or remove it so the repo default (alert-only ON) applies."""
    if value is None:
        os.environ.pop("HL_LIVE_GATES_ALERT_ONLY", None)
    else:
        os.environ["HL_LIVE_GATES_ALERT_ONLY"] = str(value)


def _slug(value) -> str:
    return "alert_only_unset" if value is None else f"alert_only_{value}"


def _offline(*_a, **_k):
    raise RuntimeError("offline test: no network")


def _core_for(tmp: Path):
    """Write the live config FIRST, then construct the core, so its own ConfigManager reads it."""
    atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {"0xwallet": {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000}}})
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.wallets = ["0xwallet"]
    import requests
    requests.post = _offline
    c.requests.post = _offline
    return core


def _close_intent(intent_id: str, reduce_only: bool, notes: str, before: float):
    return c.Intent(
        intent_id,
        c.LeaderFill("fill-" + intent_id, "0xwallet", "BTC", "SELL", 100.0, 1.0, c.utc_now_ms(), "TEST"),
        "SELL", 1.0, 100.0, "LIVE", "fixed", "EXIT_ALLOWED", "", "sleeve", "position", "LONG",
        before, 1.0, reduce_only, True, notes=notes)


def _entry_intent(intent_id: str):
    return c.Intent(
        intent_id,
        c.LeaderFill("fill-" + intent_id, "0xwallet", "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST"),
        "BUY", 1.0, 100.0, "LIVE", "fixed", "ENTRY_ALLOWED", "", "sleeve", "position", "FLAT",
        0.0, 0.0, False, True, notes="lifecycle=ENTRY")


def _assert_close_status(core, intent, label: str) -> None:
    """Drive the REAL send decision and assert the exact refusal the close does receive.

    Asserting only `!= "ENTRY_BLOCKED_LEDGER_STATUS_STALE"` also passes when the refusal is
    INTENT_NOT_SEND_ALLOWED, so the exact status is pinned to a gate reachable only AFTER the
    entry hold, and the stale refusal is excluded explicitly.
    """
    ok, status = core.sender.send_if_allowed(intent, core._entry_sends_blocked_reason)
    check(f"{label}_refused", ok is False, f"ok={ok} status={status}")
    check(f"{label}_refusal_is_ownership_gate",
          status == "OWNERSHIP_GATE_NO_MATCHING_WALLET_SLEEVE", f"status={status}")
    check(f"{label}_never_refused_for_stale_reason",
          status != "ENTRY_BLOCKED_LEDGER_STATUS_STALE", f"status={status}")


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
    core = _core_for(tmp)
    summary = core.run_cycle(poll_live=False, poll_copy=False, reconcile_exchange=False)
    check("SET009_stale_mismatch_entry_blocked_with_stale_reason",
          core._entry_sends_blocked_reason == "LEDGER_STATUS_STALE", core._entry_sends_blocked_reason)
    check("SET009_stale_alert_counter_and_age_set",
          summary.integrity_status_stale and summary.integrity_status_age_ms >= 120_000
          and "integrity_status_stale" in c.CycleSummary.__dataclass_fields__,
          f"stale={summary.integrity_status_stale} age={summary.integrity_status_age_ms}")
    _assert_close_status(core, _close_intent("stale-close", True, "lifecycle=EXIT", 1.0),
                         "SET009_stale_close")


def test_missing_status_holds_entries_and_alerts():
    """Missing status fails closed for entries and records the loud alert."""
    tmp = setup_tmp()
    if c.LIVE_INTEGRITY_STATUS_FILE.exists(): c.LIVE_INTEGRITY_STATUS_FILE.unlink()
    core = _core_for(tmp)
    summary = core.run_cycle(poll_live=False, poll_copy=False, reconcile_exchange=False)
    check("SET009_missing_status_entry_blocked_and_alerted",
          core._entry_sends_blocked_reason == "LEDGER_STATUS_STALE" and summary.integrity_status_stale
          and "integrity_status_stale" in c.CycleSummary.__dataclass_fields__,
          f"reason={core._entry_sends_blocked_reason} stale={summary.integrity_status_stale}")
    _assert_close_status(core, _close_intent("missing-close", True, "lifecycle=EXIT", 1.0),
                         "SET009_missing_status_close")

def test_close_decision_never_refused_for_stale(alert_only) -> None:
    """A reduce-only close is never refused for the stale reason - in BOTH gate modes.

    Drives the real send decision with the cycle's own entry block reason and asserts the exact
    refusal the close receives (the pre-send ownership gate), which the old != ENTRY_BLOCKED_*
    assertion never checked. The paired entry intent proves the stale hold is live in the same
    harness, so the close's refusal cannot be a vacuous pass.
    """
    tag = _slug(alert_only)
    print("\n=== CLOSE SEND DECISION under stale status, HL_LIVE_GATES_ALERT_ONLY=%r ===" % (alert_only,))
    tmp = setup_tmp()
    _alert_only(alert_only)
    check(f"SET009_{tag}_env_is_as_requested",
          ("HL_LIVE_GATES_ALERT_ONLY" in os.environ) is (alert_only is not None),
          f"present={'HL_LIVE_GATES_ALERT_ONLY' in os.environ} requested={alert_only!r}")
    atomic_write_json(c.MANUAL_LIVE_POSITIONS_FILE, {"by_wallet": {}, "by_coin_net": {}})
    atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {}})
    atomic_write_json(c.LIVE_INTEGRITY_STATUS_FILE, {
        "created_at_ms": c.utc_now_ms() - 300_000, "counts": {"exchange_manual_mismatch": 1}})
    core = _core_for(tmp)
    summary = core.run_cycle(poll_live=False, poll_copy=False, reconcile_exchange=False)
    check(f"SET009_{tag}_stale_still_blocks_entries",
          core._entry_sends_blocked_reason == "LEDGER_STATUS_STALE",
          f"block={core._entry_sends_blocked_reason!r}")
    check(f"SET009_{tag}_stale_flagged_on_summary", summary.integrity_status_stale is True,
          f"stale={summary.integrity_status_stale}")

    _assert_close_status(core, _close_intent("labelled-" + tag, True, "lifecycle=EXIT", 1.0),
                         f"SET009_{tag}_labelled_exit_close")

    unlabelled = _close_intent("unlabelled-" + tag, True, "", 0.0)
    check(f"SET009_{tag}_reduce_only_close_classifies_as_exit",
          c.classify_send_lifecycle(unlabelled) == "EXIT", c.classify_send_lifecycle(unlabelled))
    _assert_close_status(core, unlabelled, f"SET009_{tag}_reduce_only_close")

    ok, status = core.sender.send_if_allowed(_entry_intent("entry-" + tag),
                                             core._entry_sends_blocked_reason)
    check(f"SET009_{tag}_entry_control_refused_for_stale",
          (ok, status) == (False, "ENTRY_BLOCKED_LEDGER_STATUS_STALE"), f"ok={ok} status={status}")


def test_default_mode_stale_blocks_entry() -> None:
    """The whole point of exempting the two reasons: at repo default the gate is NOT inert.

    HL_LIVE_GATES_ALERT_ONLY is UNSET here, so bval() falls back to alert-only True. A stale
    status must still hold entries (it was silently cleared before the exemption).
    """
    print("\n=== DEFAULT MODE: stale blocks an entry with HL_LIVE_GATES_ALERT_ONLY unset ===")
    tmp = setup_tmp()
    _alert_only(None)
    check("SET009_default_mode_env_is_unset",
          "HL_LIVE_GATES_ALERT_ONLY" not in os.environ,
          f"present={'HL_LIVE_GATES_ALERT_ONLY' in os.environ}")
    check("SET009_default_mode_gate_defaults_to_alert_only_true",
          c.bval(os.getenv("HL_LIVE_GATES_ALERT_ONLY"), True) is True,
          f"default={c.bval(os.getenv('HL_LIVE_GATES_ALERT_ONLY'), True)}")
    atomic_write_json(c.MANUAL_LIVE_POSITIONS_FILE, {"by_wallet": {}, "by_coin_net": {}})
    atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {}})
    atomic_write_json(c.LIVE_INTEGRITY_STATUS_FILE, {
        "created_at_ms": c.utc_now_ms() - 300_000, "counts": {"exchange_manual_mismatch": 1}})
    core = _core_for(tmp)
    summary = core.run_cycle(poll_live=False, poll_copy=False, reconcile_exchange=False)
    check("SET009_default_mode_stale_entry_blocked",
          core._entry_sends_blocked_reason == "LEDGER_STATUS_STALE",
          f"block={core._entry_sends_blocked_reason!r}")
    check("SET009_default_mode_stale_flagged_on_summary", summary.integrity_status_stale is True,
          f"stale={summary.integrity_status_stale}")
    ok, status = core.sender.send_if_allowed(_entry_intent("default-mode-entry"),
                                             core._entry_sends_blocked_reason)
    check("SET009_default_mode_entry_send_refused_for_stale",
          (ok, status) == (False, "ENTRY_BLOCKED_LEDGER_STATUS_STALE"), f"ok={ok} status={status}")
    _assert_close_status(core, _close_intent("default-mode-close", True, "", 0.0),
                         "SET009_default_mode_close")


def test_writer_interval_scales_freshness_bound() -> None:
    """The freshness bound is 24 x HL_LIVE_INTEGRITY_MIN_INTERVAL_SEC, not a fixed 120 s.

    At the default 5 s interval the bound self-holds at 120 s (old behaviour preserved). At a
    60 s writer interval the new bound is 1440 s: 600 s old is FRESH (a fixed 120 s bound would
    call it stale) and 1500 s old is stale (so the new bound is finite, not unbounded).
    """
    print("\n=== FRESHNESS BOUND FOLLOWS THE WRITER INTERVAL ===")
    for tag, interval, age_ms, want_stale in [
        ("default_interval_age_300s", None, 300_000, True),
        ("interval_60s_age_600s", "60", 600_000, False),
        ("interval_60s_age_1500s", "60", 1_500_000, True),
    ]:
        tmp = setup_tmp()
        _alert_only("0")
        if interval is None:
            os.environ.pop("HL_LIVE_INTEGRITY_MIN_INTERVAL_SEC", None)
        else:
            os.environ["HL_LIVE_INTEGRITY_MIN_INTERVAL_SEC"] = interval
        atomic_write_json(c.MANUAL_LIVE_POSITIONS_FILE, {"by_wallet": {}, "by_coin_net": {}})
        atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {}})
        atomic_write_json(c.LIVE_INTEGRITY_STATUS_FILE, {
            "created_at_ms": c.utc_now_ms() - age_ms, "counts": {"exchange_manual_mismatch": 0}})
        core = _core_for(tmp)
        summary = core.run_cycle(poll_live=False, poll_copy=False, reconcile_exchange=False)
        check(f"SET009_freshness_{tag}_stale_is_{str(want_stale).lower()}",
              summary.integrity_status_stale is want_stale,
              f"stale={summary.integrity_status_stale} age_ms={summary.integrity_status_age_ms} interval={interval!r}")
        check(f"SET009_freshness_{tag}_entry_stale_block_is_{str(want_stale).lower()}",
              (core._entry_sends_blocked_reason == "LEDGER_STATUS_STALE") is want_stale,
              f"block={core._entry_sends_blocked_reason!r}")
    os.environ.pop("HL_LIVE_INTEGRITY_MIN_INTERVAL_SEC", None)


def main():
    test_polarity_exchange_has_ledger_flat()
    test_polarity_ledger_has_exchange_flat()
    test_gate_blocks_sends_on_divergence()
    test_no_block_when_matched()
    test_stale_status_holds_entries_but_not_closes()
    test_missing_status_holds_entries_and_alerts()
    test_close_decision_never_refused_for_stale("0")
    test_close_decision_never_refused_for_stale(None)
    test_default_mode_stale_blocks_entry()
    test_writer_interval_scales_freshness_bound()
    
    failed = [n for n, ok in RESULTS if not ok]
    print(f"\nTOTAL={len(RESULTS)} FAILED={len(failed)}")
    if failed:
        print("FAILED:", ", ".join(failed))
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
