import os, tempfile, unittest
os.environ.update({"HL_LIVE_AUDIT_DIR": tempfile.mkdtemp(), "HL_LIVE_ENV_FILE": "missing.env", "HL_LIVE_SCOPE_SWEEP_THREAD": "0"})
import HL_Live_Copy_Service_Core as c

W = "0x" + "a" * 40

class SizingRegression(unittest.TestCase):
    def test_merged_fill_count_is_not_a_notional_multiplier(self):
        cfg = c.ConfigManager()
        cfg.wallet_cfg = lambda _w: {"copy_mode": "fixed", "fixed_notional": 12.0}
        cfg.copy_mode = lambda _w: "fixed"
        cfg.fixed_notional = lambda _w: 12.0
        builder = object.__new__(c.IntentBuilder); builder.cfg = cfg
        one = c.LeaderFill("1", W, "BTC", "BUY", 100, 1, 1, "TEST", 0, {"merged_fill_count": 1})
        many = c.LeaderFill("14", W, "BTC", "BUY", 100, 1, 1, "TEST", 0, {"merged_fill_count": 14})
        self.assertEqual(builder._copy_notional(W, one), builder._copy_notional(W, many))

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SizingRegression)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"TOTAL={result.testsRun} FAILED={len(result.failures)+len(result.errors)}")
    raise SystemExit(not result.wasSuccessful())
