#!/usr/bin/env python3
"""Test for SET-004: Partial fill.
Expected behaviour: Ownership advances only by confirmed fill; residual authorised delta remains; no duplicate quantity (TEST-005).
Run: HL_LIVE_ENV_FILE=/nonexistent python test_cert_SET_004.py
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / '_archive' / 'hl_stage2'))
import exchange_truth as et

# Set up environment to avoid loading real .env
tmp = Path(tempfile.mkdtemp(prefix="cert_set_004_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(tmp),
    "HL_LIVE_ENV_FILE": "/nonexistent",  # never load a real .env with keys
    "HL_LEADER_NETWORK": "mainnet",
    "HL_FOLLOWER_NETWORK": "testnet",
})

R = []  # list of (name, bool) for results

def check(name, ok, detail=""):
    R.append((name, ok))
    print(f"RESULT::{name}_{'PASS' if ok else 'FAIL'}{' | ' + detail if detail and not ok else ''}")

def test_partial_fill_positive():
    """Test that a partial fill results in SETTLE_PARTIAL with correct filled and remaining."""
    # Intent: we want to buy 10 BTC (size = 10.0 BTC)
    intent = {
        "coin": "BTC",
        "side": "BUY",
        "size": 10.0,  # 10 BTC
        "oid": "oid123",
    }
    # Master fills: we got a fill for 5 BTC at price 100 (size = 5.0 BTC)
    fills = [
        {
            "oid": "oid123",
            "coin": "BTC",
            "side": "B",  # Hyperliquid uses B for BUY, A for SELL
            "sz": "5.0",
            "px": "100",
            "tid": "tid1",
            "time": "1000",
        }
    ]
    master_net = 0.0  # assume master net is 0 for simplicity
    # Note: the master_net in resolve_settlement is used for position_after in the settled full case.
    # For partial, it is returned as position_after in the result.
    result = et.resolve_settlement(intent, fills, master_net)
    # Check that we got a partial settlement
    check("SET-004_partial_fill_status", result.get("status") == et.SETTLE_PARTIAL, f"status={result.get('status')}")
    # Check that the filled amount is 5.0 (5 BTC)
    check("SET-004_partial_fill_filled", abs(result.get("filled", 0.0) - 5.0) < 1e-9, f"filled={result.get('filled')}")
    # Check that the remaining amount is 5.0 (10.0 - 5.0)
    check("SET-004_partial_fill_remaining", abs(result.get("remaining", 0.0) - 5.0) < 1e-9, f"remaining={result.get('remaining')}")
    # Check that position_after is the master_net (0.0) because we only partially filled?
    # Actually, the position_after in the result for partial is the master_net (which is the net position after the fill?).
    # In the function, for SETTLE_PARTIAL, position_after is set to master_net.
    check("SET-004_partial_fill_position_after", abs(result.get("position_after", 0.0) - master_net) < 1e-9, f"position_after={result.get('position_after')}")

def test_ack_without_fill_negative():
    """Test that an ack without fill results in SETTLE_NONE (reservation not cleared)."""
    # Intent: we sent an order for 10 BTC (size=10.0) but got no fill.
    intent = {
        "coin": "BTC",
        "side": "BUY",
        "size": 10.0,
        "oid": "oid123",
    }
    # No fills from master
    fills = []  # empty list
    master_net = 0.0
    result = et.resolve_settlement(intent, fills, master_net)
    # We expect SETTLE_NONE because there are no matching fills.
    check("SET-004_ack_without_fill_status", result.get("status") == et.SETTLE_NONE, f"status={result.get('status')}")
    # Filled should be 0
    check("SET-004_ack_without_fill_filled", result.get("filled", 0.0) == 0.0, f"filled={result.get('filled')}")
    # Remaining should be the full size
    check("SET-004_ack_without_fill_remaining", abs(result.get("remaining", 0.0) - 10.0) < 1e-9, f"remaining={result.get('remaining')}")

if __name__ == "__main__":
    test_partial_fill_positive()
    test_ack_without_fill_negative()
    passed = sum(1 for _, ok in R if ok)
    failed = sum(1 for _, ok in R if not ok)
    print(f"SUMMARY::{passed}_passed_{failed}_failed")
    sys.exit(1 if failed > 0 else 0)