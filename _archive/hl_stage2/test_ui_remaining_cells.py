"""Remaining UI cell wiring checks for the live copy panel."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import HL_Copy_App_SSOT as ui


class RemainingUiCellTests(unittest.TestCase):
    def test_live_exposure_card_labels_engine_tracked_scope(self) -> None:
        panel = ui.render_live_copy_control_panel()

        self.assertIn("['Engine-tracked exposure',exp,expCls]", panel)


if __name__ == "__main__":
    unittest.main()
