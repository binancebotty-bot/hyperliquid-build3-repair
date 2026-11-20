"""Regression tests for entry reprices crossing the final-wire notional cap.

All exchange calls use an in-memory fake. No network or order placement is used.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE))

FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
NO_MATCH = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
    {"error": "Order could not immediately match against any resting orders. asset=0"}]}}}


class FakeExchange:
    def __init__(self):
        self.calls = []

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append({"px": px, "tif": tif["limit"]["tif"], "size": size})
        return NO_MATCH


class RepriceCapBypassTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="reprice_cap_")
        self.root = Path(self.tmp.name)
        os.environ.update({
            "HL_LIVE_AUDIT_DIR": str(self.root),
            "HL_LIVE_ENV_FILE": str(self.root / "none.env"),
            "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
            "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
            "HL_LIVE_LIQ_PARITY": "0",
        })
        import HL_Live_Copy_Service_Core as c
        self.c = c
        c.requests.post = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network disabled in regression test"))
        self.saved_network = c.LEADER_NETWORK
        c.LEADER_NETWORK = c.FOLLOWER_NETWORK
        c.USER_WALLET = FOLLOWER
        c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
        c.LEADER_MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)

    def tearDown(self):
        self.c.LEADER_NETWORK = self.saved_network
        os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        self.tmp.cleanup()

    def _send(self, *, missed_entry_rule, leader_price, max_order_notional):
        c = self.c
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            "auto_send_enabled": False,
            "global_controls": {"marketable_bps": 0, "max_order_notional_usd": max_order_notional},
            "wallets": {LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000}},
        })
        os.environ["HL_LIVE_MISSED_ENTRY_RULE"] = "1" if missed_entry_rule else "0"
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64  # test placeholder; fake exchange never signs
        fill = c.LeaderFill("reprice", LEADER, "BTC", "BUY", leader_price, 1.0,
                            c.utc_now_ms(), "TEST")
        ledger = c.ManualLedger(path=self.root / "ledger.json")
        intent = c.IntentBuilder(c.ConfigManager(), ledger).build(fill)
        fake = FakeExchange()
        gateway = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
        resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2,
                    "perp_dexs": [""], "sdk_order_compatible": True, "min_order_value_usd": 1.0,
                    "min_size": 0.0, "status": "OK"}
        gateway._resolve_coin = lambda coin: dict(resolved)
        gateway._get_exchange_client = lambda *a, **k: fake
        gateway._exchange_client_has_symbol = lambda *a, **k: True
        gateway._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        saved_sdk = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        try:
            result = gateway._send_real(intent)
        finally:
            c.HLAccount, c.HLExchange = saved_sdk
        return result, fake

    def test_ioc_retry_rechecks_cap_before_reprice_exchange_call(self):
        result, fake = self._send(missed_entry_rule=False, leader_price=100.0, max_order_notional=1005.0)

        self.assertFalse(result[0])
        self.assertEqual(result[1], "MAX_ORDER_NOTIONAL_EXCEEDED_AT_WIRE")
        self.assertEqual(len(fake.calls), 1, "only the initial rejected IOC may reach the fake exchange")
        self.assertTrue(result[2].get("exchange_called"))

    def test_missed_entry_gtc_rechecks_cap_before_reprice_exchange_call(self):
        result, fake = self._send(missed_entry_rule=True, leader_price=100.8, max_order_notional=995.0)

        self.assertFalse(result[0])
        self.assertEqual(result[1], "MAX_ORDER_NOTIONAL_EXCEEDED_AT_WIRE")
        self.assertEqual(len(fake.calls), 1, "the over-cap missed-entry GTC must not reach the fake exchange")
        self.assertTrue(result[2].get("exchange_called"))


if __name__ == "__main__":
    unittest.main()
