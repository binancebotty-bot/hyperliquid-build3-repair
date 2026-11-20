"""Duplicate and replayed leader fills must not create duplicate orders."""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

os.environ["HL_LIVE_AUDIT_DIR"] = tempfile.mkdtemp(prefix="dup_fill_")
import HL_Live_Copy_Service as svcmod  # noqa: E402

svcmod.TEST_INJECTION_ENABLED = True


class DuplicateFillIdempotenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dup_fill_case_"))
        (self.tmp / "live_config.json").write_text(json.dumps({"wallets": {
            "0xw1": {"mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                     "norm_base": 100.0, "leader_equity_base": 1000.0}
        }}), encoding="utf-8")
        svcmod.configure_paths(self.tmp, self.tmp / "raw_live_fills.csv")
        self.exchange_calls = []
        self._patches = [
            mock.patch.object(svcmod, "LIVE_AUTO_SEND_ENABLED", True),
            mock.patch.object(svcmod, "LIVE_AUTO_SEND_WALLET", "0xw1"),
            mock.patch.object(svcmod, "LIVE_AUTO_SEND_MAX_PER_RUN", 10),
            mock.patch.dict(os.environ, {"HL_LIVE_HL_PRIVATE_KEY": "test-only-placeholder"}),
            mock.patch.object(svcmod, "manual_send_one_intent", self.fake_exchange_call),
        ]
        for patcher in self._patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def fake_exchange_call(self, intent_id, *args, **kwargs):
        self.exchange_calls.append(intent_id)
        return {"ok": True, "status": "ORDER_FILLED", "intent_id": intent_id}

    @staticmethod
    def fill():
        return svcmod.LeaderFill(
            fill_id="fill-dup-1", wallet="0xw1", coin="BTC", side="BUY",
            price=100.0, size=10.0, signed_size_delta=10.0, timestamp_ms=2000,
            timestamp_iso="2026-01-01T00:00:02Z", source="test",
            recording_method="test", raw={},
        )

    def fresh_service(self):
        svc = svcmod.DryRunLiveCopyService()
        svc.state["leader_event_positions"] = {}
        svc.state["baselines"] = {"0xw1": {"baseline_ts_ms": 1000, "baseline_fill_id": "base"}}
        svc.processed_ids = set()
        svc.account_net_provider = lambda coin: {
            "ok": True,
            "net": float(svc.get_position("0xw1", coin).get("signed_size") or 0.0),
            "source": "TEST_AUTHORITATIVE_ACCOUNT_NET",
        }
        return svc

    def intent_rows(self):
        path = svcmod.ORDER_INTENTS_CSV
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8-sig") as stream:
            return list(csv.DictReader(stream))

    def test_duplicate_ws_fill_creates_one_intent_without_exchange_call(self):
        svc = self.fresh_service()

        first = svc.process_ws_fill(self.fill())
        duplicate = svc.process_ws_fill(self.fill())

        self.assertTrue(first["processed"])
        self.assertEqual(duplicate, {"processed": False, "reason": "DUPLICATE"})
        self.assertEqual(len(self.intent_rows()), 1)
        self.assertEqual(len(self.exchange_calls), 0)

    def test_replayed_ws_fill_after_restart_creates_no_intent_or_exchange_call(self):
        svc = self.fresh_service()
        svc.process_ws_fill(self.fill())
        svc.persist()
        intent_count_before_restart = len(self.intent_rows())
        exchange_count_before_restart = len(self.exchange_calls)

        restarted = svcmod.DryRunLiveCopyService()
        restarted.state["leader_event_positions"] = svc.state["leader_event_positions"]
        restarted.state["baselines"] = svc.state["baselines"]
        restarted.account_net_provider = lambda coin: {
            "ok": True,
            "net": float(restarted.get_position("0xw1", coin).get("signed_size") or 0.0),
            "source": "TEST_AUTHORITATIVE_ACCOUNT_NET",
        }
        result = restarted.process_ws_fill(self.fill())

        self.assertEqual(result, {"processed": False, "reason": "DUPLICATE"})
        self.assertEqual(len(self.intent_rows()), intent_count_before_restart)
        self.assertEqual(len(self.exchange_calls), exchange_count_before_restart)


if __name__ == "__main__":
    unittest.main()
