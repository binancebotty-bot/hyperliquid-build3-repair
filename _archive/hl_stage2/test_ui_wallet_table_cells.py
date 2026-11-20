"""Wallet-table estimates are labeled without changing wallet-detail cells."""
from pathlib import Path
import unittest


SOURCE = Path(__file__).with_name("HL_Copy_App_SSOT.py").read_text(encoding="utf-8")
WALLET_ROWS = SOURCE.split("function renderWallets(){", 1)[1].split("function walletDetailHtml(wallet){", 1)[0]
WALLET_DETAIL = SOURCE.split("function walletDetailHtml(wallet){", 1)[1]


class WalletTableCellLabelsTest(unittest.TestCase):
    def test_wallet_table_labels_open_exposure_and_drawdown_as_estimates(self):
        for label in ("Open (est.):", "Exposure (est.):", "DD (est.):", "MaxDD (est.):"):
            with self.subTest(label=label):
                self.assertIn(label, WALLET_ROWS)

    def test_wallet_detail_cells_keep_their_existing_labels(self):
        self.assertIn("Open: <b", WALLET_DETAIL)
        self.assertIn("Exposure: <b", WALLET_DETAIL)
        self.assertIn("DD: <b", WALLET_DETAIL)
        self.assertIn("MaxDD: <b", WALLET_DETAIL)
        self.assertNotIn("(est.)", WALLET_DETAIL)


if __name__ == "__main__":
    unittest.main()
