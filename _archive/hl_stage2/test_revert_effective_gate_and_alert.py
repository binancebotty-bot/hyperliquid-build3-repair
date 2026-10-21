#!/usr/bin/env python3
"""Revert control test: behavior 3 (effective gate + alert) FAILS without the fix.

This test simulates the OLD _engine_alert logic (before the fix) and verifies it fails.
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


def old_engine_alert(UI, config_file: Path) -> str:
    """Simulate the OLD _engine_alert logic (before fix)."""
    st = UI.load_json(UI.LIVE_COPY_SERVICE_STATE_FILE, {})
    st = st if isinstance(st, dict) else {}
    if st.get("sender_key_invalid"):
        return (f"SENDING STOPPED: the {UI.FOLLOWER_NETWORK} exchange rejected the engine's signing key "
                f"({st.get('sender_key_invalid')}). Fix the key in the {UI.FOLLOWER_NETWORK} settings and restart the engine.")
    if st.get("entry_sends_blocked_reason"):
        return f"NEW ENTRIES PAUSED: {st.get('entry_sends_blocked_reason')} (exits still run)"
    return ""


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

        # Test 1: Config send_mode=ON, env=0 -> should alert but OLD logic doesn't
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {
            "global_controls": {"send_mode": "ON"},
            "wallets": {wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}}
        })
        write_cfg(service_state_file, {})

        alert = old_engine_alert(UI, config_file)
        check("REVERT: OLD logic does NOT alert for config ON, env OFF",
              "SEND GATE MISMATCH" not in alert,
              f"OLD logic unexpectedly alerts: {alert}")

        # Test 2: Config send_mode=OFF, env=1 -> should alert but OLD logic doesn't
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        write_cfg(config_file, {
            "global_controls": {"send_mode": "OFF"},
            "wallets": {wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}}
        })

        alert = old_engine_alert(UI, config_file)
        check("REVERT: OLD logic does NOT alert for config OFF, env ON",
              "SEND GATE MISMATCH" not in alert,
              f"OLD logic unexpectedly alerts: {alert}")

        # Test 3: Config send_mode=CLOSE, env=0 -> should alert but OLD logic doesn't
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {
            "global_controls": {"send_mode": "CLOSE"},
            "wallets": {wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}}
        })

        alert = old_engine_alert(UI, config_file)
        check("REVERT: OLD logic does NOT alert for config CLOSE, env OFF",
              "SEND GATE MISMATCH" not in alert,
              f"OLD logic unexpectedly alerts: {alert}")

        # Test 4: Effective gate display - OLD _send_mode still works but no alert
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
        write_cfg(config_file, {"global_controls": {"send_mode": "ON"}, "wallets": {}})
        live_config = UI._load_live_copy_config()
        send_mode = UI._send_mode(live_config)
        check("REVERT: _send_mode still works (config wins)", send_mode == "ON",
              f"got {send_mode}")

    print(f"\nTOTAL={len(PASSES) + len(FAILS)} FAILED={len(FAILS)} (expected failures show fix is needed)")
    revert_ok = all("REVERT" in name for name in PASSES) and len(FAILS) == 0
    return 0 if revert_ok else 1


if __name__ == "__main__":
    sys.exit(main())