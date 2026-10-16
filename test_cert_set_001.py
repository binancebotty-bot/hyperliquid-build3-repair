#!/usr/bin/env python3
"""Test for SET-001: TODO.
TODO
Run: HL_LIVE_ENV_FILE=/nonexistent python test_cert_set_001.py
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / '_archive' / 'hl_stage2'))
import exchange_truth as et

# Set up environment to avoid loading real .env
tmp = Path(tempfile.mkdtemp(prefix="cert_set-001_"))
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

def test_positive():
    """Test a simple full fill."""
    intent = {
        "coin": "BTC",
        "side": "BUY",
        "size": 1.0,  # 1.0 BTC
        "oid": "oid123",
    }
    fills = [
        {
            "oid": "oid123",
            "coin": "BTC",
            "side": "B",  # Hyperliquid uses B for BUY, A for SELL
            "sz": "1.0",
            "px": "100",
            "tid": "tid1",
            "time": "1000",
        }
    ]
    master_net = 0.0
    result = et.resolve_settlement(intent, fills, master_net)
    # We expect a full fill because we got a fill of 1.0 BTC for an intent of 1.0 BTC.
    check("SET-001_positive_status", result.get("status") == et.SETTLE_FULL, f"status={result.get('status')}")
    check("SET-001_positive_filled", abs(result.get("filled", 0.0) - 1.0) < 1e-9, f"filled={result.get('filled')}")
    check("SET-001_positive_remaining", abs(result.get("remaining", 0.0) - 0.0) < 1e-9, f"remaining={result.get('remaining')}")

def test_negative():
    """Test an ack without fill (reservation not cleared)."""
    intent = {
        "coin": "BTC",
        "side": "BUY",
        "size": 1.0,
        "oid": "oid123",
    }
    fills = []  # no fills
    master_net = 0.0
    result = et.resolve_settlement(intent, fills, master_net)
    # We expect SETTLE_NONE because there are no matching fills.
    check("SET-001_negative_status", result.get("status") == et.SETTLE_NONE, f"status={result.get('status')}")
    check("SET-001_negative_filled", result.get("filled", 0.0) == 0.0, f"filled={result.get('filled')}")
    check("SET-001_negative_remaining", abs(result.get("remaining", 0.0) - 1.0) < 1e-9, f"remaining={result.get('remaining')}")

if __name__ == "__main__":
    test_positive()
    test_negative()
    passed = sum(1 for _, ok in R if ok)
    failed = sum(1 for _, ok in R if not ok)
    print(f"SUMMARY::{passed}_passed_{failed}_failed")
    sys.exit(1 if failed > 0 else 0)