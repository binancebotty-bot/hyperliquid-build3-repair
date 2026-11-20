"""Regression test for a failed top-level order-cap lookup at the wire gate."""
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


class MaxOrderNotionalFailClosedTest(unittest.TestCase):
    def test_cap_lookup_exception_refuses_entry_before_exchange(self) -> None:
        with tempfile.TemporaryDirectory(prefix="r1_fail_closed_") as temp_dir:
            temp = Path(temp_dir)
            with patch.dict(os.environ, {
                "HL_LIVE_AUDIT_DIR": str(temp),
                "HL_LIVE_AUTO_SEND_ENABLED": "0",
                "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
            }):
                import HL_Live_Copy_Service_Core as c

                config_path = temp / "live_config.json"
                config_path.write_text(json.dumps({
                    "auto_send_enabled": False,
                    "global_controls": {"max_order_notional_usd": 0.0},
                    "wallets": {
                        "0x" + "d" * 40: {
                            "enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 100.0,
                        },
                    },
                }), encoding="utf-8")
                c.MIDS_FETCHER = lambda payload: [] if payload.get("type") == "perpDexs" else {"BTC": "100"}
                c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
                c._FOLLOWER_MIDS.update(px={}, ms=0)
                c._LEADER_MIDS.update(px={}, ms=0)
                c.RESTING_ENTRY_ORDERS_FILE = temp / "resting_entries.json"

                leader = "0x" + "d" * 40
                fill = c.LeaderFill("r1-fail-closed", leader, "BTC", "BUY", 100.0, 1.0,
                                    c.utc_now_ms(), "TEST", 0, {})
                ledger = c.ManualLedger(path=temp / "ledger.json")
                cfg = c.ConfigManager(config_path)
                intent = c.IntentBuilder(cfg, ledger).build(fill)

                def cap_lookup_fails() -> float:
                    raise RuntimeError("cap unavailable")

                cfg.max_order_notional = cap_lookup_fails

                class FakeExchange:
                    def __init__(self) -> None:
                        self.calls = []

                exchange = FakeExchange()
                gateway = c.SenderGateway(cfg, c.AuditLogWriter(), ledger)
                gateway._resolve_coin = lambda coin: {
                    "ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2,
                    "perp_dexs": [""], "sdk_order_compatible": True, "min_order_value_usd": 1.0,
                    "min_size": 0.0, "status": "OK",
                }
                gateway._get_exchange_client = lambda *args, **kwargs: exchange
                gateway._exchange_client_has_symbol = lambda *args, **kwargs: True
                gateway._validate_final_wire_order = lambda *args, **kwargs: (True, {})
                gateway._pre_exchange_asset_safety = lambda *args, **kwargs: (True, {})

                original_getenv = os.getenv
                with patch.object(c.os, "getenv", side_effect=lambda name, default=None:
                                  "configured" if name == "HL_LIVE_HL_PRIVATE_KEY" else original_getenv(name, default)):
                    saved_sdk = c.HLAccount, c.HLExchange
                    c.HLAccount, c.HLExchange = object, object
                    try:
                        ok, status, result = gateway._send_real(intent)
                    finally:
                        c.HLAccount, c.HLExchange = saved_sdk

                self.assertFalse(ok)
                self.assertEqual(status, "SEND_NOT_ATTEMPTED_MAX_ORDER_NOTIONAL")
                self.assertEqual(result.get("status"), "MAX_ORDER_NOTIONAL_EXCEEDED_AT_WIRE")
                self.assertFalse(result.get("exchange_called"))
                self.assertIn("OPERATOR ALERT", str(result.get("notes", "")))
                self.assertEqual(exchange.calls, [])


if __name__ == "__main__":
    unittest.main()
