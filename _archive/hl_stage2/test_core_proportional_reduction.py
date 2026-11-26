import os, tempfile, unittest
os.environ.update({"HL_LIVE_AUDIT_DIR": tempfile.mkdtemp(), "HL_LIVE_ENV_FILE": "missing.env", "HL_LIVE_SCOPE_SWEEP_THREAD": "0"})
import HL_Live_Copy_Service_Core as c

W = "0x" + "a" * 40

class ProportionalReductionRegression(unittest.TestCase):
    def setup_builder(self, follower_position):
        cfg = c.ConfigManager()
        cfg.wallet_cfg = lambda _w: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12.0}
        cfg.wallet_enabled = lambda _w: True
        cfg.wallet_mode = lambda _w: "ON"
        cfg.copy_mode = lambda _w: "fixed"
        cfg.fixed_notional = lambda _w: 12.0
        cfg.is_symbol_allowed = lambda _coin: (True, "")
        ledger = c.ManualLedger()
        sleeve = ledger.sleeve(W, "BTC")
        sleeve.update({"signed_size": follower_position, "direction": "LONG" if follower_position > 0 else "SHORT", "position_id": "p", "opened_by_intent_id": "i"})
        return c.IntentBuilder(cfg, ledger)

    def intent(self, builder, leader_start, leader_size):
        fill = c.LeaderFill("f", W, "BTC", "SELL", 100.0, leader_size, c.utc_now_ms(), "TEST", 0,
                            {"startPosition": str(leader_start), "dir": "Close Long"})
        return builder.build(fill)

    def test_partial_leader_reduction_scales_follower_reduction(self):
        builder = self.setup_builder(10.0)
        intent = self.intent(builder, 4.0, 2.0)
        self.assertAlmostEqual(intent.copy_size, 5.0)
        self.assertTrue(intent.reduce_only_intended)
        self.assertLessEqual(intent.copy_size, abs(intent.wallet_position_before))

    def test_reduction_never_crosses_zero(self):
        builder = self.setup_builder(3.0)
        intent = self.intent(builder, 4.0, 3.0)
        self.assertLessEqual(intent.copy_size, 3.0)
        self.assertGreaterEqual(intent.wallet_position_before + c.ManualLedger.signed_delta(intent.copy_side, intent.copy_size), 0.0)
        self.assertTrue(intent.reduce_only_intended)

    def test_full_close_only_when_leader_fill_flattens_leader(self):
        partial = self.intent(self.setup_builder(10.0), 4.0, 2.0)
        full = self.intent(self.setup_builder(10.0), 2.0, 2.0)
        self.assertEqual(partial.copy_size, 5.0)
        self.assertEqual(full.copy_size, 10.0)
        self.assertTrue(full.reduce_only_intended)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProportionalReductionRegression)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"TOTAL={result.testsRun} FAILED={len(result.failures)+len(result.errors)}")
    raise SystemExit(not result.wasSuccessful())
