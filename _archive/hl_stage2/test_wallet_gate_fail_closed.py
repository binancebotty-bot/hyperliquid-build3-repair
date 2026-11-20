import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import HL_Live_Copy_Service as svcmod


class WalletGateFailClosedTests(unittest.TestCase):
    def test_read_error_blocks_entry_exchange_call_and_alerts_operator(self):
        service = svcmod.DryRunLiveCopyService.__new__(svcmod.DryRunLiveCopyService)
        service.state = {"counters": {}}
        service.processed_ids = set()
        alerts = []
        service.log_error = lambda context, exc: alerts.append((context, str(exc)))
        service.get_position = lambda wallet, coin: {"signed_size": 0.0}
        service.model_copy_notional = lambda cfg, fill: 100.0
        service.global_order_cap = lambda: 0.0
        service.convergence_notional_for_fill = lambda cfg, fill: {"ok": True, "reduce_only": False}
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

        with mock.patch.object(Path, "exists", return_value=True), \
             mock.patch.object(Path, "read_text", side_effect=PermissionError("gate unreadable")), \
             mock.patch.object(svcmod, "send_hyperliquid_order") as exchange_send:
            service.process_fill(fill, cfg)

        self.assertEqual(service.state["counters"].get("fills_skipped_clo_entry"), 1)
        self.assertEqual(exchange_send.call_count, 0)
        self.assertTrue(any(context == "UI_WALLET_GATE_READ" for context, _ in alerts))


if __name__ == "__main__":
    unittest.main()
