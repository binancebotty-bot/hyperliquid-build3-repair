#!/usr/bin/env python3
"""CASE 2 - test_readinv_429.py
Target: _fresh_exchange_net (8215+) returns None on a failed read; _close_net_with_reread (8536-8546) performs exactly ONE bounded re-read then returns None.
Drive: fake fetcher raising a 429-style error.
Assert: exactly two read attempts (initial + one re-read), then None, then a HOLD, ZERO wire calls.
Mutation: make the except path return 0.0 instead of None -> test must go RED.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
A = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="readinv_429_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "testnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
        "HL_FOLLOWER_DEXES": "xyz",
        "HL_LIVE_DISABLE_NETWORK_REFRESH": "0",
        "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
        "HL_LIVE_HL_PRIVATE_KEY": "0x" + "1" * 64,
        "HL_LIVE_HL_ACCOUNT_ADDRESS": FOLLOWER,
    })
    os.environ["HL_LIVE_GLOBAL_LOCK_FILE"] = str(Path(tempfile.mkdtemp(prefix="hl_lock_")) / "engine-global.lock")

    import HL_Live_Copy_Service_Core as c
    state_dir = Path(tempfile.mkdtemp(prefix="hl_state_"))
    c.acquire_global_instance_lock(state_dir)

    c.USER_WALLET = FOLLOWER
    c.HLAccount, c.HLExchange = object, object
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})

    # Fake exchange that records wire calls
    class Ex:
        def __init__(self):
            self.calls = []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"coin": coin, "size": size, "px": px, "reduce_only": reduce_only})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 3}}]}}}

    # Resolved coin mock for BTC
    resolved_btc = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                    "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def mk_intent(iid, coin, kind):
        side = "SELL" if kind == "EXIT" else "BUY"
        fill = c.LeaderFill("f_" + iid, A, coin, side, 100.0, 1.0, c.utc_now_ms(), "TEST")
        return c.Intent(iid, fill, side, 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", kind, "sleeve:%s:%s" % (A, coin), "",
                        "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=%s;" % kind)

    def run_close_test(exposure_fetcher, test_name):
        """Run a close test with given exposure_fetcher."""
        ledger = c.ManualLedger(path=tmp / f"ledger_{test_name}.json")
        ledger.sleeve(A, "BTC")["signed_size"] = 10.0

        ex = Ex()
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
        g._resolve_coin = lambda coin: dict(resolved_btc)
        g._get_exchange_client = lambda *a, **k: ex
        g._exchange_client_has_symbol = lambda *a, **k: True
        g._validate_final_wire_order = lambda *a, **k: (True, {})
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._exchange_client_for_coin = lambda coin: (ex, coin)
        g._pre_send_ownership_gate = lambda it: (True, {})
        g.leader_reduced_since = lambda f: 0
        g.cfg.master_switch_now = lambda: True
        g.cfg.liq_parity_enabled = lambda: False

        # Override EXPOSURE_FETCHER so _fresh_exchange_net's try/except catches it
        c.EXPOSURE_FETCHER = exposure_fetcher

        intent = mk_intent(f"e_{test_name}", "BTC", "EXIT")
        ok, status, res = g._send_real(intent)
        return ok, status, ex.calls

    # ----- Test 1: _fresh_exchange_net returns None on 429, _close_net_with_reread does exactly ONE re-read -----
    # Track calls to EXPOSURE_FETCHER (which _fresh_exchange_net calls)
    call_count = {"count": 0}

    def fetcher_429(payload):
        call_count["count"] += 1
        raise RuntimeError("429 Too Many Requests")

    # Test _close_net_with_reread directly
    ledger = c.ManualLedger(path=tmp / "ledger_reread.json")
    ledger.sleeve(A, "BTC")["signed_size"] = 10.0
    g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    c.EXPOSURE_FETCHER = fetcher_429
    result = g._close_net_with_reread("BTC")
    check("REREAD_EXACTLY_TWO_ATTEMPTS", call_count["count"] == 2, "count=%d" % call_count["count"])
    check("REREAD_RETURNS_NONE", result is None)

    # ----- Test 2: Close path - should HOLD with zero wire calls -----
    call_count["count"] = 0
    ok, status, calls = run_close_test(fetcher_429, "429")
    check("429_CLOSE_HOLDS", ok is False and "CLOSE_PROOF_HOLD" in status and not calls, "%s %s" % (status, calls))
    check("429_EXACTLY_TWO_READS_IN_CLOSE", call_count["count"] == 2, "count=%d" % call_count["count"])

    # ----- Mutation proof -----
    # If _fresh_exchange_net's except block returned 0.0 instead of None,
    # then _finite_net_or_none(0.0) returns 0.0 (finite), _close_net_with_reread returns 0.0,
    # and the close would see a readable net (0.0) instead of unreadable, potentially SENDing.
    # The test asserts result IS None and close HOLDs, so mutation would make it FAIL.

    c.release_global_instance_lock()
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()