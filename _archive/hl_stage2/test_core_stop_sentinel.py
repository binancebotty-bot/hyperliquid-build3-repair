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

# This suite starts a real engine, and the product allows only one engine per machine. When the pair
# is running, a second engine is refused by the global lock - that is correct behaviour, not a test
# failure, so say SKIP with the reason instead of reporting eight red checks.
_GLOBAL_LOCK = Path(os.path.expanduser('~/AppData/Local/HL_Live_Copy_Service_Core/engine-global.lock'))
def _lock_is_held() -> bool:
    """The lock file outlives its process by design (a byte-range lock, Core:15718-15737), so its
    presence proves nothing. It is held when the holder's pid is alive, or when the file cannot even
    be read - the exclusive byte-range lock denies the read, which is the signal we saw earlier."""
    if not _GLOBAL_LOCK.exists():
        return False
    try:
        raw = _GLOBAL_LOCK.read_text(encoding='utf-8-sig')
    except PermissionError:
        return True
    except Exception:
        return True
    try:
        info = json.loads(raw)
        holder = info.get('holder') if isinstance(info.get('holder'), dict) else info
        pid = int(holder.get('pid') or 0)
        if not pid:
            return False
        import psutil
        return psutil.pid_exists(pid) and psutil.Process(pid).is_running()
    except Exception:
        return False


if _lock_is_held():
    try:
        _holder = json.loads(_GLOBAL_LOCK.read_text(encoding='utf-8-sig'))
    except PermissionError:
        # the running engine holds it exclusively, so its contents are not readable - which is itself
        # proof that another engine is live
        _holder = {'note': 'lock file held exclusively by another engine'}
    except Exception:
        _holder = {}
    _h = _holder.get('holder') if isinstance(_holder.get('holder'), dict) else _holder
    print('SKIP: another engine holds the machine-wide lock%s; this suite needs the machine to itself.'
          % ('' if _h.get('note') else ' (pid=%s state_dir=%s)' % (_h.get('pid'), _h.get('state_dir'))))
    print('TOTAL=0 FAILED=0 SKIPPED=GLOBAL_ENGINE_LOCK_HELD')
    sys.exit(1)


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
(state / 'STOP_REQUESTED').write_text('stale request from a crashed run' + chr(10), encoding='utf-8')
os.utime(state / 'STOP_REQUESTED', (time.time() - 600, time.time() - 600))  # a crash leftover, older than 120 s
p = subprocess.Popen([PYW] + args, cwd=str(HERE), env={**os.environ, **env},
                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
check('ENGINE_STARTS', p.poll() is None, 'rc=%s' % p.poll())
time.sleep(15)
check('ENGINE_IS_RUNNING_BEFORE_THE_REQUEST', p.poll() is None, 'rc=%s' % p.poll())
stale = list(state.glob('STOP_REQUESTED.stale.*'))
check('STALE_SENTINEL_IS_QUARANTINED', len(stale) == 1, [x.name for x in stale])
check('STALE_SENTINEL_DID_NOT_STOP_THE_RUN', p.poll() is None, 'rc=%s' % p.poll())
check('THE_STALE_SENTINEL_IS_GONE', not (state / 'STOP_REQUESTED').exists())

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


# ---- a FRESH sentinel at launch is a stop in flight: the engine must refuse to start, not steal it
state_fresh = Path(tempfile.mkdtemp(prefix='stopsent_fresh_'))
env_f = dict(env); env_f['HL_LIVE_AUDIT_DIR'] = str(state_fresh).replace(chr(92), '/')
(state_fresh / 'STOP_REQUESTED').write_text('stop in flight' + chr(10), encoding='utf-8')
pf = subprocess.Popen([PYW] + args, cwd=str(HERE), env={**os.environ, **env_f},
                      creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
try:
    rc_f = pf.wait(timeout=60)
except subprocess.TimeoutExpired:
    import psutil
    psutil.Process(pf.pid).kill()
    rc_f = 'TIMEOUT'
check('FRESH_SENTINEL_AT_LAUNCH_REFUSES_TO_START', rc_f not in (0, 'TIMEOUT'), 'rc=%s' % rc_f)
check('IN_FLIGHT_REQUEST_IS_NOT_QUARANTINED', (state_fresh / 'STOP_REQUESTED').exists())
shutil.rmtree(state_fresh, ignore_errors=True)

shutil.rmtree(state, ignore_errors=True)
failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
