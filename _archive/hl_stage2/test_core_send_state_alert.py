#!/usr/bin/env python3
"""Audit alert for the effective send mode at startup and on config reload.

Offline: temp config file only, no network, no orders, no keys.
Run: python test_core_send_state_alert.py   # TOTAL/FAILED, exit 0/1.
"""
import json
import os
import sys
import tempfile
import io
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
FAILS = []
PASSES = []


def check(name, cond, detail=""):
    if cond:
        PASSES.append(name)
        print("  PASS " + name)
    else:
        FAILS.append(name)
        print("  FAIL " + name + "  " + detail)


def write_cfg(p, payload):
    p.write_text(json.dumps(payload), encoding="utf-8")


def call_alert(cm):
    """Invoke send_state_alert, capturing stderr. Fails cleanly (no traceback) on unpatched Core."""
    method = getattr(cm, "send_state_alert", None)
    if method is None:
        return "", ""
    buf = io.StringIO()
    old = sys.stderr
    sys.stderr = buf
    try:
        line = method()
    finally:
        sys.stderr = old
    return line, buf.getvalue()


def main():
    import HL_Live_Copy_Service_Core as C
    wallet = "0x" + "a" * 40
    wallets = {wallet: {"enabled": True, "mode": "ON"}}
    old_env = os.environ.get("HL_LIVE_AUTO_SEND_ENABLED", None)
    try:
        with tempfile.TemporaryDirectory() as td:
            cfg_file = Path(td) / "live_config.json"

            def fresh(payload):
                write_cfg(cfg_file, payload)
                return C.ConfigManager(config_path=cfg_file)

            # 1. launcher env=1, config send_mode OFF -> mismatch alert
            os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
            cm = fresh({"global_controls": {"send_mode": "OFF"}, "wallets": wallets})
            line, err = call_alert(cm)
            check("env=1/config=OFF emits mode+source+mismatch alert",
                  "effective_send_mode=OFF" in line and "source=config.send_mode" in line
                  and "ALERT" in err and "OFF" in err, "line=" + line + " err=" + err)

            # 2. launcher env=1, config send_mode ON -> normal line, no alert
            os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
            cm = fresh({"global_controls": {"send_mode": "ON"}, "wallets": wallets})
            line, err = call_alert(cm)
            check("env=1/config=ON normal line, no alert",
                  "effective_send_mode=ON" in line and "source=config.send_mode" in line
                  and "ALERT" not in err, "line=" + line + " err=" + err)

            # 3. launcher env unset(=0), config auto_send_enabled True -> reverse mismatch alert
            os.environ.pop("HL_LIVE_AUTO_SEND_ENABLED", None)
            cm = fresh({"auto_send_enabled": True, "wallets": wallets})
            line, err = call_alert(cm)
            check("env-unset/config-ON reverse mismatch alert",
                  "effective_send_mode=ON" in line and "source=config.auto_send_enabled" in line
                  and "ALERT" in err, "line=" + line + " err=" + err)

            # 4. reload: re-read changed config from disk (mirrors run_cycle's ConfigManager()), re-emit
            write_cfg(cfg_file, {"global_controls": {"send_mode": "OFF"}, "wallets": wallets})
            cm_reload = C.ConfigManager(config_path=cfg_file)
            line, err = call_alert(cm_reload)
            check("reload re-emits OFF after config change", "effective_send_mode=OFF" in line, "line=" + line)
            write_cfg(cfg_file, {"global_controls": {"send_mode": "ON"}, "wallets": wallets})
            cm_reload = C.ConfigManager(config_path=cfg_file)
            line, err = call_alert(cm_reload)
            check("reload re-emits ON after config change", "effective_send_mode=ON" in line, "line=" + line)

            # bonus: source is default OFF when neither send_mode nor auto_send_enabled is present
            os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
            cm = fresh({"wallets": wallets})
            line, err = call_alert(cm)
            check("default OFF source emits no mismatch",
                  "source=default OFF" in line and "effective_send_mode=OFF" in line and "ALERT" not in err,
                  "line=" + line + " err=" + err)
    finally:
        if old_env is None:
            os.environ.pop("HL_LIVE_AUTO_SEND_ENABLED", None)
        else:
            os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = old_env
    print("\nTOTAL=" + str(len(PASSES) + len(FAILS)) + " FAILED=" + str(len(FAILS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
