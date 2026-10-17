#!/usr/bin/env python3
"""Tests for tools/cert/verify_ledger_baseline.py (H2).

Four required end-to-end cases, each driven as ONE command against a temp audit
dir (so the verifier's CLI contract is tested, not just its functions):

    (a) MATCH        every coin's exchange net equals the engine net      -> PASS
    (b) KNOWN-only   every gap equals its baseline delta                  -> PASS, known=N
    (c) new-coin     one gapped coin is not in the baseline               -> FAIL (new)
    (d) moved-delta  a baseline coin's delta drifted away                 -> FAIL (moved)

Plus the order-cap change: the cap comes from the CONFIGURED value
(global_controls.max_order_notional_usd = 500 here) and a $300 entry fill passes
while a $600 one fails - the old hard-coded $50 would have failed the $300 fill.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CERT = HERE.parent
SCRIPT = CERT / 'verify_ledger_baseline.py'
BASELINE = CERT / 'baselines' / 'j14_2026-10-17.json'

BASE_COINS = {'AR': 1.47, 'ASTER': 16.0}


def run(*args):
    env = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON')}
    env['HL_LIVE_ENV_FILE'] = '/nonexistent'
    proc = subprocess.run([sys.executable, '-u', str(SCRIPT), *[str(a) for a in args]],
                          capture_output=True, text=True, env=env, cwd=str(CERT), timeout=120)
    lines = [ln for ln in (proc.stdout or '').splitlines() if ln.strip()]
    return proc.returncode, lines, (proc.stderr or '')


def build_audit(root, coins_engine, coins_exchange, cap=500.0, fills=None, config=True):
    d = Path(root)
    d.mkdir(parents=True, exist_ok=True)
    (d / 'manual_live_positions.json').write_text(json.dumps({
        'by_coin_net': {c: {'signed_size': s} for c, s in coins_engine.items()},
        'by_wallet': {}, 'schema': 1, 'updated_at': 'test',
    }), encoding='utf-8')
    (d / 'exchange_account_snapshot.json').write_text(json.dumps({
        'created_at': 'test', 'created_at_ms': 1, 'positions_by_coin': coins_exchange, 'raw': {},
    }), encoding='utf-8')
    if config:
        (d / 'live_config.json').write_text(json.dumps({
            'global_controls': {'max_order_notional_usd': cap, 'symbol_blocklist': ['HYPE']},
        }), encoding='utf-8')
    if fills is not None:
        (d / 'fills.json').write_text(json.dumps(fills), encoding='utf-8')
    return d


def write_baseline(root, coins, drift_tol=1e-6):
    p = Path(root) / 'baseline.json'
    p.write_text(json.dumps({'coins': coins, 'drift_tol': drift_tol}), encoding='utf-8')
    return p


class VerifierBaseline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='verif_h2_'))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, audit, baseline=None):
        args = ['--audit-dir', audit, '--exchange-snapshot', audit / 'exchange_account_snapshot.json']
        if baseline is not None:
            args += ['--baseline', baseline]
        if (audit / 'fills.json').is_file():
            args += ['--fills', audit / 'fills.json']
        return run(*args)

    def test_a_match_passes(self):
        aud = build_audit(self.tmp / 'a', {'BTC': 0.5, 'ETH': -2.0}, {'BTC': 0.5, 'ETH': -2.0})
        rc, lines, err = self._run(aud, write_baseline(self.tmp / 'a', {}))
        self.assertEqual(rc, 0, lines + [err])
        self.assertTrue(lines[-1].startswith('VERIFIER_RESULT:: PASS'), lines[-1])
        self.assertIn('new=0 moved=0', lines[-1])
        self.assertIn('known=0', lines[-1])
        self.assertFalse([ln for ln in lines if ln.endswith('MISMATCH')], lines)

    def test_b_known_only_gaps_pass(self):
        aud = build_audit(self.tmp / 'b', {'AR': -0.74, 'ASTER': 0.0}, {'AR': 0.73, 'ASTER': 16.0})
        rc, lines, err = self._run(aud, write_baseline(self.tmp / 'b', BASE_COINS))
        self.assertEqual(rc, 0, lines + [err])
        self.assertTrue(lines[-1].startswith('VERIFIER_RESULT:: PASS'), lines[-1])
        self.assertIn('known=2', lines[-1])
        self.assertIn('new=0 moved=0', lines[-1])
        known_rows = [ln for ln in lines if ln.rstrip().endswith('KNOWN')]
        self.assertEqual(len(known_rows), 2, lines)
        self.assertFalse([ln for ln in lines if ln.endswith('MISMATCH')], lines)

    def test_b2_real_j14_baseline_file_covers_its_own_coins(self):
        base = json.loads(BASELINE.read_text(encoding='utf-8'))
        coins = base['coins']
        eng = {c: 0.0 for c in coins}
        ex = {c: float(v) for c, v in coins.items()}
        aud = build_audit(self.tmp / 'b2', eng, ex)
        rc, lines, err = self._run(aud, BASELINE)
        self.assertEqual(rc, 0, lines + [err])
        self.assertIn('known=%d' % len(coins), lines[-1])
        self.assertTrue(lines[-1].startswith('VERIFIER_RESULT:: PASS'), lines[-1])

    def test_c_coin_outside_baseline_fails(self):
        aud = build_audit(self.tmp / 'c', {'AR': -0.74, 'BTC': 0.5}, {'AR': 0.73, 'BTC': 0.9})
        rc, lines, err = self._run(aud, write_baseline(self.tmp / 'c', BASE_COINS))
        self.assertEqual(rc, 1, lines + [err])
        self.assertTrue(lines[-1].startswith('VERIFIER_RESULT:: FAIL'), lines[-1])
        self.assertIn('new=1', lines[-1])
        self.assertIn('known=1', lines[-1])
        bad = [ln for ln in lines if ln.endswith('MISMATCH (new)')]
        self.assertEqual(len(bad), 1, lines)
        self.assertTrue(bad[0].startswith('BTC'), bad)

    def test_d_baseline_coin_whose_delta_moved_fails(self):
        aud = build_audit(self.tmp / 'd', {'AR': -0.74, 'ASTER': 0.0}, {'AR': 0.73, 'ASTER': 20.0})
        rc, lines, err = self._run(aud, write_baseline(self.tmp / 'd', BASE_COINS))
        self.assertEqual(rc, 1, lines + [err])
        self.assertTrue(lines[-1].startswith('VERIFIER_RESULT:: FAIL'), lines[-1])
        self.assertIn('moved=1', lines[-1])
        bad = [ln for ln in lines if ln.endswith('MISMATCH (moved)')]
        self.assertEqual(len(bad), 1, lines)
        self.assertTrue(bad[0].startswith('ASTER'), bad)

    def test_d2_drift_tolerance_from_baseline_file_is_honoured(self):
        aud = build_audit(self.tmp / 'd2', {'AR': -0.74, 'ASTER': 0.0}, {'AR': 0.73, 'ASTER': 20.0})
        rc, lines, err = self._run(aud, write_baseline(self.tmp / 'd2', BASE_COINS, drift_tol=10.0))
        self.assertEqual(rc, 0, lines + [err])
        self.assertIn('known=2', lines[-1])

    def test_e_cap_is_the_configured_500_not_the_stale_50(self):
        aud = build_audit(self.tmp / 'e', {'BTC': 0.0}, {'BTC': 0.0}, cap=500.0,
                          fills=[{'oid': 1, 'dir': 'Open Long', 'sz': 1.0, 'px': 300.0}])
        rc, lines, err = self._run(aud, write_baseline(self.tmp / 'e', {}))
        self.assertEqual(rc, 0, lines + [err])
        self.assertTrue(any('CONFIG order cap 500.00' in ln for ln in lines), lines)
        self.assertIn('over_cap=0', lines[-1])

    def test_f_entry_over_the_configured_cap_fails(self):
        aud = build_audit(self.tmp / 'f', {'BTC': 0.0}, {'BTC': 0.0}, cap=500.0,
                          fills=[{'oid': 2, 'dir': 'Open Long', 'sz': 1.0, 'px': 600.0}])
        rc, lines, err = self._run(aud, write_baseline(self.tmp / 'f', {}))
        self.assertEqual(rc, 1, lines + [err])
        self.assertIn('over_cap=1', lines[-1])

    def test_g_close_fill_is_exempt_from_the_cap(self):
        aud = build_audit(self.tmp / 'g', {'BTC': 0.0}, {'BTC': 0.0}, cap=500.0,
                          fills=[{'oid': 3, 'dir': 'Close Long', 'sz': 1.0, 'px': 6000.0}])
        rc, lines, err = self._run(aud, write_baseline(self.tmp / 'g', {}))
        self.assertEqual(rc, 0, lines + [err])
        self.assertIn('over_cap=0', lines[-1])

    def test_h_missing_configured_cap_is_inconclusive(self):
        aud = build_audit(self.tmp / 'h', {'BTC': 0.0}, {'BTC': 0.0}, config=False)
        rc, lines, err = self._run(aud, write_baseline(self.tmp / 'h', {}))
        self.assertEqual(rc, 3, lines + [err])
        self.assertTrue(lines[-1].startswith('VERIFIER_RESULT:: INCONCLUSIVE'), lines[-1])

    def test_i_blocked_coin_gap_is_known_refused_not_mismatch(self):
        aud = build_audit(self.tmp / 'i', {'HYPE': 0.0}, {'HYPE': 5.0})
        rc, lines, err = self._run(aud, write_baseline(self.tmp / 'i', {}))
        self.assertEqual(rc, 0, lines + [err])
        self.assertTrue(any('KNOWN_REFUSED' in ln for ln in lines), lines)
        self.assertFalse([ln for ln in lines if ln.endswith('MISMATCH')], lines)
        self.assertIn('refused=1', lines[-1])

    def test_j_no_baseline_file_means_every_gap_is_new(self):
        aud = build_audit(self.tmp / 'j', {'AR': -0.74}, {'AR': 0.73})
        rc, lines, err = self._run(aud, None)
        self.assertEqual(rc, 1, lines + [err])
        self.assertIn('new=1', lines[-1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
