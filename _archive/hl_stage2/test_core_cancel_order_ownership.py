#!/usr/bin/env python3
"""Spec C: order-ID ownership, not position-net equality, controls ALL cancels.

Offline regression: real SenderGateway._cancel_order, _place_order,
send_if_allowed, _withdraw_rows and _cancel_orphan_order; only exchange wire
calls are faked. Run from _archive/hl_stage2 with HL_LIVE_ENV_FILE=/nonexistent.
The foreign-OID test is RED on BASE when position nets agree.
"""
from __future__ import annotations

import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.update({
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
})
import HL_Live_Copy_Service_Core as c


class Wire:
    def __init__(self):
        self.cancels = []
        self.orders = []

    def cancel(self, coin, oid):
        self.cancels.append((coin, oid))
        return {"response": {"data": {"statuses": ["success"]}}}

    def order(self, coin, buy, size, px, tif, **kwargs):
        self.orders.append((coin, buy, size, px, tif, kwargs))
        return {"response": {"data": {"statuses": [{"filled": {"oid": 9}}]}}}


class Audit:
    def __init__(self):
        self.rows = []

    def append_reconciliation(self, event, status, **fields):
        self.rows.append((event, status, fields))


class CancelOwnershipTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="specc_cancel_")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.audit_dir = self.root / "audit"
        self.audit_dir.mkdir()
        paths = {
            "AUDIT_DIR": self.audit_dir,
            "RESTING_ENTRY_ORDERS_FILE": self.audit_dir / "resting_entries.json",
            "STANDING_CLOSES_FILE": self.audit_dir / "standing_closes.json",
            "SEND_ATTEMPTS_CSV": self.audit_dir / "send_attempts.csv",
            "RECONCILIATION_CSV": self.audit_dir / "reconciliation.csv",
        }
        for name, value in paths.items():
            p = mock.patch.object(c, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.wire = Wire()
        self.audit = Audit()
        self.mode = "ON"
        self.exchange_net = 100.0
        self.ledger_net = 100.0
        self.sender = object.__new__(c.SenderGateway)
        self.sender.cfg = SimpleNamespace(send_mode_now=lambda: self.mode,
                                           master_switch_now=lambda: self.mode != "OFF")
        self.sender.ledger = SimpleNamespace(coin_net=lambda _coin: self.ledger_net)
        self.sender.audit = self.audit
        self.sender._resting_lock = threading.RLock()
        self.sender._resting_entries = {}
        self.sender._standing_closes = {}
        self.sender._fresh_exchange_net = lambda _coin: self.exchange_net
        self.sender._exchange_client_for_coin = lambda coin: (self.wire, "BTC")
        self.sender._reserve_exchange_order_slot = lambda: c.utc_now_ms()
        self.sender._last_exchange_order_ms = 0

    def own_resting(self, oid, *, verified=True):
        self.sender._resting_entries[str(oid)] = {
            "oid": str(oid), "coin": "BTC", "sdk_coin": "BTC",
            "side": "BUY", "leader_wallet": "0x1", "size": 1.0,
            "limit_px": 100.0, "why": ("engine-owned" if verified else
                c.UNVERIFIED_RESTING_ENTRY_REASON),
            "cloid": c.generate_cloid("rest-" + str(oid)),
        }

    def own_standing(self, oid):
        self.sender._standing_closes["sleeve"] = {
            "oid": str(oid), "coin": "BTC", "sdk_coin": "BTC",
            "side": "SELL", "size": 1.0, "reduce_only": False,
            "intent_id": "exit", "wallet": "0x1",
        }

    def own_send_row(self, oid, *, cloid=""):
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "attempt_id": "a" + str(oid), "intent_id": "i" + str(oid),
            "coin": "BTC", "status": "ORDER_RESTING",
            "exchange_order_id": str(oid), "cloid": cloid,
        })

    def test_foreign_oid_denied_even_when_position_nets_match(self):
        # NEGATIVE CONTROL: BASE position-only shim calls cancel here (RED).
        self.exchange_net = self.ledger_net = 1.0
        with self.assertRaisesRegex(RuntimeError, "OWNERSHIP_UNVERIFIED"):
            self.sender._cancel_order(self.wire, "BTC", "999")
        self.assertEqual(self.wire.cancels, [])
        self.assertTrue(any("OWNERSHIP" in s and
                            r.get("exchange_order_id") == "999" and
                            "NO_CANCEL" in r.get("action", "")
                            for _, s, r in self.audit.rows))

    def test_unverified_resting_registry_is_not_ownership(self):
        self.own_resting(100, verified=False)
        with self.assertRaisesRegex(RuntimeError, "OWNERSHIP_UNVERIFIED"):
            self.sender._cancel_order(self.wire, "BTC", "100")
        self.assertEqual(self.wire.cancels, [])

    def test_resting_oid_owned_despite_mismatched_position_nets(self):
        self.own_resting(101)
        self.ledger_net, self.exchange_net = 0.0, 9.0
        self.sender._cancel_order(self.wire, "BTC", "101")
        self.assertEqual(self.wire.cancels, [("BTC", 101)])

    def test_standing_close_registry_owns_order_despite_unreadable_account(self):
        self.own_standing(102)
        self.exchange_net = None
        self.sender._cancel_order(self.wire, "BTC", "102")
        self.assertEqual(self.wire.cancels, [("BTC", 102)])

    def test_send_attempt_order_id_proves_ownership(self):
        self.own_send_row(103)
        self.exchange_net, self.ledger_net = 100, 0
        self.sender._cancel_order(self.wire, "BTC", "103")
        self.assertEqual(self.wire.cancels, [("BTC", 103)])

    def test_close_mixed_owned_foreign_cancels_only_owned(self):
        self.mode = "CLOSE"
        self.own_resting(104)
        self.ledger_net, self.exchange_net = 0, 8
        rows = [dict(self.sender._resting_entries["104"]),
                {"oid": "105", "coin": "BTC", "sdk_coin": "BTC",
                 "side": "BUY", "size": 1.0, "limit_px": 100}]
        self.sender._withdraw_rows(rows, "mixed", "", "RESTING_ENTRY_CANCELLED_SENDING_OFF")
        self.assertEqual(self.wire.cancels, [("BTC", 104)])
        self.assertTrue(any(r.get("exchange_order_id") == "105" and
                            "OWNERSHIP" in s
                            for _, s, r in self.audit.rows))

    def test_startup_orphan_foreign_cloid_denied(self):
        self.mode = "CLOSE"
        self.ledger_net = self.exchange_net = 1.0
        self.sender._cancel_orphan_order("", {
            "oid": 106, "coin": "BTC", "cloid": "0x" + "f" * 32})
        self.assertEqual(self.wire.cancels, [])
        self.assertTrue(any("OWNERSHIP" in s for _, s, _ in self.audit.rows))

    def test_startup_orphan_known_cloid_cancels_without_matching_oid(self):
        self.mode = "CLOSE"
        self.ledger_net, self.exchange_net = 0, 5
        cloid = c.generate_cloid("orphan-intent")
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "attempt_id": "orphan_attempt", "intent_id": "orphan-intent",
            "coin": "BTC", "cloid": cloid, "status": "pending_send"})
        self.sender._cancel_orphan_order("", {
            "oid": 107, "coin": "BTC", "cloid": cloid})
        self.assertEqual(self.wire.cancels, [("BTC", 107)])

    def test_startup_cloid_matching_different_coin_never_cancels(self):
        self.mode = "CLOSE"
        # A known engine client ID is not authority to cancel a different coin.
        cloid = c.generate_cloid("eth-only-intent")
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "attempt_id": "eth-attempt", "intent_id": "eth-only-intent",
            "coin": "ETH", "cloid": cloid, "status": "pending_send"})
        before = list(c.read_csv_rows(c.SEND_ATTEMPTS_CSV))
        self.sender._cancel_orphan_order("", {
            "oid": 120, "coin": "BTC", "cloid": cloid})
        self.assertEqual(self.wire.cancels, [])
        self.assertTrue(any("OWNERSHIP" in status for _, status, _ in self.audit.rows))
        # The failed cancel MUST NOT promote the ETH send attempt to own BTC oid=120.
        self.assertEqual(list(c.read_csv_rows(c.SEND_ATTEMPTS_CSV)), before)
        self.assertFalse(any(row.get("exchange_order_id") == "120"
                             for row in c.read_csv_rows(c.SEND_ATTEMPTS_CSV)))
        self.assertNotIn("120", self.sender._resting_entries)

    def startup_check(self, dex, order):
        self.sender.cfg.auto_send_enabled = True
        self.sender._read_open_orders = lambda: (True, [(dex, order)], "offline fixture")
        with (
            mock.patch.object(c, "FOLLOWER_NETWORK", "testnet"),
            mock.patch.object(c, "USER_WALLET", "0x" + "a" * 40),
            mock.patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "0"}),
        ):
            return self.sender.startup_orphan_order_check()

    def test_startup_ON_wrong_coin_cloid_report_only_never_adopts(self):
        self.mode = "ON"
        cloid = c.generate_cloid("owned-only-eth")
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "attempt_id": "eth-only", "intent_id": "owned-only-eth",
            "coin": "ETH", "cloid": cloid, "status": "pending_send"})
        before = list(c.read_csv_rows(c.SEND_ATTEMPTS_CSV))
        out = self.startup_check("", {"oid": 121, "coin": "BTC", "cloid": cloid,
                                     "side": "B", "sz": "1", "limitPx": "100"})
        self.assertEqual(out["adopted"], [])
        self.assertEqual(out["cancelled"], [])
        self.assertEqual(len(out["reported"]), 1)
        self.assertNotIn("121", self.sender._resting_entries)
        self.assertFalse(c.RESTING_ENTRY_ORDERS_FILE.exists())
        self.assertEqual(list(c.read_csv_rows(c.SEND_ATTEMPTS_CSV)), before)
        self.assertEqual(self.wire.cancels, [])

    def test_startup_ON_same_coin_cloid_still_adopts_and_promotes(self):
        self.mode = "ON"
        cloid = c.generate_cloid("owned-btc-on")
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "attempt_id": "btc-on", "intent_id": "owned-btc-on",
            "coin": "BTC", "cloid": cloid, "status": "pending_send"})
        out = self.startup_check("", {"oid": 122, "coin": "BTC", "cloid": cloid,
                                     "side": "B", "sz": "1", "limitPx": "100"})
        self.assertEqual(len(out["adopted"]), 1)
        self.assertIn("122", self.sender._resting_entries)
        rows = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
                if r.get("attempt_id") == "btc-on"]
        self.assertEqual(rows[-1]["status"], "ORDER_RESTING")
        self.assertEqual(rows[-1]["exchange_order_id"], "122")
        self.assertEqual(self.wire.cancels, [])

    def test_adopted_dex_scoped_order_cannot_cancel_on_default_dex(self):
        # The startup gate correctly adopts an order on dex 'one'. Its
        # persisted identity must still include that dex at cancellation time.
        self.mode = "ON"
        cloid = c.generate_cloid("owned-dex-one-btc")
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "attempt_id": "dex-one-adoption", "intent_id": "owned-dex-one-btc",
            "coin": "one:BTC", "cloid": cloid, "status": "pending_send"})
        result = self.startup_check("one", {"oid": 127, "coin": "BTC",
                                          "cloid": cloid, "side": "B",
                                          "sz": "1", "limitPx": "100"})
        self.assertEqual(len(result["adopted"]), 1)
        self.assertIn("127", self.sender._resting_entries)
        # A separate (default) DEX uses the same SDK ticker 'BTC'.
        # Cancelling via that unscoped route must NOT inherit dex-one ownership.
        wrong_dex_wire = Wire()
        with self.assertRaisesRegex(RuntimeError, "OWNERSHIP_UNVERIFIED"):
            self.sender._cancel_order(wrong_dex_wire, "BTC", "127")
        self.assertEqual(wrong_dex_wire.cancels, [])
        self.assertTrue(any(status == "CANCEL_ORDER_OWNERSHIP_UNVERIFIED"
                            and fields.get("exchange_order_id") == "127"
                            for _, status, fields in self.audit.rows))
        row = c.load_json(c.RESTING_ENTRY_ORDERS_FILE, {})["127"]
        self.assertEqual(c.canonical_coin_key(row["coin"]),
                         c.canonical_coin_key("one:BTC"))
        # Properly routed withdrawal of that same, engine-owned dex-one order
        # remains possible; SDK wire still receives the native 'BTC' ticker.
        withdrawn = self.sender._withdraw_rows([dict(self.sender._resting_entries["127"])],
                                               "owner verified", "")
        self.assertEqual([r["oid"] for r in withdrawn], ["127"])
        self.assertEqual(self.wire.cancels, [("BTC", 127)])

    def test_startup_ON_same_coin_different_dex_is_not_owned(self):
        self.mode = "ON"
        cloid = c.generate_cloid("dex-one-btc")
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "attempt_id": "dex1-btc", "intent_id": "dex-one-btc",
            "coin": "one:BTC", "cloid": cloid, "status": "pending_send"})
        before = list(c.read_csv_rows(c.SEND_ATTEMPTS_CSV))
        out = self.startup_check("two", {"oid": 123, "coin": "BTC", "cloid": cloid,
                                        "side": "B", "sz": "1", "limitPx": "100"})
        self.assertEqual(out["adopted"], [])
        self.assertEqual(len(out["reported"]), 1)
        self.assertNotIn("123", self.sender._resting_entries)
        self.assertEqual(list(c.read_csv_rows(c.SEND_ATTEMPTS_CSV)), before)
        self.assertEqual(self.wire.cancels, [])

    def test_direct_promotion_rejects_wrong_coin_without_writing_send_index(self):
        cloid = c.generate_cloid("eth-only-direct")
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "attempt_id": "eth-direct", "intent_id": "eth-only-direct",
            "coin": "ETH", "cloid": cloid, "status": "pending_send"})
        before = list(c.read_csv_rows(c.SEND_ATTEMPTS_CSV))
        self.assertFalse(self.sender._promote_pending_row_to_resting(cloid, "125", "BTC"))
        self.assertEqual(list(c.read_csv_rows(c.SEND_ATTEMPTS_CSV)), before)

    def test_startup_CLOSE_same_coin_wrong_dex_never_cancels_or_promotes(self):
        self.mode = "CLOSE"
        cloid = c.generate_cloid("one-btc-close")
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "attempt_id": "one-btc-close", "intent_id": "one-btc-close",
            "coin": "one:BTC", "cloid": cloid, "status": "pending_send"})
        before = list(c.read_csv_rows(c.SEND_ATTEMPTS_CSV))
        out = self.startup_check("two", {"oid": 126, "coin": "BTC", "cloid": cloid,
                                        "side": "B", "sz": "1", "limitPx": "100"})
        self.assertEqual(out["cancelled"], [])
        self.assertEqual(out["adopted"], [])
        self.assertEqual(len(out["reported"]), 1)
        self.assertEqual(self.wire.cancels, [])
        self.assertEqual(list(c.read_csv_rows(c.SEND_ATTEMPTS_CSV)), before)
        self.assertNotIn("126", self.sender._resting_entries)

    def test_startup_CLOSE_cancel_failure_same_coin_preserves_link(self):
        self.mode = "CLOSE"
        cloid = c.generate_cloid("owned-btc-partfill")
        c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {
            "attempt_id": "owned-btc-partfill", "intent_id": "owned-btc-partfill",
            "coin": "BTC", "cloid": cloid, "status": "pending_send"})
        self.wire.cancel = lambda *_args: {"response": {"data": {"statuses": [{"error": "temporary failure"}]}}}
        out = self.startup_check("", {"oid": 124, "coin": "BTC", "cloid": cloid,
                                     "side": "B", "sz": "1", "limitPx": "100"})
        self.assertEqual(len(out["cancelled"]), 1)
        self.assertEqual(out["cancelled"][0]["outcome"], "ORPHAN_ORDER_CANCEL_FAILED")
        rows = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
                if r.get("attempt_id") == "owned-btc-partfill"]
        self.assertEqual(rows[-1]["status"], "ORDER_RESTING")
        self.assertEqual(rows[-1]["exchange_order_id"], "124")

    def test_real_standing_guard_cancels_owned_order_with_mismatched_nets(self):
        self.own_standing(110)
        self.sender._standing_closes["sleeve"].update({
            "placed_ms": c.utc_now_ms() - 10**9,
            "sleeve_signed": 10.0, "sleeve_tol": 0.0,
        })
        self.sender._standing_guard_ms = 0
        self.ledger_net, self.exchange_net = 0.0, 8.0
        count = c.SenderGateway.guard_standing_closes(self.sender)
        self.assertEqual(count, 1)
        self.assertEqual(self.wire.cancels, [("BTC", 110)])

    def test_real_standing_close_withdraws_owned_order_despite_net_mismatch(self):
        self.own_standing(111)
        self.ledger_net, self.exchange_net = 0.0, 9.0
        self.sender._standing_filled_size = lambda *_a: 0.0
        fill = c.LeaderFill("standing-fill", "0x" + "b" * 40, "BTC",
                            "SELL", 100.0, 1.0, c.utc_now_ms(), "TEST")
        intent = c.Intent("standing-intent", fill, "SELL", 1.0, 100.0,
                          "LIVE", "fixed", "EXIT_ALLOWED", "fixture", "sleeve", "",
                          "LONG", 1.0, 1.0, True, True, c.utc_now_ms())
        remaining, error = c.SenderGateway._withdraw_standing_close(
            self.sender, self.wire, intent, 1.0, 3, {})
        self.assertIsNone(error)
        self.assertEqual(remaining, 1.0)
        self.assertEqual(self.wire.cancels, [("BTC", 111)])

    def test_OFF_production_sender_never_calls_exchange_cancel_or_order(self):
        # These are genuine SenderGateway boundaries, NOT a FakeSender refusing OFF.
        self.mode = "OFF"
        self.own_resting(108)
        with self.assertRaises(c._OrderSwitchBlocked):
            self.sender._cancel_order(self.wire, "BTC", "108")
        with self.assertRaises(c._InitialSendSwitchBlocked):
            self.sender._place_order(self.wire, "BTC", True, 1.0,
                                     100.0, "Ioc", False, initial_lifecycle="ENTRY")
        fill = c.LeaderFill("off-fill", "0x" + "a" * 40,
                            "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST")
        intent = c.Intent("off-intent", fill, "BUY", 1.0, 100.0,
                          "LIVE", "fixed", "ENTRY_ALLOWED", "test", "s", "",
                          "FLAT", 0.0, 0.0, False, False, c.utc_now_ms())
        ok, status = c.SenderGateway.send_if_allowed(self.sender, intent)
        self.assertFalse(ok)
        self.assertEqual(status, "MASTER_REAL_ORDERS_OFF")
        self.assertEqual(self.wire.cancels, [])
        self.assertEqual(self.wire.orders, [])

    def test_CLOSED_only_cancel_requires_CLOSE_mode(self):
        self.mode = "ON"
        self.own_resting(109)
        with self.assertRaises(c._OrderSwitchBlocked):
            self.sender._cancel_order(self.wire, "BTC", "109", required_mode="CLOSE")
        self.assertEqual(self.wire.cancels, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
