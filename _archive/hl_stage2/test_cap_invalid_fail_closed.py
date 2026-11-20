"""Malformed max-order caps fail closed before any exchange call."""
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


class FakeExchange:
    def __init__(self):
        self.calls = []

    def order(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": 1}}]}}}


class InvalidCapFailClosedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="invalid_cap_")
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
        self.saved_sdk = c.HLAccount, c.HLExchange
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
        self.c.HLAccount, self.c.HLExchange = self.saved_sdk
        os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        self.tmp.cleanup()

    def _send(self, max_order_notional):
        c = self.c
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            "auto_send_enabled": False,
            "global_controls": {"marketable_bps": 0, "max_order_notional_usd": max_order_notional},
            "wallets": {LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000}},
        })
        c.LEADER_NETWORK = c.FOLLOWER_NETWORK
        c.USER_WALLET = FOLLOWER
        c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
        c.LEADER_MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
        fill = c.LeaderFill("invalid-cap", LEADER, "BTC", "BUY", 100.0, 1.0,
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
        c.HLAccount, c.HLExchange = object, object
        try:
            result = gateway._send_real(intent)
        finally:
            c.HLAccount, c.HLExchange = self.saved_sdk
        return result, fake

    def test_invalid_cap_refuses_entry_without_exchange_call(self):
        for cap in ("not-a-number", float("nan"), float("inf"), -1.0):
            with self.subTest(cap=cap):
                result, fake = self._send(cap)

                self.assertFalse(result[0])
                self.assertEqual(result[2]["status"], "MAX_ORDER_NOTIONAL_EXCEEDED_AT_WIRE")
                self.assertIn("OPERATOR ALERT", result[2]["error"])
                self.assertEqual(fake.calls, [])

    def test_explicit_zero_cap_keeps_off_semantics(self):
        result, fake = self._send(0.0)

        self.assertTrue(result[0])
        self.assertGreater(len(fake.calls), 0)


if __name__ == "__main__":
    unittest.main()
