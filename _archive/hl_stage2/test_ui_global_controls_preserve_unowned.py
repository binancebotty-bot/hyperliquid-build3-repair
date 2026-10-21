#!/usr/bin/env python3
"""Global-controls saves preserve unowned settings and accept the global send mode.

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
    source = (HERE / "HL_Copy_App_SSOT.py").read_text(encoding="utf-8")
    live_only_config = {"wallets": {
        **{f"live-{i}": {"mode": "LIVE"} for i in range(10)},
        **{f"clo-{i}": {"mode": "CLO"} for i in range(8)},
    }}
    try:
        ui._enforce_live_copy_cap(live_only_config)
        live_only_cap_accepts_clo = True
    except ValueError:
        live_only_cap_accepts_clo = False
    live_only_config["wallets"]["live-10"] = {"mode": "LIVE"}
    try:
        ui._enforce_live_copy_cap(live_only_config)
        live_only_cap_rejects_eleventh = False
    except ValueError as exc:
        live_only_cap_rejects_eleventh = str(exc) == "MAX_WALLETS_EXCEEDED"

    with TestClient(ui.app) as client:
        initial = client.get("/api/global-controls").json()["global_controls"]
        response = client.post("/api/global-controls", json={
            "max_order_notional_usd": 1250.0,
            "send_mode": "OFF",
            "follower_leverage": 99,
            "liq_parity": False,
            "custom_runtime_flag": "overwrite-attempt",
            "marketable_slippage_pct": 0.75,
        })
        changed_controls = json.loads(config_path.read_text(encoding="utf-8"))["global_controls"]
        accepted_modes = []
        for mode in ("ON", "CLOSE", "OFF"):
            mode_response = client.post("/api/global-controls", json={"send_mode": mode})
            accepted_modes.append(mode_response.status_code == 200 and json.loads(config_path.read_text(encoding="utf-8"))["global_controls"].get("send_mode") == mode)
        no_mode = json.loads(config_path.read_text(encoding="utf-8"))
        no_mode["global_controls"]["send_mode"] = "INVALID"
        config_path.write_text(json.dumps(no_mode), encoding="utf-8")
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        fail_closed_invalid = client.get("/api/global-controls").json()["global_controls"].get("send_mode") == "OFF"
        no_mode["global_controls"].pop("send_mode", None)
        config_path.write_text(json.dumps(no_mode), encoding="utf-8")
        fail_closed_default = client.get("/api/global-controls").json()["global_controls"].get("send_mode") == "OFF"
        no_mode["auto_send_enabled"] = True
        config_path.write_text(json.dumps(no_mode), encoding="utf-8")
        explicit_legacy_mode = client.get("/api/global-controls").json()["global_controls"].get("send_mode") == "ON"
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"

    controls = changed_controls
    checks = {
        "save_succeeded": response.status_code == 200 and response.json().get("ok") is True,
        "initial_send_mode_read": initial.get("send_mode") == "CLOSE",
        "send_mode_changed": controls.get("send_mode") == "OFF",
        "all_global_modes_accepted": all(accepted_modes),
        "invalid_mode_fails_closed": fail_closed_invalid,
        "header_default_off_even_when_legacy_env_on": fail_closed_default,
        "header_matches_explicit_legacy_config_without_env_fallback": explicit_legacy_mode,
        "follower_leverage_preserved": controls.get("follower_leverage") == 7,
        "liq_parity_preserved": controls.get("liq_parity") is True,
        "unknown_runtime_flag_preserved": controls.get("custom_runtime_flag") == "keep-existing",
        "form_owned_slippage_alias_applied": float(controls.get("marketable_bps") or 0.0) == 75.0,
        "form_owned_value_changed": float(controls.get("max_order_notional_usd") or 0.0) == 1250.0,
        "live_only_cap_accepts_ten_live_eight_close_only": live_only_cap_accepts_clo,
        "live_only_cap_still_rejects_eleventh_live": live_only_cap_rejects_eleventh,
        "header_mode_ui_and_fail_closed_default": 'id="lcSendMode"' in source and "mode==='CLO'||mode==='CLOSE ONLY'?'CLOSE':['ON','CLOSE','OFF'].includes(mode)?mode:'OFF'" in source,
        "mode_change_uses_inline_confirmation_and_requires_exact_engine_mode": 'id="lcSendModeConfirm"' in source and "window.confirm(mode==='CLOSE'" not in source and "engine_send_mode" in source and "awaiting exact engine confirmation" in source and "engine acknowledged" in source and "lc-amber" in source,
        "posts_existing_controls_with_mode": "...lcGlobalControls" in source and "send_mode:mode" in source and "jpost('/api/global-controls'" in source,
    }
    for name, passed in checks.items():
        print(f"RESULT::{name}_{'PASS' if passed else 'FAIL'}")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
