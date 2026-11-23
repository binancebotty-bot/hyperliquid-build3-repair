"""Exercise the final-wire cap on an ENTRY/ADD IOC reprice."""

import unittest
from os import devnull
from types import SimpleNamespace
from unittest.mock import patch

with patch.dict("os.environ", {"HL_LIVE_ENV_FILE": devnull}):
    import HL_Live_Copy_Service_Core as c


class IocRepriceCapTest(unittest.TestCase):
    def test_over_cap_reprice_never_calls_exchange_order_again(self):
        no_match = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
            {"error": "Order could not immediately match against any resting orders. asset=0"}
        ]}}}

        class FakeExchange:
            def __init__(self):
                self.calls = []
                self.info = SimpleNamespace(name_to_coin={"BTC": "BTC"})

            def order(self, coin, is_buy, size, px, order_type, reduce_only=False):
                self.calls.append((coin, is_buy, size, px, order_type["limit"]["tif"], reduce_only))
                return no_match

        for lifecycle in ("ENTRY", "ADD"):
            with self.subTest(lifecycle=lifecycle):
                exchange = FakeExchange()
                gateway = object.__new__(c.SenderGateway)
                gateway.cfg = SimpleNamespace(
                    max_order_notional=lambda: 100.5,
                    marketable_bps=lambda: 0.0,
                    min_notional=lambda: 10.0,
                )
                gateway.sender_key_invalid = ""
                gateway._resolve_coin = lambda coin: {
                    "ok": True, "raw_coin": coin, "sdk_coin": coin,
                    "sz_decimals": 3, "price_max_decimals": 2,
                }
                gateway._get_exchange_client = lambda *_args: exchange
                gateway._ensure_margin_mode = lambda *_args: None
                gateway._begin_pending_send = lambda *_args: None
                gateway._reserve_exchange_order_slot = lambda: 0
                intent = SimpleNamespace(
                    fill=SimpleNamespace(coin="BTC", price=100.0),
                    notes=f"lifecycle={lifecycle}",
                    copy_side="BUY",
                    copy_size=1.0,
                    copy_notional=100.0,
                    intent_id=f"reprice-cap-{lifecycle.lower()}",
                    reduce_only_intended=False,
                )
                with (
                    patch.dict("os.environ", {
                        "HL_LIVE_HL_PRIVATE_KEY": "fake-exchange-only",
                        "HL_LIVE_MISSED_ENTRY_RULE": "0",
                        "HL_LIVE_ENTRY_IOC_RETRY_BPS": "100",
                        "HL_LIVE_MAX_ENTRY_IOC_RETRY_BPS": "100",
                    }),
                    patch.object(c, "DEFAULT_MIN_NOTIONAL", 10.0),
                    patch.object(c, "FOLLOWER_NETWORK", "testnet"),
                    patch.object(c, "HLAccount", object()),
                    patch.object(c, "HLExchange", object()),
                    patch.object(c, "follower_mid", return_value=100.0),
                ):
                    ok, status, result = gateway._send_real(intent, {})

                self.assertEqual(exchange.calls, [("BTC", True, 1.0, 100.0, "Ioc", False)])
                self.assertFalse(ok)
                self.assertEqual(status, "MAX_ORDER_NOTIONAL_EXCEEDED_AT_WIRE")
                self.assertTrue(result["exchange_called"])
                self.assertEqual(result["exchange_response"], no_match)
