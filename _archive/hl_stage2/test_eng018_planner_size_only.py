#!/usr/bin/env python3
"""ENG-018 review must-fix: the planner's size is the ONLY size. Offline: no exchange client, no orders.

Pins:
  1  an ENTRY whose planner decision carries a notional and a price but NO usable size is REFUSED by name
     (ENTRY_PLANNER_SIZE_MISSING) -- the service never reconstructs a size from notional/price, because that
     round-trip can discard the planner's ceiling-quantised value and send a floored size;
  2  the refusal is a ledger fact: reconciliation row + counter, and ZERO send artefacts (no would-send row,
     no auto-send attempt);
  3  a size <= 0 is refused the same way (absent and non-positive are the same broken decision);
  4  the control: a valid planner size is used verbatim, never re-derived (0.51 stays 0.51, not 50/100=0.5);
  5  the non-entry paths that legitimately carry no sendable planner size are unchanged: the exit/reduce
     below the minimum still records its MANUAL_REVIEW row (that derived size is a review record, never a
     send) and an exit with a planner size still uses that size verbatim.
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
    tmp = Path(tempfile.mkdtemp(prefix="eng018_size_only_"))
    os.environ.update(HL_LIVE_AUDIT_DIR=str(tmp), HL_LIVE_AUTO_SEND_ENABLED="0", HL_LIVE_POLL_ENABLED="0")
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {}}), encoding="utf-8")
    import HL_Live_Copy_Service as svcmod
    svcmod.TEST_INJECTION_ENABLED = True
    # the refusal name is the fix under test: resolved by string so a missing guard fails on BEHAVIOUR
    SIZE_MISSING = getattr(svcmod, "PLANNER_SIZE_MISSING", "PLANNER_SIZE_MISSING")
    svcmod.HL_PERP_META_BY_COIN_CACHE = {c: {"szDecimals": d, "name": c, "canonical_name": c}
                                         for c, d in (("BTC", 5), ("XRP", 0), ("ETH", 5))}
    wallet = "0xw1"
    cfg = svcmod.LiveWalletConfig(wallet=wallet, mode="LIVE", copy_mode="proportional",
                                  norm_base=1000.0, leader_equity_base=1000.0, enabled=True)
    svc = svcmod.DryRunLiveCopyService()
    svc.global_order_cap = lambda: 0.0
    svc.load_config = lambda: {wallet: cfg}
    # only the exchange-truth boundary is faked; the planner seam and the send seam are production code
    svc.account_net_actual = lambda coin: {"ok": True, "status": "OK", "net": 0.0}
    svc.reconcile_gate = lambda coin, net: {"ok": True, "status": "OK"}

    # every sendable artefact funnels through here (append_order_intent -> append_would_send_order ->
    # maybe_auto_send_would_send), so counting calls is counting exchange-call attempts.
    sends = []
    _real_auto_send = svc.maybe_auto_send_would_send

    def counting_auto_send(c, intent_row):
        sends.append(dict(intent_row))
        return _real_auto_send(c, intent_row)

    svc.maybe_auto_send_would_send = counting_auto_send
    seq = [0]

    def rows(path):
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                return list(csv.DictReader(fh))
        except FileNotFoundError:
            return []

    def recon(fill_id):
        return [r for r in rows(svcmod.RECONCILIATION_CSV) if r.get("leader_fill_id") == fill_id]

    def intents(fill_id):
        return [r for r in rows(svcmod.ORDER_INTENTS_CSV) if r.get("leader_fill_id") == fill_id]

    def would_send(fill_id):
        return [r for r in rows(svcmod.WOULD_SEND_ORDERS_CSV) if r.get("leader_fill_id") == fill_id]

    def fresh_fill(coin, price, notional):
        seq[0] += 1
        size = notional / price
        return svcmod.LeaderFill(f"psz-{seq[0]}", wallet, coin, "BUY", price, size, size,
                                 int(time.time() * 1000) + seq[0], "2026-01-01T00:00:00Z", "ws", "test", {})

    def stub_auth(notional, action="OPEN", reduce_only=False, size=..., coin="BTC", price=100.0):
        auth = {"ok": True, "status": "OK", "notional": notional, "action": action,
                "side": "SELL" if reduce_only else "BUY", "reduce_only": reduce_only,
                "desired_net": 0.0, "reason": action, "min_notional_event": ""}
        if size is not ...:
            auth["size"] = size
        svc.convergence_notional_for_fill = lambda c, f: dict(auth)
        return fresh_fill(coin, price, notional)

    def counter(key):
        return int((svc.state.get("counters") or {}).get(key, 0) or 0)

    # ---------------------------------------------------------- 1/2) entry, size ABSENT -> refused, no send
    absent_before = counter("entries_blocked_planner_size_missing")
    f_absent = stub_auth(50.0, price=100.0)          # $50 copy at $100, planner sent NO size at all
    n_sends_before = len(sends)
    svc.process_fill(f_absent, cfg)
    del svc.convergence_notional_for_fill
    r_absent, i_absent, w_absent = recon(f_absent.fill_id), intents(f_absent.fill_id), would_send(f_absent.fill_id)
    check("an ENTRY with a planner notional and price but NO planner size is REFUSED by name",
          len(r_absent) == 1 and r_absent[0].get("status") == "ENTRY_" + SIZE_MISSING
          and r_absent[0].get("event") == "REFUSE",
          f"recon={r_absent}")
    check("that refusal reaches NO send seam: no would-send row, no auto-send attempt, no reconstructed size",
          not w_absent and len(sends) == n_sends_before
          and all(fnum(r.get("copy_size")) == 0.0 for r in i_absent),
          f"would_send={w_absent} auto_send_attempts={len(sends) - n_sends_before} order_intents={i_absent}")
    check("the refusal is counted once, under its own name",
          counter("entries_blocked_planner_size_missing") == absent_before + 1,
          f"entries_blocked_planner_size_missing={counter('entries_blocked_planner_size_missing')}")

    # ---------------------------------------------------------- 3) size <= 0 is the same broken decision
    for label, bad_size in (("size=None", None), ("size=0", 0.0), ("size=-1", -1.0)):
        f_bad = stub_auth(50.0, price=100.0, size=bad_size)
        n_before = len(sends)
        svc.process_fill(f_bad, cfg)
        del svc.convergence_notional_for_fill
        r_bad, w_bad = recon(f_bad.fill_id), would_send(f_bad.fill_id)
        check(f"an ENTRY with {label} is refused by the same name and sends nothing",
              len(r_bad) == 1 and r_bad[0].get("status") == "ENTRY_" + SIZE_MISSING
              and not w_bad and len(sends) == n_before,
              f"recon={r_bad} would_send={w_bad}")

    # ---------------------------------------------------------- 4) control: the planner's size is used verbatim
    f_ok = stub_auth(50.0, price=100.0, size=0.51)   # ceilinged size; 50/100 would be 0.50
    svc.process_fill(f_ok, cfg)
    del svc.convergence_notional_for_fill
    i_ok, w_ok = intents(f_ok.fill_id), would_send(f_ok.fill_id)
    got = fnum(w_ok[0].get("copy_size")) if w_ok else 0.0
    check("a valid planner size is carried verbatim to the wire (0.51 stays 0.51, never re-derived 0.50)",
          abs(got - 0.51) < 1e-12 and bool(i_ok),
          f"would_send_copy_size={got} order_intent_copy_size={[r.get('copy_size') for r in i_ok]}")

    # ---------------------------------------------------------- 5) non-entry paths unchanged
    f_exit_small = stub_auth(5.0, action="REDUCE", reduce_only=True, price=100.0)   # $5 exit, no size
    n_before = len(sends)
    svc.process_fill(f_exit_small, cfg)
    del svc.convergence_notional_for_fill
    r_small, w_small = recon(f_exit_small.fill_id), would_send(f_exit_small.fill_id)
    check("an EXIT below the minimum still records its MANUAL_REVIEW row (review size only) and sends nothing",
          len(r_small) == 1 and r_small[0].get("event") == "REVIEW"
          and r_small[0].get("status") == "EXIT_BELOW_MIN_NOTIONAL"
          and not w_small and len(sends) == n_before,
          f"recon={r_small} would_send={w_small}")

    f_exit_ok = stub_auth(20.0, action="REDUCE", reduce_only=True, size=0.203, price=100.0)
    svc.process_fill(f_exit_ok, cfg)
    del svc.convergence_notional_for_fill
    i_exit = intents(f_exit_ok.fill_id)
    check("an EXIT above the minimum still uses its planner size verbatim and is not caught by the entry guard",
          bool(i_exit) and abs(fnum(i_exit[0].get("copy_size")) - 0.203) < 1e-12
          and i_exit[0].get("intent_type") == "EXIT",
          f"order_intents={i_exit}")

    failed = [name for name, ok in checks if not ok]
    for i, (name, ok) in enumerate(checks, 1):
        print(f"RESULT::ENG018_SIZEONLY_{i}_{'PASS' if ok else 'FAIL'}")
    print(f"TOTAL={len(checks)} FAILED={len(failed)}")
    if failed:
        print("FAILING_CHECKS=" + " | ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
