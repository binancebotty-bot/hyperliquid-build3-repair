#!/usr/bin/env python3
"""G4 focused executable tests -- 8014 event-sliced attributed-sleeve FIXED mode.

Authority: Project Architect ruling B3-A2C-G4-8014-SLICE-SEMANTICS-RULING-1 (b35be5e9),
implemented per packet B3-C2H-G4-IMPLEMENT-8014-SLEEVES-ORIGINAL-UI-1.

Run:  python test_g4_fixed_slices.py     # prints RESULT:: markers, exit 0/1
Pure/offline: no network, no exchange, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="g4fx_"))
    os.environ["HL_AUDIT_DIR"] = str(tmp)
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)  # the variable the service reads: never the live state folder

    import HL_Live_Copy_Service as svcmod
    svcmod.TEST_INJECTION_ENABLED = True

    def fill(fid, wallet, coin, side, price, size, ts, delta=None):
        d = delta if delta is not None else (size if side.upper() == "BUY" else -size)
        return svcmod.LeaderFill(
            fill_id=fid, wallet=wallet.lower(), coin=coin.upper(), side=side.upper(),
            price=price, size=abs(size), signed_size_delta=d, timestamp_ms=ts,
            timestamp_iso="2026-01-01T00:00:00Z", source="test", recording_method="test", raw={},
        )

    COIN = "BTC"
    PX = 100.0
    FN = 12.0
    SLICE = FN / PX          # 0.12 units per slice
    eps = 1e-9

    def svc_fixed():
        s = svcmod.DryRunLiveCopyService()
        s.state["leader_event_positions"] = {}
        s.state["fixed_sleeves"] = {}
        return s

    cfg = svcmod.LiveWalletConfig(wallet="0xfixed", mode="LIVE", copy_mode="fixed",
                                  fixed_notional=FN, norm_base=100.0,
                                  leader_equity_base=1000.0, enabled=True)
    cfg_prop = svcmod.LiveWalletConfig(wallet="0xfixed", mode="LIVE", copy_mode="proportional",
                                       norm_base=100.0, leader_equity_base=1000.0, enabled=True)
    cfg_w2 = svcmod.LiveWalletConfig(wallet="0xw2", mode="LIVE", copy_mode="fixed",
                                     fixed_notional=FN, norm_base=100.0,
                                     leader_equity_base=1000.0, enabled=True)
    configs = {"0xfixed": cfg, "0xw2": cfg_w2}

    # ---------------- F1: first OPEN -> exactly one slice ----------------
    s = svc_fixed()
    s.apply_leader_event(cfg, fill("f1", "0xfixed", COIN, "BUY", PX, 1.0, 1))
    u = s.fixed_sleeve_units("0xfixed", COIN)
    n = len(s.state["fixed_sleeves"]["0xfixed"][COIN]["slices"])
    check("F1_FIRST_OPEN_ONE_SLICE", abs(u - SLICE) < 1e-9 and n == 1, f"units={u} n={n}")

    # ---------------- F2 + F9: distinct INCREASE -> one more slice, magnitude-agnostic ----------------
    before_u = u
    s.apply_leader_event(cfg, fill("f2", "0xfixed", COIN, "BUY", PX, 7.0, 2))   # materially larger event
    u2 = s.fixed_sleeve_units("0xfixed", COIN)
    n2 = len(s.state["fixed_sleeves"]["0xfixed"][COIN]["slices"])
    check("F2_DISTINCT_INCREASE_ONE_MORE_SLICE", abs(u2 - 2 * SLICE) < 1e-9 and n2 == 2, f"units={u2} n={n2}")
    check("F9_EVENT_MAGNITUDE_DOES_NOT_SCALE_SLICE", abs((u2 - before_u) - SLICE) < 1e-9,
          f"added={u2 - before_u} expected={SLICE}")

    # ---------------- F3: sleeve == sum of attributable slices ----------------
    check("F3_SLEEVE_EQ_SUM_OF_SLICES", abs(u2 - n2 * SLICE) < 1e-9, f"units={u2} n={n2}")

    # ---------------- F4: 25% leader REDUCE -> 25% of CURRENT sleeve ----------------
    s.apply_leader_event(cfg, fill("f3", "0xfixed", COIN, "SELL", PX, 2.0, 3, delta=-2.0))  # 8 -> 6 = 25%
    u3 = s.fixed_sleeve_units("0xfixed", COIN)
    check("F4_REDUCE_25PCT_OF_CURRENT_SLEEVE", abs(u3 - (2 * SLICE) * 0.75) < 1e-9, f"units={u3}")

    # ---------------- F5: later 40% REDUCE -> 40% of THEN-CURRENT sleeve ----------------
    s.apply_leader_event(cfg, fill("f4", "0xfixed", COIN, "SELL", PX, 2.4, 4, delta=-2.4))  # 6 -> 3.6 = 40%
    u4 = s.fixed_sleeve_units("0xfixed", COIN)
    check("F5_REDUCE_40PCT_THEN_CURRENT_SLEEVE", abs(u4 - ((2 * SLICE) * 0.75) * 0.60) < 1e-9, f"units={u4}")

    # ---------------- F6: CLOSE -> attributed sleeve zero ----------------
    s.apply_leader_event(cfg, fill("f5", "0xfixed", COIN, "SELL", PX, 3.6, 5, delta=-3.6))
    u5 = s.fixed_sleeve_units("0xfixed", COIN)
    check("F6_CLOSE_SLEEVE_ZERO", abs(u5) < 1e-12 and s.state["fixed_sleeves"]["0xfixed"][COIN]["slices"] == [],
          f"units={u5}")

    # ---------------- F7: FLIP -> old sleeve zero + exactly one new opposite slice ----------------
    s.apply_leader_event(cfg, fill("f6", "0xfixed", COIN, "BUY", PX, 1.0, 6))
    s.apply_leader_event(cfg, fill("f7", "0xfixed", COIN, "SELL", PX, 3.0, 7, delta=-3.0))  # +1 -> -2 = FLIP
    sl7 = s.state["fixed_sleeves"]["0xfixed"][COIN]
    check("F7_FLIP_ZERO_THEN_ONE_OPPOSITE_SLICE",
          sl7["side"] == -1 and len(sl7["slices"]) == 1 and abs(sl7["slices"][0] - SLICE) < 1e-9,
          f"side={sl7['side']} slices={sl7['slices']}")

    # ---------------- F8: other leader sleeves / unrelated inventory untouched ----------------
    s2 = svc_fixed()
    s2.apply_leader_event(cfg, fill("g1", "0xfixed", COIN, "BUY", PX, 1.0, 1))
    w1_before = s2.fixed_sleeve_units("0xfixed", COIN)
    s2.apply_leader_event(cfg_w2, fill("g2", "0xw2", COIN, "BUY", PX, 5.0, 2))
    w2_units = s2.fixed_sleeve_units("0xw2", COIN)
    w1_after = s2.fixed_sleeve_units("0xfixed", COIN)
    check("F8_OTHER_SLEEVE_UNTOUCHED",
          abs(w1_after - w1_before) < 1e-12 and abs(w2_units - SLICE) < 1e-9,
          f"w1 {w1_before}->{w1_after} w2={w2_units}")

    # ---------------- F10: proportional unchanged; norm_base never sizes fixed ----------------
    prop = svcmod.sleeve_from_leader_event_position(cfg_prop, 5.0)
    fixed_ignores_norm = svcmod.sleeve_from_leader_event_position(cfg, 5.0, 0.24)
    check("F10_PROPORTIONAL_UNCHANGED_AND_NORM_BASE_INERT",
          abs(prop - 0.5) < 1e-9 and abs(fixed_ignores_norm - 0.24) < 1e-9,
          f"prop={prop} fixed={fixed_ignores_norm}")

    # ---------------- desired net uses the attributed sleeve, sign from leader side ----------------
    dn = svcmod.event_authorised_desired_net(COIN, {"0xfixed": 3.0}, configs, {"0xfixed": 0.24, "0xw2": 0.0})
    dn_flat = svcmod.event_authorised_desired_net(COIN, {"0xfixed": 0.0}, configs, {"0xfixed": 0.24, "0xw2": 0.0})
    check("DESIRED_NET_FROM_ATTRIBUTED_SLEEVE_AND_FLAT_IS_ZERO",
          dn.get("ok") and abs(dn["desired_net"] - 0.24) < 1e-9 and abs(dn_flat["desired_net"]) < 1e-9,
          f"dn={dn} flat={dn_flat}")

    # ---------------- NEGATIVE AUTHORITY ----------------
    sN = svc_fixed()
    sN.apply_leader_event(cfg, fill("n0", "0xfixed", COIN, "BUY", PX, 1.0, 1))
    base_u = sN.fixed_sleeve_units("0xfixed", COIN)
    sN.apply_leader_event(cfg, fill("n1", "0xfixed", COIN, "BUY", 0.0, 5.0, 2))        # missing/stale mark
    check("NEG_MISSING_MARK_MINTS_ZERO", abs(sN.fixed_sleeve_units("0xfixed", COIN) - base_u) < 1e-12)
    sN.apply_leader_event(cfg_prop, fill("n2", "0xfixed", COIN, "BUY", PX, 5.0, 3))     # proportional cfg
    check("NEG_PROPORTIONAL_CFG_MINTS_ZERO", abs(sN.fixed_sleeve_units("0xfixed", COIN) - base_u) < 1e-12)
    sN.apply_leader_event(cfg, fill("n3", "0xfixed", "ETH", "BUY", PX, 0.0, 4, delta=0.0))  # zero-delta
    check("NEG_ZERO_DELTA_MINTS_ZERO", abs(sN.fixed_sleeve_units("0xfixed", "ETH")) < 1e-12)

    # structural: apply_leader_event is the ONLY writer of slice authority
    src = Path(svcmod.__file__).read_text(encoding="utf-8", errors="replace")
    writers = [ln for ln in src.splitlines()
               if 'state["fixed_sleeves"]' in ln and "=" in ln and "==" not in ln and "get(" not in ln]
    check("NEG_SINGLE_SLICE_MINT_SITE", len(writers) <= 2, f"writers={writers}")

    # ---------------- no attributed ledger -> fixed mode STILL holds fail-closed ----------------
    sH = svc_fixed()
    hold = svcmod.event_authorised_desired_net(
        COIN, {"0xfixed": 3.0}, configs, sH.fixed_sleeve_units_by_wallet(COIN, configs)
    )
    check("NEG_NO_LEDGER_KEEPS_FIXED_MODE_HOLD",
          (not hold.get("ok")) and hold.get("status") == "FIXED_MODE_AUTHORITY_HOLD", f"hold={hold}")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
