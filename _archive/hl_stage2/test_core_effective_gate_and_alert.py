#!/usr/bin/env python3
"""Test: Effective master send gate shown + alert when env and config disagree.

This test verifies:
1. The effective master send gate value is displayed correctly
2. An alert fires when HL_LIVE_AUTO_SEND_ENABLED env and global_controls.send_mode disagree
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FAILS = []
PASSES = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print("  PASS " + name)
        PASSES.append(name)
    else:
        print("  FAIL " + name + "  " + detail)
        FAILS.append(name)


def write_cfg(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    import HL_Copy_App_SSOT as UI

    with tempfile.TemporaryDirectory() as td:
        audit_dir = Path(td) / "hl_live_copy_audit"
        audit_dir.mkdir(parents=True)
        config_file = audit_dir / "live_config.json"
        service_state_file = audit_dir / "live_service_state.json"

        UI.LIVE_COPY_CONFIG_FILE = config_file
        UI.LIVE_COPY_AUDIT_DIR = audit_dir
        UI.LIVE_CONFIG_FILE = config_file
        UI.LIVE_CONFIG_DIR = audit_dir
        UI.LIVE_COPY_SERVICE_STATE_FILE = service_state_file

        wallet = "0x" + "a" * 40

        # Test 1: Config send_mode=ON, env HL_LIVE_AUTO_SEND_ENABLED=0 -> disagreement
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {
            "global_controls": {"send_mode": "ON"},
            "wallets": {wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}}
        })
        write_cfg(service_state_file, {"effective_real_orders_enabled": True})

        live_config = UI._load_live_copy_config()
        send_mode = UI._send_mode(live_config)
        master_on = UI._master_switch_on(live_config)
        env_val = UI._local_env_value("HL_LIVE_AUTO_SEND_ENABLED")
        
        check("Test 1: config send_mode=ON, env=0 -> send_mode=ON (config wins)",
              send_mode == "ON", f"got {send_mode}")
        check("Test 1: master switch ON", master_on is True, f"got {master_on}")
        check("Test 1: env value is 0", env_val == "0", f"got {env_val}")

        # Test 2: Config send_mode=OFF, env HL_LIVE_AUTO_SEND_ENABLED=1 -> disagreement
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        write_cfg(config_file, {
            "global_controls": {"send_mode": "OFF"},
            "wallets": {wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}}
        })
        write_cfg(service_state_file, {"effective_real_orders_enabled": False})

        live_config = UI._load_live_copy_config()
        send_mode = UI._send_mode(live_config)
        master_on = UI._master_switch_on(live_config)
        env_val = UI._local_env_value("HL_LIVE_AUTO_SEND_ENABLED")
        
        check("Test 2: config send_mode=OFF, env=1 -> send_mode=OFF (config wins)",
              send_mode == "OFF", f"got {send_mode}")
        check("Test 2: master switch OFF", master_on is False, f"got {master_on}")
        check("Test 2: env value is 1", env_val == "1", f"got {env_val}")

        # Test 3: Config send_mode=CLOSE, env HL_LIVE_AUTO_SEND_ENABLED=0 -> config wins
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {
            "global_controls": {"send_mode": "CLOSE"},
            "wallets": {wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}}
        })

        live_config = UI._load_live_copy_config()
        send_mode = UI._send_mode(live_config)
        master_on = UI._master_switch_on(live_config)
        
        check("Test 3: config send_mode=CLOSE, env=0 -> send_mode=CLOSE (config wins)",
              send_mode == "CLOSE", f"got {send_mode}")
        check("Test 3: master switch ON (CLOSE counts as armed)", master_on is True, f"got {master_on}")

        # Test 4: No send_mode in config, env HL_LIVE_AUTO_SEND_ENABLED=1 -> env wins (legacy)
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        write_cfg(config_file, {
            "global_controls": {},  # no send_mode
            "wallets": {wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}}
        })

        live_config = UI._load_live_copy_config()
        send_mode = UI._send_mode(live_config)
        master_on = UI._master_switch_on(live_config)
        
        check("Test 4: no send_mode, env=1 -> send_mode=ON (legacy)",
              send_mode == "ON", f"got {send_mode}")
        check("Test 4: master switch ON", master_on is True, f"got {master_on}")

        # Test 5: No send_mode in config, env HL_LIVE_AUTO_SEND_ENABLED=0 -> OFF
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {
            "global_controls": {},
            "wallets": {wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}}
        })

        live_config = UI._load_live_copy_config()
        send_mode = UI._send_mode(live_config)
        master_on = UI._master_switch_on(live_config)
        
        check("Test 5: no send_mode, env=0 -> send_mode=OFF",
              send_mode == "OFF", f"got {send_mode}")
        check("Test 5: master switch OFF", master_on is False, f"got {master_on}")

        # Test 6: _engine_alert should detect env/config disagreement
        # Test alert function
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {"global_controls": {"send_mode": "ON"}, "wallets": {}})
        alert = UI._engine_alert()
        check("Test 6a: alert fires for config ON, env OFF",
              "SEND GATE MISMATCH" in alert and "config send_mode=ON" in alert and "HL_LIVE_AUTO_SEND_ENABLED=0" in alert,
              f"got: {alert}")

        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        write_cfg(config_file, {"global_controls": {"send_mode": "OFF"}, "wallets": {}})
        alert = UI._engine_alert()
        check("Test 6b: alert fires for config OFF, env ON",
              "SEND GATE MISMATCH" in alert and "config send_mode=OFF" in alert and "HL_LIVE_AUTO_SEND_ENABLED=1" in alert,
              f"got: {alert}")

        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        write_cfg(config_file, {"global_controls": {"send_mode": "ON"}, "wallets": {}})
        alert = UI._engine_alert()
        check("Test 6c: no alert for config ON, env ON",
              alert == "", f"got: {alert}")

        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {"global_controls": {"send_mode": "OFF"}, "wallets": {}})
        alert = UI._engine_alert()
        check("Test 6d: no alert for config OFF, env OFF",
              alert == "", f"got: {alert}")

        # Test CLOSE mode
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {"global_controls": {"send_mode": "CLOSE"}, "wallets": {}})
        alert = UI._engine_alert()
        check("Test 6e: alert fires for config CLOSE, env OFF",
              "SEND GATE MISMATCH" in alert and "config send_mode=CLOSE" in alert and "HL_LIVE_AUTO_SEND_ENABLED=0" in alert,
              f"got: {alert}")

        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        write_cfg(config_file, {"global_controls": {"send_mode": "CLOSE"}, "wallets": {}})
        alert = UI._engine_alert()
        check("Test 6f: no alert for config CLOSE, env ON",
              alert == "", f"got: {alert}")

        # Test no send_mode in config (legacy) - no alert
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        write_cfg(config_file, {"global_controls": {}, "wallets": {}})
        alert = UI._engine_alert()
        check("Test 6g: no alert for no send_mode, env ON (legacy)",
              alert == "", f"got: {alert}")

        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {"global_controls": {}, "wallets": {}})
        alert = UI._engine_alert()
        check("Test 6h: no alert for no send_mode, env OFF",
              alert == "", f"got: {alert}")

    print(f"\nTOTAL={len(PASSES) + len(FAILS)} FAILED={len(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())