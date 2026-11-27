"""Cancel guards must honor the switch and engine position ownership."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

with patch.dict(os.environ, {"HL_LIVE_ENV_FILE": os.devnull, "HL_LEADER_NETWORK": "testnet",
                             "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"}):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import HL_Live_Copy_Service_Core as c


class CountingExchange:
    def __init__(self):
        self.cancels = []

    def cancel(self, coin, oid):
        self.cancels.append((coin, oid))
        return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}


class CancelOwnershipTest(unittest.TestCase):
    def gateway(self, send_mode, engine_position, exchange_position):
        gateway = object.__new__(c.SenderGateway)
        gateway.cfg = SimpleNamespace(send_mode_now=lambda: send_mode)
        gateway.ledger = SimpleNamespace(coin_net=lambda _coin: engine_position)
        gateway._reserve_exchange_order_slot = lambda: c.utc_now_ms()
        gateway._fresh_exchange_net = lambda _coin: exchange_position
        return gateway

    def test_switch_off_never_sends_cancel(self):
        exchange = CountingExchange()
        gateway = self.gateway("OFF", 1.0, 1.0)

        with self.assertRaises(c._OrderSwitchBlocked):
            gateway._cancel_order(exchange, "BTC", "17")

        self.assertEqual(exchange.cancels, [])

    def test_unowned_exchange_position_never_sends_cancel(self):
        exchange = CountingExchange()
        gateway = self.gateway("ON", 0.0, 1.0)

        with self.assertRaisesRegex(RuntimeError, "CANCEL_POSITION_OWNERSHIP_UNVERIFIED"):
            gateway._cancel_order(exchange, "BTC", "17")

        self.assertEqual(exchange.cancels, [])


if __name__ == "__main__":
    unittest.main()
