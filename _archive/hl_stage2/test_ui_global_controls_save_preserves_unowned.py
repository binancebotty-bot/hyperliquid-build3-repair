#!/usr/bin/env python3
"""A real form submit (form-owned fields only) must not reset unowned settings.

Run: python test_ui_global_controls_save_preserves_unowned.py  # temp config, no network/orders.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="global_controls_form_save_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp / "audit")
    os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
    os.environ["HL_LIVE_POLL_ENABLED"] = "0"

    config_path = tmp / "live_config.json"
    config_path.write_text(json.dumps({
        "wallets": {},
        "global_controls": {
            "send_mode": "CLOSE",
            "follower_leverage": 7,
            "liq_parity": True,
            "max_order_notional_usd": 1000.0,
            "marketable_bps": 20.0,
        },
    }), encoding="utf-8")

    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient

    ui.LIVE_COPY_CONFIG_FILE = config_path
    with TestClient(ui.app) as client:
        # exactly the payload the Global Controls form builds
        response = client.post("/api/global-controls", json={
            "max_total_live_exposure_usd": 0.0,
            "max_asset_directional_exposure_usd": 0.0,
            "max_daily_loss_usd": 0.0,
            "max_wallet_exposure_usd": 0.0,
            "max_order_notional_usd": 1250.0,
            "marketable_slippage_pct": 0.75,
            "max_close_adverse_diff_pct": 0.0,
            "symbol_allowlist": [],
            "symbol_blocklist": [],
        })
        reloaded = client.get("/api/global-controls")

    written = json.loads(config_path.read_text(encoding="utf-8"))
    controls = written["global_controls"]
    reloaded_gc = (reloaded.json() or {}).get("global_controls") or {}
    checks = {
        "save_succeeded": response.status_code == 200 and response.json().get("ok") is True,
        "send_mode_unchanged": controls.get("send_mode") == "CLOSE",
        "follower_leverage_unchanged": controls.get("follower_leverage") == 7,
        "liq_parity_unchanged": controls.get("liq_parity") is True,
        "form_owned_max_order_notional_changed": float(controls.get("max_order_notional_usd") or 0.0) == 1250.0,
        "form_owned_marketable_bps_changed": float(controls.get("marketable_bps") or 0.0) == 75.0,
        "unowned_keys_survive_reload": (
            reloaded_gc.get("send_mode") == "CLOSE"
            and reloaded_gc.get("follower_leverage") == 7
            and reloaded_gc.get("liq_parity") is True
        ),
        "absent_key_still_defaulted": float(controls.get("max_daily_loss_usd") or 0.0) == 0.0,
    }
    for name, passed in checks.items():
        print(f"RESULT::{name}_{'PASS' if passed else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
