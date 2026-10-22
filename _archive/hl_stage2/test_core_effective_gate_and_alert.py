#!/usr/bin/env python3
"""Test: Effective master send gate shown + alert when engine state and config disagree.

This test verifies:
1. The effective master send gate value is displayed correctly
2. An alert fires when persisted engine send state and global_controls.send_mode disagree
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

        # Test 4: No send_mode or explicit legacy key must fail closed despite an env flag.
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        write_cfg(config_file, {
            "global_controls": {},  # no send_mode
            "wallets": {wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}}
        })

        live_config = UI._load_live_copy_config()
        send_mode = UI._send_mode(live_config)
        master_on = UI._master_switch_on(live_config)
        
        check("Test 4: no send_mode or legacy key, env=1 -> send_mode=OFF",
              send_mode == "OFF", f"got {send_mode}")
        check("Test 4: master switch OFF", master_on is False, f"got {master_on}")

        # Test 5: The explicit legacy config key remains supported.
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {
            "auto_send_enabled": True,
            "global_controls": {},
            "wallets": {wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}}
        })

        live_config = UI._load_live_copy_config()
        send_mode = UI._send_mode(live_config)
        master_on = UI._master_switch_on(live_config)
        
        check("Test 5: explicit legacy auto_send_enabled=true -> send_mode=ON",
              send_mode == "ON", f"got {send_mode}")
        check("Test 5: explicit legacy master switch ON", master_on is True, f"got {master_on}")

        # Invalid explicit modes fail closed instead of falling through to legacy config.
        check("invalid explicit send_mode fails closed despite legacy true",
              UI._send_mode({"global_controls": {"send_mode": "INVALID"}, "auto_send_enabled": True}) == "OFF")
        check("send-mode acknowledgement requires exact engine-reported mode",
              "String(st.engine_send_mode||'').toUpperCase()===mode" in
              (HERE / "HL_Copy_App_SSOT.py").read_text(encoding="utf-8"))
        top = UI._build_live_top_status(
            {"global_controls": {"send_mode": "CLOSE"}, "wallets": {}}, {},
            {"send_mode": "CLOSE"}, {"available": False}, [], [], [])
        no_engine_mode = UI._build_live_top_status(
            {"global_controls": {"send_mode": "CLOSE"}, "wallets": {}}, {},
            {}, {"available": False}, [], [], [])
        check("status forwards exact engine mode when present", top.get("engine_send_mode") == "CLOSE")
        check("status leaves engine mode unconfirmed when absent", no_engine_mode.get("engine_send_mode") == "")

        # Test 6: _engine_alert compares config with persisted engine state, not UI env.
        write_cfg(config_file, {"global_controls": {"send_mode": "ON"}, "wallets": {}})
        write_cfg(service_state_file, {"send_mode": "ON", "master_real_orders_enabled": True})
        alert = UI._engine_alert()
        check("Test 6a: matching ON engine/config has no alert",
              alert == "",
              f"got: {alert}")

        write_cfg(config_file, {"global_controls": {"send_mode": "OFF"}, "wallets": {}})
        write_cfg(service_state_file, {"send_mode": "ON", "master_real_orders_enabled": True})
        alert = UI._engine_alert()
        check("Test 6b: engine ON/config OFF disagreement alerts",
              "SEND GATE MISMATCH" in alert and "config send_mode=OFF" in alert and "engine state send_mode=ON" in alert,
              f"got: {alert}")

        write_cfg(config_file, {"global_controls": {"send_mode": "CLOSE"}, "wallets": {}})
        write_cfg(service_state_file, {"master_real_orders_enabled": True})
        alert = UI._engine_alert()
        check("Test 6c: CLOSE remains armed when engine master is ON",
              alert == "", f"got: {alert}")

        write_cfg(config_file, {"global_controls": {"send_mode": "ON"}, "wallets": {}})
        write_cfg(service_state_file, {"master_real_orders_enabled": False})
        alert = UI._engine_alert()
        check("Test 6d: engine master OFF/config ON disagreement alerts",
              "SEND GATE MISMATCH" in alert and "config send_mode=ON" in alert and "master_real_orders_enabled=false" in alert,
              f"got: {alert}")

        write_cfg(config_file, {"global_controls": {}, "wallets": {}})
        write_cfg(service_state_file, {"send_mode": "ON", "master_real_orders_enabled": True})
        alert = UI._engine_alert()
        check("Test 6e: absent config send_mode produces no mismatch alert",
              alert == "", f"got: {alert}")

        # Without engine send truth there is no basis to claim a mismatch.
        service_state_file.unlink()
        write_cfg(config_file, {"global_controls": {}, "wallets": {}})
        alert = UI._engine_alert()
        check("Test 6f: missing engine/config mode has no mismatch alert",
              alert == "", f"got: {alert}")

    print(f"\nTOTAL={len(PASSES) + len(FAILS)} FAILED={len(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
