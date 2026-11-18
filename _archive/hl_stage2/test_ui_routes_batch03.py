#!/usr/bin/env python3
"""Direct JSON GET handler checks for routes beyond batch 02."""
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
    tmp = Path(tempfile.mkdtemp(prefix="uiroutes_batch03_", dir=os.environ.get("TMPDIR") or None))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp / "audit")
    import HL_Copy_App_SSOT as ui
    ui.DATA_DIR = tmp / "data"
    ui.LIVE_COPY_AUDIT_DIR = tmp / "audit"
    ui.RAW_FILLS_CSV = tmp / "missing_raw.csv"
    ui.COPY_TRADES_CSV = tmp / "missing_trades.csv"
    ui.LIVE_COPY_ORDER_INTENTS_CSV = tmp / "missing_intents.csv"
    ui.SEND_ATTEMPTS_CSV = tmp / "missing_attempts.csv"
    ui.WALLET_GATE_FILE = tmp / "wallet_gate.json"
    ui._load_live_copy_config = lambda: {"enabled": True, "send_mode": "PAPER", "global_controls": dict(ui._GLOBAL_CONTROLS_DEFAULTS)}
    ui._master_switch_on = lambda config: bool(config.get("enabled"))
    ui._send_mode = lambda config: str(config.get("send_mode"))
    # Real handler, isolated file paths and configuration builder.
    r = ui.api_state()
    check("UI_ROUTE_05_STATE_GATE_COUNT", b'"wallet_gate_on_count":0' in r.body, r.body.decode()[:240])
    check("UI_ROUTE_05_STATE_SEND_MODE", b'"send_mode":"PAPER"' in r.body, r.body.decode()[:240])

    ui._MODEL_REFRESH_STATUS.clear()
    ui._MODEL_CACHE["state"] = {"sentinel": 1}
    ui._MODEL_DASHBOARD_HTML_CACHE.clear()
    ui.MODEL_DASHBOARD_LAST_GOOD_HTML_FILE = tmp / "absent.html"
    r = ui.api_model_cache_status()
    check("UI_ROUTE_04_CACHE_STATE_PRESENT", b'"model_state_present":true' in r.body, r.body.decode()[:240])
    check("UI_ROUTE_04_CACHE_HTML_ABSENT", b'"disk_html_present":false' in r.body, r.body.decode()[:240])

    # These routes render HTML rather than JSON and are intentionally not represented as JSON checks.
    print("SKIP::GET /wallet-meta/{wallet} — HTMLResponse page, not JSON")
    print("SKIP::GET /sort/{column} — HTML redirect/page rendering, not JSON")
    print("SKIP::GET /wallet/{wallet} — HTML dashboard page, not JSON")
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    if failed: print("FAILED: " + ", ".join(failed))
    return 1 if failed else 0
if __name__ == "__main__":
    raise SystemExit(main())
