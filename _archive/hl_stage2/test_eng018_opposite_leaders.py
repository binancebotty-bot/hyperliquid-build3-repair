#!/usr/bin/env python3
"""ENG-018 / OD-09: opposing leaders on one coin net a copy whose notional rounds BELOW the $10 exchange
minimum. That copy must never quietly become no copy at all: it is either SENT at the minimum notional, or
refused with a NAMED reason (distinguishable from every other hold) plus a counter.

Offline only: no exchange client, no network, no order. Drives the service's real planner entry point
(DryRunLiveCopyService.convergence_order_for_coin -> convergence_shadow.compute_convergence_order).
Run: python test_eng018_opposite_leaders.py
"""
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
    tmp = Path(tempfile.mkdtemp(prefix="eng018_od09_"))
    os.environ.update(HL_LIVE_AUDIT_DIR=str(tmp), HL_LIVE_AUTO_SEND_ENABLED="0", HL_LIVE_POLL_ENABLED="0")
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {}}), encoding="utf-8")
    import HL_Live_Copy_Service as svcmod
    import convergence_shadow as shadow
    svcmod.TEST_INJECTION_ENABLED = True
    wallets = ("0xw1", "0xw2")
    configs = {w: svcmod.LiveWalletConfig(wallet=w, mode="LIVE", copy_mode="proportional",
                                          norm_base=1000.0, leader_equity_base=1000.0, enabled=True)
               for w in wallets}
    svc = svcmod.DryRunLiveCopyService()

    def decide(sleeves, actual, price):
        svc.state["leader_event_positions"] = {svc.position_key(w, "BTC"): v for w, v in sleeves.items()}
        f = svcmod.LeaderFill("od09", wallets[0], "BTC", "BUY", price, 1.0, 1.0, 1,
                              "2026-01-01T00:00:00Z", "test", "test", {})
        return svc.convergence_order_for_coin(configs[wallets[0]], f, configs, actual)

    def counts():
        ev = getattr(shadow, "MIN_NOTIONAL_EVENTS", None) or {}
        return int(ev.get("uplifted", 0) or 0), int(ev.get("refused", 0) or 0)

    # The two leaders oppose each other: +3 and -1 net to a +2 copy (same fixture as the ENG-018 send pins).
    # At $4/unit that copy is $8: a real leader trade whose copy rounds below the $10 exchange minimum.
    up0, ref0 = counts()
    r = decide({wallets[0]: 3.0, wallets[1]: -1.0}, 0.0, 4.0)
    o = r.get("order")
    check("OD09_OPPOSING_LEADERS_SUBMIN_COPY_IS_SENT_AT_MIN_NOTIONAL",
          getattr(o, "action", None) in ("OPEN", "ADD")
          and getattr(o, "side", "") == "BUY"
          and abs(getattr(o, "size", 0.0) - 2.5) < 1e-9            # 10.0 / 4.0 -> exactly the minimum
          and abs(getattr(o, "size", 0.0) * 4.0 - 10.0) < 1e-9
          and abs(r.get("desired", {}).get("desired_net", 0.0) - 2.0) < 1e-9,
          f"{r.get('desired', {}).get('desired_net')} net -> {getattr(o, 'short', lambda: o)()}")

    up1, _ = counts()
    check("OD09_SUBMIN_COPY_ROUND_UP_IS_COUNTED", up1 - up0 == 1, f"uplifted {up0} -> {up1}")

    # A copy so small that rounding it up to $10 is not a rounding any more (a 5x chase) is refused BY NAME.
    up2, ref1 = counts()
    r2 = decide({wallets[0]: 3.0, wallets[1]: -1.0}, 0.0, 1.0)  # 2.0 units * $1 = a $2 copy
    o2 = r2.get("order")
    check("OD09_UNROUNDABLE_SUBMIN_COPY_IS_REFUSED_BY_NAME",
          getattr(o2, "action", None) == "NONE"
          and getattr(o2, "reason", "") == "BELOW_MIN_NOTIONAL_REFUSED"
          and getattr(o2, "reason", "") not in ("BELOW_MIN_NOTIONAL_HOLD", "IN_FLIGHT_HOLD",
                                               "LEADER_UNKNOWN_HOLD", "CONVERGED", "BELOW_DUST_HOLD"),
          getattr(o2, "short", lambda: o2)())
    up3, ref2 = counts()
    check("OD09_NAMED_REFUSAL_IS_COUNTED", ref2 - ref1 == 1 and up3 == up2, f"refused {ref1} -> {ref2}")

    # The $10 threshold itself is untouched: a copy that already clears it is sent as-is, not uplifted.
    r3 = decide({wallets[0]: 3.0, wallets[1]: -1.0}, 0.0, 5.0)  # 2.0 units * $5 = exactly $10
    o3 = r3.get("order")
    check("OD09_EXACT_MIN_NOTIONAL_COPY_SENT_UNCHANGED",
          getattr(o3, "action", None) == "OPEN" and getattr(o3, "side", "") == "BUY"
          and abs(getattr(o3, "size", 0.0) - 2.0) < 1e-9,
          getattr(o3, "short", lambda: o3)())

    # Shedding exposure below the minimum stays allowed: the minimum gates OPENS, never a flatten.
    r4 = decide({wallets[0]: 0.25, wallets[1]: 0.0}, 2.0, 4.0)
    o4 = r4.get("order")
    check("OD09_SUBMIN_REDUCE_STILL_ALLOWED", getattr(o4, "action", None) in ("REDUCE", "FLATTEN")
          and getattr(o4, "reduce_only", False) is True,
          getattr(o4, "short", lambda: o4)())

    failed = [name for name, ok in checks if not ok]
    for i, (name, ok) in enumerate(checks, 1):
        print(f"RESULT::ENG018_OD09_{i}_{'PASS' if ok else 'FAIL'}")
    print(f"TOTAL={len(checks)} FAILED={len(failed)}")
    if failed:
        print("FAILING_CHECKS=" + " | ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
