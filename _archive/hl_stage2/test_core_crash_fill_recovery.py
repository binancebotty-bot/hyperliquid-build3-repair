#!/usr/bin/env python3
"""Crash kill-points for leader journal and engine-owned copy fills.

Offline only. Run from _archive/hl_stage2:
    HL_LIVE_ENV_FILE=/nonexistent python -u test_core_crash_fill_recovery.py
Expected on BASE: L1 and C1 RED. No live exchange, keys, or network.
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
os.environ.setdefault("HL_LIVE_SCOPE_SWEEP_THREAD", "0")
os.environ.setdefault("HL_LIVE_WS_ENABLED", "0")
os.environ.setdefault("HL_LIVE_PREWARM_SYMBOL_META", "0")
os.environ.setdefault("HL_LIVE_PREWARM_SDK_CLIENT", "0")

import HL_Live_Copy_Service_Core as c


class CrashFillRecoveryTests(unittest.TestCase):
    wallet = "0x" + "a" * 40

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="crash_fill_")
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.audit_dir = d / "audit"
        self.append_dir = self.audit_dir / "append_only"
        self.append_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "AUDIT_DIR": self.audit_dir,
            "APPEND_ONLY_DIR": self.append_dir,
            "MANUAL_LIVE_POSITIONS_FILE": self.audit_dir / "positions.json",
            "LIVE_FILLS_CSV": self.append_dir / "live_fills.csv",
            "SEND_ATTEMPTS_CSV": self.append_dir / "send_attempts.csv",
            "ORDER_INTENTS_CSV": self.append_dir / "order_intents.csv",
            "RECONCILIATION_CSV": self.append_dir / "reconciliation.csv",
            "CORE_RUNTIME_STATE_FILE": self.audit_dir / "core_state.json",
        }
        for name, value in paths.items():
            p = mock.patch.object(c, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.fill_id = "leader-crash-" + d.name
        now = c.utc_now_ms()
        self.fill = c.LeaderFill(self.fill_id, self.wallet, "BTC", "BUY",
                                 100.0, 1.0, now, "POLL", 0, {})
        self.intent = c.Intent(
            c.stable_hash(["intent", self.fill_id, self.wallet, "BTC", "BUY", now]),
            self.fill, "BUY", 0.25, 25.0, "LIVE", "fixed",
            "ENTRY_ALLOWED", "test", c.ManualLedger.sleeve_id(self.wallet, "BTC"),
            "", "FLAT", 0.0, 0.0, False, False, now, "lifecycle=ENTRY")
        self.exchange_calls = {}

    def copy_raw(self, cid):
        return {"copy_fill_id": cid, "hash": cid, "tid": 1,
                "intent_id": self.intent.intent_id, "coin": "BTC", "side": "BUY",
                "price": "100", "size": "0.25", "timestamp_ms": self.fill.timestamp_ms}

    def copy_rows(self):
        if not c.LIVE_FILLS_CSV.exists():
            return []
        return list(c.iter_csv_rows(c.LIVE_FILLS_CSV))

    def fresh_copy(self):
        ledger = c.ManualLedger(path=c.MANUAL_LIVE_POSITIONS_FILE)
        matcher = c.CopyFillMatcher(ledger, c.AuditLogWriter())
        return ledger, matcher

    def assert_one_copy(self, ledger, copy_id):
        self.assertAlmostEqual(ledger.wallet_coin_position(self.wallet, "BTC"), 0.25)
        self.assertEqual(sum(r.get("copy_fill_id") == copy_id for r in self.copy_rows()), 1)

    def test_C1_claim_then_crash_recovers_on_new_matcher(self):
        raw = self.copy_raw("c1")
        cid = c.CopyAccountIngestor.copy_fill_id(raw)
        self.assertTrue(c.claim_copy_fill_process_marker(cid))
        ledger, matcher = self.fresh_copy()  # new objects, same files
        self.assertTrue(matcher.match_and_apply(raw, {self.intent.intent_id: self.intent}))
        self.assert_one_copy(ledger, cid)
        ledger2, matcher2 = self.fresh_copy()
        self.assertFalse(matcher2.match_and_apply(raw, {self.intent.intent_id: self.intent}))
        self.assert_one_copy(ledger2, cid)

    def test_C2_applied_ledger_then_crash_before_csv(self):
        raw = self.copy_raw("c2")
        cid = c.CopyAccountIngestor.copy_fill_id(raw)
        self.assertTrue(c.claim_copy_fill_process_marker(cid))
        ledger, _ = self.fresh_copy()
        event = dict(raw, copy_fill_id=cid, _crash_match_method="MATCHED_BY_INTENT_ID")
        ledger.apply_copy_fill(self.intent, event)  # injection: stop before append_live_fill
        self.assertEqual(len(self.copy_rows()), 0)
        ledger2, matcher2 = self.fresh_copy()
        self.assertIn(cid, matcher2.matched_copy_fill_ids)
        self.assert_one_copy(ledger2, cid)
        self.assertFalse(matcher2.match_and_apply(raw, {self.intent.intent_id: self.intent}))

    def test_C3_csv_then_crash_before_matched_id(self):
        raw = self.copy_raw("c3")
        cid = c.CopyAccountIngestor.copy_fill_id(raw)
        self.assertTrue(c.claim_copy_fill_process_marker(cid))
        ledger, _ = self.fresh_copy()
        ledger.apply_copy_fill(self.intent, dict(raw, copy_fill_id=cid,
                                                 _crash_match_method="MATCHED_BY_INTENT_ID"))
        pending = ledger.data.get("_pending_copy_fill_rows", {}).get(cid)
        self.assertIsInstance(pending, dict)
        c.AuditLogWriter().append_live_fill(pending)  # injection: do not add matched id
        ledger2, matcher2 = self.fresh_copy()
        self.assertFalse(matcher2.match_and_apply(raw, {self.intent.intent_id: self.intent}))
        self.assert_one_copy(ledger2, cid)

    def test_copy_foreign_intent_not_adopted(self):
        raw = dict(self.copy_raw("foreign"), intent_id="foreign", coin="NO_SUCH_ASSET")
        ledger, matcher = self.fresh_copy()
        self.assertFalse(matcher.match_and_apply(raw, {}))
        self.assertEqual(ledger.wallet_coin_position(self.wallet, "BTC"), 0.0)
        self.assertEqual(len(self.copy_rows()), 0)

    def leader_journal_and_restart(self, stage):
        # Inject at L1 (after claim), L2 (after durable intent) or L3
        # (pending send + successful exchange call before copy ledger update).
        c.append_leader_crash_journal(self.fill)
        dedupe = c.DedupeStore(state_dir=self.audit_dir)
        dedupe.accept_leader(self.fill_id)
        dedupe.flush_jsonl()
        if stage in ("L2", "L3"):
            c.AuditLogWriter().append_order_intent(self.intent)
        if stage == "L3":
            cloid = c.generate_cloid(self.intent.intent_id)
            c.AuditLogWriter().append_send_attempt({
                "attempt_id": c.generate_attempt_id(self.intent.intent_id),
                "intent_id": self.intent.intent_id, "leader_fill_id": self.fill_id,
                "cloid": cloid, "status": "pending_send"})
            self.exchange_calls[cloid] = 1
        # A fresh core stand-in with the genuine replay method, fresh dedupe
        # loaded from the same disk and a fake exchange. No network.
        fake = object.__new__(c.LiveCopyCore)
        fake.dedupe = c.DedupeStore(state_dir=self.audit_dir)
        fake.audit = c.AuditLogWriter()
        fake._idem_lock = threading.Lock()
        fake._idem_accepted = set()
        fake._crash_replay_checked = False
        fake.cfg = mock.Mock()
        fake.cfg.send_mode_now.return_value = "ON"
        fake.cfg.master_switch_now.return_value = True
        fake.sender = mock.Mock()
        fake.sender._read_open_orders.return_value = (True, [], "offline")
        fake.ledger = c.ManualLedger(path=c.MANUAL_LIVE_POSITIONS_FILE)
        def receive(fill, *_args, **_kwargs):
            intent_id = c.stable_hash(["intent", fill.leader_fill_id, fill.leader_wallet,
                                       fill.coin, fill.side, fill.timestamp_ms])
            cloid = c.generate_cloid(intent_id)
            self.exchange_calls[cloid] = self.exchange_calls.get(cloid, 0) + 1
            c.AuditLogWriter().append_send_attempt({
                "attempt_id": c.generate_attempt_id(intent_id), "intent_id": intent_id,
                "leader_fill_id": fill.leader_fill_id, "cloid": cloid,
                "status": "ORDER_FILLED"})
            return True, "ORDER_FILLED", None
        fake._process_leader_fill = receive
        fake._replay_crashed_leader_fills_once()
        cloid = c.generate_cloid(self.intent.intent_id)
        self.assertLessEqual(self.exchange_calls.get(cloid, 0), 1)
        if stage != "L3":
            self.assertEqual(self.exchange_calls.get(cloid, 0), 1)
        fake._crash_replay_checked = False
        fake._replay_crashed_leader_fills_once()
        self.assertLessEqual(self.exchange_calls.get(cloid, 0), 1)
        return cloid

    def test_L1_accepted_before_intent_recovers(self):
        self.leader_journal_and_restart("L1")

    def test_L2_intent_before_send_attempt_recovers(self):
        self.leader_journal_and_restart("L2")

    def test_L3_exchange_called_then_crash_never_resends(self):
        cloid = self.leader_journal_and_restart("L3")
        self.assertEqual(self.exchange_calls.get(cloid), 1)

    def test_completed_copy_replay_deduped(self):
        raw = self.copy_raw("complete")
        cid = c.CopyAccountIngestor.copy_fill_id(raw)
        ledger, matcher = self.fresh_copy()
        self.assertTrue(matcher.match_and_apply(raw, {self.intent.intent_id: self.intent}))
        self.assertFalse(matcher.match_and_apply(raw, {self.intent.intent_id: self.intent}))
        ledger2, matcher2 = self.fresh_copy()
        self.assertFalse(matcher2.match_and_apply(raw, {self.intent.intent_id: self.intent}))
        self.assert_one_copy(ledger2, cid)


if __name__ == "__main__":
    unittest.main(verbosity=2)
