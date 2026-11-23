#!/usr/bin/env python3
"""Spec A kill-boundary integration: real leader handler + durable sender pending-row writer.

No SDK, no keys, no network. Faults are injected at the real acceptance,
order_intents and pending_send boundaries. Every restart creates fresh state
objects backed by exactly the same files. Run via unittest with original Core
and mutations deleting the journal hook / the intent or pending-row fsync.
"""
from __future__ import annotations

from dataclasses import replace
import errno
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
os.environ.setdefault("HL_LIVE_WS_ENABLED", "0")
os.environ.setdefault("HL_LIVE_SCOPE_SWEEP_THREAD", "0")
os.environ.setdefault("HL_LIVE_PREWARM_SYMBOL_META", "0")
os.environ.setdefault("HL_LIVE_PREWARM_SDK_CLIENT", "0")

import HL_Live_Copy_Service_Core as c


class KillPoint(BaseException):
    """Simulate an abrupt process kill without the production exception handler."""


class FakeSender:
    """Only the wire call is fake. The pending send row is produced by production code."""

    def __init__(self, audit, wire_calls, after_wire=None, mode="ON"):
        self.audit = audit
        self.wire_calls = wire_calls
        self.after_wire = after_wire
        self.mode = mode

    def resting_entries_against(self, fill):
        return []

    def cancel_resting_entries_against(self, fill):
        return []

    def _read_open_orders(self):
        return True, [], "offline fake exchange"

    def send_if_allowed(self, intent, entry_block_reason=""):
        if self.mode == "OFF":
            return False, "MASTER_REAL_ORDERS_OFF"
        cloid = c.generate_cloid(intent.intent_id)
        timing = {"send_attempt_id": c.generate_attempt_id(intent.intent_id)}
        c.SenderGateway._begin_pending_send(
            self, intent, "Ioc", "REAL_IOC", intent.fill.price,
            intent.copy_size, cloid, timing)
        # This is the only physical-order boundary (fake, no real exchange).
        self.wire_calls.append(cloid)
        if self.after_wire:
            self.after_wire()
        return True, "ORDER_FILLED"


