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

os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
os.environ.setdefault("HL_LEADER_NETWORK", "testnet")
os.environ.setdefault("HL_FOLLOWER_NETWORK", "testnet")
os.environ.setdefault("HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS", "0")
os.environ.setdefault("HL_LIVE_SCOPE_SWEEP_THREAD", "0")
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
