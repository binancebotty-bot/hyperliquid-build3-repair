#!/usr/bin/env python3
"""ENG-018 review must-fix 2: on the AUTO-LIVE route the planner's size is the only size.

The bypass under test: manual_send_one_intent's fixed-open branch re-derived payload["copy_size"]
from the WALLET config (fixed_notional / price) for auto_live sends, so an autonomous entry reached
the exchange at a size process_fill's planner-size guard never authorised - and never passed through
that guard at all.

Pins:
  A  an auto-live fixed open reaches the exchange at the PLANNER's size (row copy_size) and the
     planner's notional, never at fixed_notional/price (RED before the fix);
  B  an auto-live entry whose row carries no planner size reaches no exchange call (the pre-existing
     payload validation) and is now refused by the planner-size NAME, not as a generic bad row;
  C  the manual operator send - the same wallet, the same row - still reaches the exchange
     (control), and on that route the wallet's configured fixed_notional is the size authority
     (the distinction: human instruction vs autonomous copy).

Offline: send_hyperliquid_order is replaced by a recording stub. No exchange client, no orders.
"""
from __future__ import annotations
import csv, json, os, sys, tempfile
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
    tmp = Path(tempfile.mkdtemp(prefix="eng018_autofixed_"))
    os.environ.update(
        HL_LIVE_AUDIT_DIR=str(tmp),
        HL_LIVE_AUTO_SEND_ENABLED="1",          # this suite exercises the auto-live route itself
        HL_LIVE_AUTO_SEND_MAX_PER_RUN="10",
        HL_LIVE_AUTO_SEND_MARKETABLE_BPS="5",
        HL_LIVE_AUTO_SEND_WALLET="",
        HL_LIVE_POLL_ENABLED="0",
        HL_LIVE_HL_PRIVATE_KEY="0xselftest-not-a-key",
    )
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {}}), encoding="utf-8")
    import HL_Live_Copy_Service as svcmod
    svcmod.TEST_INJECTION_ENABLED = True
    svcmod.HL_PERP_META_BY_COIN_CACHE = {"TESTFIXED": {"szDecimals": 0, "name": "TESTFIXED"}}
    SIZE_MISSING = getattr(svcmod, "PLANNER_SIZE_MISSING", "PLANNER_SIZE_MISSING")

    wallet = "0xw1"
    coin, price = "TESTFIXED", 1.40
    planner_size = 8.0                      # planner's ceilinged size for an $11.20 entry at $1.40
    planner_notional = planner_size * price

    # the ONLY exchange seam: recording stub. Every call here is an order that would have been sent.
    sent = []

    def fake_send(payload, marketable_bps=0.0, use_current_quote=False, max_notional=None):
        size = fnum(payload.get("copy_size"))
        sent.append({"copy_size": size, "limit_price": fnum(payload.get("limit_price")),
                     "copy_notional": size * fnum(payload.get("limit_price")),
                     "reduce_only": bool(payload.get("reduce_only")), "max_notional": max_notional})
        return {"ok": True, "status": "ORDER_FILLED", "oid": "selftest-oid",
                "fill_size": size, "size": size, "coin": payload.get("coin"),
                "side": payload.get("side"), "reduce_only": payload.get("reduce_only")}

    svcmod.send_hyperliquid_order = fake_send

    def set_wallet(fixed_notional):
        (tmp / "live_config.json").write_text(json.dumps({"wallets": {wallet: {
            "mode": "LIVE", "enabled": True, "copy_mode": "fixed", "fixed_notional": fixed_notional}}}),
            encoding="utf-8", )

    def new_service():
        svc = svcmod.DryRunLiveCopyService()
        svc.global_order_cap = lambda: 0.0
        svc.account_net_actual = lambda c: {"ok": True, "status": "OK", "net": 0.0}
        svc.reconcile_gate = lambda c, net: {"ok": True, "status": "OK"}
        svc.load_config = lambda: {wallet: cfg}
        return svc

    def row(intent_id, size, notional):
        return {"created_at": svcmod.utc_now_iso(), "dry_run": True, "intent_id": intent_id,
                "leader_wallet": wallet, "leader_fill_id": intent_id,
                "source_reason": "LIVE_WS_DETECTED", "execution_decision": "WOULD_PLACE_IOC_LIMIT",
                "decision_reason": "LIVE_WS_FAST_PATH", "coin": coin, "side": "BUY",
                "copy_size": size, "copy_notional": notional, "order_type": "IOC_LIMIT",
                "limit_price": price, "reduce_only": False, "manual_reconcile_required": False,
                "status": "WOULD_SEND_DRY_RUN", "notes": "eng018 auto-live fixed open fixture"}

    # ---------------------------------------------------------------- A) auto-live fixed ENTRY, end to end
    set_wallet(20.0)                                   # wallet config would size 15 lots ($21) at $1.40
    cfg = svcmod.LiveWalletConfig(wallet=wallet, mode="LIVE", copy_mode="fixed",
                                  fixed_notional=20.0, enabled=True)
    svc = new_service()
    auth = {"ok": True, "status": "OK", "notional": planner_notional, "size": planner_size,
            "action": "OPEN", "side": "BUY", "reduce_only": False, "reason": "OPEN",
            "min_notional_event": ""}
    svc.convergence_notional_for_fill = lambda c, f: dict(auth)
    svcmod.dry_run_intent_audit_decision = lambda cfg_, fill, it, reducing, replay_history=False, quote_getter=None, side="": {
        "execution_decision": "WOULD_PLACE_IOC_LIMIT", "status": "DRY_RUN_FILLED",
        "reason": "LIVE_WS_DETECTED", "decision_reason": "LIVE_WS_FAST_PATH",
        "target_price": price, "suggested_order_type": "IOC_LIMIT",
        "suggested_limit_price": price, "manual_reconcile_required": False}
    fill = svcmod.LeaderFill("autofixed-1", wallet, coin, "BUY", price, 1.0, 1.0, 1700000000000,
                             "2026-01-01T00:00:00Z", "ws", "test", {})
    svc.process_fill(fill, cfg)                        # planner -> intent -> would-send -> AUTO-LIVE send
    got = sent[-1] if sent else {}
    check("an auto-live fixed open sends the PLANNER's size to the exchange, not fixed_notional/price",
          bool(sent) and abs(fnum(got.get("copy_size")) - planner_size) < 1e-12,
          f"planner_size={planner_size} wallet_fixed_notional=20.0 -> derived={20.0 / price:.4f} "
          f"exchange_copy_size={got.get('copy_size')} exchange_calls={len(sent)}")
    check("the auto-live entry's wire notional is the planner's notional, not the wallet's fixed_notional",
          bool(sent) and abs(fnum(got.get("copy_notional")) - planner_notional) < 1e-9,
          f"planner_notional={planner_notional} exchange_notional={fnum(got.get('copy_notional')):.6f}")

    # ---------------------------------------------------------------- B) auto-live ENTRY with NO planner size
    n_before = len(sent)
    svc_b = new_service()
    no_size_row = row("autofixed-nosize", 0.0, 0.0)
    svcmod.append_csv(svcmod.WOULD_SEND_ORDERS_CSV, svcmod.WOULD_SEND_ORDER_FIELDS, no_size_row)
    # maybe_auto_send_would_send inspects the order-intent row ("reason"), which append_would_send_order
    # renames to "source_reason" in the CSV; the intent-row shape is what the production caller passes.
    res_b = svc_b.maybe_auto_send_would_send(cfg, dict(no_size_row, reason="LIVE_WS_DETECTED"))
    attempt_b = {}
    if svcmod.SEND_ATTEMPTS_CSV.exists():
        with open(svcmod.SEND_ATTEMPTS_CSV, newline="", encoding="utf-8-sig") as fh:
            attempt_b = list(csv.DictReader(fh))[-1]
    check("an auto-live fixed open with NO planner size reaches no exchange call",
          len(sent) == n_before,
          f"exchange_calls_added={len(sent) - n_before} status={res_b.get('status')}")
    check("that refusal is by the planner-size NAME, not a generic invalid-row refusal",
          str(res_b.get("status") or "") == "ENTRY_" + SIZE_MISSING
          and "ENTRY_" + SIZE_MISSING in str(attempt_b.get("status") or ""),
          f"status={res_b.get('status')} send_attempt_status={attempt_b.get('status')} "
          f"error={attempt_b.get('error')}")

    # ---------------------------------------------------------------- C) MANUAL operator send: unchanged route
    set_wallet(10.5)                                   # wallet config: $10.5 at szDecimals=0 -> ceil 8 @ $1.40
    manual_row = row("autofixed-manual", 7500.0, 7500.0 * price)
    svcmod.append_csv(svcmod.WOULD_SEND_ORDERS_CSV, svcmod.WOULD_SEND_ORDER_FIELDS, manual_row)
    n_before = len(sent)
    manual = svcmod.manual_send_one_intent("autofixed-manual", True)   # the operator CLI route: no auto_live
    got_m = sent[-1] if len(sent) > n_before else {}
    check("a MANUAL operator send of the same fixed wallet still reaches the exchange (control)",
          len(sent) == n_before + 1 and manual.get("status") == "ORDER_FILLED",
          f"status={manual.get('status')} exchange_calls_added={len(sent) - n_before}")
    check("the manual send is sized by the wallet's configured fixed_notional (10.5 -> 8 lots), not the row's 7500",
          abs(fnum(got_m.get("copy_size")) - 8.0) < 1e-12,
          f"exchange_copy_size={got_m.get('copy_size')} intended_notional="
          f"{manual.get('payload', {}).get('intended_notional')}")

    failed = [name for name, ok in checks if not ok]
    for i, (name, ok) in enumerate(checks, 1):
        print(f"RESULT::ENG018_AUTOFIXED_{i}_{'PASS' if ok else 'FAIL'}")
    print(f"TOTAL={len(checks)} FAILED={len(failed)}")
    if failed:
        print("FAILING_CHECKS=" + " | ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
