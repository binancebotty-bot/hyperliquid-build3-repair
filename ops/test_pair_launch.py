#!/usr/bin/env python3
"""Pair-launch seeding: the behaviours that must hold before an engine may start on a fresh dir.

FAILING FIRST: written before the launcher features exist, so every check below that names a
missing capability fails on the current code. Run: python ops/test_pair_launch.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED_TOOL = HERE / 'seed_pair_state.py'
SEED = HERE / 'live_config_seed.json'
PY = sys.executable
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:160]) if not ok else ''))


def run(args, cwd=None):
    return subprocess.run([PY, str(SEED_TOOL), *args], capture_output=True, text=True, cwd=cwd)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# 1. a seed kept INSIDE a state dir must be rejected: the seed is the thing that must survive a wipe
state = Path(tempfile.mkdtemp(prefix='pairlaunch_'))
inside = state / 'live_config_seed.json'
shutil.copy(SEED, inside)
r = run(['--state-dir', str(state), '--seed', str(inside), '--start-ms', '1792968600000'])
check('LAUNCH_REJECTS_SEED_INSIDE_STATE_DIR',
      r.returncode != 0 and 'inside' in (r.stdout + r.stderr).lower(), r.stdout[-160:])

# 2. every run writes a config change log naming the hashes before and after
state2 = Path(tempfile.mkdtemp(prefix='pairlaunch2_'))
r = run(['--state-dir', str(state2), '--seed', str(SEED), '--start-ms', '1792968600000'])
log = Path(os.environ.get('PAIR_LAUNCH_LOG', str(Path.home() / '.hermes' / 'state' / 'pair_launch.log')))
logged = log.exists() and 'config_sha_before' in log.read_text(encoding='utf-8', errors='replace')
check('LAUNCH_WRITES_CHANGE_LOG_WITH_HASHES', r.returncode == 0 and logged, 'log=%s rc=%s' % (log, r.returncode))

# 3. the written config's hash is reported and matches the file on disk
cfg = state2 / 'live_config.json'
same = cfg.exists() and sha(cfg) in (r.stdout + (log.read_text(encoding='utf-8', errors='replace') if logged else ''))
check('LAUNCH_REPORTS_WRITTEN_CONFIG_HASH', same, 'cfg exists=%s' % cfg.exists())

# 4. a tampered seed (cap removed) is refused loudly, and nothing is written
state3 = Path(tempfile.mkdtemp(prefix='pairlaunch3_'))
bad = json.loads(SEED.read_text(encoding='utf-8'))
bad['global_controls'].pop('max_total_live_exposure_usd', None)
badseed = state3.parent / (state3.name + '_bad.json')
badseed.write_text(json.dumps(bad), encoding='utf-8')
r = run(['--state-dir', str(state3), '--seed', str(badseed), '--start-ms', '1792968600000'])
check('LAUNCH_REFUSES_SEED_MISSING_CAPS',
      r.returncode != 0 and not (state3 / 'live_config.json').exists(), r.stdout[-160:])

# 5. a config hash mismatch AFTER writing (someone edits mid-flight) aborts
state4 = Path(tempfile.mkdtemp(prefix='pairlaunch4_'))
run(['--state-dir', str(state4), '--seed', str(SEED), '--start-ms', '1792968600000'])  # seed it first
r = run(['--state-dir', str(state4), '--seed', str(SEED), '--start-ms', '1792968600000', '--verify-only'])
check('LAUNCH_SUPPORTS_VERIFY_ONLY', r.returncode == 0 and 'VERIFIED' in r.stdout, r.stdout[-120:])

# 6. seeding twice is refused (a second start must not silently rewrite cursors)
r = run(['--state-dir', str(state2), '--seed', str(SEED), '--start-ms', '1792968600000'])
check('LAUNCH_REFUSES_SECOND_SEED', r.returncode != 0, r.stdout[-120:])

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
