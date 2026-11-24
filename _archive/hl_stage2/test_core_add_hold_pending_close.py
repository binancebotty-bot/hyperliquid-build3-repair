"""Regression tests for ADD holds while a full-sleeve close is pending."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

TMP = tempfile.mkdtemp(prefix="add_hold_pending_close_")
os.environ.update({
    "HL_LIVE_AUDIT_DIR": TMP,
    "HL_LIVE_ENV_FILE": os.path.join(TMP, "missing.env"),
    "HL_LIVE_MOCK_SEND": "1",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
    "HL_LIVE_ADD_HOLD_MAX_SEC": "300",
})
import HL_Live_Copy_Service_Core as c


WALLET = "0x" + "a" * 40
OTHER = "0x" + "b" * 40


def make_intent(wallet=WALLET, side="SELL", lifecycle="ADD", before=-10.0):
    fill = c.LeaderFill("fill-1", wallet, "BTC", side, 100.0, 1.0, c.utc_now_ms(), "TEST")
    return c.Intent("intent-1", fill, side, 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "",
                    f"sleeve:{wallet}:BTC", "position-1", "SHORT", before, before, False, False,
                    c.utc_now_ms(), f"lifecycle={lifecycle}")


class AddHoldPendingCloseTest(unittest.TestCase):
    def sender(self, wallet=WALLET, age_ms=1000):
        rows = []
        ledger = SimpleNamespace(wallet_coin_position=lambda w, coin: -10.0 if w == wallet else 0.0)
        cfg = SimpleNamespace(master_switch_now=lambda: True, send_mode_now=lambda: "ON", liq_parity_enabled=lambda: False)
        sender = object.__new__(c.SenderGateway)
        sender.cfg, sender.ledger = cfg, ledger
        sender.sender_key_invalid = ""
        sender._resting_lock = __import__("threading").RLock()
        sender._standing_closes = {f"sleeve:{wallet}:BTC": {
            "oid": "close-oid-9", "wallet": wallet, "coin": "BTC", "side": "BUY", "size": 10.0,
            "placed_ms": c.utc_now_ms() - age_ms, "intent_id": "exit-1",
        }}
        sender._pending_exit_guard = {}
        sender._pending_exit_lock = __import__("threading").Lock()
        sender.leader_reduced_since = lambda _fill: 0
        sender._pre_send_ownership_gate = lambda _intent: (True, {})
        sender.liq_parity_block = lambda _intent: None
        sender._base_timing = lambda _intent: {}
        sender._append_mock_attempt = lambda intent, status, timing: rows.append((intent, status))
        sender._append_local_block_reconciliation = lambda intent, status, details: rows.append((intent, status, details))
        sender._fresh_exchange_net = lambda _coin: None
        sender.audit = SimpleNamespace(append_reconciliation=lambda *a, **kw: rows.append((a, kw)))
        return sender, rows

    def test_h1_same_direction_add_is_held_without_send(self):
        sender, rows = self.sender()
        exchange_calls = []
        sender._send_real = lambda *_args: exchange_calls.append("send")
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "0"}):
            result = sender.send_if_allowed(make_intent())
        self.assertEqual(result, (False, "ADD_HELD_PENDING_CLOSE"))
        self.assertEqual(rows[0][1], "ADD_HELD_PENDING_CLOSE")
        self.assertIn("close-oid-9", rows[0][2]["notes"])
        self.assertEqual(exchange_calls, [])

    def test_close_intent_in_flight_holds_add_before_order_is_registered(self):
        sender, rows = self.sender()
        sender._standing_closes.clear()
        sender._pending_exit_guard[f"sleeve:{WALLET}:BTC"] = {
            "ts_ms": c.utc_now_ms(), "position_abs_before": 10.0, "intent_id": "exit-in-flight", "in_flight": True,
        }
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
            self.assertEqual(sender.send_if_allowed(make_intent()), (False, "ADD_HELD_PENDING_CLOSE"))
        self.assertIn("exit-in-flight", rows[0][2]["notes"])

    def test_negative_control_exit_only_guard_fails_h1(self):
        sender, _ = self.sender()
        sender._pending_close_for_add = lambda _intent: None
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
            result = sender.send_if_allowed(make_intent())
        # This is the observed failure mode: the legacy exit-only guard sends the ADD.
        self.assertEqual(result, (True, "MOCK_ORDER_SENT"))

    def test_h2_reduction_is_not_held(self):
        sender, rows = self.sender()
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
            result = sender.send_if_allowed(make_intent(side="BUY", lifecycle="EXIT"))
        self.assertEqual(result, (True, "MOCK_ORDER_SENT"))

    def test_h3_flat_sleeve_new_entry_is_not_held(self):
        sender, _ = self.sender()
        sender.ledger.wallet_coin_position = lambda _w, _coin: 0.0
        intent = make_intent(side="SELL", lifecycle="ENTRY", before=0.0)
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
            with patch.object(c, "atomic_write_json"):
                self.assertEqual(sender.send_if_allowed(intent), (True, "MOCK_ORDER_SENT"))
        self.assertNotIn(intent.sleeve_id, sender._standing_closes)

    def test_h4_withdrawn_close_releases_add(self):
        sender, _ = self.sender()
        sender._standing_closes.clear()
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
            self.assertEqual(sender.send_if_allowed(make_intent()), (True, "MOCK_ORDER_SENT"))

    def test_completed_exit_intent_guard_does_not_hold_add(self):
        sender, _ = self.sender()
        sender._standing_closes.clear()
        sender._pending_exit_guard[f"sleeve:{WALLET}:BTC"] = {
            "ts_ms": c.utc_now_ms(), "position_abs_before": 10.0, "intent_id": "exit-complete",
            "in_flight": False,
        }
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
            self.assertEqual(sender.send_if_allowed(make_intent()), (True, "MOCK_ORDER_SENT"))

    def test_h5_old_hold_emits_manual_review_once(self):
        sender, rows = self.sender(age_ms=301_000)
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
            sender.send_if_allowed(make_intent())
            sender.send_if_allowed(make_intent())
        alerts = [r for r in rows if isinstance(r[0], tuple) and r[0][0] == "ADD_HOLD_PENDING_CLOSE"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][1]["terminal_state"], "MANUAL_REVIEW")
        self.assertTrue(alerts[0][1]["notes"].startswith("severity=CRITICAL;"))

    def test_h7_another_wallet_is_not_held(self):
        sender, _ = self.sender()
        sender.ledger.wallet_coin_position = lambda _w, _coin: -2.0
        intent = make_intent(wallet=OTHER)
        intent.sleeve_id = f"sleeve:{OTHER}:BTC"
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
            self.assertEqual(sender.send_if_allowed(intent), (True, "MOCK_ORDER_SENT"))

    def test_hype_ratchet_soak_keeps_pending_close_sleeve_constant(self):
        sender, rows = self.sender()
        net = -30.15
        sender.ledger.wallet_coin_position = lambda _w, _coin: net
        sender._standing_closes[f"sleeve:{WALLET}:BTC"]["size"] = 30.15
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
            outcomes = [sender.send_if_allowed(make_intent()) for _ in range(108)]
        self.assertTrue(all(result == (False, "ADD_HELD_PENDING_CLOSE") for result in outcomes))
        self.assertFalse(any(len(row) == 2 and row[1] == "MOCK_ORDER_SENT" for row in rows))
        self.assertEqual(net, -30.15)

if __name__ == "__main__":
    unittest.main()
