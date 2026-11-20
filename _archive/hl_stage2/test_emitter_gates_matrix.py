"""Exchange-call regression matrix for the Core sender's last-mile gates.

All exchange objects in this module are in-memory fakes. The test suite does
not create an SDK client or read credentials.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Keep Core's audit/config state isolated from the operator's local state.
_TEST_STATE = tempfile.TemporaryDirectory(prefix="emitter_gates_")
os.environ.update({
    "HL_LIVE_AUDIT_DIR": _TEST_STATE.name,
    "HL_LIVE_ENV_FILE": str(Path(_TEST_STATE.name) / "no-env-file"),
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
    "HL_LIVE_MOCK_SEND": "0",
})

import HL_Live_Copy_Service_Core as c


WALLET = "0x" + "a" * 40


class FakeExchange:
    def __init__(self, responses=()):
        self.calls = []
        self.responses = list(responses)

    def order(self, coin, is_buy, size, price, tif, reduce_only=False, **kwargs):
        self.calls.append((coin, is_buy, size, price, tif, reduce_only))
        if self.responses:
            return self.responses.pop(0)
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
            {"filled": {"totalSz": str(size), "avgPx": str(price), "oid": 1}}
        ]}}}


def make_intent(lifecycle="ENTRY", side="BUY", size=1.0, before=0.0,
                *, decision=None, reduce_only=False, notional=None):
    decision = decision or ("EXIT_ALLOWED" if lifecycle in {"EXIT", "REDUCE"} else "ENTRY_ALLOWED")
    fill = c.LeaderFill("fill-1", WALLET, "BTC", side, 100.0, size, c.utc_now_ms(), "TEST")
    return c.Intent(
        "intent-1", fill, side, size, notional if notional is not None else size * 100.0,
        "ON", "fixed", decision, lifecycle, f"sleeve:{WALLET}:BTC", "",
        "LONG" if before > 0 else "FLAT", before, before, reduce_only, reduce_only,
        c.utc_now_ms(), f"lifecycle={lifecycle}",
    )


class EmitterGateMatrixTests(unittest.TestCase):
    """No-call assertions are mutation controls: bypassing a gate reaches FakeExchange."""

    def gateway(self, send_mode="ON", *, max_order=0.0):
        cfg = c.ConfigManager()
        cfg.config = {
            "global_controls": {
                "send_mode": send_mode,
                "max_order_notional_usd": max_order,
                "min_notional": 1,
                "marketable_bps": 0,
            },
            "wallets": {WALLET: {"enabled": True, "mode": "ON"}},
        }
        gw = c.SenderGateway(cfg, c.AuditLogWriter(), c.ManualLedger(path=Path(_TEST_STATE.name) / "ledger.json"))
        gw.leader_reduced_since = lambda fill: 0
        gw._pre_send_ownership_gate = lambda intent: (True, {})
        gw._append_local_block_reconciliation = lambda *args, **kwargs: None
        return gw

    def test_send_off_blocks_first_send_and_retry_entry_points(self):
        """Each OFF entry point must be blocked before the fake exchange is called."""
        for stage, intent in (
            ("first_send", make_intent()),
            ("ioc_retry", make_intent()),
            ("gtc_reprice", make_intent()),
        ):
            with self.subTest(stage=stage):
                gw = self.gateway("OFF")
                fake = FakeExchange()
                gw._send_real = lambda *args, _fake=fake, **kwargs: (
                    _fake.order("BTC", True, 1, 100, {"limit": {"tif": "Ioc"}}),
                    "ORDER_SENT", {"exchange_called": True},
                )
                ok, status = gw.send_if_allowed(intent)
                self.assertFalse(ok, stage)
                self.assertEqual(status, "MASTER_REAL_ORDERS_OFF", stage)
                self.assertEqual(fake.calls, [], stage)

    def test_close_only_refuses_entry_but_allows_reduce_only_close(self):
        gw = self.gateway("CLOSE ONLY")
        fake = FakeExchange()
        gw._send_real = lambda *args, **kwargs: (
            fake.order("BTC", False, 0.25, 100, {"limit": {"tif": "Ioc"}}, reduce_only=True),
            "ORDER_SENT", {"exchange_called": True},
        )

        entry = gw.send_if_allowed(make_intent("ENTRY"))
        self.assertEqual(entry, (False, "ENTRY_BLOCKED_GLOBAL_CLOSE_ONLY"))
        self.assertEqual(fake.calls, [])

        close = gw.send_if_allowed(make_intent("REDUCE", "SELL", 0.25, 1.0, reduce_only=True))
        self.assertTrue(close[0])
        self.assertEqual(len(fake.calls), 1)
        self.assertTrue(fake.calls[0][-1])

    def test_entry_over_configured_cap_has_zero_exchange_calls(self):
        gw = self.gateway("ON", max_order=50.0)
        fake = FakeExchange()
        gw._place_order = lambda exchange, coin, is_buy, size, price, tif, reduce_only, *args, **kwargs: fake.order(
            coin, is_buy, size, price, {"limit": {"tif": tif}}, reduce_only=reduce_only
        )
        intent = make_intent("ENTRY", notional=100.0)

        # Exercise Core's cap check at the last wire boundary without an SDK or key.
        gw._resolve_coin = lambda coin: {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3,
                                         "price_max_decimals": 2, "min_order_value_usd": 1.0}
        gw._floor_wire_size = lambda size, places: size
        gw._format_limit_px = lambda price, places: price
        gw._get_exchange_client = lambda *args, **kwargs: fake
        gw._exchange_client_has_symbol = lambda *args, **kwargs: True
        gw._validate_final_wire_order = lambda *args, **kwargs: (True, {})
        gw._pre_exchange_asset_safety = lambda *args, **kwargs: (True, {})
        gw._symbol_reject_circuit_active = lambda resolved: False
        original_getenv = os.getenv
        with patch.object(c.os, "getenv", side_effect=lambda name, default=None:
                          "test-only-placeholder" if name == "HL_LIVE_HL_PRIVATE_KEY" else original_getenv(name, default)), \
             patch.object(c, "HLAccount", object), patch.object(c, "HLExchange", object):
            with patch.object(c, "follower_mid", return_value=100.0), \
                 patch.object(c, "leader_mid", return_value=100.0), \
                 patch.dict(os.environ, {"HL_LIVE_MISSED_ENTRY_RULE": "0"}):
                result = gw.send_if_allowed(intent)

        self.assertFalse(result[0])
        self.assertIn("MAX_ORDER_NOTIONAL", result[1])
        self.assertEqual(fake.calls, [])

    def test_unowned_position_close_has_zero_exchange_calls(self):
        gw = self.gateway("ON")
        fake = FakeExchange()
        intent = make_intent("EXIT", "SELL", 1.0, 1.0, reduce_only=True)
        gw._audit_proof_block_reason = lambda: ""
        gw._persisted_exchange_positions = lambda: ({"BTC": 2.0}, "")
        gw._pre_send_ownership_gate = lambda candidate: c.SenderGateway._pre_send_ownership_gate(gw, candidate)
        gw._send_real = lambda *args, **kwargs: (
            fake.order("BTC", False, 1, 100, {"limit": {"tif": "Ioc"}}, reduce_only=True),
            "ORDER_SENT", {"exchange_called": True},
        )

        ok, status = gw.send_if_allowed(intent)
        self.assertFalse(ok)
        self.assertIn("OWNERSHIP_GATE", status)
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
