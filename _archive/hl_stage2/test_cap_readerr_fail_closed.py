"""Global order cap read errors must refuse entries and leave an operator-visible status."""
from __future__ import annotations

import unittest
from unittest.mock import patch

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


if __name__ == "__main__":
    unittest.main()
