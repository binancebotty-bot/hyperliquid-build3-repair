#!/usr/bin/env python3
"""Offline UI checks for scoped account values and engine-owned send alerts."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FAILS: list[str] = []
PASSES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSES if condition else FAILS).append(name)
    print(("  PASS " if condition else "  FAIL ") + name + ("  " + detail if detail and not condition else ""))


def load_ui_without_environment(audit_dir: Path):
    """Import the app with synthetic settings; never read the process environment or env file."""
    import exchange_truth as xnet

    xnet.env_with_file = lambda _path: {
        "HL_LEADER_NETWORK": "testnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_AUDIT_DIR": str(audit_dir),
        "HL_APP_PORT": "8031",
    }
    xnet.claim_network_stamp = lambda *_args, **_kwargs: None
    original_environ, original_getenv = os.environ, os.getenv
    try:
        os.environ = {}
        os.getenv = lambda _key, default=None: default or ""
        import HL_Copy_App_SSOT as ui
    finally:
        os.environ, os.getenv = original_environ, original_getenv
    ui.LIVE_COPY_AUDIT_DIR = audit_dir
    ui.LIVE_COPY_CONFIG_FILE = audit_dir / "live_config.json"
    ui.LIVE_CONFIG_FILE = ui.LIVE_COPY_CONFIG_FILE
    ui.LIVE_CONFIG_DIR = audit_dir
    ui.LIVE_COPY_SERVICE_STATE_FILE = audit_dir / "live_service_state.json"
    return ui


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def audit_fixture(snapshot: dict, alert: str = "") -> dict:
    return {
        "status_banner": {"account_value": 120.0, "follower_network": "testnet", "health": {"text": "OK", "level": "green"}},
        "exchange_account_snapshot": snapshot,
        "follower_account": {"ok": True, "value": 120.0},
        "master_real_orders_enabled": True,
        "engine_alert": alert,
        "live_top_status": {"health": {"text": "OK", "level": "green"}, "ws_enabled": False, "ws_status": "POLLING"},
        "pnl_tally": {"start_available": False, "reason": "synthetic fixture"},
        "exchange_account_history": [],
        "exchange_history": [],
        "live_graph": {"account_points": [], "realized_pnl_points": []},
        "live_wallet_rows": [],
        "live_leader_performance": {},
        "manual_live_summary": {},
        "execution_quality_rows": [],
        "execution_quality_summary": {},
        "owned_copy_positions": [],
        "orphan_exchange_positions": [],
        "manual_reconciliation_rows": [],
        "recent_send_attempts": [],
        "send_attempt_counts": {},
        "audit_rows": [],
        "last_rows": [],
        "rows": [],
        "reason_counts": {},
        "status_counts": {},
        "source_counts": {},
        "execution_decision_counts": {},
        "decision_reason_counts": {},
        "manual_reconcile_required_counts": {},
        "market_data_error_counts": {},
        "send_terminal_rows": [],
        "legacy_terminal_rows": [],
        "reconciliation_rows": [],
        "clean_core_status": {"service_state": {}},
    }


def render_headless(ui, audit: dict) -> tuple[str, list[str]]:
    from playwright.sync_api import sync_playwright

    api = {
        "/api/live-config": {"config": {"global_controls": {"send_mode": "ON"}, "wallets": {}}},
        "/api/live-ws-health": {"health": {"overall": "POLLING", "ws_summary": {}, "wallets": {}}},
        "/api/live-audit-summary": audit,
        "/api/global-controls": {"global_controls": {"send_mode": "ON"}, "networks": {"leader": "testnet", "follower": "testnet", "follower_dexes": [], "state_dir": "synthetic"}},
    }
    api_json = json.dumps(api)
    fake_fetch = """<script>
