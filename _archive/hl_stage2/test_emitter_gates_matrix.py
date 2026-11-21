"""Regression coverage for final emitter gates."""

import unittest
from types import SimpleNamespace

import HL_Live_Copy_Service_Core as c


class EmitterGatesMatrixTest(unittest.TestCase):
    def test_over_cap_entry_has_zero_exchange_calls(self):
        gateway = object.__new__(c.SenderGateway)
        gateway.cfg = SimpleNamespace(max_order_notional=lambda: 50.0)
        gateway._effective_symbol_min_notional = lambda _resolved: 1.0

        intent = SimpleNamespace(
            fill=SimpleNamespace(coin="BTC", price=100.0),
            notes="lifecycle=ENTRY",
            reason="ENTRY",
            wallet_position_before=0.0,
            copy_side="BUY",
            copy_size=1.0,
            intent_id="over-cap-entry",
            reduce_only_intended=False,
        )

        class FakeExchange:
            def __init__(self):
                self.calls = []

            def order(self, *args, **kwargs):
                self.calls.append((args, kwargs))

        exchange = FakeExchange()
        allowed, block = gateway._validate_final_wire_order(
            intent, {"raw_coin": "BTC"}, "BTC", 1.0, 100.0, {}
        )
        if allowed:
            exchange.order("BTC", True, 1.0, 100.0, {"limit": {"tif": "Ioc"}})

        self.assertFalse(allowed)
        self.assertEqual(block["status"], "MAX_ORDER_NOTIONAL_EXCEEDED_AT_WIRE")
        self.assertEqual(exchange.calls, [])


if __name__ == "__main__":
    unittest.main()
