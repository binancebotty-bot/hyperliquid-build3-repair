#!/usr/bin/env python3
"""ENG-018: opposing leader sleeves remain distinct while desired net aggregates.

Pure/offline: calls the same event-authorised aggregation used by the G2 suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import HL_Live_Copy_Service as svcmod

_passes = 0
_fails = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passes, _fails
    if condition:
        _passes += 1
    else:
        _fails += 1
    print(f"{'PASS' if condition else 'FAIL'}: {name}" + (f" :: {detail}" if detail else ""))


def result_check(name: str, condition: bool, detail: str = "") -> None:
    """Emit the production RESULT:: marker for a new physical-path case."""
    global _passes, _fails
    if condition:
        _passes += 1
    else:
        _fails += 1
    suffix = "PASS_GREEN_BY_CODE" if condition else "FAIL"
    print(f"RESULT::{name}_{suffix}" + (f" | {detail}" if detail and not condition else ""))


def run_physical_cases() -> None:
    """ENG-018: drive opposing +2/-2 through the REAL process_fill intake, no network/orders."""
    import ast
    import csv
    import json
    import tempfile

    from convergence_shadow import compute_convergence_order

    COIN, PX = "BTC", 100.0
    W1, W2 = "0xw1", "0xw2"
    F1, F2 = "eng018-opp-a", "eng018-opp-b"
    cfgmap = {
        w: svcmod.LiveWalletConfig(wallet=w, mode="LIVE", copy_mode="proportional",
                                   norm_base=100.0, leader_equity_base=1000.0, enabled=True)
        for w in (W1, W2)
    }

    def make_fill(fid, wallet, side, size, ts):
        return svcmod.LeaderFill(
            fill_id=fid, wallet=wallet.lower(), coin=COIN, side=side, price=PX,
            size=abs(size), signed_size_delta=(size if side == "BUY" else -size),
            timestamp_ms=ts, timestamp_iso="2026-01-01T00:00:00Z",
            source="test", recording_method="test", raw={},
        )

    f1 = make_fill(F1, W1, "BUY", 20.0, 1000)
    f2 = make_fill(F2, W2, "SELL", 20.0, 1001)

    def csv_rows(path):
        try:
            with open(path, newline="", encoding="utf-8-sig") as fh:
                return list(csv.DictReader(fh))
        except FileNotFoundError:
            return []

    def at_target_provider(svc, configs):
        # Account already at the event-authorised target: opposing leaders cancel to zero orders.
        def provider(coin):
            signed = svc.leader_signed_by_wallet(coin, configs)
            agg = svcmod.event_authorised_desired_net(coin, signed, configs)
            return {"ok": True, "net": float(agg.get("desired_net", 0.0)),
                    "source": "TEST_ACCOUNT_AT_TARGET"}
        return provider

    def run_intake():
        tmp = Path(tempfile.mkdtemp(prefix="eng018opp_"))
        svcmod.configure_paths(tmp, tmp / "raw_live_fills.csv")
        svcmod.TEST_INJECTION_ENABLED = True
        svcmod.XTRUTH = None  # test-only: never reach master/exchange truth (no network)
        svcmod.LIVE_AUTO_SEND_ENABLED = False
        svcmod.LIVE_POLL_ENABLED = False
        (tmp / "live_config.json").write_text(json.dumps({"wallets": {
            w: {"mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                "norm_base": 100.0, "leader_equity_base": 1000.0}
            for w in (W1, W2)}}), encoding="utf-8")

        svc = svcmod.DryRunLiveCopyService()
        svc.state["leader_event_positions"] = {}
        svc.state["counters"] = {}
        svc.processed_ids = set()
        svc.processed_id_order = []
        svc.account_net_provider = at_target_provider(svc, cfgmap)
        svc.process_fill(f1, cfgmap[W1])   # +2 sleeve via the real production intake
        svc.process_fill(f2, cfgmap[W2])   # -2 sleeve via the real production intake

        signed = svc.leader_signed_by_wallet(COIN, cfgmap)
        agg = svcmod.event_authorised_desired_net(COIN, signed, cfgmap)
        sleeves = agg.get("sleeves") or {}
        counters = svc.state.get("counters") or {}
        skip_keys = [k for k in counters if "skip" in k or "block" in k or "review" in k]
        skip_counter = sum(int(counters.get(k, 0)) for k in skip_keys)
        recs = [r for r in csv_rows(svcmod.RECONCILIATION_CSV)
                if r.get("leader_fill_id") in (F1, F2)]
        intents = [r for r in csv_rows(svcmod.ORDER_INTENTS_CSV)
                   if r.get("leader_fill_id") in (F1, F2)]
        would = [r for r in csv_rows(svcmod.WOULD_SEND_ORDERS_CSV)
                 if r.get("leader_fill_id") in (F1, F2)]
        decision = compute_convergence_order(
            COIN, float(agg.get("desired_net", 0.0)), 0.0,
            mark_px=PX, min_notional=svcmod.MIN_ORDER_NOTIONAL)
        return {
            "consumed": F1 in svc.processed_ids and F2 in svc.processed_ids,
            "agg_ok": bool(agg.get("ok")),
            "net_target": float(agg.get("desired_net", float("nan"))),
            "sleeves": dict(sleeves),
            "signed": dict(signed),
            "skip_counter": skip_counter,
            "skip_keys": skip_keys,
            "rec_events": [r.get("event") for r in recs],
            "rec_ids": {r.get("leader_fill_id") for r in recs},
            "intents": len(intents),
            "would": len(would),
            "decision_action": str(getattr(decision, "action", "")),
            "decision_reason": str(getattr(decision, "reason", "")),
        }

    def evaluate(obs):
        sleeves = obs["sleeves"]
        # Case 5: re-derive the account-net target independently of the send decision.
        target = svcmod.event_authorised_desired_net(COIN, obs["signed"], cfgmap)
        target_ok = bool(target.get("ok")) and abs(float(target.get("desired_net", float("nan")))) < 1e-12
        return [
            ("PHYS_INTAKE_BOTH_EVENTS_CONSUMED", obs["consumed"],
             f"both fill ids in processed_ids"),
            ("PHYS_INTAKE_NET_TARGET_ZERO", obs["agg_ok"] and abs(obs["net_target"]) < 1e-12,
             f"net={obs['net_target']}"),
            ("PHYS_PER_LEADER_SLEEVES_DISTINCT",
             set(sleeves) == {W1, W2} and abs(float(sleeves.get(W1, 0)) - 2.0) < 1e-12
             and abs(float(sleeves.get(W2, 0)) + 2.0) < 1e-12,
             f"sleeves={sleeves}"),
            ("PHYS_PER_LEADER_PNL_NOT_MERGED",
             len(obs["signed"]) == 2 and abs(float(obs["signed"].get(W1, 0)) - 20.0) < 1e-12
             and abs(float(obs["signed"].get(W2, 0)) + 20.0) < 1e-12,
             f"signed={obs['signed']}"),
            ("PHYS_SKIP_COUNTER_ZERO_BOTH",
             obs["skip_counter"] == 0 and len(obs["rec_events"]) == 2
             and all(e == "CONVERGED" for e in obs["rec_events"]),
             f"skip={obs['skip_counter']} keys={obs['skip_keys']} events={obs['rec_events']}"),
            ("PHYS_ZERO_PHYSICAL_ORDERS", obs["intents"] == 0 and obs["would"] == 0,
             f"intents={obs['intents']} would_send={obs['would']}"),
            ("PHYS_BOTH_IDS_IN_LEDGER", obs["rec_ids"] == {F1, F2},
             f"ledger_ids={sorted(obs['rec_ids'])}"),
            ("PHYS_ACCOUNT_NET_TARGET_ASSERTED", target_ok,
             f"independent_target={target.get('desired_net')}"),
            ("PHYS_SEND_DECISION_NO_ORDER", obs["decision_action"] == "NONE",
             f"action={obs['decision_action']} reason={obs['decision_reason']}"),
        ]

    def exchange_order_calls(path):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        return [n for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "order" and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "exchange"]

    print("=== PHYSICAL PATH: opposing +2/-2 through process_fill ===")
    green = run_intake()
    for name, cond, detail in evaluate(green):
        result_check(name, cond, detail)

    core = Path(svcmod.__file__).with_name("HL_Live_Copy_Service_Core.py")
    core_calls = len(exchange_order_calls(core))
    result_check("PHYS_AST_SINGLE_EXCHANGE_ORDER_CALLSITE", core_calls == 1,
                 f"core_exchange_order_calls={core_calls}")

    # ---- FALSIFICATION: inject a mismatched per-leader attribution ----
    original = svcmod.event_authorised_desired_net

    def corrupt_attribution(coin, signed, configs, fixed=None):
        res = original(coin, signed, configs, fixed) if fixed is not None else original(coin, signed, configs)
        if not res.get("ok"):
            return res
        sleeves = res.get("sleeves") or {}
        if len(sleeves) < 2:
            return res
        first = next(iter(sleeves))
        res = dict(res)
        # Attribute BOTH leaders' PnL to a single wallet key (mismatched sleeve).
        res["sleeves"] = {first: sum(float(v) for v in sleeves.values())}
        return res

    svcmod.event_authorised_desired_net = corrupt_attribution
    try:
        corrupt_obs = run_intake()
        detected = [n for n, c, _ in evaluate(corrupt_obs) if not c]
    finally:
        svcmod.event_authorised_desired_net = original

    result_check("FALSIFICATION_MISMATCH_DETECTED", bool(detected),
                 "no new check failed under injected mismatch" if not detected else "")
    print("FALSIFICATION_OUTCOME: injected per-leader attribution mismatch -> "
          + (", ".join(detected) if detected else "NOT DETECTED"))


def main() -> None:
    configs = {
        wallet: svcmod.LiveWalletConfig(wallet=wallet, mode="LIVE", copy_mode="proportional",
                                        norm_base=100.0, leader_equity_base=1000.0, enabled=True)
        for wallet in ("0xw1", "0xw2")
    }

    def run_case(label: str, leader_sizes: dict[str, float], expected_net: float) -> None:
        agg = svcmod.event_authorised_desired_net("BTC", leader_sizes, configs)
        sleeves = agg.get("sleeves", {})
        check(f"{label}: both leader entries retained", agg.get("ok") and len(sleeves) == 2,
              f"entries={len(sleeves)} sleeves={sleeves}")
        check(f"{label}: desired_net equals arithmetic sum {expected_net:+.1f}",
              agg.get("ok") and abs(float(agg.get("desired_net", float('nan'))) - expected_net) < 1e-12,
              f"desired_net={agg.get('desired_net')}")
        check(f"{label}: each attributed sleeve keeps its signed size",
              all(wallet in sleeves and abs(float(sleeves[wallet]) - size * 0.1) < 1e-12
                  for wallet, size in leader_sizes.items()),
              f"sleeves={sleeves}")

    print("=== Opposing leaders +2 / -2 ===")
    run_case("opposing +2/-2", {"0xw1": 20.0, "0xw2": -20.0}, 0.0)
    print("=== Opposing leaders +3 / -1 ===")
    run_case("opposing +3/-1", {"0xw1": 30.0, "0xw2": -10.0}, 2.0)
    print("=== Same-side control +1 / +1 ===")
    run_case("same-side +1/+1", {"0xw1": 10.0, "0xw2": 10.0}, 2.0)

    run_physical_cases()
    print(f"TOTAL={_passes + _fails} FAILED={_fails}")
    raise SystemExit(1 if _fails else 0)


if __name__ == "__main__":
    main()
