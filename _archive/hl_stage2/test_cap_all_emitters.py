"""Every live order path must apply the final entry cap before the exchange call."""

# Exchange order emitters traced in the send path:
# - _archive/hl_stage2/HL_Live_Copy_Service_Core.py:4295, SenderGateway._place_order:
#   YES on the _send_real path; _validate_final_wire_order is called at line 6327 first.
# - _archive/hl_stage2/HL_Live_Copy_Service.py:936, send_hyperliquid_order:
#   not an emitter; this legacy direct sender is disabled and makes no exchange call.

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
os.environ.update({
    "HL_LIVE_AUDIT_DIR": tempfile.mkdtemp(prefix="cap_all_emitters_"),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
})

import sys

sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as c


LEADER = "0x" + "d" * 40
RESOLVED_BTC = {
    "ok": True,
    "sdk_coin": "BTC",
    "sz_decimals": 3,
    "price_max_decimals": 2,
    "perp_dexs": [""],
    "sdk_order_compatible": True,
    "min_order_value_usd": 1.0,
    "min_size": 0.0,
    "status": "OK",
}


class FakeExchange:
    def __init__(self):
        self.calls = []

    def order(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"status": "ok", "response": {"data": {"statuses": [{" resting": {"oid": 1}}]}}}


class CapAllEmittersTest(unittest.TestCase):
    def test_oversized_entry_is_blocked_before_exchange_order(self):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            "auto_send_enabled": True,
            "global_controls": {"max_order_notional_usd": 100.0},
            "wallets": {
                LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000.0},
            },
        })
        cfg = c.ConfigManager()
        ledger = c.ManualLedger(path=Path(os.environ["HL_LIVE_AUDIT_DIR"]) / "ledger.json")
        gateway = c.SenderGateway(cfg, c.AuditLogWriter(), ledger)
        fake = FakeExchange()
        gateway._resolve_coin = lambda _coin: dict(RESOLVED_BTC)
        gateway._get_exchange_client = lambda *args, **kwargs: fake
        gateway._exchange_client_has_symbol = lambda *args, **kwargs: True
        gateway._pre_exchange_asset_safety = lambda *args, **kwargs: (True, {})
        gateway._pre_send_ownership_gate = lambda _intent: (True, {})

        fill = c.LeaderFill("cap-entry", LEADER, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST")
        intent = c.IntentBuilder(cfg, ledger).build(fill)
        self.assertEqual(intent.copy_notional, 1000.0)

        # The value is only a non-key placeholder: client construction is replaced above.
        with patch.dict(os.environ, {"HL_LIVE_HL_PRIVATE_KEY": "unused-test-placeholder"}):
            ok, status, result = gateway._send_real(intent)

        self.assertFalse(ok)
        self.assertEqual(status, "SEND_NOT_ATTEMPTED_MAX_ORDER_NOTIONAL")
        self.assertFalse(result.get("exchange_called", True))
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
