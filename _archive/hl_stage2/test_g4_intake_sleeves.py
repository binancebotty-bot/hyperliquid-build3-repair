#!/usr/bin/env python3
"""G4 intake-level + ledger-integrity suite for 8014 event-sliced attributed-sleeve FIXED mode.

Answers the adversarial review items:
  A. exercise the ACTUAL process_fill intake (duplicate WS fragments, replay/restart,
     rebaseline) -> zero new slices/orders; distinct second INCREASE -> exactly one slice;
     reductions/close/flip never touch another wallet's sleeve or inventory.
  D. fixed OPEN / REDUCE / CLOSE plan through the real desired-net -> planner path,
     with exactly one exchange order call site.
  Ledger integrity: empty-with-side, non-empty-with-side-0, NaN and negative slices must
     FAIL CLOSED (no authority), never silently release or reset.

Run: python test_g4_intake_sleeves.py      # RESULT:: markers, exit 0/1. No network, no LIVE.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="g4intake_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)
    os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
    os.environ["HL_LIVE_POLL_ENABLED"] = "0"
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {
        "0xfixed": {"mode": "LIVE", "enabled": True, "copy_mode": "fixed",
                    "norm_base": 100.0, "leader_equity_base": 1000.0, "fixed_notional": 10.0},
        "0xprop": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                   "norm_base": 100.0, "leader_equity_base": 1000.0},
    }}), encoding="utf-8")

    import HL_Live_Copy_Service as svcmod
    svcmod.TEST_INJECTION_ENABLED = True

    def fill(fid, wallet, coin, side, price, size, ts, delta=None):
        d = delta if delta is not None else (size if side.upper() == "BUY" else -size)
        return svcmod.LeaderFill(
            fill_id=fid, wallet=wallet.lower(), coin=coin.upper(), side=side.upper(),
            price=price, size=abs(size), signed_size_delta=d, timestamp_ms=ts,
            timestamp_iso="2026-01-01T00:00:00Z", source="test", recording_method="test", raw={},
        )

    FIX = svcmod.LiveWalletConfig(wallet="0xfixed", mode="LIVE", copy_mode="fixed",
                                  fixed_notional=10.0, norm_base=100.0,
                                  leader_equity_base=1000.0, enabled=True)
    # Larger sleeve so REDUCE/CLOSE stay above the exchange minimum notional and actually
    # exercise the planner (a 0.05-share reduce is correctly refused as sub-minimum).
    FIX_BIG = svcmod.LiveWalletConfig(wallet="0xfixed", mode="LIVE", copy_mode="fixed",
                                      fixed_notional=1000.0, norm_base=100.0,
                                      leader_equity_base=1000.0, enabled=True)
    PROP = svcmod.LiveWalletConfig(wallet="0xprop", mode="LIVE", copy_mode="proportional",
                                   norm_base=100.0, leader_equity_base=1000.0, enabled=True)
    PX = 100.0
    SLICE = 10.0 / PX   # 0.1

    def wire_account_net(svc, wallets):
        def provider(coin):
            total = 0.0
            for w in wallets:
                total += float(svc.get_position(w, coin).get("signed_size") or 0.0)
            return {"ok": True, "net": total, "source": "TEST_AUTHORITATIVE_ACCOUNT_NET"}
        return provider

    def fresh(wallets=("0xfixed",)):
        svc = svcmod.DryRunLiveCopyService()
        svc.state["leader_event_positions"] = {}
        svc.processed_ids = set()
        svc.account_net_provider = wire_account_net(svc, list(wallets))
        return svc

    COIN = "BTC"

    # ============ A1: duplicate WS fragment at the REAL intake mints exactly once ============
    svc = fresh()
    svc.process_fill(fill("d1", "0xfixed", COIN, "BUY", PX, 10.0, 1000), FIX)
    n1 = len(svc.state["fixed_sleeves"]["0xfixed"][COIN]["slices"])
    svc.process_fill(fill("d1", "0xfixed", COIN, "BUY", PX, 10.0, 1000), FIX)   # duplicate id
    n2 = len(svc.state["fixed_sleeves"]["0xfixed"][COIN]["slices"])
    check("A_DUPLICATE_INTAKE_MINTS_ONCE", n1 == 1 and n2 == 1, f"n1={n1} n2={n2}")

    # ============ A2: distinct INCREASE -> exactly one more slice ============
    svc.process_fill(fill("d2", "0xfixed", COIN, "BUY", PX, 30.0, 2000), FIX)   # delta +30
    n3 = len(svc.state["fixed_sleeves"]["0xfixed"][COIN]["slices"])
    check("A_DISTINCT_INCREASE_ADDS_ONE_SLICE", n3 == 2, f"n3={n3}")

    # ============ A3: restart/replay does not mint (ledger is loaded, not re-derived) ============
    svc.persist()
    svc_re = svcmod.DryRunLiveCopyService()
    svc_re.account_net_provider = wire_account_net(svc_re, ["0xfixed"])
    before = svc_re.fixed_sleeve_units("0xfixed", COIN)
    n_re = len(svc_re.state["fixed_sleeves"]["0xfixed"][COIN]["slices"])
    svc_re.process_fill(fill("d2", "0xfixed", COIN, "BUY", PX, 30.0, 2000), FIX)  # replay after restart
    after = svc_re.fixed_sleeve_units("0xfixed", COIN)
    check("A_RESTART_AND_REPLAY_MINT_NOTHING", n_re == 2 and abs(after - before) < 1e-12,
          f"n={n_re} before={before} after={after}")
    svc_re.persist()

    # ============ A4: fixed events never touch another wallet's sleeve or inventory ============
    svc2 = fresh(("0xfixed", "0xprop"))
    svc2.process_fill(fill("p1", "0xprop", COIN, "BUY", PX, 5.0, 100), PROP)     # prop follower holds 0.5
    prop_pos = float(svc2.get_position("0xprop", COIN).get("signed_size") or 0.0)
    svc2.process_fill(fill("k1", "0xfixed", COIN, "BUY", PX, 10.0, 200), FIX)
    svc2.process_fill(fill("k2", "0xfixed", COIN, "SELL", PX, 10.0, 300, delta=-10.0), FIX)  # close fixed
    prop_pos2 = float(svc2.get_position("0xprop", COIN).get("signed_size") or 0.0)
    check("A_FIXED_EVENTS_ISOLATED_FROM_OTHER_WALLET",
          prop_pos > 0 and abs(prop_pos2 - prop_pos) < 1e-9
          and "0xprop" not in (svc2.state.get("fixed_sleeves") or {}),
          f"prop {prop_pos}->{prop_pos2}")

    # ============ D: fixed OPEN / REDUCE / CLOSE through the real planner path ============
    SLICE_BIG = 1000.0 / PX   # 10.0 shares -- keeps REDUCE/CLOSE above the exchange minimum
    svcD = fresh()
    svcD.process_fill(fill("o1", "0xfixed", COIN, "BUY", PX, 10.0, 1000), FIX_BIG)
    open_pos = float(svcD.get_position("0xfixed", COIN).get("signed_size") or 0.0)
    check("D_FIXED_OPEN_PLANS_ATTRIBUTED_SLEEVE", abs(open_pos - SLICE_BIG) < 1e-9, f"open={open_pos}")
    svcD.process_fill(fill("o2", "0xfixed", COIN, "SELL", PX, 5.0, 2000, delta=-5.0), FIX_BIG)  # 50% reduce
    red_pos = float(svcD.get_position("0xfixed", COIN).get("signed_size") or 0.0)
    check("D_FIXED_REDUCE_FOLLOWS_SLEEVE_FRACTION", abs(red_pos - SLICE_BIG * 0.5) < 1e-9, f"reduce={red_pos}")
    svcD.process_fill(fill("o3", "0xfixed", COIN, "SELL", PX, 5.0, 3000, delta=-5.0), FIX_BIG)  # close
    close_pos = float(svcD.get_position("0xfixed", COIN).get("signed_size") or 0.0)
    check("D_FIXED_CLOSE_FLATTENS_TO_ZERO", abs(close_pos) < 1e-9, f"close={close_pos}")

    src = Path(svcmod.__file__).read_text(encoding="utf-8", errors="replace")
    order_sites = [ln for ln in src.splitlines() if ".order(" in ln and "exchange" in ln.lower()]
    check("D_SINGLE_EXCHANGE_ORDER_SITE", len(order_sites) == 1, f"sites={len(order_sites)}")

    # ============ LEDGER INTEGRITY: malformed entries must FAIL CLOSED ============
    def authority_for(entry):
        s = fresh()
        s.state["fixed_sleeves"] = {"0xfixed": {COIN: entry}}
        res = svcmod.event_authorised_desired_net(COIN, {"0xfixed": 1.0}, {"0xfixed": FIX},
                                                  s.fixed_sleeve_units_by_wallet(COIN, {"0xfixed": FIX}))
        return res

    bad = {
        "NEG_LEDGER_EMPTY_SLICES_NONZERO_SIDE_FAILS_CLOSED": {"side": 1, "slices": []},
        "NEG_LEDGER_NONEMPTY_SLICES_ZERO_SIDE_FAILS_CLOSED": {"side": 0, "slices": [SLICE]},
        "NEG_LEDGER_NEGATIVE_SLICE_FAILS_CLOSED": {"side": 1, "slices": [-SLICE]},
        "NEG_LEDGER_NAN_SLICE_FAILS_CLOSED": {"side": 1, "slices": [float("nan")]},
        "NEG_LEDGER_NONNUMERIC_SLICE_FAILS_CLOSED": {"side": 1, "slices": ["x"]},
    }
    for name, entry in bad.items():
        res = authority_for(entry)
        check(name, (not res.get("ok")) and res.get("status") == "FIXED_MODE_AUTHORITY_HOLD", f"res={res}")

    good = authority_for({"side": 0, "slices": []})   # legitimate close -> released at zero
    check("POS_LEDGER_LEGITIMATE_CLOSE_RELEASES_AT_ZERO",
          good.get("ok") and abs(good.get("desired_net", 1)) < 1e-12, f"res={good}")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