class CrashBoundaryIntegration(unittest.TestCase):
    wallet = "0x" + "a" * 40

    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="speca_boundaries_")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.audit_dir = self.root / "audit"
        ap = self.audit_dir / "append_only"
        ap.mkdir(parents=True)
        mapping = {
            "AUDIT_DIR": self.audit_dir, "APPEND_ONLY_DIR": ap,
            "MANUAL_LIVE_POSITIONS_FILE": self.audit_dir / "ledger.json",
            "ORDER_INTENTS_CSV": ap / "order_intents.csv",
            "SEND_ATTEMPTS_CSV": ap / "send_attempts.csv",
            "LIVE_FILLS_CSV": ap / "live_fills.csv",
            "RECONCILIATION_CSV": ap / "reconciliation.csv",
            "ERRORS_CSV": ap / "errors.csv",
            "CORE_RUNTIME_STATE_FILE": self.audit_dir / "core_state.json",
        }
        for key, value in mapping.items():
            patch = mock.patch.object(c, key, value)
            patch.start()
            self.addCleanup(patch.stop)
        ts = c.utc_now_ms()
        self.fill = c.LeaderFill("speca-real-fill", self.wallet, "BTC",
                                 "BUY", 100.0, 0.25, ts, "POLL")
        self.intent = c.Intent(
            c.stable_hash(["intent", self.fill.leader_fill_id, self.wallet,
                           "BTC", "BUY", ts]),
            self.fill, "BUY", 0.25, 25.0, "LIVE", "fixed",
            "ENTRY_ALLOWED", "fixture", c.ManualLedger.sleeve_id(self.wallet, "BTC"),
            "", "FLAT", 0.0, 0.0, False, False, ts, "lifecycle=ENTRY")
        self.wire_calls = []
        self.cloid = c.generate_cloid(self.intent.intent_id)

    def new_core(self, mode="ON", after_wire=None):
        # New objects are constructed from disk. The real _process_leader_fill_inner
        # and _handle_leader_fill methods are NOT mocked.
        core = object.__new__(c.LiveCopyCore)
        journal = self.audit_dir / "leader_crash_journal.jsonl"
        core._crash_journal_start_size = journal.stat().st_size if journal.exists() else 0
        core.audit = c.AuditLogWriter()
        core.ledger = c.ManualLedger(path=c.MANUAL_LIVE_POSITIONS_FILE)
        core.dedupe = c.DedupeStore(state_dir=self.audit_dir)
        core.cfg = SimpleNamespace(send_mode_now=lambda: mode,
                                   master_switch_now=lambda: mode != "OFF")
        core.sender = FakeSender(core.audit, self.wire_calls, after_wire, mode)
        core.intent_builder = SimpleNamespace(
            blocked_locally=lambda *_a, **_k: False,
            build=lambda fill: self.intent)
        core._prewarm_with_parity = lambda *_a, **_k: None
        core._defer_unreadable_truth = lambda *_a, **_k: False
        core._send_lock = threading.RLock()
        core._idem_lock = threading.Lock()
        core._idem_accepted = set()
        core._idem_duplicate_audited = set()
        core.intents_by_id = {}
        core._intent_inserts = 0
        core._past_send_keys = set()
        core._deferred = {}
        core._deferred_lock = threading.Lock()
        core._crash_replay_checked = False
        # The startup replay must call the same genuine production handler.
        core._process_leader_fill = lambda fill: c.LiveCopyCore._process_leader_fill_inner(core, fill)
        return core

    def attempts(self):
        return list(c.iter_csv_rows(c.SEND_ATTEMPTS_CSV))

    def assert_once_after_restart(self):
        restarted = self.new_core()
        restarted._replay_crashed_leader_fills_once()
        self.assertEqual(self.wire_calls, [self.cloid])
        restarted_again = self.new_core()
        restarted_again._replay_crashed_leader_fills_once()
        self.assertEqual(self.wire_calls, [self.cloid])
        self.assertEqual(len([r for r in self.attempts()
                              if r.get("status") == "pending_send"]), 1)

    def test_real_L1_journal_hook_before_acceptance(self):
        first = self.new_core()
        def die_before_intent(_fill):
            raise KillPoint()

        # Stop inside the production handler after _idem_accepted.add, but
        # before order_intents is appended. Removing the production journal
        # hook leaves no durable record and makes this test RED.
        first.intent_builder.build = die_before_intent
        with self.assertRaises(KillPoint):
            first._process_leader_fill_inner(self.fill)
        self.assertIn(self.fill.leader_fill_id, first._idem_accepted)
        self.assertFalse(c.ORDER_INTENTS_CSV.exists())
        self.assertTrue((self.audit_dir / "leader_crash_journal.jsonl").is_file())
        self.assert_once_after_restart()

    def test_real_L2_kill_after_durable_intent_before_send_attempt(self):
        first = self.new_core()
        original = first.audit.append_order_intent

        def die_after_intent(intent):
            original(intent)
            raise KillPoint()

        with mock.patch.object(first.audit, "append_order_intent", side_effect=die_after_intent):
            with self.assertRaises(KillPoint):
                first._process_leader_fill_inner(self.fill)
        self.assertEqual(len(list(c.iter_csv_rows(c.ORDER_INTENTS_CSV))), 1)
        self.assertFalse(self.attempts())
        self.assert_once_after_restart()

    def test_real_L3_after_fake_exchange_before_ledger_never_resends(self):
        def die_after_exchange():
            raise KillPoint()

        # A hard kill crosses the pending-send/exchange boundary, not a mock
        # direct row write. The sender is invoked by the REAL _handle_leader_fill.
        first = self.new_core(after_wire=die_after_exchange)
        with self.assertRaises(KillPoint):
            first._process_leader_fill_inner(self.fill)
        self.assertEqual(self.wire_calls, [self.cloid])
        self.assertEqual(len(self.attempts()), 1)
        self.assertEqual(self.attempts()[0]["status"], "pending_send")
        self.assert_once_after_restart()

    def test_intent_fsync_failure_prevents_physical_order(self):
        first = self.new_core()
        original = c.os.fsync
        fsync_count = []

        def fail_on_intent(fd):
            fsync_count.append(fd)
            if len(fsync_count) == 2:  # journal fsync first, then intent fsync
                raise OSError(errno.EIO, "injected intent fsync failure")
            return original(fd)

        with mock.patch.object(c.os, "fsync", side_effect=fail_on_intent):
            with self.assertRaises(OSError):
                first._process_leader_fill_inner(self.fill)
        self.assertGreaterEqual(len(fsync_count), 2)
        self.assertEqual(self.wire_calls, [])
        # Removing the production intent os.fsync makes this test RED.

    def test_pending_send_fsync_failure_prevents_physical_order(self):
        first = self.new_core()
        original = c.os.fsync
        fsync_count = []

        def fail_on_pending(fd):
            fsync_count.append(fd)
            if len(fsync_count) == 3:  # journal, intent, then pending_send
                raise OSError(errno.EIO, "injected pending fsync failure")
            return original(fd)

        with mock.patch.object(c.os, "fsync", side_effect=fail_on_pending):
            result = first._process_leader_fill_inner(self.fill)
        # The production handler catches sender errors; a failed fsync must
        # yield a no-send terminal result, not a physical exchange call.
        self.assertEqual(result[1], "SEND_EXCEPTION")
        self.assertGreaterEqual(len(fsync_count), 3)
        self.assertEqual(self.wire_calls, [])
        # Removing pending-send fsync instead reaches the fake exchange: RED.

    def test_marker_IO_failure_refuses_copy_ledger_mutation(self):
        ledger = c.ManualLedger(path=c.MANUAL_LIVE_POSITIONS_FILE)
        matcher = c.CopyFillMatcher(ledger, c.AuditLogWriter())
        raw = {"copy_fill_id": "marker-denied", "intent_id": self.intent.intent_id,
               "coin": "BTC", "side": "BUY", "price": 100, "size": 0.25,
               "time": self.fill.timestamp_ms}
        with mock.patch.object(c.os, "open", side_effect=OSError(errno.EIO, "marker inaccessible")):
            ok = matcher.match_and_apply(raw, {self.intent.intent_id: self.intent})
        self.assertFalse(ok)
        self.assertEqual(ledger.wallet_coin_position(self.wallet, "BTC"), 0)
        self.assertFalse(c.LIVE_FILLS_CSV.exists())

    def test_incomplete_real_fill_refused_before_acceptance(self):
        first = self.new_core()
        missing = replace(self.fill, side=None)
        result = first._process_leader_fill_inner(missing)
        self.assertEqual(result[1], "INVALID_LEADER_FILL_PRE_ACCEPT")
        self.assertNotIn(missing.leader_fill_id, first._idem_accepted)
        self.assertEqual(self.wire_calls, [])

    def test_send_mode_OFF_has_zero_orders(self):
        first = self.new_core(mode="OFF")
        first._process_leader_fill_inner(self.fill)
        self.assertEqual(self.wire_calls, [])
        self.assertEqual(self.attempts(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
