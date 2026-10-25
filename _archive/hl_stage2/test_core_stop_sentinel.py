#!/usr/bin/env python3
"""A stop request must reach the engine as a CLEAN exit, not a killed process.

On 2026-10-25 the engine was killed with TerminateProcess, which runs no atexit hook, so its
write-behind audit queue was discarded: 8 of 133 engine-era fills had an exchange fill and no
journal row. pythonw has no console, so CTRL_BREAK cannot be used to ask politely. The engine now
honours a STOP_REQUESTED sentinel at the top of its --loop cycle.

This starts a REAL engine (inert: a temp audit dir, no private key, converge thread off), writes the
sentinel and asserts: it exits on its own, with rc 0, having written a clean shutdown record naming
the sentinel, and having removed the sentinel itself.
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
PYW = r'C:/Users/wigmore/AppData/Local/Programs/Python/Python311/pythonw.exe'
spec = json.load(open(os.path.expanduser('~/.hermes/state/core_launch_env.json'), encoding='utf-8'))
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:160]) if not ok else ''))


state = Path(tempfile.mkdtemp(prefix='stopsent_'))
env = {k: str(v) for k, v in spec['env'].items()}
env['HL_LIVE_AUDIT_DIR'] = str(state).replace(chr(92), '/')
env.pop('HL_LIVE_HL_PRIVATE_KEY', None)          # cannot send even if it tried
env['HL_LIVE_CONVERGE_THREAD'] = '0'
args = list(spec['args'])
if '--loop' not in args:
    args.append('--loop')
p = subprocess.Popen([PYW] + args, cwd=str(HERE), env={**os.environ, **env},
                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
check('ENGINE_STARTS', p.poll() is None, 'rc=%s' % p.poll())
time.sleep(15)
check('ENGINE_IS_RUNNING_BEFORE_THE_REQUEST', p.poll() is None, 'rc=%s' % p.poll())
check('SENTINEL_ALONE_DOES_NOT_EXIST', not (state / 'STOP_REQUESTED').exists())

(state / 'STOP_REQUESTED').write_text('test stop\n', encoding='utf-8')
rc = None
try:
    rc = p.wait(timeout=90)
except subprocess.TimeoutExpired:
    import psutil
    psutil.Process(p.pid).kill()
check('EXITS_ON_THE_SENTINEL', rc == 0, 'rc=%s' % rc)

rec = state / 'core_shutdown_record.json'
r = json.loads(rec.read_text(encoding='utf-8-sig')) if rec.exists() else {}
check('WRITES_A_CLEAN_SHUTDOWN_RECORD', bool(r.get('clean')) is True, r)
check('RECORD_NAMES_THE_SENTINEL', r.get('reason') == 'stop_sentinel', r.get('reason'))
check('ENGINE_REMOVES_THE_SENTINEL', not (state / 'STOP_REQUESTED').exists())

shutil.rmtree(state, ignore_errors=True)
failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
