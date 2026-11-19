#!/usr/bin/env python3
"""ENG-018 / OD-09 review must-fixes: one check per finding. Offline: no exchange client, no orders.

Pins:
  1  ONE envelope: the same notional gets the same verdict from the planner and from the ledger seam, and
     the env knobs are honoured at CALL time (no import-time freeze), so the two layers cannot disagree.
  2  ONE minimum: the effective minimum (max of $10, wallet cfg, symbol) is what the planner is given.
  3  the seam: a planner refusal is written as a REFUSAL, never as CONVERGED.
  4  wire validity: the uplift is ceiling-quantised to szDecimals and re-asserted, so the sender's own
     floor cannot drop the wire notional below the minimum (XRP/BTC/DOGE cases).
  5  non-finite input is refused by name at both layers, before any division.
  6  ONE counter, in service state, keyed by the planner's own classification.
"""
from __future__ import annotations
import csv, json, os, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

checks = []


def check(name, condition, detail=""):
    passed = bool(condition)
    checks.append((name, passed))
    print(f"{'PASS' if passed else 'FAIL'}: {name}" + (f" :: {detail}" if detail else ""))


def fnum(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def main():
    tmp = Path(tempfile.mkdtemp(prefix="eng018_od09_review_"))
    os.environ.update(HL_LIVE_AUDIT_DIR=str(tmp), HL_LIVE_AUTO_SEND_ENABLED="0", HL_LIVE_POLL_ENABLED="0")
    os.environ.pop("HL_LIVE_MAX_ENTRY_UPLIFT_RATIO", None)
    os.environ.pop("HL_LIVE_MAX_ENTRY_UPLIFT_ABS_USD", None)
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {}}), encoding="utf-8")
    import HL_Live_Copy_Service as svcmod
    import convergence_shadow as shadow
    svcmod.TEST_INJECTION_ENABLED = True
    svcmod.HL_PERP_META_BY_COIN_CACHE = {c: {"szDecimals": d, "name": c, "canonical_name": c}
                                         for c, d in (("BTC", 5), ("XRP", 0), ("DOGE", 0), ("ETH", 5))}
    MIN = svcmod.MIN_ORDER_NOTIONAL
    wallet = "0xw1"
    cfg = svcmod.LiveWalletConfig(wallet=wallet, mode="LIVE", copy_mode="proportional",
                                  norm_base=1000.0, leader_equity_base=1000.0, enabled=True)
    svc = svcmod.DryRunLiveCopyService()
    svc.global_order_cap = lambda: 0.0
    svc.load_config = lambda: {wallet: cfg}
    # only the exchange-truth boundary is faked; the planner, the minimum and the seam are production code
    svc.account_net_actual = lambda coin: {"ok": True, "status": "OK", "net": 0.0}
    svc.reconcile_gate = lambda coin, net: {"ok": True, "status": "OK"}
    seq = [0]

    def rows(path):
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                return list(csv.DictReader(fh))
        except FileNotFoundError:
            return []

    def recon(fill_id):
        return [r for r in rows(svcmod.RECONCILIATION_CSV) if r.get("leader_fill_id") == fill_id]

    def would_send(fill_id):
        return [r for r in rows(svcmod.WOULD_SEND_ORDERS_CSV) if r.get("leader_fill_id") == fill_id]

    def counter(key):
        return int((svc.state.get("min_notional_events") or {}).get(key, 0) or 0)

    def fresh_fill(coin, notional, price):
        seq[0] += 1
        size = notional / price
        return svcmod.LeaderFill(f"od09r-{seq[0]}", wallet, coin, "BUY", price, size, size,
                                 int(time.time() * 1000) + seq[0], "2026-01-01T00:00:00Z", "ws", "test", {})

    def reset_lineage():
        svc.state["leader_event_positions"] = {}   # every case starts from a flat, empty event lineage

    # ------------------------------------------------------------------ 1) one envelope, honoured live
    def planner_verdict(coin, notional, price):
        reset_lineage()
        return svc.convergence_notional_for_fill(cfg, fresh_fill(coin, notional, price))

    def seam_verdict(coin, notional, price):
        reset_lineage()
        fill = fresh_fill(coin, notional, price)
        svc.process_fill(fill, cfg)
        return fill.fill_id

    os.environ["HL_LIVE_MAX_ENTRY_UPLIFT_RATIO"], os.environ["HL_LIVE_MAX_ENTRY_UPLIFT_ABS_USD"] = "1.1", "0.5"
    ref_fill = seam_verdict("BTC", 7.50, 3.75)
    tight_auth = planner_verdict("BTC", 7.50, 3.75)
    tight_recon = recon(ref_fill)
    check("$7.50 copy, tight env: planner refuses and the LEDGER records the same refusal (not CONVERGED)",
          str(tight_auth.get("reason")) == shadow.MIN_NOTIONAL_REFUSAL
          and float(tight_auth.get("notional") or 0.0) == 0.0
          and len(tight_recon) == 1
          and tight_recon[0].get("status") == "ENTRY_BELOW_MIN_NOTIONAL_REFUSED"
          and tight_recon[0].get("event") == "REFUSE"
          and not would_send(ref_fill),
          f"planner={tight_auth.get('reason')} recon={tight_recon}")

    tight_refused_counter = counter("refused")
    os.environ["HL_LIVE_MAX_ENTRY_UPLIFT_RATIO"], os.environ["HL_LIVE_MAX_ENTRY_UPLIFT_ABS_USD"] = "2.0", "0.5"
    up_fill = seam_verdict("BTC", 7.50, 3.75)
    wide_auth = planner_verdict("BTC", 7.50, 3.75)
    wide_ws = would_send(up_fill)
    check("the SAME $7.50 copy under a wider LIVE env is uplifted by the planner and sent by the ledger "
          "(the envelope is read per call, never frozen at import)",
          str(wide_auth.get("reason")).endswith("ROUNDED_UP_TO_MIN_NOTIONAL")
          and fnum(wide_auth.get("notional")) >= MIN - 1e-9
          and bool(wide_ws) and all(fnum(r.get("copy_notional")) >= MIN - 1e-9 for r in wide_ws),
          f"planner={wide_auth.get('reason')} notional={wide_auth.get('notional')} would_send={wide_ws}")

    # ------------------------------------------------------------------ 6) ONE counter, planner-keyed
    # each env setting consumes the planner twice (once through the seam, once directly), so each
    # classification must have been counted exactly twice -- no other counter exists to disagree.
    check("ONE counter moves on the planner's own classification (refused, then uplifted)",
          tight_refused_counter == 2 and counter("refused") == tight_refused_counter
          and counter("uplifted") == 2,
          f"min_notional_events={svc.state.get('min_notional_events')}")
    check("the planner keeps NO counter of its own (the duplicate counter is gone)",
          not hasattr(shadow, "MIN_NOTIONAL_EVENTS"),
          f"shadow attrs with counter: {[a for a in dir(shadow) if 'COUNT' in a.upper()]}")

    # ------------------------------------------------------------------ 2) one effective minimum
    hi_min = svcmod.LiveWalletConfig(wallet=wallet, mode="LIVE", copy_mode="proportional",
                                     norm_base=1000.0, leader_equity_base=1000.0, enabled=True,
                                     min_notional=25.0)
    eff, szd = svc.planner_entry_minimum(hi_min, "BTC")
    eff_default, _ = svc.planner_entry_minimum(cfg, "BTC")
    check("the planner is given the EFFECTIVE minimum (max of $10 floor, wallet cfg, symbol), not a bare 10",
          abs(eff - 25.0) < 1e-9 and abs(eff_default - MIN) < 1e-9 and szd == 5,
          f"cfg_min=25 -> {eff}; default -> {eff_default}; szDecimals={szd}")
    reset_lineage()
    big_min_fill = fresh_fill("BTC", 12.0, 100.0)   # $12 copy clears $10 but not a $25 configured minimum
    svc.process_fill(big_min_fill, hi_min)
    big_recon = recon(big_min_fill.fill_id)
    check("a copy below the EFFECTIVE minimum is uplifted/refused against that minimum, not against $10",
          bool(big_recon) and big_recon[0].get("status") == "ENTRY_BELOW_MIN_NOTIONAL_REFUSED",
          repr(big_recon))

    # ------------------------------------------------------------------ 4) wire-valid uplift at szDecimals
    os.environ.pop("HL_LIVE_MAX_ENTRY_UPLIFT_RATIO", None)
    os.environ.pop("HL_LIVE_MAX_ENTRY_UPLIFT_ABS_USD", None)
    for coin, px, sz_d in (("XRP", 1.40, 0), ("BTC", 61000.0, 5), ("DOGE", 0.1234, 0)):
        auth = planner_verdict(coin, 8.00, px)
        size = fnum(auth.get("size"))
        reason = str(auth.get("reason") or "")
        if reason == shadow.MIN_NOTIONAL_REFUSAL:
            ok, detail = True, f"refused by name: {reason}"
        else:
            wire = float(svcmod.round_size_hl_perp(size, sz_d)[0])   # the sender's own floor
            ok = abs(wire - size) < 1e-12 and wire * px >= MIN - 1e-9
            detail = f"size={size} wire_size={wire} wire_notional={wire * px:.4f} (min {MIN})"
        check(f"{coin} @{px:g} szD={sz_d}: settled size survives the sender's szDecimals floor at >= the minimum",
              ok, detail)

    # ------------------------------------------------------------------ 5) non-finite is refused by name
    reset_lineage()
    nan_auth = svc.convergence_order_for_coin(cfg, fresh_fill("BTC", 7.5, 3.75), {wallet: cfg}, float("nan"))
    nan_order = nan_auth.get("order")
    check("NaN account-net is refused by name in the planner (no fabricated order)",
          getattr(nan_order, "action", None) == "NONE" and getattr(nan_order, "reason", "") == shadow.NON_FINITE_REFUSAL
          and getattr(nan_order, "size", 1.0) == 0.0,
          getattr(nan_order, "short", lambda: nan_order)())

    # a NaN notional arriving from the planner layer must never fall through `<= 0` / `> cap` into a send
    nan_fill = fresh_fill("BTC", 7.5, 3.75)
    svc.convergence_notional_for_fill = lambda c, f: {
        "ok": True, "status": "OK", "notional": float("nan"), "size": float("nan"), "action": "OPEN",
        "side": "BUY", "reduce_only": False, "desired_net": 2.0, "reason": "OPEN", "min_notional_event": ""}
    svc.process_fill(nan_fill, cfg)
    del svc.convergence_notional_for_fill
    nan_recon = recon(nan_fill.fill_id)
    check("a NaN planner notional is a NAMED refusal at the seam (never an order, never CONVERGED)",
          len(nan_recon) == 1
          and nan_recon[0].get("status") == "ENTRY_" + shadow.NON_FINITE_REFUSAL
          and nan_recon[0].get("event") == "REFUSE"
          and not would_send(nan_fill.fill_id),
          repr(nan_recon))

    failed = [name for name, ok in checks if not ok]
    for i, (name, ok) in enumerate(checks, 1):
        print(f"RESULT::ENG018_OD09R_{i}_{'PASS' if ok else 'FAIL'}")
    print(f"TOTAL={len(checks)} FAILED={len(failed)}")
    if failed:
        print("FAILING_CHECKS=" + " | ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
