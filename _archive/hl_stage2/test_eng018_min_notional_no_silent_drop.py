#!/usr/bin/env python3
"""ENG-018 / OD-09: a copy size that rounds BELOW the $10 minimum must never vanish silently.

It must either be sent at the $10 minimum (bounded round-up) or refused BY NAME with a counter.
Never a bare drop, never an unflushed accumulator, and never a refusal recorded as CONVERGED.
Offline only; never submits orders.

The planner is NOT stubbed: only the exchange-truth boundary is (account-net actual, reconciliation
gate), so the effective minimum, the uplift envelope, the szDecimals ceiling and the ledger seam are
all production code.
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
    tmp = Path(tempfile.mkdtemp(prefix="eng018_min_"))
    os.environ.update(HL_LIVE_AUDIT_DIR=str(tmp), HL_LIVE_AUTO_SEND_ENABLED="0", HL_LIVE_POLL_ENABLED="0")
    os.environ.pop("HL_LIVE_MAX_ENTRY_UPLIFT_RATIO", None)
    os.environ.pop("HL_LIVE_MAX_ENTRY_UPLIFT_ABS_USD", None)
    (tmp / "live_config.json").write_text(json.dumps({"wallets": {}}), encoding="utf-8")
    import HL_Live_Copy_Service as svcmod
    svcmod.TEST_INJECTION_ENABLED = True
    # pin the venue metadata so the lot size is a fixture, not a network call
    svcmod.HL_PERP_META_BY_COIN_CACHE = {c: {"szDecimals": 5, "name": c, "canonical_name": c}
                                         for c in ("BTC", "ETH", "SOL")}
    MIN = svcmod.MIN_ORDER_NOTIONAL
    wallet = "0xw1"
    cfg = svcmod.LiveWalletConfig(wallet=wallet, mode="LIVE", copy_mode="proportional",
                                  norm_base=1000.0, leader_equity_base=1000.0, enabled=True)
    svc = svcmod.DryRunLiveCopyService()
    svc.global_order_cap = lambda: 0.0   # no operator cap in this check
    svc.load_config = lambda: {wallet: cfg}
    # only the exchange-truth boundary is faked: flat follower, reconciled. The planner itself is real,
    # so this checks the production decision (effective minimum, envelope, szDecimals) and the seam.
    svc.account_net_actual = lambda coin: {"ok": True, "status": "OK", "net": 0.0}
    svc.reconcile_gate = lambda coin, net: {"ok": True, "status": "OK"}

    def rows(path):
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                return list(csv.DictReader(fh))
        except FileNotFoundError:
            return []

    def intents(fill_id):
        return [r for r in rows(svcmod.ORDER_INTENTS_CSV) if r.get("leader_fill_id") == fill_id]

    def recon(fill_id):
        return [r for r in rows(svcmod.RECONCILIATION_CSV) if r.get("leader_fill_id") == fill_id]

    def counter(key):
        # OD-09: ONE counter, in service state, keyed by the planner's own classification
        return int((svc.state.get("min_notional_events") or {}).get(key, 0) or 0)

    def would_send(fill_id):
        return [r for r in rows(svcmod.WOULD_SEND_ORDERS_CSV) if r.get("leader_fill_id") == fill_id]

    def run_case(fill_id, coin, notional, price=100.0):
        size = notional / price
        fill = svcmod.LeaderFill(fill_id, wallet, coin, "BUY", price, size, size,
                                 int(time.time() * 1000), "2026-01-01T00:00:00Z", "ws", "test", {})
        svc.process_fill(fill, cfg)
        return fill

    # (1) a size that rounds just under $10 must still reach the book at the $10 minimum
    run_case("od09-round-up", "BTC", 9.60)
    ws1 = would_send("od09-round-up")
    sent_at_min = [r for r in ws1 if abs(fnum(r.get("copy_notional")) - MIN) < 1e-9]
    check("below-min $9.60 rounds UP to the $10 minimum and is SENT (never dropped)",
          bool(sent_at_min) and counter("uplifted") >= 1,
          f"would_send={ws1} counter={svc.state.get('min_notional_events')}")

    # (2) a size too small to round up must be an explicit NAMED refusal, with a counter
    run_case("od09-named-refusal", "ETH", 2.00)
    refused = [r for r in intents("od09-named-refusal") if r.get("status") == "ENTRY_BELOW_MIN_NOTIONAL_REFUSED"]
    check("deep below-min $2.00 is a NAMED refusal with a counter (never a silent drop)",
          bool(refused) and counter("refused") >= 1 and not would_send("od09-named-refusal"),
          f"statuses={[r.get('status') for r in intents('od09-named-refusal')]} counter={svc.state.get('min_notional_events')}")

    # (2b) the refusal must be written AS a refusal, never as convergence (the old silent-drop seam)
    refusal_recon = recon("od09-named-refusal")
    check("a planner refusal is NEVER reconciled as CONVERGED",
          len(refusal_recon) == 1
          and refusal_recon[0].get("status") == "ENTRY_BELOW_MIN_NOTIONAL_REFUSED"
          and refusal_recon[0].get("action") == "REFUSED_BELOW_MIN_NOTIONAL"
          and refusal_recon[0].get("event") == "REFUSE",
          repr(refusal_recon))
    check("no CONVERGED row is written for the refused fill",
          not [r for r in recon("od09-named-refusal")
               if r.get("event") == "CONVERGED" or r.get("status") == "CONVERGED"],
          repr(refusal_recon))

    # (3) the old silent-drop signature: parked in an accumulator that is never flushed
    dangling = [r for r in rows(svcmod.ORDER_INTENTS_CSV) if r.get("status") == "ACCUMULATED_NO_ORDER"]
    check("no fill is parked in an unflushed accumulator (the silent-drop signature)",
          not dangling, f"dangling={len(dangling)}")

    # (4) the $10 minimum itself is unchanged: an exact-$10 copy sends directly, not refused, not uplifted
    before_uplift = counter("uplifted")
    run_case("od09-exact-min", "SOL", 10.00)
    ex_ws = would_send("od09-exact-min")
    check("an exact $10.00 copy is still sent at $10.00 (minimum unchanged)",
          bool(ex_ws) and all(abs(fnum(r.get("copy_notional")) - MIN) < 1e-9 for r in ex_ws)
          and counter("uplifted") == before_uplift,
          f"would_send={ex_ws} uplifts_before={before_uplift} uplifts_after={counter('uplifted')}")

    failed = [name for name, ok in checks if not ok]
    for i, (name, ok) in enumerate(checks, 1):
        print(f"RESULT::ENG018_MIN_{i}_{'PASS' if ok else 'FAIL'}")
    print(f"TOTAL={len(checks)} FAILED={len(failed)}")
    if failed:
        print("FAILING_CHECKS=" + " | ".join(failed))
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
