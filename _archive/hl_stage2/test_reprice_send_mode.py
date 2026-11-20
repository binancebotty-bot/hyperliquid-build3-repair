"""Send-mode changes during repricing must stop the next exchange call."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
NO_MATCH = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
    {"error": "Order could not immediately match against any resting orders. asset=0"}]}}}


class FakeExchange:
    def __init__(self, config_path: Path, off_after_call: int):
        self.calls = []
        self.config_path = config_path
        self.off_after_call = off_after_call

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append({"px": px, "tif": tif["limit"]["tif"], "buy": is_buy,
                           "size": size, "reduce_only": reduce_only})
        if len(self.calls) == self.off_after_call:
            self.config_path.write_text(json.dumps({"auto_send_enabled": False,
                "global_controls": {"send_mode": "OFF"}, "wallets": {
                    LEADER: {"enabled": True, "mode": "ON"}}}), encoding="utf-8")
        return NO_MATCH


class RepriceSendModeTests(unittest.TestCase):
    def setUp(self):
        import HL_Live_Copy_Service_Core as c
        self.c = c
        self.tmp = tempfile.TemporaryDirectory(prefix="reprice_send_mode_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        os.environ.update({"HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_AUDIT_DIR": str(self.root),
            "HL_LIVE_ENV_FILE": str(self.root / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
            "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_ENTRY_IOC_RETRY_BPS": "100",
            "HL_LIVE_MAX_ENTRY_IOC_RETRY_BPS": "100"})
        self.config_path = self.root / "live_config.json"
        self._write_config("ON")
        c.LIVE_CONFIG_FILE = self.config_path
        c.FOLLOWER_NETWORK = "testnet"
        c.LEADER_NETWORK = "testnet"
        c.USER_WALLET = FOLLOWER
        c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "99.9"}
        c.LEADER_MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)
        self.c.requests.post = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline test"))

    def _write_config(self, mode):
        self.config_path.write_text(json.dumps({"auto_send_enabled": False,
            "global_controls": {"send_mode": mode, "marketable_bps": 20}, "wallets": {
                LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000}}}),
            encoding="utf-8")

    def _run_reprice(self, switch_off_after_call):
        c = self.c
        resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3,
            "price_max_decimals": 2, "perp_dexs": [""], "sdk_order_compatible": True,
            "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
        fake = FakeExchange(self.config_path, switch_off_after_call)
        gw = c.SenderGateway(c.ConfigManager(config_path=self.config_path), c.AuditLogWriter())
        gw._resolve_coin = lambda coin: dict(resolved)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        ledger = c.ManualLedger(path=self.root / f"ledger-{switch_off_after_call}.json")
        fill = c.LeaderFill("test-fill", LEADER, "BTC", "BUY", 100.0, 1.0,
                            c.utc_now_ms(), "TEST", 0, {})
        intent = c.IntentBuilder(gw.cfg, ledger).build(fill)
        old_account, old_exchange = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        real_getenv = os.getenv
        def test_getenv(name, default=None):
            if name == "HL_LIVE_HL_PRIVATE_KEY":
                return "test-stub-not-a-key"
            return real_getenv(name, default)
        try:
            with patch.object(os, "getenv", side_effect=test_getenv):
                result = gw._send_real(intent)
        finally:
            c.HLAccount, c.HLExchange = old_account, old_exchange
        return result, fake.calls

    def test_send_off_before_ioc_retry_makes_no_retry_exchange_call(self):
        (_ok, status, _result), calls = self._run_reprice(switch_off_after_call=1)
        self.assertEqual(status, "MASTER_REAL_ORDERS_OFF")
        self.assertEqual([call["tif"] for call in calls], ["Ioc"])

    def test_send_off_before_gtc_reprice_makes_no_gtc_exchange_call(self):
        (_ok, status, _result), calls = self._run_reprice(switch_off_after_call=2)
        self.assertEqual(status, "MASTER_REAL_ORDERS_OFF")
        self.assertEqual([call["tif"] for call in calls], ["Ioc", "Ioc"])


if __name__ == "__main__":
    unittest.main()
