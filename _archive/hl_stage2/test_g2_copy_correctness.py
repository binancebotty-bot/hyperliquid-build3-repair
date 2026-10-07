#!/usr/bin/env python3
"""G2 focused executable tests — core Build3 copy correctness (Gate 2).

Authority: Architect ruling B3-A2C-G1-PASS-G2-1. Proves the blind fixed-notional-per-fill
authority is gone: desired exposure comes ONLY from the genuine post-baseline leader EVENT
lineage, and the order size is the convergence DELTA toward it.

Run:  python test_g2_copy_correctness.py     # prints PASS/FAIL + RESULT:: markers, exit 0/1
Pure/offline: no network, no exchange, no orders (dry-run service).
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_fails = 0
_passes = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global _fails, _passes
    if cond:
        _passes += 1
    else:
        _fails += 1
    print(f"  {'PASS' if cond else 'FAIL'}: {name}" + (f"  ::  {detail}" if detail else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="g2_audit_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)
    os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
    os.environ["HL_LIVE_POLL_ENABLED"] = "0"

    (tmp / "live_config.json").write_text(json.dumps({
        "wallets": {
            "0xw1": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                     "norm_base": 100.0, "leader_equity_base": 1000.0},
            "0xfixed": {"mode": "LIVE", "enabled": True, "copy_mode": "fixed",
                        "norm_base": 100.0, "leader_equity_base": 1000.0, "fixed_notional": 10.0},
        }
    }), encoding="utf-8")

    import HL_Live_Copy_Service as svcmod

    def fill(fid, wallet, coin, side, price, size, ts, delta=None):
        d = delta if delta is not None else (size if side.upper() == "BUY" else -size)
        return svcmod.LeaderFill(
            fill_id=fid, wallet=wallet.lower(), coin=coin.upper(), side=side.upper(),
            price=price, size=abs(size), signed_size_delta=d, timestamp_ms=ts,
            timestamp_iso="2026-01-01T00:00:00Z", source="test", recording_method="test", raw={},
        )

    configs = {"0xw1": svcmod.LiveWalletConfig(
        wallet="0xw1", mode="LIVE", copy_mode="proportional", norm_base=100.0, leader_equity_base=1000.0, enabled=True)}

    print("=== t1) repeated genuine ADDs -> event-authorised desired, delta-sized (no per-fill fixed notional) ===")
    svc = svcmod.DryRunLiveCopyService()
    svc.state["leader_event_positions"] = {}
    svc.processed_ids = set()
    # leader BUY 10 @100 three times -> leader_signed 10,20,30 -> desired 1.0,2.0,3.0 (scale 0.1)
    for i, ts in enumerate((1000, 2000, 3000), start=1):
        svc.process_fill(fill(f"f{i}", "0xw1", "BTC", "BUY", 100.0, 10.0, ts), configs["0xw1"])
    pos = svc.get_position("0xw1", "BTC")
    check("three ADDs converge follower to desired 3.0", abs(float(pos["signed_size"]) - 3.0) < 1e-9,
          f"signed_size={pos['signed_size']}")
    check("order was DELTA-sized, not fixed-notional/price (would be 0.1)",
          abs(float(pos["signed_size"]) - 3.0) < 1e-9)
    # duplicate genuine event (same fill_id) must mint nothing
    before_ct = dict(svc.state["counters"])
    svc.process_fill(fill("f3", "0xw1", "BTC", "BUY", 100.0, 10.0, 3000), configs["0xw1"])
    check("duplicate leader event -> zero new orders",
          int(svc.state["counters"].get("dry_run_fills_processed", 0)) == int(before_ct.get("dry_run_fills_processed", 0)),
          f"counters={svc.state['counters'].get('dry_run_fills_processed')}")

    print("\\n=== t2) reduction/close does not flip or flatten unrelated inventory ===")
    svc.process_fill(fill("f4", "0xw1", "ETH", "BUY", 2000.0, 5.0, 4000), configs["0xw1"])   # unrelated coin
    eth_before = float(svc.get_position("0xw1", "ETH")["signed_size"])
    svc.process_fill(fill("f5", "0xw1", "BTC", "SELL", 100.0, 10.0, 5000), configs["0xw1"])  # leader reduces
    btc_after = float(svc.get_position("0xw1", "BTC")["signed_size"])
    eth_after = float(svc.get_position("0xw1", "ETH")["signed_size"])
    check("reduction moves follower 3.0 -> 2.0 without flipping", abs(btc_after - 2.0) < 1e-9, f"btc={btc_after}")
    check("unrelated coin inventory untouched", abs(eth_after - eth_before) < 1e-12, f"eth {eth_before}->{eth_after}")
    svc.process_fill(fill("f6", "0xw1", "BTC", "SELL", 100.0, 20.0, 6000), configs["0xw1"])  # leader closes
    check("leader full close flattens follower to 0 (no flip)",
          abs(float(svc.get_position("0xw1", "BTC")["signed_size"])) < 1e-9,
          f"btc={svc.get_position('0xw1','BTC')['signed_size']}")

    print("\\n=== t3) proportional sizing unit semantics ===")
    scale = svcmod.proportional_sleeve_scale(configs["0xw1"])
    check("scale == norm_base/leader_equity_base", abs(scale - 0.1) < 1e-12, f"scale={scale}")
    sleeve = svcmod.sleeve_from_leader_event_position(configs["0xw1"], 25.0)
    check("sleeve == leader_signed * scale (25*0.1==2.5)", abs(sleeve - 2.5) < 1e-12, f"sleeve={sleeve}")
    agg = svcmod.event_authorised_desired_net("BTC", {"0xw1": 30.0}, configs)
    check("single-wallet desired_net == 3.0", agg["ok"] and abs(agg["desired_net"] - 3.0) < 1e-12, str(agg))

    print("\\n=== t4) fixed mode -> AUTHORITY_CONFLICT (config defines no fixed TARGET exposure) ===")
    fixed_cfg = svcmod.LiveWalletConfig(wallet="0xfixed", mode="LIVE", copy_mode="fixed",
                                        norm_base=100.0, leader_equity_base=1000.0, fixed_notional=10.0, enabled=True)
    res = svcmod.event_authorised_desired_net("BTC", {"0xfixed": 5.0}, {"0xfixed": fixed_cfg})
    check("fixed mode returns AUTHORITY_CONFLICT", res.get("status") == "AUTHORITY_CONFLICT", str(res))
    svc2 = svcmod.DryRunLiveCopyService()
    svc2.state["leader_event_positions"] = {}
    svc2.processed_ids = set()
    before = int(svc2.state["counters"].get("dry_run_fills_processed", 0))
    svc2.process_fill(fill("g1", "0xfixed", "BTC", "BUY", 100.0, 10.0, 7000), fixed_cfg)
    check("fixed-mode auto path places ZERO orders",
          int(svc2.state["counters"].get("dry_run_fills_processed", 0)) == before
          and int(svc2.state["counters"].get("fills_blocked_authority_conflict", 0)) >= 1,
          f"counters={ {k: v for k, v in svc2.state['counters'].items() if 'fill' in k} }")

    print("\\n=== t5) snapshot/restart creates ZERO new trade authority ===")
    svc.persist()
    svc_restart = svcmod.DryRunLiveCopyService()  # fresh instance over the same audit dir
    check("restart does NOT seed lineage from a snapshot/current position",
          svc_restart.state.get("leader_event_positions", {}) == svc.state.get("leader_event_positions", {}),
          f"store={svc_restart.state.get('leader_event_positions')}")
    probe = fill("probe", "0xw1", "BTC", "BUY", 100.0, 10.0, 9000)
    desired = svcmod.event_authorised_desired_net("BTC", svc_restart.leader_signed_by_wallet("BTC", configs), configs)
    sizing = svc_restart.convergence_order_for_coin(configs["0xw1"], probe, configs, float(desired["desired_net"]))
    check("actual == desired (snapshot) -> NONE (no order minted)",
          sizing.get("ok") and sizing["order"].action == "NONE", str(sizing.get("order")))

    print("\\n=== t6) exactly one physical .order() call site remains ===")
    src = (HERE / "HL_Live_Copy_Service.py").read_text(encoding="utf-8", errors="replace")
    n_order = src.count(".order(")
    n_exch = src.count("exchange.order(")
    check("exactly one '.order(' call site in production source", n_order == 1, f"count={n_order}")
    check("that call site is exchange.order(...)", n_exch == 1, f"exchange.order count={n_exch}")

    print("\\n=== Result ===")
    print(f"  checks: {_passes} passed, {_fails} failed")
    if _fails == 0:
        print("RESULT::G2_EVENT_AUTHORISED_DESIRED_PASS")
        print("RESULT::G2_DELTA_SIZED_NOT_FIXED_PER_FILL_PASS")
        print("RESULT::G2_REDUCE_NEVER_FLIPS_OR_FLATTENS_UNRELATED_PASS")
        print("RESULT::G2_PROPORTIONAL_UNIT_SEMANTICS_PASS")
        print("RESULT::G2_FIXED_MODE_AUTHORITY_CONFLICT_PASS")
        print("RESULT::G2_SNAPSHOT_RESTART_ZERO_AUTHORITY_PASS")
        print("RESULT::G2_SINGLE_ORDER_CALL_SITE_PASS")
    else:
        print("RESULT::G2_COPY_CORRECTNESS_TESTS_FAIL")
    sys.exit(1 if _fails else 0)


if __name__ == "__main__":
    main()
