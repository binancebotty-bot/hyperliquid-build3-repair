"""One-sided book guard and close-fault escalation (H8-H10) tests."""
import os
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

TMP = tempfile.mkdtemp(prefix="one_sided_close_fault_")
os.environ.update({
    "HL_LIVE_AUDIT_DIR": TMP,
    "HL_LIVE_ENV_FILE": os.path.join(TMP, "missing.env"),
    "HL_LIVE_MOCK_SEND": "1",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
})
import HL_Live_Copy_Service_Core as c

WALLET = "0x" + "a" * 40
OTHER = "0x" + "b" * 40  # a different leader wallet copying the same coin


def make_intent(side="SELL", lifecycle="ENTRY", before=0.0, coin="BTC", wallet=WALLET):
    fill = c.LeaderFill("fill-1", wallet, coin, side, 100.0, 1.0, c.utc_now_ms(), "TEST")
    return c.Intent("intent-1", fill, side, 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "",
                    f"sleeve:{wallet}:{coin}", "position-1", "SHORT", before, before, False, False,
                    c.utc_now_ms(), f"lifecycle={lifecycle}")


class Base(unittest.TestCase):
    def sender(self, book=(5, 5)):
        rows = []
        cfg = SimpleNamespace(master_switch_now=lambda: True, send_mode_now=lambda: "ON", liq_parity_enabled=lambda: False)
        s = object.__new__(c.SenderGateway)
        s.cfg, s.ledger = cfg, SimpleNamespace(wallet_coin_position=lambda w, coin: 0.0)
        s.sender_key_invalid = ""
        s._resting_lock = threading.RLock()
        s._standing_closes = {}
        s._pending_exit_guard = {}
        s._pending_exit_lock = threading.Lock()
        s.leader_reduced_since = lambda _f: 0
        s._pre_send_ownership_gate = lambda _i: (True, {})
        s.liq_parity_block = lambda _i: None
        s._base_timing = lambda _i: {}
        s._append_mock_attempt = lambda i, st, t: rows.append(("SENT", st))
        s._append_local_block_reconciliation = lambda i, st, d: rows.append(("BLOCK", st, d))
        s._fresh_exchange_net = lambda _c: None
        s.audit = SimpleNamespace(append_reconciliation=lambda *a, **kw: rows.append(("AUDIT", a, kw)))
        s._fetch_book_sides = lambda _coin: book
        return s, rows

    def send(self, s, intent):
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
            return s.send_if_allowed(intent)


class OneSidedBookTest(Base):
    def test_no_bids_blocks_entry_and_logs_reason(self):
        s, rows = self.sender(book=(0, 5))
        self.assertEqual(self.send(s, make_intent(lifecycle="ENTRY")), (False, "ENTRY_BLOCKED_ONE_SIDED_BOOK"))
        self.assertIn("bids=0", rows[0][2]["notes"])

    def test_no_asks_blocks_add(self):
        s, rows = self.sender(book=(5, 0))
        self.assertEqual(self.send(s, make_intent(lifecycle="ADD", before=-3.0)), (False, "ENTRY_BLOCKED_ONE_SIDED_BOOK"))
        self.assertIn("asks=0", rows[0][2]["notes"])

    def test_two_sided_book_sends(self):
        s, _ = self.sender(book=(3, 4))
        self.assertEqual(self.send(s, make_intent()), (True, "MOCK_ORDER_SENT"))

    def test_close_never_blocked_on_one_sided_book(self):
        s, _ = self.sender(book=(0, 0))
        self.assertEqual(self.send(s, make_intent(side="BUY", lifecycle="EXIT", before=-3.0)), (True, "MOCK_ORDER_SENT"))

    def test_unreadable_book_is_not_treated_as_one_sided(self):
        s, _ = self.sender(book=None)
        self.assertEqual(self.send(s, make_intent()), (True, "MOCK_ORDER_SENT"))

    def test_negative_control_without_guard_one_sided_entry_is_sent(self):
        s, _ = self.sender(book=(0, 5))
        s._one_sided_book_block = lambda _i: ""
        self.assertEqual(self.send(s, make_intent()), (True, "MOCK_ORDER_SENT"))

    def test_guard_can_be_disabled_by_env(self):
        s, _ = self.sender(book=(0, 5))
        with patch.dict(os.environ, {"HL_LIVE_ONE_SIDED_BOOK_GUARD": "0", "HL_LIVE_MOCK_SEND": "1"}):
            self.assertEqual(s.send_if_allowed(make_intent()), (True, "MOCK_ORDER_SENT"))

    def test_book_fetch_counts_levels(self):
        s, _ = self.sender()
        del s.__dict__["_fetch_book_sides"]
        resp = SimpleNamespace(json=lambda: {"levels": [[{"px": "1"}], []]})
        with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "0"}), patch.object(c.requests, "post", return_value=resp):
            self.assertEqual(s._fetch_book_sides("BTC"), (1, 0))


