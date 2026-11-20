"""Wallet detail cells must use exchange/account truth, not replay aliases."""
from pathlib import Path
import re
import unittest


SOURCE = Path(__file__).with_name("HL_Copy_App_SSOT.py").read_text(encoding="utf-8")
DETAIL = re.search(r"function walletDetailHtml\(wallet\)\{(?P<body>.*?)\n\}", SOURCE, re.S).group("body")


class WalletDetailCellTests(unittest.TestCase):
    def test_wallet_detail_pnl_cells_use_account_reconciliation(self):
        self.assertIn("const actual=lcAudit.account_reconciliation||{}", DETAIL)
        self.assertIn("actual.exchange_realized_pnl_since_baseline", DETAIL)
        self.assertIn("actual.exchange_unrealized_pnl", DETAIL)
        self.assertIn("actual.net_account_value_change_unadjusted", DETAIL)
        self.assertNotIn("perf.live_realized_pnl", DETAIL)
        self.assertNotIn("perf.live_unrealized_pnl", DETAIL)
        self.assertNotIn("perf.live_net_pnl", DETAIL)

    def test_wallet_detail_open_positions_use_exchange_account_snapshot(self):
        self.assertIn("const openPos=(lcAudit.exchange_account_snapshot||{}).open_positions||[]", DETAIL)
        self.assertNotIn("perf.current_open_positions", DETAIL)


if __name__ == "__main__":
    unittest.main()
