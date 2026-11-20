"""Non-finite send inputs are rejected before the physical exchange call."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import HL_Live_Copy_Service_Core as C


class FakeExchange:
    def __init__(self):
        self.calls = []

    def order(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"status": "ok"}


class NonfiniteSendPathTests(unittest.TestCase):
    def setUp(self):
        self.old_network = C.FOLLOWER_NETWORK
        C.FOLLOWER_NETWORK = "testnet"

    def tearDown(self):
        C.FOLLOWER_NETWORK = self.old_network

    def test_nonfinite_prices_and_sizes_never_reach_exchange(self):
        bad_values = (float("nan"), float("inf"), None)
        for field in ("size", "price"):
            for bad in bad_values:
                with self.subTest(field=field, value=bad):
                    exchange = FakeExchange()
                    gateway = object.__new__(C.SenderGateway)
                    gateway._reserve_exchange_order_slot = lambda: C.utc_now_ms()
                    size = bad if field == "size" else 1.0
                    price = bad if field == "price" else 100.0
                    with self.assertRaises((ValueError, TypeError)):
                        gateway._place_order(exchange, "BTC", True, size, price, "Ioc", False)
                    self.assertEqual(exchange.calls, [])

    def test_nonfinite_cached_balances_are_unavailable_for_sizing(self):
        for balance in (float("nan"), float("inf"), None):
            with self.subTest(balance=balance):
                builder = object.__new__(C.IntentBuilder)
                builder._leader_equity = {"leader": (balance, C.utc_now_ms())}
                self.assertIsNone(builder.leader_equity("leader"))


if __name__ == "__main__":
    unittest.main()
