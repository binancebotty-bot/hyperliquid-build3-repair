from pathlib import Path
import unittest


class SendingBannerTests(unittest.TestCase):
    def test_sending_banner_uses_effective_sending_state(self):
        source = Path(__file__).with_name("HL_Copy_App_SSOT.py").read_text(encoding="utf-8")

        self.assertIn(
            "const armed=lcAudit.effective_real_orders_enabled===true;",
            source,
        )
        self.assertIn(
            "set('lcBannerSending',armed?'ON':'OFF',armed?'lc-green':'lc-grey',armed?'real orders are being sent':'sending is switched off (a choice, not a fault)');",
            source,
        )


if __name__ == "__main__":
    unittest.main()
