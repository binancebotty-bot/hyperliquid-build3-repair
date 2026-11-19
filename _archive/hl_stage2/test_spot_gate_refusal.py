#!/usr/bin/env python3
"""Core engine: spot pairs are refused at the DECISION gate, not later at the sender.

A leader fill for a spot pair (PURR, @107, */USDC, */USDT) must resolve to
BLOCKED_SPOT_NOT_SUPPORTED before any send path is reachable, and a leader spot close with no
owned sleeve resolves to NOT_APPLICABLE_SPOT (SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION keeps its
single meaning). Perp coins are unaffected.

Run: python test_spot_gate_refusal.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="corespot_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env")})
    import HL_Live_Copy_Service_Core as c

    LEADER = "0x" + "d" * 40

    def fetcher(payload):
        t = payload.get("type")
        if t == "perpDexs":
            return []
        if t == "allMids":
            return {"BTC": "100", "PURR": "0.2"}
        return {"assetPositions": []}
    c.EXPOSURE_FETCHER = fetcher
    c.MIDS_FETCHER = fetcher

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
        LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000}}})

    seq = [0]

    def fill(side="BUY", coin="BTC", price=100.0, size=1.0, raw=None):
        seq[0] += 1
        return c.LeaderFill("s%d" % seq[0], LEADER, coin, side, price, size, c.utc_now_ms(), "TEST", raw=raw or {})

    def decide(coin, side="BUY", sleeve=0.0, price=100.0, raw=None):
        led = c.ManualLedger(path=tmp / ("pos%d.json" % seq[0]))
        if sleeve:
            led.sleeve(LEADER, coin)["signed_size"] = sleeve
        i = c.IntentBuilder(c.ConfigManager(), led).build(fill(side, coin, price, raw=raw))
        return i.decision, i.reason, i.send_allowed

    for coin in ("PURR", "@107", "PURR/USDC", "HYPE/USDT"):
        d, r, sendable = decide(coin, price=0.2)
        check("SPOT_REFUSED_AT_GATE_" + c._safe_marker_name(coin), d == "BLOCKED_SPOT_NOT_SUPPORTED", "%s -> %s / %s" % (coin, d, r))
        check("SPOT_NOT_SENDABLE_" + c._safe_marker_name(coin), sendable is False, "%s send_allowed=%s" % (coin, sendable))

    # ---- spot close with no owned sleeve: NOT_APPLICABLE_SPOT, not the no-manual-position reason ----
    # lifecycle is ENTRY (a spot sleeve is never owned), so close evidence comes from the raw fill dir.
    d, r, sendable = decide("PURR", side="SELL", price=0.2, raw={"dir": "Close Long"})
    check("SPOT_CLOSE_NO_SLEEVE_NOT_APPLICABLE", d == "NOT_APPLICABLE_SPOT", "%s / %s" % (d, r))
    check("SPOT_CLOSE_NOT_SENDABLE", sendable is False, str(sendable))

    d, r, sendable = decide("BTC")
    check("PERP_ENTRY_STILL_ALLOWED", d == "ENTRY_ALLOWED" and sendable is True, "%s / %s" % (d, r))
    led = c.ManualLedger(path=tmp / "perp_exit.json")
    led.sleeve(LEADER, "BTC")["signed_size"] = 10.0
    i = c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", "BTC"))
    check("PERP_EXIT_STILL_ALLOWED", i.decision == "EXIT_ALLOWED", "%s / %s" % (i.decision, i.reason))

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
        LEADER: {"enabled": True, "mode": "CLO", "copy_mode": "fixed", "fixed_notional": 1000}}})
    d, r, _ = decide("PURR", price=0.2)
    check("SPOT_REFUSAL_PRECEDES_CLO", d == "BLOCKED_SPOT_NOT_SUPPORTED", "%s / %s" % (d, r))
    d, r, _ = decide("BTC")
    check("PERP_CLO_STILL_BLOCKED_CLO_ENTRY", d == "BLOCKED_CLO_ENTRY", "%s / %s" % (d, r))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
