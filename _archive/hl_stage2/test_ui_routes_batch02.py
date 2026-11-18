#!/usr/bin/env python3
"""Direct JSON GET handler checks; isolated, no HTTP server or TestClient."""
from __future__ import annotations
import os, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []

def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"RESULT::{name}_{'PASS' if ok else 'FAIL'}" + (f" | {detail}" if not ok else ""))

def main():
    tmp = Path(tempfile.mkdtemp(prefix="uiroutes_batch02_", dir=os.environ.get("TMPDIR") or None))
    os.environ.update(HL_LIVE_AUDIT_DIR=str(tmp / "audit"), HL_LEADER_NETWORK="mainnet", HL_FOLLOWER_NETWORK="testnet")
    import HL_Copy_App_SSOT as ui
    # Keep all filesystem paths isolated; these read-only handlers receive explicit builder stubs below.
    ui.DATA_DIR = tmp / "data"
    ui.LIVE_COPY_AUDIT_DIR = tmp / "audit"
    ui.LIVE_COPY_CONFIG_FILE = tmp / "audit" / "live_config.json"
    ui.LIVE_CONFIG_FILE = ui.LIVE_COPY_CONFIG_FILE

    ui._load_live_copy_config = lambda: {"global_controls": dict(ui._GLOBAL_CONTROLS_DEFAULTS), "enabled": True}
    r = ui.get_live_config()
    body = r.body.decode()
    check("UI_ROUTE_23_LIVE_CONFIG_ENABLED", '"enabled":true' in body, body[:160])

    ui.get_model_state_cached = lambda **kw: {"wallet_rows": [{"wallet": "derived-wallet"}], "portfolio": {"equity": 73.25}, "copy_trades": [{"wallet": "0xabc", "coin": "ETH"}], "wallets": {"0xabc": {"curve": [{"equity": 91.5}]}}}
    r = ui.api_metrics()
    check("UI_ROUTE_06_METRICS_PORTFOLIO_EQUITY", b'73.25' in r.body, r.body.decode()[:180])
    r = ui.api_trades("0xABC")
    check("UI_ROUTE_07_TRADES_WALLET_FILTER", b'"coin":"ETH"' in r.body and b'0xabc' in r.body, r.body.decode())
    r = ui.api_equity("0xABC")
    check("UI_ROUTE_08_EQUITY_CURVE_VALUE", b'91.5' in r.body, r.body.decode())

    ui._live_audit_summary = lambda: {"open_orders": 4, "source": "stubbed-builder"}
    r = ui.live_copy_dashboard_json()
    check("UI_ROUTE_25_LIVE_COPY_JSON_AUDIT", b'"open_orders":4' in r.body, r.body.decode())
    r = ui.get_live_copy_summary()
    check("UI_ROUTE_26_LIVE_COPY_SUMMARY_AUDIT", b'"source":"stubbed-builder"' in r.body, r.body.decode())

    ui._load_live_ws_health = lambda: {"connected": True, "reconnects": 3}
    r = ui.get_live_ws_health()
    check("UI_ROUTE_29_WS_HEALTH_RECONNECTS", b'"reconnects":3' in r.body, r.body.decode())

    ui._load_live_copy_config = lambda: {"global_controls": dict(ui._GLOBAL_CONTROLS_DEFAULTS)}
    r = ui.get_global_controls()
    check("UI_ROUTE_27_GLOBAL_CONTROLS_NETWORK", b'"leader":"mainnet"' in r.body, r.body.decode()[:250])

    # Explicit skips: HTML-only /model /legacy-model /live-copy and root; excluded rather than faked.
    print("SKIP::GET /model, /legacy-model, /live-copy, / — HTML responses; this batch asserts derived JSON only")
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    if failed: print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