class CloseFaultTest(Base):
    def sender_with_close(self, age_s, coin="BTC"):
        s, rows = self.sender()
        s._standing_closes[f"sleeve:{WALLET}:{coin}"] = {
            "oid": "close-9", "wallet": WALLET, "coin": coin, "side": "BUY", "size": 3.0,
            "placed_ms": c.utc_now_ms() - int(age_s * 1000), "intent_id": "exit-1"}
        return s, rows

    def test_h8_stale_close_escalates_once_and_blocks_add(self):
        s, rows = self.sender_with_close(500)
        self.assertEqual(s.escalate_stale_closes(), 1)
        self.assertEqual(s.escalate_stale_closes(), 0)  # once only
        alerts = [r for r in rows if r[0] == "AUDIT"]
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][2]["terminal_state"], "MANUAL_REVIEW")
        self.assertTrue(alerts[0][2]["notes"].startswith("severity=CRITICAL;"))
        self.assertEqual(self.send(s, make_intent(lifecycle="ADD", before=-3.0, wallet=OTHER)), (False, "ADD_BLOCKED_CLOSE_FAULT"))

    def test_h9_young_close_neither_escalates_nor_blocks_and_other_coin_unaffected(self):
        s, rows = self.sender_with_close(5)
        self.assertEqual(s.escalate_stale_closes(), 0)
        self.assertEqual(self.send(s, make_intent(lifecycle="ADD", before=-3.0, wallet=OTHER)), (True, "MOCK_ORDER_SENT"))
        s2, _ = self.sender_with_close(500, coin="ETH")
        self.assertEqual(self.send(s2, make_intent(coin="BTC", wallet=OTHER)), (True, "MOCK_ORDER_SENT"))

    def test_h9b_reductions_never_blocked_by_close_fault(self):
        s, _ = self.sender_with_close(500)
        self.assertEqual(self.send(s, make_intent(side="BUY", lifecycle="EXIT", before=-3.0, wallet=OTHER)), (True, "MOCK_ORDER_SENT"))

    def test_h10_close_gone_releases_block(self):
        s, _ = self.sender_with_close(500)
        self.assertEqual(self.send(s, make_intent(lifecycle="ADD", before=-3.0, wallet=OTHER))[1], "ADD_BLOCKED_CLOSE_FAULT")
        s._standing_closes.clear()
        self.assertEqual(self.send(s, make_intent(lifecycle="ADD", before=-3.0, wallet=OTHER)), (True, "MOCK_ORDER_SENT"))

    def test_close_fault_alerts_even_when_no_add_arrives(self):
        s, rows = self.sender_with_close(500)
        s.escalate_stale_closes()
        self.assertEqual(len([r for r in rows if r[0] == "AUDIT"]), 1)

    def test_negative_control_without_escalation_add_is_sent(self):
        s, _ = self.sender_with_close(500)
        s._close_fault_block = lambda _i: ""
        self.assertEqual(self.send(s, make_intent(lifecycle="ADD", before=-3.0, wallet=OTHER)), (True, "MOCK_ORDER_SENT"))

    def test_threshold_zero_disables(self):
        s, _ = self.sender_with_close(500)
        with patch.dict(os.environ, {"HL_LIVE_CLOSE_FAULT_SEC": "0", "HL_LIVE_MOCK_SEND": "1"}):
            self.assertEqual(s.send_if_allowed(make_intent(lifecycle="ADD", before=-3.0, wallet=OTHER)), (True, "MOCK_ORDER_SENT"))


if __name__ == "__main__":
    unittest.main()
