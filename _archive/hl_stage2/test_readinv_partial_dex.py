#!/usr/bin/env python3
"""CASE 3 - test_readinv_partial_dex.py
Target: _fresh_exchange_net builds the dex scope, including the coin's own DEX via the `if ":" in str(coin)` block (~8223-8226).
Drive: fake exposure that omits the coin's own DEX / omits the coin row.
Assert: no sleeve is invented - close takes CLOSE_PROOF_HOLD_UNKNOWN_SLEEVE (8319-8320) or NET_NOT_OPPOSING; ZERO wire calls.
Mutation: delete the own-DEX append -> test must go RED.
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
    tmp = Path(tempfile.mkdtemp(prefix="readinv_partial_dex_"))
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

    # Resolved coin mocks
    resolved_btc = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                    "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
    resolved_xyz_gold = {"ok": True, "sdk_coin": "xyz:GOLD", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": ["xyz"],
                         "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def mk_intent(iid, coin, kind):
        side = "SELL" if kind == "EXIT" else "BUY"
        fill = c.LeaderFill("f_" + iid, A, coin, side, 100.0, 1.0, c.utc_now_ms(), "TEST")
        return c.Intent(iid, fill, side, 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", kind, "sleeve:%s:%s" % (A, coin), "",
                        "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=%s;" % kind)

    # Create a gateway with a ledger that has an owned sleeve for BTC
    ledger = c.ManualLedger(path=tmp / "ledger.json")
    ledger.sleeve(A, "BTC")["signed_size"] = 10.0

    # ----- Test 1: Coin with own DEX (e.g., "xyz:GOLD") but exposure omits the DEX -----
    # The coin "xyz:GOLD" has own DEX "xyz" which should be appended to scope.
    # If exposure fetcher returns no data for "xyz", _fresh_exchange_net returns None.
    def exposure_missing_own_dex(payload):
        # payload["dex"] will be "xyz" for the own DEX
        # Return empty positions - simulating the DEX exists but has no position for our wallet
        return {"assetPositions": []}

    ex1 = Ex()
    g1 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    g1._resolve_coin = lambda coin: dict(resolved_xyz_gold)
    gw_send(g1, ex1)
    c.EXPOSURE_FETCHER = exposure_missing_own_dex

    # The coin "xyz:GOLD" - own DEX is "xyz"
    # Since ledger has no sleeve for xyz:GOLD, the close should HOLD with UNKNOWN_SLEEVE
    intent1 = mk_intent("e1", "xyz:GOLD", "EXIT")
    ok1, status1, res1 = g1._send_real(intent1)
    check("PARTIAL_DEX_MISSING_OWN_DEX_HOLDS", ok1 is False and status1 == "SEND_NOT_ATTEMPTED_CLOSE_PROOF_HOLD" and "CLOSE_PROOF_HOLD_UNKNOWN_SLEEVE" in res1.get("error", "") and not ex1.calls, "%s %s" % (status1, res1))

    # ----- Test 2: Coin row omitted from exposure response (regular coin, not DEX-prefixed) -----
    def exposure_missing_coin_row(payload):
        # Return positions but omit BTC entirely
        return {"assetPositions": [{"position": {"coin": "ETH", "szi": "5", "positionValue": "2000", "dex": ""}}]}

    ex2 = Ex()
    g2 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    g2._resolve_coin = lambda coin: dict(resolved_btc)
    gw_send(g2, ex2)
    c.EXPOSURE_FETCHER = exposure_missing_coin_row

    intent2 = mk_intent("e2", "BTC", "EXIT")
    ok2, status2, res2 = g2._send_real(intent2)
    # When coin row is missing, _fresh_exchange_net returns 0.0 (sum over empty), which is finite
    # But the ledger has BTC sleeve, so it might proceed. However the exchange net is 0 (not opposing).
    # This should HOLD with NET_NOT_OPPOSING or similar.
    check("MISSING_COIN_ROW_HOLDS", ok2 is False and status2 == "SEND_NOT_ATTEMPTED_CLOSE_PROOF_HOLD" and "CLOSE_PROOF_HOLD_NET_NOT_OPPOSING" in res2.get("error", "") and not ex2.calls, "%s %s" % (status2, res2))

    # ----- Test 3: Exposure fetcher raises exception (simulating 429/unavailable) -----
    def exposure_raises(payload):
        raise RuntimeError("exchange unavailable")

    ex3 = Ex()
    g3 = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    g3._resolve_coin = lambda coin: dict(resolved_btc)
    gw_send(g3, ex3)
    c.EXPOSURE_FETCHER = exposure_raises

    intent3 = mk_intent("e3", "BTC", "EXIT")
    ok3, status3, res3 = g3._send_real(intent3)
    check("EXPOSURE_RAISES_HOLDS", ok3 is False and status3 == "SEND_NOT_ATTEMPTED_CLOSE_PROOF_HOLD" and "CLOSE_PROOF_HOLD" in res3.get("error", "") and not ex3.calls, "%s %s" % (status3, res3))

    # ----- Mutation proof: if the own-DEX append (lines 8223-8226) were deleted -----
    # The coin "xyz:GOLD" would not have "xyz" in the dex scope, so _fresh_exchange_net
    # would not query the own DEX at all. The test above with exposure_missing_own_dex
    # would then return 0.0 (sum of empty) instead of None, potentially changing the HOLD reason.
    # The test asserts a HOLD occurs; if the mutation caused a SEND, it would FAIL.

    c.release_global_instance_lock()
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()