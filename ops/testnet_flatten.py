#!/usr/bin/env python3
"""TESTNET flatten script: cancel all open orders and close all positions via reduce-only.

Usage:
    python ops/testnet_flatten.py --dry-run
    python ops/testnet_flatten.py --execute
"""

import sys
import os
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Add the _archive/hl_stage2 to path

INFO_URL = "https://api.hyperliquid-testnet.xyz/info"
FOLLOWER_ADDR = "0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205"

def fetch_open_orders():
    """Fetch open orders from TESTNET."""
    req = Request(
        INFO_URL,
        data=json.dumps({"type": "openOrders", "user": FOLLOWER_ADDR}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urlopen(req, timeout=10) as resp:
        return json.load(resp)

def fetch_mids():
    """Fetch mid prices from TESTNET."""
    req = Request(
        "https://api.hyperliquid-testnet.xyz/info",
        data=json.dumps({"type": "allMids"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urlopen(req, timeout=10) as resp:
        return json.load(resp)

def fetch_positions():
    """Fetch positions from TESTNET."""
    req = Request(
        INFO_URL,
        data=json.dumps({"type": "clearinghouseState", "user": FOLLOWER_ADDR}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    return data.get("assetPositions", [])

def cancel_all_orders(dry_run: bool):
    """Cancel all open orders via TESTNET API."""
    orders = fetch_open_orders()
    if not orders:
        print("No open orders to cancel.")
        return True
    
    print(f"Found {len(orders)} open orders to cancel.")
    
    for order in orders:
        oid = order.get("oid")
        coin = order.get("coin")
        if not oid:
            print(f"  WARNING: Order missing oid: {order}")
            continue
        
        if dry_run:
            print(f"  [DRY-RUN] Would cancel order {oid} ({coin})")
            continue
        
        # Use the TESTNET cancel endpoint
        try:
            # Use the Hyperliquid cancel endpoint
            cancel_req = Request(
                "https://api.hyperliquid-testnet.xyz/exchange",
                data=json.dumps({
                    "action": {"type": "cancel", "cancels": [{"coin": coin, "oid": int(oid)}]}
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urlopen(cancel_req, timeout=10) as resp:
                result = json.load(resp)
                print(f"  Cancelled order {oid} ({coin}): {result}")
        except (URLError, HTTPError, Exception) as e:
            print(f"  ERROR cancelling order {oid} ({coin}): {e}")
            return False
    return True

def close_positions(dry_run: bool):
    """Close all positions via reduce-only orders."""
    positions = fetch_positions()
    if not positions:
        print("No positions to close.")
        return True
    
    # Filter non-zero positions
    active_positions = [p for p in positions if float(p.get("szi", "0")) != 0]
    if not active_positions:
        print("All positions already flat.")
        return True
    
    print(f"Found {len(active_positions)} non-flat positions to close.")
    
    mids = fetch_mids()
    
    for pos in active_positions:
        coin = pos.get("coin")
        szi = float(pos.get("szi", "0"))
        if szi == 0:
            continue
        
        side = "sell" if szi > 0 else "buy"
        size = abs(szi)
        
        if dry_run:
            print(f"  [DRY-RUN] Would close {coin} {side} {size}")
            continue
        
        mid_price = mids.get(coin)
        if not mid_price:
            print(f"  ERROR: No mid price for {coin}")
            return False
        
        mid = float(mid_price)
        if side == "sell":
            limit_px = str(mid * 0.99)
        else:
            limit_px = str(mid * 1.01)
        
        try:
            order_req = Request(
                "https://api.hyperliquid-testnet.xyz/exchange",
                data=json.dumps({
                    "action": {
                        "type": "order",
                        "orders": [{
                            "coin": coin,
                            "is_buy": side == "buy",
                            "sz": str(size),
                            "limit_px": limit_px,
                            "reduce_only": True,
                            "tif": "Ioc"
                        }]
                    }
                }).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urlopen(order_req, timeout=10) as resp:
                result = json.load(resp)
                print(f"  Closed {coin} {side} {size} @ {limit_px}: {result}")
        except (URLError, HTTPError, Exception) as e:
            print(f"  ERROR closing {coin}: {e}")
            return False
    return True

def verify_flat(dry_run: bool):
    """Verify zero open orders and flat positions."""
    orders = fetch_open_orders()
    positions = fetch_positions()
    
    if orders:
        print(f"FAIL: {len(orders)} open orders remain")
        return False
    
    active_positions = [p for p in positions if float(p.get("szi", "0")) != 0]
    if active_positions:
        print(f"FAIL: {len(active_positions)} non-flat positions remain")
        for p in active_positions:
            print(f"  {p['coin']}: {p['szi']}")
        return False
    
    if dry_run:
        print("DRY-RUN: Would verify zero open orders and flat positions")
    else:
        print("VERIFIED: Zero open orders, all positions flat")
    return True

def main():
    import argparse
    parser = argparse.ArgumentParser(description="TESTNET flatten: cancel all orders and close positions")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--execute", action="store_true", help="Actually execute the flatten")
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        parser.error("Must specify either --dry-run or --execute")
    
    dry_run = args.dry_run
    
    if dry_run:
        print("=== DRY RUN MODE ===")
    else:
        print("=== EXECUTE MODE ===")
    
    print(f"Target account: {FOLLOWER_ADDR}")
    print(f"TESTNET endpoint: {INFO_URL}")
    
    # Step 1: Cancel all open orders
    print("\n--- Step 1: Cancel all open orders ---")
    if not cancel_all_orders(dry_run):
        print("FAILED: Could not cancel all orders")
        return 1
    
    # Step 2: Close all positions (reduce-only)
    print("\n--- Step 2: Close all positions (reduce-only) ---")
    if not close_positions(dry_run):
        print("FAILED: Could not close all positions")
        return 1
    
    # Step 3: Verify flat
    print("\n--- Step 3: Verify flat ---")
    if not verify_flat(dry_run):
        print("FAILED: Verification failed")
        return 1
    
    if dry_run:
        print("\n=== DRY RUN COMPLETE: Would flatten successfully ===")
    else:
        print("\n=== FLATTEN COMPLETE ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())