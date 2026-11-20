import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import HL_Live_Copy_Service as svcmod


class WalletGateFailClosedTests(unittest.TestCase):
    def test_read_error_blocks_entry_intent_and_position_but_allows_planned_close(self):
        service = svcmod.DryRunLiveCopyService.__new__(svcmod.DryRunLiveCopyService)
        service.state = {"counters": {}}
        service.processed_ids = set()
        service.positions = {}
        alerts = []
        intents = []
        service.log_error = lambda context, exc: alerts.append((context, str(exc)))
        service.model_copy_notional = lambda cfg, fill: 100.0
        service.global_order_cap = lambda: 0.0
        service.convergence_notional_for_fill = mock.Mock(side_effect=[
            {"ok": True, "reduce_only": False, "notional": 100.0, "side": "BUY"},
            {"ok": True, "reduce_only": True, "notional": 5.0, "side": "SELL"},
        ])
        service.append_order_intent = lambda *args, **kwargs: intents.append((args, kwargs))
        service.append_reconciliation = lambda *args, **kwargs: None

        fill = svcmod.LeaderFill(
            fill_id="gate-read-error-entry",
            wallet="0xabc",
            coin="BTC",
            side="BUY",
            price=100.0,
            size=1.0,
            signed_size_delta=1.0,
            timestamp_ms=1,
            timestamp_iso="1970-01-01T00:00:00Z",
            source="test",
            recording_method="test",
            raw={},
        )
        cfg = svcmod.LiveWalletConfig(wallet="0xabc", mode="ON")
        close_fill = svcmod.LeaderFill(
            fill_id="gate-read-error-close",
            wallet="0xabc",
            coin="BTC",
            side="SELL",
            price=100.0,
            size=1.0,
            signed_size_delta=-1.0,
            timestamp_ms=2,
            timestamp_iso="1970-01-01T00:00:00Z",
            source="test",
            recording_method="test",
            raw={},
        )

        with mock.patch.object(Path, "exists", return_value=True), \
             mock.patch.object(Path, "read_text", side_effect=PermissionError("gate unreadable")):
            service.process_fill(fill, cfg)
            service.process_fill(close_fill, cfg)

        self.assertEqual(service.state["counters"].get("fills_skipped_clo_entry"), 1)
        entry_intents = [args for args, _ in intents if args[4] == "ENTRY"]
        self.assertEqual(entry_intents, [])
        self.assertEqual(service.positions[service.position_key("0xabc", "BTC")]["signed_size"], 0.0)
        planner_calls = service.convergence_notional_for_fill.call_args_list
        self.assertEqual([call[0][1] for call in planner_calls], [fill, close_fill])
        self.assertTrue(all(call[0][0].mode == "CLO" for call in planner_calls))
        self.assertTrue(any(context == "UI_WALLET_GATE_READ" for context, _ in alerts))


if __name__ == "__main__":
    unittest.main()
