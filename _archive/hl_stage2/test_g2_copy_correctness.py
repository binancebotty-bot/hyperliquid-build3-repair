#!/usr/bin/env python3
"""G2 focused executable tests -- corrected per Architect ruling B3-A2C-G2-AUTHORITY-RULING-1.

Authority: desired exposure comes ONLY from the genuine post-baseline leader EVENT lineage; the
order size is the convergence DELTA toward the aggregated ACCOUNT-NET desired target; direction is
the PLANNER side (never the leader event side); account-net truth is REQUIRED (fail closed if
unavailable); un-settled sends suppress overlapping authorisation; the lineage is a checkpoint
coupled to the processed-event ledger; fixed mode is HELD fail-closed.

Run:  python test_g2_copy_correctness.py     # prints PASS/FAIL + RESULT:: markers, exit 0/1
Pure/offline: no network, no exchange, no orders (dry-run service).
"""
from __future__ import annotations

import json
import os
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
    tmp = Path(tempfile.mkdtemp(prefix="g2_corr_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)
    os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
    os.environ["HL_LIVE_POLL_ENABLED"] = "0"

    (tmp / "live_config.json").write_text(json.dumps({
        "wallets": {
            "0xw1": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                     "norm_base": 100.0, "leader_equity_base": 1000.0},
            "0xw2": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                     "norm_base": 100.0, "leader_equity_base": 1000.0},
            "0xfixed": {"mode": "LIVE", "enabled": True, "copy_mode": "fixed",
                        "norm_base": 100.0, "leader_equity_base": 1000.0, "fixed_notional": 10.0},
        }
    }), encoding="utf-8")

    import HL_Live_Copy_Service as svcmod
    svcmod.TEST_INJECTION_ENABLED = True  # test-only seam: injected providers/durability bypass

    def fill(fid, wallet, coin, side, price, size, ts, delta=None, source="test"):
        d = delta if delta is not None else (size if side.upper() == "BUY" else -size)
        return svcmod.LeaderFill(
            fill_id=fid, wallet=wallet.lower(), coin=coin.upper(), side=side.upper(),
            price=price, size=abs(size), signed_size_delta=d, timestamp_ms=ts,
            timestamp_iso="2026-01-01T00:00:00Z", source=source, recording_method="test", raw={},
        )

    configs = {
        "0xw1": svcmod.LiveWalletConfig(wallet="0xw1", mode="LIVE", copy_mode="proportional",
                                        norm_base=100.0, leader_equity_base=1000.0, enabled=True),
        "0xw2": svcmod.LiveWalletConfig(wallet="0xw2", mode="LIVE", copy_mode="proportional",
                                        norm_base=100.0, leader_equity_base=1000.0, enabled=True),
    }

    def wire_account_net(svc, wallets):
        """Test double for AUTHORITATIVE account-net truth (aggregated account exposure).

        In G2 production there is no live account-net plumbing, so the service holds (see t10);
        here we inject the authoritative source the G3 plumbing will provide.
        """
        def provider(coin):
            total = 0.0
            for w in wallets:
                total += float(svc.get_position(w, coin).get("signed_size") or 0.0)
            return {"ok": True, "net": total, "source": "TEST_AUTHORITATIVE_ACCOUNT_NET"}
        return provider

    def fresh(wallets=("0xw1",), provider=None):
        svc = svcmod.DryRunLiveCopyService()
        svc.state["leader_event_positions"] = {}
        svc.processed_ids = set()
        svc.account_net_provider = provider if provider is not None else wire_account_net(svc, list(wallets))
        return svc

    print("=== t1) repeated genuine ADDs -> event-authorised desired, delta-sized ===")
    svc = fresh()
    for i, ts in enumerate((1000, 2000, 3000), start=1):
        svc.process_fill(fill(f"f{i}", "0xw1", "BTC", "BUY", 100.0, 10.0, ts), configs["0xw1"])
    pos = svc.get_position("0xw1", "BTC")
    check("three ADDs converge follower to desired 3.0 (delta, not fixed per-fill)",
          abs(float(pos["signed_size"]) - 3.0) < 1e-9, f"signed_size={pos['signed_size']}")
    before_ct = dict(svc.state["counters"])
    svc.process_fill(fill("f3", "0xw1", "BTC", "BUY", 100.0, 10.0, 3000), configs["0xw1"])
    check("duplicate genuine event -> zero new orders",
          int(svc.state["counters"].get("dry_run_fills_processed", 0)) == int(before_ct.get("dry_run_fills_processed", 0)),
          f"counters={svc.state['counters'].get('dry_run_fills_processed')}")

    print("\n=== t2) reductions and closes move toward desired without sign error ===")
    svc.process_fill(fill("f4", "0xw1", "ETH", "BUY", 2000.0, 5.0, 4000), configs["0xw1"])
    eth_before = float(svc.get_position("0xw1", "ETH")["signed_size"])
    svc.process_fill(fill("f5", "0xw1", "BTC", "SELL", 100.0, 10.0, 5000), configs["0xw1"])
    check("reduction moves follower 3.0 -> 2.0 without flipping",
          abs(float(svc.get_position("0xw1", "BTC")["signed_size"]) - 2.0) < 1e-9)
    check("unrelated coin inventory untouched",
          abs(float(svc.get_position("0xw1", "ETH")["signed_size"]) - eth_before) < 1e-12)
    svc.process_fill(fill("f6", "0xw1", "BTC", "SELL", 100.0, 20.0, 6000), configs["0xw1"])
    check("leader full close flattens follower to 0 (no flip)",
          abs(float(svc.get_position("0xw1", "BTC")["signed_size"])) < 1e-9)

    print("\n=== t3) proportional sizing unit semantics ===")
    scale = svcmod.proportional_sleeve_scale(configs["0xw1"])
    check("scale == norm_base/leader_equity_base", abs(scale - 0.1) < 1e-12, f"scale={scale}")
    check("sleeve == leader_signed * scale (25*0.1==2.5)",
          abs(svcmod.sleeve_from_leader_event_position(configs["0xw1"], 25.0) - 2.5) < 1e-12)
    agg = svcmod.event_authorised_desired_net("BTC", {"0xw1": 30.0}, configs)
    check("single-wallet desired_net == 3.0", agg["ok"] and abs(agg["desired_net"] - 3.0) < 1e-12, str(agg))

    print("\n=== t4) fixed mode -> FIXED_MODE_AUTHORITY_HOLD, ZERO order ===")
    fixed_cfg = svcmod.LiveWalletConfig(wallet="0xfixed", mode="LIVE", copy_mode="fixed",
                                        norm_base=100.0, leader_equity_base=1000.0,
                                        fixed_notional=10.0, enabled=True)
    res = svcmod.event_authorised_desired_net("BTC", {"0xfixed": 5.0}, {"0xfixed": fixed_cfg})
    check("fixed mode returns FIXED_MODE_AUTHORITY_HOLD",
          res.get("status") == "FIXED_MODE_AUTHORITY_HOLD", str(res))
    svcF = fresh()
    svcF.account_net_provider = wire_account_net(svcF, ["0xfixed"])
    # SUPERSEDED-LOCKED-CHECK (G4-B): Project Architect ruling B3-A2C-G4-8014-SLICE-SEMANTICS-RULING-1
    # (b35be5e9) deliberately replaces the pre-ruling "fixed mode always holds / zero orders"
    # invariant with the 8014 event-sliced attributed-sleeve model. The fail-closed hold is retained
    # ONLY for a wallet with NO attributed sleeve ledger (asserted directly above, and re-asserted in
    # test_g4_fixed_slices.py::NEG_NO_LEDGER_KEEPS_FIXED_MODE_HOLD). A wallet WITH a genuine ledger
    # must now size from its attributed sleeve, so this check asserts that ruled behaviour instead.
    before = int(svcF.state["counters"].get("dry_run_fills_processed", 0))
    svcF.process_fill(fill("g1", "0xfixed", "BTC", "BUY", 100.0, 10.0, 7000), fixed_cfg)
    check("fixed-mode auto path trades on its attributed sleeve once a ledger exists",
          svcF.fixed_sleeve_units("0xfixed", "BTC") > 0
          and int(svcF.state["counters"].get("fills_blocked_fixed_mode_authority_hold", 0)) == 0,
          f"counters={ {k: v for k, v in svcF.state['counters'].items() if 'fill' in k} } "
          f"sleeve={svcF.fixed_sleeve_units('0xfixed', 'BTC')}")

    print("\n=== t5) restart does not seed authority from a snapshot ===")
    svc.persist()
    svc_restart = svcmod.DryRunLiveCopyService()
    check("restart lineage == persisted lineage (not a snapshot/current position)",
          svc_restart.state.get("leader_event_positions", {}) == svc.state.get("leader_event_positions", {}),
          f"store={svc_restart.state.get('leader_event_positions')}")
    probe = fill("probe", "0xw1", "BTC", "BUY", 100.0, 10.0, 9000)
    desired = svcmod.event_authorised_desired_net("BTC", svc_restart.leader_signed_by_wallet("BTC", configs), configs)
    sizing = svc_restart.convergence_order_for_coin(configs["0xw1"], probe, configs, float(desired["desired_net"]))
    check("actual == desired -> NONE (no order minted)",
          sizing.get("ok") and sizing["order"].action == "NONE", str(sizing.get("order")))

    print("\n=== t6) exactly one physical .order() call site ===")
    src = (HERE / "HL_Live_Copy_Service.py").read_text(encoding="utf-8", errors="replace")
    check("exactly one '.order(' call site", src.count(".order(") == 1, f"count={src.count('.order(')}")
    check("that call site is exchange.order(...)", src.count("exchange.order(") == 1)

    print("\n=== t7) sign flip: planner side preserved, first leg only flattens ===")
    svc7 = fresh()
    for i, ts in enumerate((1000, 2000, 3000), start=1):
        svc7.process_fill(fill(f"c{i}", "0xw1", "BTC", "BUY", 100.0, 10.0, ts), configs["0xw1"])
    flat_before = float(svc7.get_position("0xw1", "BTC")["signed_size"])
    svc7.process_fill(fill("c4", "0xw1", "BTC", "SELL", 100.0, 60.0, 4000), configs["0xw1"])  # -30 leader -> -3.0 desired
    # planner boundary: desired -3.0 vs ACTUAL +3.0 -> the FIRST leg must only flatten
    o7 = svcmod.compute_convergence_order("BTC", -3.0, flat_before, mark_px=100.0, min_notional=10.0)
    check("sign flip -> FLATTEN_THEN_OPEN, SELL, reduce_only, size == |actual|",
          o7.action == "FLATTEN_THEN_OPEN" and o7.side == "SELL" and o7.reduce_only
          and abs(o7.size - flat_before) < 1e-9, o7.short())
    check("first leg only flattens; follower never crosses zero",
          abs(float(svc7.get_position("0xw1", "BTC")["signed_size"])) < 1e-9,
          f"signed={svc7.get_position('0xw1','BTC')['signed_size']}")

    print("\n=== t8) short OPEN from flat sends SELL, not positive BUY state ===")
    svc8 = fresh()
    svc8.process_fill(fill("s1", "0xw1", "BTC", "SELL", 100.0, 30.0, 1000), configs["0xw1"])
    o8 = svc8.convergence_order_for_coin(configs["0xw1"], fill("s1b", "0xw1", "BTC", "SELL", 100.0, 30.0, 1001),
                                         configs, 0.0)["order"]
    check("short OPEN from flat -> OPEN SELL 3.0", o8.action == "OPEN" and o8.side == "SELL"
          and abs(o8.size - 3.0) < 1e-9, o8.short())
    check("follower position is short (-3.0), never positive",
          abs(float(svc8.get_position("0xw1", "BTC")["signed_size"]) + 3.0) < 1e-9,
          f"signed={svc8.get_position('0xw1','BTC')['signed_size']}")

    print("\n=== t9) same-coin multi-wallet sleeves aggregate to one account-net target ===")
    agg9 = svcmod.event_authorised_desired_net("BTC", {"0xw1": 10.0, "0xw2": 30.0}, configs)
    check("two wallets aggregate (1.0 + 3.0 == 4.0)", agg9["ok"] and abs(agg9["desired_net"] - 4.0) < 1e-12, str(agg9))

    print("\n=== t10) account-net truth UNAVAILABLE -> HOLD (never wallet-local fallback) ===")
    svc10 = svcmod.DryRunLiveCopyService()
    svc10.state["leader_event_positions"] = {}
    svc10.processed_ids = set()
    check("production default provider is None (no live account-net plumbing in G2)",
          svc10.account_net_provider is None)
    truth = svc10.account_net_actual("BTC")
    check("account_net_actual -> ACCOUNT_NET_TRUTH_UNAVAILABLE", truth.get("status") == "ACCOUNT_NET_TRUTH_UNAVAILABLE", str(truth))
    before10 = int(svc10.state["counters"].get("dry_run_fills_processed", 0))
    svc10.process_fill(fill("h1", "0xw1", "BTC", "BUY", 100.0, 10.0, 1000), configs["0xw1"])
    check("unavailable account-net -> ZERO order authority",
          int(svc10.state["counters"].get("dry_run_fills_processed", 0)) == before10
          and abs(float(svc10.get_position("0xw1", "BTC")["signed_size"])) < 1e-12,
          f"counters={svc10.state['counters'].get('dry_run_fills_processed')}")

    print("\n=== t11) in-flight suppression blocks overlapping authorisation ===")
    svc11 = fresh()
    svc11.mark_in_flight("BTC", {"intent_id": "unsettled", "side": "BUY", "size": 1.0})
    o11 = svc11.convergence_order_for_coin(configs["0xw1"], fill("i1", "0xw1", "BTC", "BUY", 100.0, 10.0, 1000),
                                           configs, 0.0)["order"]
    check("existing in-flight exposure -> planner returns NONE", o11.action == "NONE", o11.short())
    before11 = int(svc11.state["counters"].get("dry_run_fills_processed", 0))
    svc11.process_fill(fill("i2", "0xw1", "BTC", "BUY", 100.0, 10.0, 1001), configs["0xw1"])
    check("overlapping send not authorised (zero new orders, position unchanged)",
          int(svc11.state["counters"].get("dry_run_fills_processed", 0)) == before11
          and abs(float(svc11.get_position("0xw1", "BTC")["signed_size"])) < 1e-12)

    print("\n=== t12) lineage checkpoint: valid reload / corrupt + missing fail closed ===")
    svc12 = fresh()
    svc12.process_fill(fill("k1", "0xw1", "BTC", "BUY", 100.0, 10.0, 1000), configs["0xw1"])
    svc12.persist()
    reload_valid = svcmod.DryRunLiveCopyService()
    check("restart reloads a valid event-coupled checkpoint", reload_valid.lineage_valid is True,
          f"ck={reload_valid.state.get('leader_event_checkpoint')}")
    # corrupt: checkpoint points at an event NOT in the processed ledger
    svc12.state["leader_event_checkpoint"] = {"seq": 99, "last_fill_id": "NOT-A-PROCESSED-EVENT"}
    svc12.persist()
    reload_corrupt = svcmod.DryRunLiveCopyService()
    check("corrupt/inconsistent checkpoint fails closed", reload_corrupt.lineage_valid is False)
    check("failed checkpoint -> account-net authority held",
          reload_corrupt.account_net_actual("BTC").get("status") == "LINEAGE_CHECKPOINT_INVALID")
    # missing: positions present, no checkpoint
    svc12.state["leader_event_checkpoint"] = {}
    svc12.persist()
    reload_missing = svcmod.DryRunLiveCopyService()
    check("missing checkpoint (with lineage present) fails closed", reload_missing.lineage_valid is False)
    # snapshot with NO lineage -> no authority, but nothing to invalidate
    svc12.state["leader_event_positions"] = {}
    svc12.state["leader_event_checkpoint"] = {"seq": 0, "last_fill_id": ""}
    svc12.persist()
    reload_snap = svcmod.DryRunLiveCopyService()
    check("snapshot (no lineage) -> valid-but-empty, zero authority",
          reload_snap.lineage_valid is True and not reload_snap.state.get("leader_event_positions"))

    print("\n=== t13) LIVE-SEND SEAM: planner side/reduce_only + in-flight BEFORE the sender ===")
    # isolate the live-seam tests: their own audit dir, so no earlier test's persisted follower
    # position can make the planner see 'already converged'.
    _seam_dir = Path(tempfile.mkdtemp(prefix="g2_seam_"))
    (_seam_dir / "live_config.json").write_text(json.dumps({
        "wallets": {
            "0xw1": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional", "norm_base": 100.0, "leader_equity_base": 1000.0},
            "0xw2": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional", "norm_base": 100.0, "leader_equity_base": 1000.0},
            "0xfixed": {"mode": "LIVE", "enabled": True, "copy_mode": "fixed", "norm_base": 100.0, "leader_equity_base": 1000.0, "fixed_notional": 10.0},
        }
    }), encoding="utf-8")
    svcmod.configure_paths(_seam_dir, tmp / "raw_live_fills.csv")
    svcmod.LIVE_AUTO_SEND_ENABLED = True
    svcmod.LIVE_AUTO_SEND_WALLET = "0xw1"
    svcmod.LIVE_AUTO_SEND_MAX_PER_RUN = 5
    svcmod.LIVE_POLL_ENABLED = False
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    svcmod.HL_PERP_META_BY_COIN_CACHE = {"BTC": {"szDecimals": 5, "name": "BTC", "canonical_name": "BTC"}}
    seen = []

    def fake_sender(payload, marketable_bps=0.0, use_current_quote=False, max_notional=None):
        seen.append({"side": str(payload.get("side")), "reduce_only": bool(payload.get("reduce_only")),
                     "in_flight": dict(svc13.in_flight), "size": payload.get("copy_size")})
        return {"ok": True, "status": "ORDER_FILLED", "fill_avg_px": str(payload.get("limit_price")),
                "fill_size": str(payload.get("copy_size")), "oid": "t13", "coin": payload.get("coin"),
                "side": payload.get("side"), "size": payload.get("copy_size"),
                "limit_price": payload.get("limit_price"), "reduce_only": payload.get("reduce_only")}

    _real_sender = svcmod.send_hyperliquid_order
    svcmod.send_hyperliquid_order = fake_sender
    svc13 = fresh()
    _r0 = svc13.process_ws_fill(fill("w0", "0xw1", "BTC", "BUY", 100.0, 1.0, 500, source="live_ws"))    # baseline only
    _r1 = svc13.process_ws_fill(fill("w1", "0xw1", "BTC", "BUY", 100.0, 10.0, 1000, source="live_ws"))   # planner OPEN BUY 1.0
    check("planner side reaches the SENDER payload unchanged (OPEN BUY)",
          bool(seen) and seen[-1]["side"] == "BUY", str(seen[-1:]))
    check("in-flight reservation is PRESENT at the sender boundary",
          bool(seen) and bool(seen[-1]["in_flight"]), str(seen[-1:]))
    check("real send is NOT settled by the local dry-run mutation (reservation retained)",
          svc13.in_flight.get("BTC") is not None, str(svc13.in_flight))
    svc13.clear_in_flight("BTC")   # stands in for the G3 exchange ack arriving
    svc13.process_ws_fill(fill("w2", "0xw1", "BTC", "SELL", 100.0, 10.0, 2000, source="live_ws"))  # planner FLATTEN SELL 1.0
    check("planner reduce_only + side reach the SENDER payload (FLATTEN SELL)",
          seen[-1]["side"] == "SELL" and seen[-1]["reduce_only"] is True, str(seen[-1:]))
    svcmod.send_hyperliquid_order = _real_sender
    svcmod.LIVE_AUTO_SEND_ENABLED = False
    os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)

    print("\n=== t14) manual send cannot overwrite planner side (contradiction => FAIL CLOSED) ===")
    svcmod.save_manual_live_positions({"BTC": {"signed_size": 2.0, "last_updated_at": "t", "last_oid": "x", "last_intent_id": "x"}})
    _row14 = {"created_at": "t", "dry_run": True, "intent_id": "planner-conflict", "leader_wallet": "0xw1",
              "coin": "BTC", "side": "BUY", "copy_size": 1.0, "copy_notional": 100.0, "order_type": "IOC_LIMIT",
              "limit_price": 100.0, "reduce_only": True, "execution_decision": "WOULD_REDUCE_OR_EXIT",
              "decision_reason": "RISK_REDUCING_EXIT", "manual_reconcile_required": False, "status": "WOULD_SEND_DRY_RUN"}
    svcmod.append_csv(svcmod.WOULD_SEND_ORDERS_CSV, svcmod.WOULD_SEND_ORDER_FIELDS, _row14)
    conflict = svcmod.manual_send_one_intent("planner-conflict", False, close_position=True, planner_side="BUY")
    check("planner side vs local position contradiction FAILS CLOSED (never rewritten)",
          conflict.get("status") == "PLANNER_LOCAL_DIRECTION_CONFLICT", str(conflict))
    svcmod.save_manual_live_positions({"BTC": {"signed_size": 2.0, "last_updated_at": "t", "last_oid": "x", "last_intent_id": "x"}})
    _row14b = dict(_row14); _row14b.update({"intent_id": "planner-ok", "side": "SELL", "copy_size": 5.0, "copy_notional": 500.0})
    svcmod.append_csv(svcmod.WOULD_SEND_ORDERS_CSV, svcmod.WOULD_SEND_ORDER_FIELDS, _row14b)
    ok14 = svcmod.manual_send_one_intent("planner-ok", False, close_position=True, planner_side="SELL")
    _p14 = ok14.get("payload", {})
    check("planner side preserved and local position only CAPS size",
          _p14.get("side") == "SELL" and abs(float(_p14.get("copy_size")) - 2.0) < 1e-9, str(_p14))
    svcmod.save_manual_live_positions({})

    print("\n=== t15) manual (operator) close without planner side keeps local derivation ===")
    svcmod.save_manual_live_positions({"ETH": {"signed_size": -1.5, "last_updated_at": "t", "last_oid": "y", "last_intent_id": "y"}})
    _row15 = {"created_at": "t", "dry_run": True, "intent_id": "manual-close-eth", "leader_wallet": "0xw1",
              "coin": "ETH", "side": "SELL", "copy_size": 1.5, "copy_notional": 3000.0, "order_type": "IOC_LIMIT",
              "limit_price": 2000.0, "reduce_only": True, "execution_decision": "WOULD_REDUCE_OR_EXIT",
              "decision_reason": "RISK_REDUCING_EXIT", "manual_reconcile_required": False, "status": "WOULD_SEND_DRY_RUN"}
    svcmod.append_csv(svcmod.WOULD_SEND_ORDERS_CSV, svcmod.WOULD_SEND_ORDER_FIELDS, _row15)
    op15 = svcmod.manual_send_one_intent("manual-close-eth", False, close_position=True)
    check("operator close (no planner side) still derives side from local position",
          op15.get("payload", {}).get("side") == "BUY", str(op15.get("payload", {})))
    svcmod.save_manual_live_positions({})

    print("\n=== t16) CLO executes planner reductions only ===")
    _cfgpath = _seam_dir / "live_config.json"
    _orig_cfg = _cfgpath.read_text(encoding="utf-8")
    _clo_cfg = json.loads(_orig_cfg)
    _clo_cfg["wallets"]["0xw1"]["mode"] = "CLO"
    _cfgpath.write_text(json.dumps(_clo_cfg), encoding="utf-8")
    try:
        _clo_cfgobj = svcmod.LiveWalletConfig(wallet="0xw1", mode="CLO", copy_mode="proportional", norm_base=100.0, leader_equity_base=1000.0, enabled=True)
        clo_block = fresh(provider=lambda coin: {"ok": True, "net": 0.0, "source": "TEST_AUTHORITATIVE_ACCOUNT_NET"})
        clo_block.process_fill(fill("c1", "0xw1", "BTC", "BUY", 100.0, 10.0, 1000), _clo_cfgobj)
        check("CLO BLOCKS a planner OPEN (leader-side entry) with zero orders",
              int(clo_block.state["counters"].get("fills_skipped_clo_entry", 0)) >= 1
              and abs(float(clo_block.get_position("0xw1", "BTC")["signed_size"])) < 1e-12,
              f"counters={ {k: v for k, v in clo_block.state['counters'].items() if 'clo' in k} }")
        clo_allow = fresh(provider=lambda coin: {"ok": True, "net": 1.0, "source": "TEST_AUTHORITATIVE_ACCOUNT_NET"})
        # local dry-run state must agree with the authoritative account-net (long 1.0)
        clo_allow.apply_signed_delta_to_position(_clo_cfgobj, fill("seed", "0xw1", "BTC", "BUY", 100.0, 1.0, 900), 1.0)
        clo_allow.process_fill(fill("c2", "0xw1", "BTC", "BUY", 100.0, 10.0, 1000), _clo_cfgobj)
        clo_allow.process_fill(fill("c3", "0xw1", "BTC", "SELL", 100.0, 10.0, 2000), _clo_cfgobj)
        _clo_pos = float(clo_allow.get_position("0xw1", "BTC")["signed_size"])
        _clo_row = svcmod.last_csv_row(svcmod.ORDER_INTENTS_CSV)
        check("CLO ALLOWS a planner-authorised FLATTEN (reduce_only, SELL) and flattens to 0",
              abs(_clo_pos) < 1e-9 and str(_clo_row.get("side")) == "SELL", f"pos={_clo_pos} row={_clo_row}")
    finally:
        _cfgpath.write_text(_orig_cfg, encoding="utf-8")
        svcmod.configure_paths(tmp, tmp / "raw_live_fills.csv")

    print("\n=== t17) DURABLE AUDIT SURFACES retain planner reduce_only and planner follower side ===")
    import csv as _csv17

    def _durable_row(path, intent_id):
        with open(path, newline="", encoding="utf-8-sig") as _f:
            for _r in _csv17.DictReader(_f):
                if str(_r.get("intent_id", "")).strip() == str(intent_id).strip():
                    return _r
        return None

    svc17 = fresh()
    # over-sized follower: locally LONG 5.0 while the leader's BUY only implies +2.0 -> the planner
    # must REDUCE (SELL) even though the leader fill side is BUY (opposite-direction durable audit case)
    svc17.apply_signed_delta_to_position(configs["0xw1"], fill("seed17", "0xw1", "BTC", "BUY", 100.0, 5.0, 100), 5.0)
    svc17.process_fill(fill("o1", "0xw1", "BTC", "BUY", 100.0, 20.0, 1000), configs["0xw1"])
    _iid = str(svcmod.last_csv_row(svcmod.ORDER_INTENTS_CSV).get("intent_id") or "")
    _duro = _durable_row(svcmod.ORDER_INTENTS_CSV, _iid)
    _durf = _durable_row(svcmod.LIVE_FILLS_CSV, _iid)
    check("durable order_intents.csv retains planner reduce_only (read back from disk)",
          _duro is not None and svcmod.truthy_csv(_duro.get("reduce_only")), str(_duro))
    check("durable live_fills.csv records the PLANNER follower side, not the leader fill side",
          _durf is not None and str(_durf.get("side")).upper() == "SELL",
          f"leader_fill_side=BUY durable_live_fill_side={(_durf or {}).get('side')}")

    print("\n=== Result ===")
    print(f"  checks: {_passes} passed, {_fails} failed")
    if _fails == 0:
        for tag in (
            "G2_EVENT_AUTHORISED_DESIRED_PASS", "G2_DELTA_SIZED_NOT_FIXED_PER_FILL_PASS",
            "G2_REDUCE_NEVER_FLIPS_PASS", "G2_SIDE_PRESERVED_SIGN_FLIP_FIRST_LEG_FLATTENS_PASS",
            "G2_SHORT_OPEN_SELL_FROM_FLAT_PASS", "G2_MULTI_WALLET_ACCOUNT_NET_AGGREGATE_PASS",
            "G2_ACCOUNT_NET_REQUIRED_FAIL_CLOSED_PASS", "G2_IN_FLIGHT_SUPPRESSION_PASS",
            "G2_LINEAGE_CHECKPOINT_COUPLED_PASS", "G2_FIXED_MODE_AUTHORITY_HOLD_PASS",
            "G2_LIVE_SEND_SEAM_SIDE_REDUCE_ONLY_PASS", "G2_IN_FLIGHT_BEFORE_SENDER_PASS",
            "G2_MANUAL_SIDE_NOT_OVERWRITTEN_PASS", "G2_CLO_PLANNER_REDUCTION_ONLY_PASS",
            "G2_DURABLE_ORDER_INTENT_REDUCE_ONLY_PASS", "G2_DURABLE_LIVE_FILL_PLANNER_SIDE_PASS",
            "G2_SINGLE_ORDER_CALL_SITE_PASS",
        ):
            print(f"RESULT::{tag}")
    else:
        print("RESULT::G2_COPY_CORRECTNESS_TESTS_FAIL")
    sys.exit(1 if _fails else 0)


if __name__ == "__main__":
    main()
