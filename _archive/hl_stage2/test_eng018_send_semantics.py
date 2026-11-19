#!/usr/bin/env python3
"""Offline ENG-018 send-decision semantics; never submits orders."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

checks = []
def check(name, condition, detail=""):
    passed = bool(condition)
    checks.append((name, passed))
    print(f"{'PASS' if passed else 'FAIL'}: {name}" + (f" :: {detail}" if detail else ""))

def main():
    tmp = Path(tempfile.mkdtemp(prefix="eng018_send_"))
    os.environ.update(HL_LIVE_AUDIT_DIR=str(tmp), HL_LIVE_AUTO_SEND_ENABLED="0", HL_LIVE_POLL_ENABLED="0")
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {}}), encoding="utf-8")
    import HL_Live_Copy_Service as svcmod
    svcmod.TEST_INJECTION_ENABLED = True
    wallets = ("0xw1", "0xw2")
    configs = {w: svcmod.LiveWalletConfig(wallet=w, mode="LIVE", copy_mode="proportional",
               norm_base=1000.0, leader_equity_base=1000.0, enabled=True) for w in wallets}
    svc = svcmod.DryRunLiveCopyService()
    def decide(positions, actual):
        svc.state["leader_event_positions"] = {svc.position_key(w, "BTC"): v for w, v in positions.items()}
        f = svcmod.LeaderFill("eng018", wallets[0], "BTC", "BUY", 100.0, 1.0, 1.0,
                              1, "2026-01-01T00:00:00Z", "test", "test", {})
        return svc.convergence_order_for_coin(configs[wallets[0]], f, configs, actual)
    def fields(result):
        o = result.get("order")
        return getattr(o, "side", None), getattr(o, "size", None), getattr(o, "action", None)
    r = decide({wallets[0]: 3.0, wallets[1]: -1.0}, 0.0); side,size,action=fields(r)
    check("opposing +3/-1 net sends BUY 2", r.get("desired",{}).get("desired_net") == 2.0 and side == "BUY" and size == 2.0, repr(r))
    r = decide({wallets[0]: 2.0, wallets[1]: -2.0}, 0.0); side,size,action=fields(r)
    check("exact +2/-2 offset is NO-OP", r.get("desired",{}).get("desired_net") == 0.0 and action == "NONE" and not side and size == 0.0, repr(r))
    r = decide({wallets[0]: 1.0, wallets[1]: 1.0}, 0.0); side,size,action=fields(r)
    check("same-side +1/+1 sends BUY 2", r.get("desired",{}).get("desired_net") == 2.0 and side == "BUY" and size == 2.0, repr(r))
    r = decide({wallets[0]: 1.0, wallets[1]: 1.0}, 2.0); side,size,action=fields(r)
    check("already at desired net is NO-OP", r.get("desired",{}).get("desired_net") == 2.0 and action == "NONE" and not side and size == 0.0, repr(r))
    r = decide({wallets[0]: 3.0, wallets[1]: -1.0}, 0.0); sleeves=r.get("desired",{}).get("sleeves",{})
    check("netted sleeves retain both wallet attributions", sleeves.get(wallets[0]) == 3.0 and sleeves.get(wallets[1]) == -1.0, repr(sleeves))
    failed=[name for name,ok in checks if not ok]
    for i,(name,ok) in enumerate(checks,1): print(f"RESULT::ENG018_SEND_{i}_{'PASS' if ok else 'FAIL'}")
    print(f"TOTAL={len(checks)} FAILED={len(failed)}")
    if failed: print("FAILING_CHECKS=" + " | ".join(failed))
    return 1 if failed else 0
if __name__ == "__main__": sys.exit(main())
