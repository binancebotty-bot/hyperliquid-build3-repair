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

    def test_missing_start_position_skips_reduction(self):
        builder = self.setup_builder(10.0)
        fill = c.LeaderFill("f", W, "BTC", "SELL", 100.0, 2.0, c.utc_now_ms(), "TEST", 0,
                            {"dir": "Close Long"})
        intent = builder.build(fill)
        self.assertEqual(intent.decision, "UNRESOLVED")
        self.assertEqual(intent.copy_size, 0.0)
        self.assertFalse(intent.reduce_only_intended)

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

    def test_malformed_start_position_is_unresolved(self):
        builder = self.setup_builder(10.0)
        fill = c.LeaderFill("f", W, "BTC", "SELL", 100.0, 2.0, c.utc_now_ms(), "TEST", 0,
                            {"startPosition": "NaN", "dir": "Close Long"})
        intent = builder.build(fill)
        self.assertEqual(intent.decision, "UNRESOLVED")
        self.assertEqual(intent.copy_size, 0.0)
        self.assertFalse(intent.reduce_only_intended)

    def test_flip_build_all_returns_reduce_then_fixed_notional_open(self):
        builder = self.setup_builder(10.0)
        fill = c.LeaderFill("flip", W, "BTC", "SELL", 100.0, 6.0, c.utc_now_ms(), "TEST", 0,
                            {"startPosition": "4", "dir": "Open Short"})
        intents = builder.build_all(fill)
        self.assertEqual(len(intents), 2)
        self.assertEqual(intents[0].copy_size, 10.0)
        self.assertTrue(intents[0].reduce_only_intended)
        self.assertEqual(intents[1].copy_notional, 12.0)
        self.assertFalse(intents[1].reduce_only_intended)

    def test_production_fill_handler_processes_and_sends_flip_intents_in_order(self):
        builder = self.setup_builder(10.0)
        fill = c.LeaderFill("flip", W, "BTC", "SELL", 100.0, 6.0, c.utc_now_ms(), "TEST", 0,
                            {"startPosition": "4", "dir": "Open Short"})
        close_open = []
        sent = []
        class Builder:
            def build_all(self, _fill): return builder.build_all(_fill)
            def blocked_locally(self, *_args): return ""
        class Audit:
            def append_order_intent(self, intent): close_open.append(("persist", intent.reduce_only_intended))
            def has_fill_row(self, _fill_id): return True
        class Dedupe:
            live_start_ms = 0
            processed = set()
            def accept_leader(self, _fid): return True
            def confirm_leader(self, _fid): pass
        class Sender:
            def resting_entries_against(self, _fill): return []
            def cancel_resting_entries_against(self, _fill): return []
            def send_if_allowed(self, intent, _reason):
                sent.append(intent.reduce_only_intended)
                return False, "BLOCKED_TEST"
        core = c.LiveCopyCore.__new__(c.LiveCopyCore)
        core.intent_builder = Builder()
        core.intents_by_id = {}
        core.dedupe = Dedupe()
        core.audit = Audit()
        core.sender = Sender()
        core._intent_inserts = 0
        core._past_send_keys = set()
        core._guard_key = lambda _fill: "guard"
        core._defer_unreadable_truth = lambda *_args: False
        core._append_send_terminal = lambda *_args: None
        core._process_leader_fill = lambda *_args: None
        # Exercise the production caller directly with its lock and lifecycle dependencies bypassed.
        core._send_lock = __import__("threading").Lock()
        core._idem_lock = __import__("threading").Lock()
        core._idem_accepted = set()
        core._idem_duplicate_audited = set()
        core._leader_fill_seen_locked = lambda *_args: False
        core.cfg = type("Cfg", (), {"send_mode_now": lambda _self: "OFF"})()
        core.ledger = type("Ledger", (), {"classify_leader_side_for_wallet": lambda *_args: ("OPEN", "")})()
        core._prewarm_with_parity = lambda *_args: None
        core._read_fills_of_withdrawn_limits = lambda *_args: None
        core._apply_fills_of_withdrawn_limits = lambda *_args: None
        core._send_lock = type("Lock", (), {"__enter__": lambda _s: None, "__exit__": lambda *_a: None})()
        result = core._handle_leader_fill(fill, None, "", "guard", [], False, set())
        self.assertEqual(close_open, [("persist", True), ("persist", False)])
        self.assertEqual(sent, [True, False])

    def test_reversal_does_not_close_follower_more_than_leader_reduction(self):
        builder = self.setup_builder(10.0)
        intent = self.intent(builder, 2.0, 3.0)
        self.assertEqual(intent.decision, "UNRESOLVED")
        self.assertEqual(intent.copy_size, 0.0)
        self.assertFalse(intent.reduce_only_intended)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ProportionalReductionRegression)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(f"TOTAL={result.testsRun} FAILED={len(result.failures)+len(result.errors)}")
    raise SystemExit(not result.wasSuccessful())
