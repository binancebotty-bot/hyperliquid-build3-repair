#!/usr/bin/env python3
"""Per-wallet money fields on :8031 must each declare ONE scope, and gross must differ from net.

Pins the account_reconciliation scope pair that was collapsed before 2026-10-21:
  attributed_open_pnl  = sum of live_unrealized_pnl  (open position P&L only, no fees, no funding)
  estimated_copy_pnl   = sum of live_net_pnl         (closed + open - fees, i.e. net of fees)
Both used to be assigned the same expression (live_net_pnl), so a caller reading
"attributed_open_pnl" got a fee-netted figure labelled as open P&L.

The fixture has non-zero fees, so gross != net by construction.

Run: python test_ui_wallet_pnl_scope.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["HL_LIVE_AUDIT_DIR"] = tempfile.mkdtemp(prefix="pnlscope_")  # never the live state folder
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> int:
    import HL_Copy_App_SSOT as app

    # Two leaders, non-zero fees on both, so net != open by more than rounding.
    perf = {
        "0x" + "a" * 40: {"live_net_pnl": -0.8735, "live_unrealized_pnl": 0.0, "live_realized_pnl": -0.4098, "fees": 0.4637},
        "0x" + "b" * 40: {"live_net_pnl": 2.5, "live_unrealized_pnl": 3.0, "live_realized_pnl": 0.6, "fees": 1.1},
    }
    # A wallet whose open P&L is unknown must not contribute 0 to the open sum.
    perf["0x" + "c" * 40] = {"live_net_pnl": None, "live_unrealized_pnl": None}

    snap = {"available": False, "updated_at": "2026-10-21T00:00:00Z"}
    out = app._build_account_reconciliation(snap, perf)

    open_pnl = out.get("attributed_open_pnl")
    copy_pnl = out.get("estimated_copy_pnl")

    check("open_pnl_is_sum_of_open_only", open_pnl == 3.0, f"got {open_pnl!r} want 3.0")
    check("copy_pnl_is_sum_of_net", copy_pnl == 1.6265, f"got {copy_pnl!r} want 1.6265")
    check("gross_open_differs_from_net_copy", open_pnl != copy_pnl, f"both {open_pnl!r}")
    check("open_pnl_is_not_fee_netted", open_pnl == 3.0 and copy_pnl < open_pnl, "open must sit above the fee-netted figure")
    check("scope_label_open", "open position" in str(out.get("attributed_open_pnl_scope", "")).lower(), str(out.get("attributed_open_pnl_scope")))
    check("scope_label_copy", "fees" in str(out.get("estimated_copy_pnl_scope", "")).lower(), str(out.get("estimated_copy_pnl_scope")))

    passed = sum(1 for _n, ok in RESULTS if ok)
    failed = len(RESULTS) - passed
    print(f"RESULT::SUMMARY_{'PASS' if failed == 0 else 'FAIL'} | {passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
