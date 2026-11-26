#!/usr/bin/env python3
"""Two leaders, one follower account, one coin: per-leader share accounting.

Run: python test_core_shared_follower_leader_attribution.py   # no network, no orders.

The follower account holds ONE net position per coin; the ledger owns a signed sleeve
per leader (by_wallet[leader][coin]). These tests drive the real ManualLedger and
IntentBuilder production methods: a fill for leader A only moves A's sleeve, an
opposite-side leader's reduction cannot consume A's share, A's close never generates
an order larger than A's share, and the follower net is the signed sum of sleeves.
"""
import os
import tempfile
import unittest
from pathlib import Path

TMP = tempfile.mkdtemp(prefix="shared_follower_attrib_")
os.environ.update({
    "HL_LIVE_AUDIT_DIR": TMP,
    "HL_LIVE_ENV_FILE": os.path.join(TMP, "missing.env"),
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
})
import HL_Live_Copy_Service_Core as c

A = "0x" + "a" * 40
B = "0x" + "b" * 40
COIN = "BTC"
PX = 100.0
TOL = 1e-9


class SharedFollowerAttribution(unittest.TestCase):
    def setUp(self):
        # Offline follower mid so real IntentBuilder.build() prices entries without a network read.
        c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {COIN: str(PX)}
        c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)
        self.ledger = c.ManualLedger(path=Path(TMP) / ("ledger_%s.json" % self._testMethodName))
        # Config knobs only; ledger and intent builder under test are the real classes.
        cfg = c.ConfigManager()
        cfg.wallet_cfg = lambda _w: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 0.0}
        cfg.wallet_enabled = lambda _w: True
        cfg.wallet_mode = lambda _w: "ON"
        cfg.copy_mode = lambda _w: "fixed"
        self.current_notional = 0.0
        cfg.fixed_notional = lambda _w: self.current_notional
        cfg.is_symbol_allowed = lambda _coin: (True, "")
        cfg.min_notional = lambda: 0.0
        cfg.max_order_notional = lambda: 1e9
        cfg.max_wallet_exposure = lambda _w: 0.0
        cfg.max_total_exposure = lambda: 0.0
        cfg.max_asset_directional_exposure = lambda: 0.0
        cfg.marketable_bps = lambda: 0.0
        self.cfg = cfg
        self.seq = 0

    # -- helpers (every ledger mutation goes through real production methods) -----------------------
    def fill(self, wallet, side, size, raw, expected_share=None, expected_before=None):
        self.seq += 1
        fid = "%s_f%d" % (self._testMethodName, self.seq)
        leader_fill = c.LeaderFill(fid, wallet, COIN, side, PX, size, c.utc_now_ms(), "TEST", 0, raw)
        self.current_notional = size * PX
        intent = c.IntentBuilder(self.cfg, self.ledger).build(leader_fill)
        self.assertTrue(intent.send_allowed, "intent not sendable: %s / %s" % (intent.decision, intent.reason))
        if expected_before is not None:
            self.assertAlmostEqual(intent.wallet_position_before, expected_before, delta=TOL)
        if expected_share is not None:
            self.assertAlmostEqual(intent.copy_size, expected_share, delta=TOL)
        self.ledger.apply_copy_fill(intent, {
            "side": intent.copy_side, "sz": str(intent.copy_size), "px": str(PX), "hash": fid,
        })
        return intent

    def open(self, wallet, side, size):
        raw = {"dir": "Open Long" if side == "BUY" else "Open Short"}
        return self.fill(wallet, side, size, raw, expected_share=size)

    def reduce(self, wallet, side, size, start, expected_share):
        raw = {"startPosition": str(start), "dir": "Close Long" if side == "SELL" else "Close Short"}
        return self.fill(wallet, side, size, raw, expected_share=expected_share)

    def sleeve(self, wallet):
        return self.ledger.wallet_coin_position(wallet, COIN)

    def assert_sum_invariant(self):
        signed_sum = sum(float(s[COIN]["signed_size"]) for s in self.ledger.data["by_wallet"].values() if COIN in s)
        self.assertAlmostEqual(self.ledger.coin_net(COIN), signed_sum, delta=TOL)

    # -- 1: same coin, same side: A's fills never move B's sleeve ------------------------------------
    def test_1_same_side_fill_only_moves_the_filling_leaders_sleeve(self):
        self.open(A, "BUY", 2.0)
        self.open(B, "BUY", 3.0)
        self.assertAlmostEqual(self.sleeve(A), 2.0, delta=TOL)
        self.assertAlmostEqual(self.sleeve(B), 3.0, delta=TOL)

        self.fill(A, "BUY", 1.0, {"dir": "Open Long"}, expected_share=1.0, expected_before=2.0)
        self.assertAlmostEqual(self.sleeve(A), 3.0, delta=TOL)
        self.assertAlmostEqual(self.sleeve(B), 3.0, delta=TOL)  # B untouched by A's fill

        self.reduce(A, "SELL", 1.0, start=3.0, expected_share=1.0)
        self.assertAlmostEqual(self.sleeve(A), 2.0, delta=TOL)
        self.assertAlmostEqual(self.sleeve(B), 3.0, delta=TOL)  # B untouched by A's reduction
        self.assertAlmostEqual(self.ledger.coin_net(COIN), 5.0, delta=TOL)
        self.assert_sum_invariant()

    # -- 2: opposite sides: one leader's reduction cannot consume the other's opposing share --------
    def test_2_opposite_side_reduction_does_not_consume_other_leaders_share(self):
        self.open(A, "BUY", 2.0)
        self.open(B, "SELL", 3.0)  # opposite sleeve on the same coin, same follower account
        self.assertAlmostEqual(self.sleeve(A), 2.0, delta=TOL)
        self.assertAlmostEqual(self.sleeve(B), -3.0, delta=TOL)
        self.assertAlmostEqual(self.ledger.coin_net(COIN), -1.0, delta=TOL)

        # B covers 1 of its own 3: sizing must use B's sleeve (-3), not the account net (-1).
        it = self.reduce(B, "BUY", 1.0, start=-3.0, expected_share=1.0)
        self.assertAlmostEqual(it.wallet_position_before, -3.0, delta=TOL)
        self.assertTrue(it.reduce_only_intended)
        self.assertAlmostEqual(self.sleeve(A), 2.0, delta=TOL)  # A's opposing share intact
        self.assertAlmostEqual(self.sleeve(B), -2.0, delta=TOL)
        self.assertAlmostEqual(self.ledger.coin_net(COIN), 0.0, delta=TOL)

        # A reduces 1 of its own 2; B's short sleeve is untouched.
        self.reduce(A, "SELL", 1.0, start=2.0, expected_share=1.0)
        self.assertAlmostEqual(self.sleeve(A), 1.0, delta=TOL)
        self.assertAlmostEqual(self.sleeve(B), -2.0, delta=TOL)
        self.assertAlmostEqual(self.ledger.coin_net(COIN), -1.0, delta=TOL)
        self.assert_sum_invariant()

    # -- 3: A's full close generates at most A's share; remainder is exactly B's share --------------
    def test_3_full_close_leaves_exactly_the_other_leaders_share(self):
        self.open(A, "BUY", 2.0)
        self.open(B, "BUY", 2.0)
        self.assertAlmostEqual(self.ledger.coin_net(COIN), 4.0, delta=TOL)

        a_share_before = self.sleeve(A)
        b_share_before = self.sleeve(B)
        it = self.reduce(A, "SELL", 2.0, start=2.0, expected_share=a_share_before)
        # No generated order may close more than the closing leader's own share.
        self.assertLessEqual(it.copy_size, a_share_before + TOL)
        self.assertAlmostEqual(it.wallet_position_before, a_share_before, delta=TOL)
        self.assertTrue(it.reduce_only_intended)

        self.assertAlmostEqual(self.sleeve(A), 0.0, delta=TOL)
        self.assertAlmostEqual(self.sleeve(B), b_share_before, delta=TOL)
        self.assertAlmostEqual(self.ledger.coin_net(COIN), b_share_before, delta=TOL)
        self.assert_sum_invariant()

    # -- 4: total follower position == signed sum of per-leader sleeves at every step ---------------
    def test_4_follower_net_equals_signed_sum_of_sleeves_every_step(self):
        steps = [
            ("openA", A, "BUY", 2.0, None, None),
            ("openB", B, "BUY", 3.0, None, None),
            ("addB", B, "BUY", 1.0, None, None),
            ("cutA", A, "SELL", 1.0, 2.0, 1.0),
            ("closeB", B, "SELL", 4.0, 4.0, 4.0),
            ("openShortB", B, "SELL", 2.0, None, None),
            ("coverB", B, "BUY", 2.0, -2.0, 2.0),
            ("closeA", A, "SELL", 1.0, 1.0, 1.0),
        ]
        for name, wallet, side, size, start, expect_share in steps:
            if start is None:
                self.open(wallet, side, size)
            else:
                self.reduce(wallet, side, size, start=start, expected_share=expect_share)
            expected = sum(self.sleeve(w) for w in (A, B))
            self.assertAlmostEqual(self.ledger.coin_net(COIN), expected, delta=TOL, msg="at " + name)
            self.assert_sum_invariant()
        self.assertAlmostEqual(self.sleeve(A), 0.0, delta=TOL)
        self.assertAlmostEqual(self.sleeve(B), 0.0, delta=TOL)
        self.assertAlmostEqual(self.ledger.coin_net(COIN), 0.0, delta=TOL)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SharedFollowerAttribution)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("TOTAL=%d FAILED=%d" % (result.testsRun, len(result.failures) + len(result.errors)))
    raise SystemExit(not result.wasSuccessful())
