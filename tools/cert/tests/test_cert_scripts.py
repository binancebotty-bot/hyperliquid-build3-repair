#!/usr/bin/env python3
"""Tests for the J4 offline certification scripts (tools/cert/*.py).

Every test drives a script as ONE command (subprocess) against a fixture and asserts
both the process exit code and the single verdict line, because that is the contract
the J4 run specs promise the PC operator:

    PASS -> exit 0,  FAIL -> exit 1,  INCONCLUSIVE -> exit 3, verdict line last.

The pure decision functions are unit-tested too, so the gates can be checked without
building multi-hundred-MB fixtures (the live-size files stay a PC-side measurement).

Run:  C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe -u \
          tools/cert/tests/test_cert_scripts.py
      (or `python -m unittest tools.cert.tests.test_cert_scripts` from the repo root)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CERT = HERE.parent
FIX = CERT / 'fixtures'
REPO = CERT.parents[1]
CORE = REPO / '_archive' / 'hl_stage2'


def run(script, *args, expect_env=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith('PYTHON')} if expect_env else dict(os.environ)
    env['HL_LIVE_ENV_FILE'] = '/nonexistent'  # never load a real .env with keys
    proc = subprocess.run([sys.executable, '-u', str(CERT / script), *[str(a) for a in args]],
                          capture_output=True, text=True, env=env, cwd=str(CERT), timeout=600)
    lines = [ln for ln in (proc.stdout or '').splitlines() if ln.strip()]
    return proc.returncode, lines


def load_module(name):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, CERT / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Gap1OutageClassifier(unittest.TestCase):
    AUD = FIX / 'audit_outage'
    WIN = ('--stop-ms', 1791705404255, '--restart-ms', 1791705404441, '--blocked-coins', 'SOL')

    def test_covered_window_passes(self):
        rc, lines = run('cert_outage_classify.py', '--audit-dir', self.AUD, '--leader-fills',
                        FIX / 'fills_ok.json', *self.WIN)
        self.assertEqual(rc, 0, lines)
        self.assertTrue(lines[-1].startswith('GAP1_RESULT:: PASS'), lines[-1])
        self.assertIn('missed=0 duplicates=0', lines[-1])

    def test_missed_fill_fails(self):
        rc, lines = run('cert_outage_classify.py', '--audit-dir', self.AUD, '--leader-fills',
                        FIX / 'fills_missing.json', *self.WIN)
        self.assertEqual(rc, 1, lines)
        self.assertTrue(lines[-1].startswith('GAP1_RESULT:: FAIL'), lines[-1])
        self.assertIn('missed=1', lines[-1])

    def test_double_copy_fails(self):
        rc, lines = run('cert_outage_classify.py', '--audit-dir', self.AUD, '--leader-fills',
                        FIX / 'fills_dup.json', *self.WIN)
        self.assertEqual(rc, 1, lines)
        self.assertIn('duplicates=1', lines[-1])

    def test_empty_window_is_inconclusive_not_pass(self):
        rc, lines = run('cert_outage_classify.py', '--audit-dir', self.AUD, '--leader-fills',
                        FIX / 'fills_empty.json')
        self.assertEqual(rc, 3, lines)
        self.assertIn('INCONCLUSIVE', lines[-1])

    def test_decide(self):
        mod = load_module('cert_outage_classify')
        self.assertTrue(mod.decide(0, 0))
        self.assertFalse(mod.decide(1, 0))
        self.assertFalse(mod.decide(0, 1))


class Gap2MemoryScan(unittest.TestCase):
    def test_small_audit_copy_passes(self):
        rc, lines = run('cert_memory_scan.py', '--audit-dir', FIX / 'audit_small', '--core-dir', CORE)
        self.assertEqual(rc, 0, lines)
        self.assertTrue(lines[-1].startswith('GAP2_RESULT:: PASS'), lines[-1])
        self.assertIn('max_retained_full_mb=', lines[-1])

    def test_gate_fires_above_threshold(self):
        mod = load_module('cert_memory_scan')
        self.assertTrue(mod.decide(1.0, 1.0, 1.0, 10.0, 15.0))
        self.assertFalse(mod.decide(11.0, 1.0, 1.0, 10.0, 15.0))   # retained_mb > 10
        self.assertFalse(mod.decide(1.0, 1.0, 16.0, 10.0, 15.0))   # rss_delta_mb > 15

    def test_missing_audit_dir_is_inconclusive(self):
        rc, lines = run('cert_memory_scan.py', '--audit-dir', FIX / 'nope', '--core-dir', CORE)
        self.assertEqual(rc, 3, lines)
        self.assertIn('INCONCLUSIVE', lines[-1])


class Gap3LiqParity(unittest.TestCase):
    def test_parity_holds(self):
        rc, lines = run('cert_liq_parity_offline.py', '--audit-dir', FIX / 'liq_ok')
        self.assertEqual(rc, 0, lines)
        self.assertTrue(lines[-1].startswith('GAP3_RESULT:: PASS'), lines[-1])
        self.assertIn('positions_checked=2 unchecked=0', lines[-1])

    def test_follower_closer_to_liq_fails(self):
        rc, lines = run('cert_liq_parity_offline.py', '--audit-dir', FIX / 'liq_violation')
        self.assertEqual(rc, 1, lines)
        self.assertIn('GAP3_RESULT:: FAIL', lines[-1])

    def test_unchecked_position_fails(self):
        rc, lines = run('cert_liq_parity_offline.py', '--audit-dir', FIX / 'liq_unchecked')
        self.assertEqual(rc, 1, lines)
        self.assertIn('unchecked=1', lines[-1])

    def test_missing_input_is_inconclusive(self):
        rc, lines = run('cert_liq_parity_offline.py', '--audit-dir', FIX / 'liq_missing')
        self.assertEqual(rc, 3, lines)
        self.assertIn('INCONCLUSIVE_NO_DATA', lines[-1])

    def test_json_mode_leaves_one_stdout_json_line_before_verdict(self):
        rc, lines = run('cert_liq_parity_offline.py', '--audit-dir', FIX / 'liq_ok', '--json')
        self.assertEqual(rc, 0, lines)
        payload = json.loads(lines[0])
        self.assertEqual(payload['checked'], 2)
        self.assertTrue(lines[-1].startswith('GAP3_RESULT:: PASS'), lines[-1])

    def test_wiring_line_reports_unwired_snapshot(self):
        rc, lines = run('cert_liq_parity_offline.py', '--audit-dir', FIX / 'liq_ok')
        wiring = [ln for ln in lines if ln.startswith('GAP3_GAP:: WIRING')]
        self.assertTrue(wiring, lines)
        self.assertIn('exchange_reported_liquidation_px_used=False', wiring[0])
        self.assertIn('liq_parity_blocked_rows=1', wiring[0])


@unittest.skipUnless(os.name == 'nt' and shutil.which('icacls'), 'needs Windows + icacls')
class Gap5DiskGuard(unittest.TestCase):
    def test_denied_append_fails_loudly_and_recovers(self):
        work = Path(os.environ.get('TMPDIR', '.')) / 'k2_disk_guard_test'
        shutil.rmtree(work, ignore_errors=True)
        rc, lines = run('cert_disk_guard.py', '--audit-dir', FIX / 'audit_small',
                        '--core-dir', CORE, '--work-dir', work)
        shutil.rmtree(work, ignore_errors=True)
        self.assertEqual(rc, 0, lines)
        self.assertTrue(lines[-1].startswith('GAP5_RESULT:: PASS'), lines[-1])
        self.assertIn('append_failed_loudly=yes', lines[-1])
        self.assertIn('error_logged=yes', lines[-1])

    def test_decide(self):
        mod = load_module('cert_disk_guard')
        self.assertTrue(mod.decide(True, True, True, True, True))
        self.assertFalse(mod.decide(True, False, True, True, True))   # append did not raise
        self.assertFalse(mod.decide(True, True, True, True, False))   # rows not exact


class ExportLeaderFills(unittest.TestCase):
    """The one network step: its wallet selection and JSON shape are tested offline;
    the HTTP call itself is not (that is the PC operator's read-only export)."""

    def test_wallet_selection_uses_only_live_and_clo(self):
        mod = load_module('export_leader_fills')
        cfg = json.loads((FIX / 'live_config_copy.json').read_text(encoding='utf-8'))
        self.assertEqual(mod.wallets(cfg), ['0x1111111111111111111111111111111111111111'])

    def test_list_form_config(self):
        mod = load_module('export_leader_fills')
        w = mod.wallets({'wallets': [{'address': '0xAAA', 'mode': 'LIVE'},
                                     {'address': '0xBBB', 'mode': 'OFF'},
                                     {'wallet': '0xCCC', 'mode': 'CLO'}]})
        self.assertEqual(w, ['0xAAA', '0xCCC'])


def _report_total(result):
    total = result.testsRun
    failed = len(result.failures) + len(result.errors) + len(getattr(result, 'unexpectedSuccesses', []))
    print('TOTAL=%d FAILED=%d' % (total, failed))
    return failed


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(1 if _report_total(res) else 0)
