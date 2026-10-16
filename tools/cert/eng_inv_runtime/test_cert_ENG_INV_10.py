#!/usr/bin/env python3
"""ENG-INV-10: Ack without MASTER fill never settles; only independent MASTER evidence settles."""
from __future__ import annotations

import os
import sys
from pathlib import Path

HL_STAGE2 = Path(r"C:\Users\wigmore\trading_stack\hl-build3-testnet-cert\_archive\hl_stage2")
sys.path.insert(0, str(HL_STAGE2))

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    import exchange_truth as xt

    # ENG-INV-10: Stub an API ack with no MASTER fill and no position delta
    intent = {"size": 1.0, "coin": "BTC", "side": "BUY", "oid": ""}

    # Phase 1: Ack with no fill and no position delta -> must NOT settle
    r1 = xt.resolve_settlement(intent, fills=[], master_net=0.0)
    check("ENG_INV_10_ack_no_fill_unsettled",
          r1["settled"] is False and r1["status"] == xt.SETTLE_NONE,
          "expected unsettled, got settled=%s status=%s" % (r1.get("settled"), r1.get("status")))

    # Phase 2: Independent MASTER userfills + account-net verification -> settles
    master_fills = [{"coin": "BTC", "side": "B", "sz": 1.0}]
    r2 = xt.resolve_settlement(intent, fills=master_fills, master_net=1.0)
    check("ENG_INV_10_master_evidence_settles",
          r2["settled"] is True and r2["status"] == xt.SETTLE_FULL,
          "expected settled full, got settled=%s status=%s" % (r2.get("settled"), r2.get("status")))

    # Phase 3: Partial fill -> still unsettled
    r3 = xt.resolve_settlement(intent, fills=[{"coin": "BTC", "side": "B", "sz": 0.5}], master_net=0.5)
    check("ENG_INV_10_partial_fill_unsettled",
          r3["settled"] is False and r3["status"] == xt.SETTLE_PARTIAL,
          "expected partial unsettled, got settled=%s status=%s" % (r3.get("settled"), r3.get("status")))

    # Phase 4: Reject evidence with no fill -> terminal reject
    r4 = xt.resolve_settlement(intent, fills=[], master_net=0.0,
                                reject_evidence={"terminal_reject": True, "no_fill_proved": True})
    check("ENG_INV_10_reject_evidence_settles",
          r4["settled"] is True and r4["status"] == xt.SETTLE_REJECTED,
          "expected terminal reject, got settled=%s status=%s" % (r4.get("settled"), r4.get("status")))

    # Phase 5: No fills and no master_net -> unknown (no independent evidence)
    r5 = xt.resolve_settlement(intent, fills=None, master_net=None)
    check("ENG_INV_10_no_evidence_unknown",
          r5["settled"] is False and r5["status"] == xt.SETTLE_UNKNOWN,
          "expected unknown, got settled=%s status=%s" % (r5.get("settled"), r5.get("status")))

    # Summary
    passed = sum(1 for _, ok in RESULTS if ok)
    total = len(RESULTS)
    print("SUMMARY::%d/%d passed" % (passed, total))
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
