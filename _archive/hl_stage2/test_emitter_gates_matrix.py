"""Regression coverage for final emitter gates."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import HL_Live_Copy_Service_Core as c


class EmitterGatesMatrixTest(unittest.TestCase):
    def test_cap_read_failures_block_entries_adds_and_allow_exit_only_via_fake_exchange(self):
        class FakeExchange:
            def __init__(self):
                self.calls = []
                self.info = SimpleNamespace(name_to_coin={"BTC": 0})

            def order(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                return {"status": "err", "response": "fake exchange rejection"}

        def run_send(lifecycle, cap_reader):
            gateway = object.__new__(c.SenderGateway)
            gateway.cfg = SimpleNamespace(
                max_order_notional=cap_reader,
                marketable_bps=lambda: 0.0,
                max_close_adverse_diff_pct=lambda: 0.0,
                min_notional=lambda: 1.0,
                send_mode_now=lambda: "ON",
                master_switch_now=lambda: True,
            )
            exchange = FakeExchange()
            resolved = {
                "ok": True,
                "raw_coin": "BTC",
                "sdk_coin": "BTC",
                "sz_decimals": 3,
                "price_max_decimals": 2,
                "perp_dexs": None,
                "min_order_value_usd": 1.0,
                "min_size": 0.0,
            }
            gateway._resolve_coin = lambda _coin: resolved
            gateway._get_exchange_client = lambda *_args: exchange
            gateway._effective_symbol_min_notional = lambda _resolved: 1.0
            gateway._pre_exchange_asset_safety = lambda *_args: (True, {})
            gateway._ensure_margin_mode = lambda *_args: None
            gateway._begin_pending_send = lambda *_args: None
            gateway._reserve_exchange_order_slot = lambda: 0
            gateway._note_sender_key_rejection = lambda _response: None
            gateway._withdraw_standing_close = lambda _exchange, _intent, size, *_args: (size, None)
            gateway._close_wire_plan = lambda _intent, size, *_args: (True, size, "")
            gateway._closes_whole_account_position = lambda *_args: False
            intent = SimpleNamespace(
                fill=SimpleNamespace(coin="BTC", price=100.0, leader_wallet="test", leader_fill_id="fill"),
                notes=f"lifecycle={lifecycle}",
                reason=lifecycle,
                wallet_position_before=1.0 if lifecycle == "EXIT" else 0.0,
                copy_side="SELL" if lifecycle == "EXIT" else "BUY",
                copy_size=1.0,
                copy_notional=100.0,
                intent_id=f"cap-{lifecycle.lower()}",
                reduce_only_intended=lifecycle == "EXIT",
            )
            with (
                patch.dict("os.environ", {
                    "HL_LIVE_HL_PRIVATE_KEY": "test-only-placeholder",
                    "HL_LIVE_MISSED_ENTRY_RULE": "0",
                }),
                patch.object(c, "HLAccount", object()),
                patch.object(c, "HLExchange", object()),
                patch.object(c, "follower_mid", return_value=100.0),
            ):
                result = gateway._send_real(intent, {})
            return exchange, result

        def read_error():
            raise RuntimeError("cap unavailable")

        scenarios = [
            (lifecycle, read_error)
            for lifecycle in ("ENTRY", "ADD")
        ]
        scenarios.extend(
            (lifecycle, lambda value=value: value)
            for lifecycle in ("ENTRY", "ADD")
            for value in ("not-a-cap", float("nan"), float("inf"))
        )
        for lifecycle, cap_reader in scenarios:
            with self.subTest(lifecycle=lifecycle, cap_reader=cap_reader):
                exchange, result = run_send(lifecycle, cap_reader)
                self.assertEqual(exchange.calls, [])
                self.assertFalse(result[2]["exchange_called"])

        exchange, result = run_send("EXIT", read_error)
        self.assertEqual(len(exchange.calls), 1)
        self.assertTrue(result[2]["exchange_called"])

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
