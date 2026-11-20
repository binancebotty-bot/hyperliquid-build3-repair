from pathlib import Path
import re
import unittest


SOURCE = Path(__file__).with_name("HL_Copy_App_SSOT.py").read_text(encoding="utf-8")
DETAIL = re.search(r"function walletDetailHtml\(wallet\)\{(?P<body>.*?)\n\}", SOURCE, re.S).group("body")


class WalletDetailAttributionTests(unittest.TestCase):
    def test_account_wide_positions_are_labeled_in_wallet_detail(self):
        self.assertIn("B — Account-wide Open Positions", DETAIL)

    def test_account_wide_pnl_is_labeled_in_wallet_detail(self):
        self.assertIn("Account closed:", DETAIL)
        self.assertIn("Account open:", DETAIL)
        self.assertIn("Account net:", DETAIL)


if __name__ == "__main__":
    unittest.main()
