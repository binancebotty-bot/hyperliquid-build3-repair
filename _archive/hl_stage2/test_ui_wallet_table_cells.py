"""Regression tests for estimate labels in the live-copy wallet table."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


@unittest.skipUnless(
    (Path(__file__).with_name("HL_Copy_App_SSOT.py")).is_file(),
    "wallet table source is not available",
)
class WalletTableEstimateLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = Path(__file__).with_name("HL_Copy_App_SSOT.py").read_text(encoding="utf-8")
        match = re.search(
            r"function renderWallets\(\)\s*\{(?P<body>.*?)\n\}\nfunction walletDetailHtml",
            source,
            re.DOTALL,
        )
        if match is None:
            raise AssertionError("renderWallets() was not found in the wallet table template")
        cls.wallet_renderer = match.group("body")

    def test_open_pnl_cell_marks_estimate(self) -> None:
        self.assertIn("Open (est.):", self.wallet_renderer)

    def test_exposure_cell_marks_estimate(self) -> None:
        self.assertIn("Exposure (est.):", self.wallet_renderer)

    def test_drawdown_cell_marks_estimate(self) -> None:
        self.assertIn("DD (est.):", self.wallet_renderer)

    def test_max_drawdown_cell_marks_estimate(self) -> None:
        self.assertIn("MaxDD (est.):", self.wallet_renderer)


if __name__ == "__main__":
    unittest.main()
