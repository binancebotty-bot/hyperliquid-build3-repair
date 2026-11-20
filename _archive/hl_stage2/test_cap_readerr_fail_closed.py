"""Global order cap read errors must refuse entries and leave an operator-visible status."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import HL_Live_Copy_Service as svcmod


class GlobalOrderCapReadErrorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = svcmod.DryRunLiveCopyService()

    def test_cap_read_exception_blocks_entry_and_emits_operator_status(self) -> None:
        with patch.object(svcmod, "load_json", side_effect=OSError("config unavailable")):
            status = self.service.global_order_cap_block("ENTRY", 100.0, False, {})

        self.assertEqual(status, "BLOCKED_GLOBAL_MAX_ORDER_NOTIONAL_CAP_READ_ERROR")
        self.assertGreater(
            self.service.state["counters"].get(
                "entries_blocked_global_max_order_notional_cap_read_error", 0
            ),
            0,
        )

    def test_explicit_zero_cap_still_allows_entry(self) -> None:
        with patch.object(svcmod, "load_json", return_value={
            "global_controls": {"max_order_notional_usd": 0}
        }):
            status = self.service.global_order_cap_block("ENTRY", 100.0, False, {})

        self.assertEqual(status, "")

    def test_nonnumeric_cap_blocks_entry_before_exchange_call(self) -> None:
        cfg = svcmod.LiveWalletConfig(
            wallet="0xfixed", mode="LIVE", copy_mode="fixed", fixed_notional=100.0
        )
        fill = svcmod.LeaderFill(
            fill_id="bad-cap", wallet=cfg.wallet, coin="BTC", side="BUY",
            price=100.0, size=1.0, signed_size_delta=1.0, timestamp_ms=1,
            timestamp_iso="2026-01-01T00:00:00Z", source="test",
            recording_method="test", raw={},
        )
        exchange_call = Mock(return_value={"ok": True, "net": 0.0})
        self.service.account_net_provider = exchange_call
        self.service.state["leader_event_positions"] = {}
        self.service.processed_ids.clear()

        with (
            patch.object(svcmod, "TEST_INJECTION_ENABLED", True),
            patch.object(svcmod, "XTRUTH", None),
            patch.object(svcmod, "load_json", return_value={
                "global_controls": {"max_order_notional_usd": "not-a-number"}
            }),
            patch.object(svcmod, "append_csv"),
        ):
            self.service.process_fill(fill, cfg)

        exchange_call.assert_not_called()
        self.assertGreater(
            self.service.state["counters"].get(
                "entries_blocked_global_max_order_notional_cap_read_error", 0
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
