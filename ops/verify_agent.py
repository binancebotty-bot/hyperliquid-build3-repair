#!/usr/bin/env python3
'''Read-only pre-flight: is the configured signing key usable for the follower account on one network?

Derives the public address from HL_LIVE_HL_PRIVATE_KEY, queries userRole on the chosen network and
compares it against the follower account - the same check the Core does in sender_key_check
(HL_Live_Copy_Service_Core.py:524-552). Prints ONLY the derived address, the follower address, a
PASS/FAIL verdict and one reason line. The key is never printed, logged or written anywhere.
'''
from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.request import Request, urlopen

from eth_account import Account

NETWORKS = {"testnet": "https://api.hyperliquid-testnet.xyz/info",
            "mainnet": "https://api.hyperliquid.xyz/info"}
TIMEOUT_SEC = 3.0


def fail(reason: str) -> int:
    print("FAIL: " + reason)
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--network", choices=sorted(NETWORKS), default="testnet")
    ap.add_argument("--follower", default=os.getenv("HL_LIVE_HL_ACCOUNT_ADDRESS", ""))
    args = ap.parse_args()

    key = os.environ.get("HL_LIVE_HL_PRIVATE_KEY", "").strip()
    if not key:
        return fail("HL_LIVE_HL_PRIVATE_KEY not set (run with the env file: set /a HL_LIVE_ENV_FILE=<path> & python ops/verify_agent.py)")
    try:
        signer = Account.from_key(key).address
    except Exception as exc:
        return fail("HL_LIVE_HL_PRIVATE_KEY is not a valid private key (%s)" % exc.__class__.__name__)

    follower = str(args.follower or "").strip()
    print("derived=%s follower=%s network=%s" % (signer, follower or "(unset)", args.network))
    if not (follower.startswith("0x") and len(follower) == 42):
        return fail("follower address is not a 42-char 0x address")

    req = Request(NETWORKS[args.network], method="POST",
                  data=json.dumps({"type": "userRole", "user": signer}).encode(),
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return fail("userRole unreadable on %s: %s: signing key not checked" % (args.network, exc.__class__.__name__))
    if not isinstance(data, dict) or not data.get("role"):
        return fail("userRole unreadable on %s: signing key not checked" % args.network)

    role = str(data["role"]).lower()
    owner = data.get("data", {}).get("user", "") if isinstance(data.get("data"), dict) else ""
    if role == "user" and signer.lower() == follower.lower():
        print("PASS: signing wallet is the follower account itself on %s" % args.network)
        return 0
    if role == "agent" and str(owner).lower() == follower.lower():
        print("PASS: signing wallet is an agent approved by the follower account on %s" % args.network)
        return 0
    return fail("signing wallet is %r on %s, not usable for the follower account (key from another network)" % (role, args.network))


if __name__ == "__main__":
    sys.exit(main())
