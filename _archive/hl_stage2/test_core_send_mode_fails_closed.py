import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
FAILS = []
PASSES = []

def check(name, cond, detail=""):
    if cond:
        print("  PASS " + name)
        PASSES.append(name)
    else:
        print("  FAIL " + name + "  " + detail)
        FAILS.append(name)

def write(p, payload):
    p.write_text(json.dumps(payload), encoding="utf-8")

def main():
    import HL_Live_Copy_Service_Core as C
    with tempfile.TemporaryDirectory() as td:
        cfg_file = Path(td) / "live_config.json"
        wallet = "0x" + "a" * 40
        wallets = {wallet: {"enabled": True, "mode": "ON"}}
        def fresh(payload):
            write(cfg_file, payload)
            return C.ConfigManager(config_path=cfg_file)
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        cm = fresh({"global_controls": {"send_mode": "BANANA"}, "wallets": wallets})
        check("invalid send_mode does not arm sending", cm.master_real_orders_enabled is False, "send_mode=" + repr(cm.send_mode) + " enabled=" + repr(cm.master_real_orders_enabled))
        cm = fresh({"auto_send_enabled": "banana", "wallets": wallets, "global_controls": {}})
        check("invalid auto_send_enabled does not arm sending", cm.master_real_orders_enabled is False, "send_mode=" + repr(cm.send_mode) + " enabled=" + repr(cm.master_real_orders_enabled))
        cm = fresh({"wallets": wallets, "global_controls": {}})
        check("missing mode + legacy env ON sends nothing", cm.master_real_orders_enabled is False, "send_mode=" + repr(cm.send_mode) + " enabled=" + repr(cm.master_real_orders_enabled))
        os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "1"
        cfg_file.write_text("{ this is not json", encoding="utf-8")
        cm = C.ConfigManager(config_path=cfg_file)
        check("corrupt config + legacy env ON sends nothing", cm.master_real_orders_enabled is False, "send_mode=" + repr(cm.send_mode) + " enabled=" + repr(cm.master_real_orders_enabled))
        os.environ.pop("HL_LIVE_AUTO_SEND_ENABLED", None)
        for want in ("OFF", "CLOSE", "ON"):
            cm = fresh({"global_controls": {"send_mode": want}, "wallets": wallets})
            check("send_mode " + want + " reads back", cm.send_mode == want, "got " + repr(cm.send_mode))
            cm2 = C.ConfigManager(config_path=cfg_file)
            check("send_mode " + want + " survives reload", cm2.send_mode == want, "got " + repr(cm2.send_mode))
            armed = cm2.master_real_orders_enabled
            check("send_mode " + want + " arms=" + str(want != "OFF"), armed is (want != "OFF"), "armed=" + repr(armed))
    print("\nTOTAL=" + str(len(PASSES) + len(FAILS)) + " FAILED=" + str(len(FAILS)))
    return 1 if FAILS else 0

if __name__ == "__main__":
    sys.exit(main())