window.fetch = async (url) => {
  const path = new URL(url, 'http://127.0.0.1:8031/').pathname;
  const value = (%s)[path] || {};
  return {ok:true, status:200, json:async()=>value};
};
</script>""" % api_json
    response = ui.live_copy_dashboard()
    page_html = response.body.decode("utf-8").replace("<body>", "<body>" + fake_fetch, 1)
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(page_html, wait_until="networkidle")
            page.wait_for_function("document.querySelector('#lcBannerAcct')?.textContent.includes('$120.00')", timeout=5000)
            return page.locator("body").inner_text(), errors
        finally:
            browser.close()


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        audit_dir = Path(td)
        ui = load_ui_without_environment(audit_dir)

        env_reads: list[str] = []
        ui._local_env_value = lambda key: (env_reads.append(key) or "0")
        write_json(ui.LIVE_COPY_CONFIG_FILE, {"global_controls": {"send_mode": "ON"}, "wallets": {}})
        write_json(ui.LIVE_COPY_SERVICE_STATE_FILE, {"send_mode": "ON", "master_real_orders_enabled": True})
        alert = ui._engine_alert()
        check("view-only UI env OFF does not alert when engine state agrees with config", alert == "", alert)
        check("send-mode alert does not read the UI environment", not env_reads, str(env_reads))

        write_json(ui.LIVE_COPY_CONFIG_FILE, {"global_controls": {"send_mode": "OFF"}, "wallets": {}})
        write_json(ui.LIVE_COPY_SERVICE_STATE_FILE, {"send_mode": "ON", "master_real_orders_enabled": True})
        alert = ui._engine_alert()
        check("real engine/config disagreement still alerts", "SEND GATE MISMATCH" in alert and "engine" in alert.lower(), alert)

        values = {"account_value": 65.5, "unified_portfolio_value": 116.7, "raw_spot_balances": [{"coin": "USDC", "total": 116.7}]}
        write_json(ui.LIVE_COPY_CONFIG_FILE, {"global_controls": {"send_mode": "ON"}, "wallets": {}})
        write_json(ui.LIVE_COPY_SERVICE_STATE_FILE, {"send_mode": "ON", "master_real_orders_enabled": True})
        view_only_alert = ui._engine_alert()
        rendered, errors = render_headless(ui, audit_fixture(values, view_only_alert))
        check("rendered DOM keeps the account-value header", "ACCOUNT VALUE (TESTNET)" in rendered and "$120.00" in rendered)
        check("rendered DOM distinguishes unified spot-backed value from perp margin view", all(s in rendered for s in ("Unified account value (spot USDC; backs perps): $116.70", "Perp margin view (accountValue): $65.50")) and "SPOT USDC: $116.70" not in rendered, rendered[:1000])
        values["xyz_perp_account_value"] = 62.25
        rendered_xyz, xyz_errors = render_headless(ui, audit_fixture(values, view_only_alert))
        check("XYZ scope renders separately without changing default-scope value", all(s in rendered_xyz for s in ("Perp margin view (accountValue): $65.50", "XYZ perp DEX margin view (accountValue): $62.25")) and rendered_xyz.count("Perp margin view (accountValue): $65.50") == 1, rendered_xyz[:1200])
        check("XYZ-scope headless render has no JavaScript errors", not xyz_errors, "; ".join(xyz_errors))
        values["xyz_perp_account_value"] = None
        unavailable_xyz, unavailable_xyz_errors = render_headless(ui, audit_fixture(values, view_only_alert))
        check("failed XYZ read renders unavailable and not zero", "XYZ perp DEX margin view (accountValue): unavailable" in unavailable_xyz and "$0.00" not in unavailable_xyz)
        check("unavailable XYZ-scope render has no JavaScript errors", not unavailable_xyz_errors, "; ".join(unavailable_xyz_errors))
        check("wallet P&L is visibly labelled as sleeve profit, not balance", "NET P&L (SLEEVE)" in rendered and "does not sum to account value" in rendered)
        check("matching engine state renders no false red alert", "SEND GATE MISMATCH" not in rendered)
        check("headless UI rendered without JavaScript errors", not errors, "; ".join(errors))

        missing = {"account_value": None, "unified_portfolio_value": None, "raw_spot_balances": []}
        unavailable, missing_errors = render_headless(ui, audit_fixture(missing, ""))
        check("missing scoped values render as unavailable, not zero", all(s in unavailable for s in ("Unified account value (spot USDC; backs perps): unavailable", "Perp margin view (accountValue): unavailable")) and "$0.00" not in unavailable)
        check("missing-value headless render has no JavaScript errors", not missing_errors, "; ".join(missing_errors))

    print(f"\nTOTAL={len(PASSES) + len(FAILS)} FAILED={len(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
