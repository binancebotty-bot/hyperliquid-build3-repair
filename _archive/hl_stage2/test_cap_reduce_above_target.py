"""A planner-approved reduce remains sendable when the entry cap cannot be read."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
os.environ.update({
    "HL_LIVE_AUDIT_DIR": tempfile.mkdtemp(prefix="cap_reduce_above_target_"),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
})

import sys

sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as c
import convergence_shadow as planner


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
        return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": 1}}]}}}


class CapReduceAboveTargetTest(unittest.TestCase):
    def test_planner_approved_reduce_reaches_exchange_once_when_cap_read_fails(self):
        cfg_data = {
            "auto_send_enabled": True,
            "global_controls": {"max_order_notional_usd": 100.0},
            "wallets": {
                LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000.0},
            },
        }
        c.atomic_write_json(c.LIVE_CONFIG_FILE, cfg_data)
        cfg = c.ConfigManager()
        ledger = c.ManualLedger(path=Path(os.environ["HL_LIVE_AUDIT_DIR"]) / "ledger.json")
        gateway = c.SenderGateway(cfg, c.AuditLogWriter(), ledger)
        fake = FakeExchange()
        gateway._resolve_coin = lambda _coin: dict(RESOLVED_BTC)
        gateway._get_exchange_client = lambda *args, **kwargs: fake
        gateway._exchange_client_has_symbol = lambda *args, **kwargs: True
        gateway._pre_exchange_asset_safety = lambda *args, **kwargs: (True, {})
        gateway._pre_send_ownership_gate = lambda _intent: (True, {})
        gateway._fresh_exchange_net = lambda _coin: 2.0
        ledger.data["by_coin_net"]["BTC"] = {"signed_size": 1.0}

        planned = planner.compute_convergence_order("BTC", desired_net=1.0, actual_net=2.0, mark_px=100.0)
        self.assertEqual((planned.action, planned.side, planned.size, planned.reduce_only), ("REDUCE", "SELL", 1.0, True))

        fill = c.LeaderFill("cap-readerr-reduce", LEADER, "BTC", "SELL", 100.0, 1.0, c.utc_now_ms(), "TEST")
        intent = c.IntentBuilder(cfg, ledger).build(fill)
        intent.reason = planned.action
        intent.notes = f"lifecycle={planned.action}"
        intent.wallet_position_before = 2.0
        intent.copy_side = planned.side
        intent.copy_size = planned.size
        intent.copy_notional = planned.size * fill.price
        intent.reduce_only_intended = planned.reduce_only
        intent.reduce_only_sent_planned = planned.reduce_only
        cfg.max_order_notional = lambda: (_ for _ in ()).throw(RuntimeError("cap unavailable"))

        with patch.dict(os.environ, {"HL_LIVE_HL_PRIVATE_KEY": "unused-test-placeholder"}):
            ok, status, result = gateway._send_real(intent)

        self.assertTrue(ok, (status, result))
        self.assertTrue(result.get("exchange_called"))
        self.assertEqual(len(fake.calls), 1)


if __name__ == "__main__":
    unittest.main()
