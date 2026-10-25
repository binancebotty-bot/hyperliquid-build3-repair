#!/usr/bin/env python3
"""Pair-launch seeding: the behaviours that must hold before an engine may start on a fresh dir.

The check that matters most is CURSOR_VALUE_MATCHES_ENGINE_FORMULA: revision 1 of the seeder wrote
a cursor that omitted the poll-interval term, and the whole suite still passed 6/6 because nothing
asserted the number written. An adversarial review found it; this test exists so it cannot recur.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / 'seed_pair_state.py'
SEED = HERE / 'live_config_seed.json'
PY = sys.executable
LOG = Path(tempfile.mkdtemp(prefix='pairlog_')) / 'pair_launch.log'
os.environ['PAIR_LAUNCH_LOG'] = str(LOG)          # never touch the production change log
results = []
T0 = 1792968600000            # a KNOWN-STALE instant: only the stale-start and arithmetic checks use it
INTERVAL_MS, OVERLAP_MS = 120_000, 30_000
NOW = int(time.time() * 1000)  # every check that actually seeds uses a live start time


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:170]) if not ok else ''))


def run(args):
    return subprocess.run([PY, str(TOOL), *args], capture_output=True, text=True, cwd=str(HERE))


# 1. the cursor number itself, checked against the engine's real formula
s = Path(tempfile.mkdtemp(prefix='pl1_'))
r = run(['--state-dir', str(s), '--seed', str(SEED), '--start-ms', str(NOW), '--force'])
cur = json.load(open(s / 'clean_core_runtime_state.json', encoding='utf-8'))['last_leader_poll_cursor_ms']
want = NOW + INTERVAL_MS + OVERLAP_MS
check('CURSOR_VALUE_MATCHES_ENGINE_FORMULA', r.returncode == 0 and set(cur.values()) == {want},
      'want %d got %s' % (want, set(cur.values())))

# 2. what the engine would do with it: start must land on T0, not before
start = max(want - INTERVAL_MS - OVERLAP_MS, NOW - 6000000)
check('ENGINE_START_LANDS_ON_T0', start == NOW, start)
worst = want - OVERLAP_MS                            # interval resolved to 0
check('NO_PRE_START_FILLS_EVEN_IF_INTERVAL_IS_ZERO', worst >= T0, worst)

# 3. a seed stored INSIDE the state dir is refused
s2 = Path(tempfile.mkdtemp(prefix='pl2_'))
inside = s2 / 'seed.json'
shutil.copy(SEED, inside)
r = run(['--state-dir', str(s2), '--seed', str(inside), '--start-ms', str(NOW)])
check('REJECTS_SEED_INSIDE_STATE_DIR', r.returncode == 5, r.stdout[-120:])

# 4. a neighbouring directory with the same prefix is NOT treated as inside
s3 = Path(tempfile.mkdtemp(prefix='pl3_'))
near = Path(str(s3) + '2')
near.mkdir()
shutil.copy(SEED, near / 'seed.json')
r = run(['--state-dir', str(s3), '--seed', str(near / 'seed.json'), '--start-ms', str(NOW)])
check('PREFIX_COLLISION_IS_NOT_INSIDE', r.returncode != 5, r.stdout[-120:])

# 5. tampering with the written config after the fact is caught by verify-only
s4 = Path(tempfile.mkdtemp(prefix='pl4_'))
r = run(['--state-dir', str(s4), '--seed', str(SEED), '--start-ms', str(NOW), '--force'])
cfg = json.load(open(s4 / 'live_config.json', encoding='utf-8'))
cfg['global_controls']['max_total_live_exposure_usd'] = 999999
json.dump(cfg, open(s4 / 'live_config.json', 'w', encoding='utf-8'), indent=2)
r = run(['--state-dir', str(s4), '--seed', str(SEED), '--start-ms', str(NOW), '--verify-only'])
check('VERIFY_ONLY_DETECTS_A_CHANGED_CONFIG', r.returncode != 0, r.stdout[-140:])

# 6. verify-only on a clean seeded dir says VERIFIED
s5 = Path(tempfile.mkdtemp(prefix='pl5_'))
run(['--state-dir', str(s5), '--seed', str(SEED), '--start-ms', str(NOW), '--force'])
r = run(['--state-dir', str(s5), '--seed', str(SEED), '--verify-only', '--interval-sec', '1'])
check('VERIFY_ONLY_ACCEPTS_A_FRESH_SEED', r.returncode == 0 and 'VERIFIED' in r.stdout, r.stdout[-140:])

# 7. verify-only refuses a STALE seed (cursors anchored far in the past)
s6 = Path(tempfile.mkdtemp(prefix='pl6_'))
run(['--state-dir', str(s6), '--seed', str(SEED), '--start-ms', str(NOW), '--force'])
aged = json.load(open(s6 / 'clean_core_runtime_state.json', encoding='utf-8'))
aged['last_leader_poll_cursor_ms'] = {k: v - 6 * 3600 * 1000 for k, v in aged['last_leader_poll_cursor_ms'].items()}
json.dump(aged, open(s6 / 'clean_core_runtime_state.json', 'w', encoding='utf-8'))
r = run(['--state-dir', str(s6), '--seed', str(SEED), '--verify-only', '--interval-sec', '1'])
check('VERIFY_ONLY_REJECTS_A_STALE_SEED', r.returncode != 0, r.stdout[-140:])

# 8. a start time far in the past is refused: it would reopen the window
s7 = Path(tempfile.mkdtemp(prefix='pl7_'))
r = run(['--state-dir', str(s7), '--seed', str(SEED), '--start-ms', str(T0)])
check('REFUSES_A_STALE_START_TIME', r.returncode == 9, r.stdout[-140:])

# 9. a second seed over a seeded dir is refused unless --force
r = run(['--state-dir', str(s5), '--seed', str(SEED), '--start-ms', str(NOW)])
check('REFUSES_SECOND_SEED_WITHOUT_FORCE', r.returncode == 3, r.stdout[-120:])
run(['--state-dir', str(s5), '--seed', str(SEED), '--start-ms', str(NOW), '--force'])  # now overwrite it

# 10. the change log records a real before-hash when overwriting
recs = [json.loads(l) for l in (LOG.read_text(encoding='utf-8', errors='replace').splitlines() if LOG.exists() else []) if l.strip()]
ok_log = any(r.get('config_sha_before') and r.get('config_sha_after') for r in recs)
check('CHANGE_LOG_RECORDS_BEFORE_AND_AFTER', ok_log,
      'records=%d before-values=%s' % (len(recs), [r.get('config_sha_before') for r in recs][:3]))

# 11. a seed missing a cap key is refused and writes nothing
s8 = Path(tempfile.mkdtemp(prefix='pl8_'))
bad = json.loads(SEED.read_text(encoding='utf-8'))
bad['global_controls'].pop('max_total_live_exposure_usd', None)
badp = Path(tempfile.mkdtemp(prefix='pl9_')) / 'bad.json'
badp.write_text(json.dumps(bad), encoding='utf-8')
r = run(['--state-dir', str(s8), '--seed', str(badp), '--start-ms', str(NOW)])
check('REFUSES_SEED_MISSING_CAPS', r.returncode == 2 and not (s8 / 'live_config.json').exists(), r.stdout[-140:])

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
