#!/usr/bin/env python3
"""CASE 4 - test_readinv_wrong_wallet.py
Target: _close_proof_account_ok (8904-8915) compares the reader wallet to HL_LIVE_HL_ACCOUNT_ADDRESS;
the lag planner raises CLOSE_PROOF_HOLD_ACCOUNT_MISMATCH (8470-8471) / CLOSE_PROOF_HOLD_ORDER_ACCOUNT_MISMATCH (8476-8477).
Drive: set HL_LIVE_HL_ACCOUNT_ADDRESS to a different VALID wallet.
Assert: HOLD with the account-mismatch reason, ZERO wire calls.
Mutation: make _close_proof_account_ok `return True` -> test must go RED.
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
WRONG_ACCOUNT = "0x" + "d" * 40  # Different valid wallet


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="readinv_wrong_wallet_"))
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
        "HL_LIVE_HL_ACCOUNT_ADDRESS": WRONG_ACCOUNT,  # Different from USER_WALLET (FOLLOWER)
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

    def gw_send(g, ex):
        g._get_exchange_client = lambda *a, **k: ex
        g._exchange_client_has_symbol = lambda *a, **k: True
        g._validate_final_wire_order = lambda *a, **k: (True, {})
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._exchange_client_for_coin = lambda coin: (ex, coin)
        g._pre_send_ownership_gate = lambda it: (True, {})
        g.leader_reduced_since = lambda f: 0
        g.cfg.master_switch_now = lambda: True
        g.cfg.liq_parity_enabled = lambda: False

    # Resolved coin mock for BTC
    resolved_btc = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                    "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def mk_intent(iid, coin, kind):
        side = "SELL" if kind == "EXIT" else "BUY"
        fill = c.LeaderFill("f_" + iid, A, coin, side, 100.0, 1.0, c.utc_now_ms(), "TEST")
        return c.Intent(iid, fill, side, 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", kind, "sleeve:%s:%s" % (A, coin), "",
                        "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=%s;" % kind)

    # Create a gateway with a ledger that has an owned sleeve
    ledger = c.ManualLedger(path=tmp / "ledger.json")
    ledger.sleeve(A, "BTC")["signed_size"] = 10.0

    # ----- Test 1: Direct test of _close_proof_account_ok -----
    # With HL_LIVE_HL_ACCOUNT_ADDRESS = WRONG_ACCOUNT and USER_WALLET = FOLLOWER, they don't match
    account_ok = c.SenderGateway._close_proof_account_ok()
    check("ACCOUNT_OK_RETURNS_FALSE_WHEN_MISMATCH", account_ok is False)

    # ----- Test 2: Close path (non-lag) - _close_wire_plan -----
    ex1 = Ex()
    g1 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    g1._resolve_coin = lambda coin: dict(resolved_btc)
    gw_send(g1, ex1)
    intent1 = mk_intent("e1", "BTC", "EXIT")
    ok1, status1, res1 = g1._send_real(intent1)
    check("WRONG_WALLET_CLOSE_HOLDS_ACCOUNT_MISMATCH", ok1 is False and status1 == "SEND_NOT_ATTEMPTED_CLOSE_PROOF_HOLD" and "CLOSE_PROOF_HOLD_ACCOUNT_MISMATCH" in res1.get("error", "") and not ex1.calls, "%s %s" % (status1, res1))

    # ----- Test 3: Close path (lag planner) - _close_wire_plan_ledger_lag -----
    # Test the lag planner directly with a ledger that has an owned sleeve
    ex2 = Ex()
    g2 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    g2._resolve_coin = lambda coin: dict(resolved_btc)
    gw_send(g2, ex2)
    # Call the lag planner directly with a decide function
    intent2 = mk_intent("e2", "BTC", "EXIT")
    # Mock _proven_owned_for_sleeve to return the owned amount
    g2._proven_owned_for_sleeve = lambda w, c: (10.0, "fills")
    captured = {}
    def decide(kind: str, amount: float = 0.0, ro: bool = False, why: str = "") -> tuple:
        captured["kind"] = kind
        captured["amount"] = amount
        captured["ro"] = ro
        captured["why"] = why
        return ro, amount, why
    ro, amount, why = c.SenderGateway._close_wire_plan_ledger_lag(g2, intent2, 1.0, 3, lambda sz: True, decide)
    check("WRONG_WALLET_LAG_HOLDS_ACCOUNT_MISMATCH", ro is False and why == "CLOSE_PROOF_HOLD_ACCOUNT_MISMATCH" and not ex2.calls, "%s %s" % (why, ex2.calls))

    # ----- Test 4: _follower_order_account_for_proof mismatch path -----
    # This tests the ORDER_ACCOUNT_MISMATCH path (lines 8337-8342, 8472-8477)
    # We need _close_proof_account_ok to pass (USER_WALLET == HL_LIVE_HL_ACCOUNT_ADDRESS)
    # but _follower_order_account_for_proof to return a different account
    os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = FOLLOWER
    ex3 = Ex()
    g3 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    g3._resolve_coin = lambda coin: dict(resolved_btc)
    gw_send(g3, ex3)
    g3._follower_order_account_for_proof = lambda: "0x" + "e" * 40  # Different from USER_WALLET
    intent3 = mk_intent("e3", "BTC", "EXIT")
    ok3, status3, res3 = g3._send_real(intent3)
    check("WRONG_ORDER_ACCOUNT_HOLDS_ORDER_MISMATCH", ok3 is False and status3 == "SEND_NOT_ATTEMPTED_CLOSE_PROOF_HOLD" and "CLOSE_PROOF_HOLD_ORDER_ACCOUNT_MISMATCH" in res3.get("error", "") and not ex3.calls, "%s %s" % (status3, res3))
    # Restore for any subsequent tests
    os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = WRONG_ACCOUNT

    # ----- Mutation proof: if _close_proof_account_ok returned True -----
    # The tests above assert HOLD with ACCOUNT_MISMATCH or ORDER_ACCOUNT_MISMATCH.
    # If the mutation made _close_proof_account_ok return True, these would not HOLD
    # and might SEND instead, causing the tests to FAIL (go RED).

    c.release_global_instance_lock()
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()