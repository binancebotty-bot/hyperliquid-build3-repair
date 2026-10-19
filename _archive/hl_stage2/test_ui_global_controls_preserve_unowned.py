#!/usr/bin/env python3
"""A global-controls save must preserve settings that the form does not own.

Run: python test_ui_global_controls_preserve_unowned.py  # isolated temp config, no network or orders.
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
    tmp = Path(tempfile.mkdtemp(prefix="global_controls_preserve_"))
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
            "custom_runtime_flag": "keep-existing",
            "max_order_notional_usd": 1000.0,
        },
    }), encoding="utf-8")

    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient

    ui.LIVE_COPY_CONFIG_FILE = config_path
    with TestClient(ui.app) as client:
        response = client.post("/api/global-controls", json={
            "max_order_notional_usd": 1250.0,
            "send_mode": "OFF",
            "follower_leverage": 99,
            "liq_parity": False,
            "custom_runtime_flag": "overwrite-attempt",
            "marketable_slippage_pct": 0.75,
        })

    written = json.loads(config_path.read_text(encoding="utf-8"))
    controls = written["global_controls"]
    checks = {
        "save_succeeded": response.status_code == 200 and response.json().get("ok") is True,
        "send_mode_preserved": controls.get("send_mode") == "CLOSE",
        "follower_leverage_preserved": controls.get("follower_leverage") == 7,
        "liq_parity_preserved": controls.get("liq_parity") is True,
        "unknown_runtime_flag_preserved": controls.get("custom_runtime_flag") == "keep-existing",
        "form_owned_slippage_alias_applied": float(controls.get("marketable_bps") or 0.0) == 75.0,
        "form_owned_value_changed": float(controls.get("max_order_notional_usd") or 0.0) == 1250.0,
    }
    for name, passed in checks.items():
        print(f"RESULT::{name}_{'PASS' if passed else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
