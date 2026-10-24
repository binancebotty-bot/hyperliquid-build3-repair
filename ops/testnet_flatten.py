#!/usr/bin/env python3
"""TESTNET flatten script: cancel all open orders and close all positions via reduce-only.

Usage:
    python ops/testnet_flatten.py --dry-run
    python ops/testnet_flatten.py --execute
    python ops/testnet_flatten.py --auth-check
"""

import sys
import os
import json
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Load testnet env
TESTNET_ENV = Path(r"C:/Users/wigmore/trading_stack/hl-prod-base/.env.testnet")
if TESTNET_ENV.exists():
    for line in TESTNET_ENV.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

# Hyperliquid SDK
try:
    from eth_account import Account
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Testnet constants
TESTNET_URL = "https://api.hyperliquid-testnet.xyz"
INFO_URL = f"{TESTNET_URL}/info"
EXCHANGE_URL = f"{TESTNET_URL}/exchange"
MASTER_ADDR = "0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205"  # Follower account (vault)
AGENT_KEY = os.getenv("HL_TESTNET_AGENT_PRIVATE_KEY", "")
if not AGENT_KEY:
    print("ERROR: HL_TESTNET_AGENT_PRIVATE_KEY not set")
    sys.exit(1)

# Hard fail if mainnet URL or wrong account
if TESTNET_URL != constants.TESTNET_API_URL:
    print("ERROR: Only testnet URL allowed")
    sys.exit(1)

# Initialize SDK
agent_acct = Account.from_key(AGENT_KEY)
exchange = Exchange(
    wallet=agent_acct,
    base_url=TESTNET_URL,
    vault_address=MASTER_ADDR
)
info = Info(base_url=TESTNET_URL)

# Verify we're the right agent
if agent_acct.address.lower() != "0x34f322d8eb97461da8f1bd2f1b95dcf4ca52a76d":
    print(f"ERROR: Unexpected agent address: {agent_acct.address}")
    sys.exit(1)

def fetch_open_orders():
    """Fetch open orders from TESTNET."""
    req = Request(
        INFO_URL,
        data=json.dumps({"type": "openOrders", "user": MASTER_ADDR}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urlopen(req, timeout=10) as resp:
        return json.load(resp)

def fetch_mids():
    """Fetch mid prices from TESTNET."""
    req = Request(
        INFO_URL,
        data=json.dumps({"type": "allMids"}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urlopen(req, timeout=10) as resp:
        return json.load(resp)

def fetch_positions():
    """Fetch positions from TESTNET."""
    req = Request(
        INFO_URL,
        data=json.dumps({"type": "clearinghouseState", "user": MASTER_ADDR}).encode(),
        headers={"Content-Type": "application/json"}
    )
    with urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    return data.get("assetPositions", [])

def cancel_all_orders(dry_run: bool, auth_check: bool = False):
    """Cancel all open orders via TESTNET API (signed)."""
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
        
        if dry_run or auth_check:
            print(f"  [DRY-RUN] Would cancel order {oid} ({coin})")
            continue
        
        # Use SDK to sign and send cancel
        try:
            result = exchange.cancel(coin, int(oid))
            print(f"  Cancelled order {oid} ({coin}): {result}")
        except Exception as e:
            print(f"  ERROR cancelling order {oid} ({coin}): {e}")
            return False
    return True

def close_positions(dry_run: bool, auth_check: bool = False):
    """Close all positions via reduce-only orders (signed)."""
    positions = fetch_positions()
    if not positions:
        print("No positions to close.")
        return True
    
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
        
        if dry_run or auth_check:
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
            result = exchange.order(
                coin,
                side == "buy",
                size,
                limit_px,
                {"limit": {"tif": "Ioc"}},
                reduce_only=True
            )
            print(f"  Closed {coin} {side} {size} @ {limit_px}: {result}")
        except Exception as e:
            print(f"  ERROR closing {coin}: {e}")
            return False
    return True

def verify_flat(dry_run: bool):
    """Verify zero open orders and flat positions."""
    if dry_run:
        print("DRY-RUN: Would verify zero open orders and flat positions")
        return True
    
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
    
    print("VERIFIED: Zero open orders, all positions flat")
    return True

def auth_check():
    """Sign one harmless action to verify authentication works."""
    print("=== AUTH CHECK MODE ===")
    print(f"Agent: {agent_acct.address}")
    print(f"Vault (master): {MASTER_ADDR}")
    print(f"Base URL: {TESTNET_URL}")
    print(f"Testnet only: {TESTNET_URL == constants.TESTNET_API_URL}")
    
    # Try to cancel a non-existent order (should get order-not-found, not auth error)
    try:
        result = exchange.cancel("BTC", 99999999999)
        print(f"Auth check cancel result: {result}")
        if "error" in str(result).lower() and ("signature" in str(result).lower() or "auth" in str(result).lower()):
            print("FAIL: Authentication error")
            return False
        print("PASS: Signed request accepted (order not found is expected)")
        return True
    except Exception as e:
        err_str = str(e).lower()
        if "signature" in err_str or "auth" in err_str or "unauthorized" in err_str:
            print(f"FAIL: Authentication error: {e}")
            return False
        print(f"PASS: Signed request accepted (expected error: {e})")
        return True

def main():
    parser = argparse.ArgumentParser(description="TESTNET flatten: cancel all orders and close positions")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--execute", action="store_true", help="Actually execute the flatten")
    parser.add_argument("--auth-check", action="store_true", help="Verify signed auth works")
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute and not args.auth_check:
        parser.error("Must specify --dry-run, --execute, or --auth-check")
    if sum([args.dry_run, args.execute, args.auth_check]) > 1:
        parser.error("Only one mode allowed")
    
    if args.auth_check:
        return 0 if auth_check() else 1
    
    dry_run = args.dry_run
    
    if dry_run:
        print("=== DRY RUN MODE ===")
    else:
        print("=== EXECUTE MODE ===")
    
    print(f"Agent: {agent_acct.address}")
    print(f"Vault (master): {MASTER_ADDR}")
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
