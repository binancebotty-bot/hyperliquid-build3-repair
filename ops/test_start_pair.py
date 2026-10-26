#!/usr/bin/env python3
"""ops/start_pair.py: argument handling and every refusal path. **No engine is started by this test.**

Every check runs with --dry-run, which performs the full validation and prints the plan without launching
anything, so the refusal logic is exercised on a live machine without touching the running pair or the port.

The refusals that matter, and why:
  * a checkout with no engine / no ops/stop_pair.py  -> we would start someone else's tree
  * --expect-sha mismatch                            -> the build on disk is not the build that was reviewed
  * state dir missing / unseeded (no live_config)    -> an unseeded cursor replays the retention window as live
                                                        intents; that is the 2026-10-25 runaway, so refuse
  * engine already running for that state dir        -> two writers on one dir
  * something already listening on the UI port       -> the second UI would fail or fight the first
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import time
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / 'start_pair.py'
PY = sys.executable
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:220]) if not ok else ''))


def run(args):
    p = subprocess.run([PY, str(TOOL)] + args, capture_output=True, text=True, timeout=120)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


tmp = Path(tempfile.mkdtemp(prefix='startpair_'))


def free_port():
    import socket
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = free_port()

# ---- argument handling ----
rc, out = run([])
check('NO_ARGUMENTS_IS_A_USAGE_ERROR', rc == 2, 'rc=%s out=%s' % (rc, out[:160]))

rc, out = run(['--checkout', str(tmp)])
check('MISSING_STATE_IS_A_USAGE_ERROR', rc == 2, 'rc=%s out=%s' % (rc, out[:160]))

# ---- refusal paths (all with --dry-run: nothing is started) ----
rc, out = run(['--checkout', str(tmp / 'nope'), '--state', str(tmp / 'st'), '--dry-run'])
check('A_DIRECTORY_THAT_IS_NOT_A_CHECKOUT_IS_REFUSED', rc == 1 and 'not a pair checkout' in out,
      'rc=%s out=%s' % (rc, out[:200]))

# a fake checkout: has the engine path and ops/stop_pair.py, but nothing else
fake = tmp / 'fake'
(fake / '_archive' / 'hl_stage2').mkdir(parents=True)
(fake / '_archive' / 'hl_stage2' / 'HL_Live_Copy_Service_Core.py').write_text('# stub\n', encoding='utf-8')
(fake / 'ops').mkdir()
(fake / 'ops' / 'stop_pair.py').write_text('def pids(d):\n    return []\ndef listener(p):\n    return None\n',
                                            encoding='utf-8')

# the fake checkout must be a REAL git repo, or --expect-sha cannot be exercised (an unreadable sha refuses first)
try:
    subprocess.run(['git', 'init', '-q', str(fake)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(fake), 'add', '-A'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(fake), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'fake'],
                   check=True, capture_output=True)
    print('fake checkout initialised as a git repo')
except Exception as exc:
    print('could not initialise git in the fake checkout:', exc)

state_missing = tmp / 'stack' / 'run99' / 'state_20260101'
rc, out = run(['--checkout', str(fake), '--state', str(state_missing), '--dry-run'])
check('A_MISSING_STATE_DIR_IS_REFUSED_NOT_CREATED', rc == 1 and 'does not exist' in out,
      'rc=%s out=%s' % (rc, out[:200]))
check('THE_REFUSAL_DID_NOT_CREATE_THE_DIR', not state_missing.exists(), 'the tool created %s' % state_missing)

# an existing but UNSEEDED state dir must be refused: this is the runaway condition
state_unseeded = tmp / 'stack' / 'run98' / 'state_20260101'
state_unseeded.mkdir(parents=True)
rc, out = run(['--checkout', str(fake), '--state', str(state_unseeded), '--dry-run'])
check('AN_UNSEEDED_STATE_DIR_IS_REFUSED', rc == 1 and 'seed it first' in out,
      'rc=%s out=%s' % (rc, out[:240]))

# seeded: it should get as far as the dry-run plan
state_ok = tmp / 'stack' / 'run97' / 'state_20260101'
state_ok.mkdir(parents=True)
state_ok.joinpath('live_config.json').write_text('{}', encoding='utf-8', **({} if state_ok.joinpath('clean_core_runtime_state.json').exists() else {}))
(state_ok / 'clean_core_runtime_state.json').write_text('{"last_leader_poll_cursor_ms": %d}' % (int(time.time()*1000) - 300_000),
                                                       encoding='utf-8')
rc, out = run(['--checkout', str(fake), '--state', str(state_ok), '--ui-port', str(PORT), '--dry-run'])
check('A_SEEDED_DIRECTORY_PRODUCES_A_PLAN_WITHOUT_STARTING', rc == 0 and '"dry_run": true' in out,
      'rc=%s out=%s' % (rc, out[:240]))
check('THE_PLAN_NAMES_THE_POINTER_IT_WOULD_WRITE', 'CURRENT_AUDIT_DIR' in out,
      'the plan does not mention the pointer: %s' % out[:200])
check('A_DRY_RUN_WRITES_NO_POINTER', not (state_ok.parent.parent / 'CURRENT_AUDIT_DIR').exists(),
      'the dry run created the pointer')

# --expect-sha: git is not available in the fake checkout, so this exercises the mismatch branch safely
rc, out = run(['--checkout', str(fake), '--state', str(state_ok), '--expect-sha', 'deadbee', '--dry-run'])
check('AN_EXPECT_SHA_THAT_DOES_NOT_MATCH_IS_REFUSED', rc == 1 and ('expected' in out or 'rev-parse' in out.lower()),
      'rc=%s out=%s' % (rc, out[:200]))

# the "already running" refusal, proved against the engine that IS running (read-only, nothing started):
# its state dir has a live engine, so the tool must refuse before doing anything at all.
LIVE_STATE = Path('C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-evidence/run13/state_20261026')
if LIVE_STATE.exists():
    rc, out = run(['--checkout', str(fake), '--state', str(LIVE_STATE), '--ui-port', str(PORT), '--dry-run'])
    check('AN_ALREADY_RUNNING_ENGINE_IS_REFUSED', rc == 1 and 'already running' in out,
          'rc=%s out=%s' % (rc, out[:240]))
else:
    print('SKIP::AN_ALREADY_RUNNING_ENGINE_IS_REFUSED (no live state dir to point at)')

import socket
busy = socket.socket(); busy.bind(('127.0.0.1', 0)); busy.listen(1)
busy_port = busy.getsockname()[1]
rc, out = run(['--checkout', str(fake), '--state', str(state_ok), '--ui-port', str(busy_port), '--dry-run'])
check('AN_OCCUPIED_UI_PORT_IS_REFUSED', rc == 1 and 'already listening' in out,
      'rc=%s out=%s' % (rc, out[:240]))
busy.close()

# ---- the source carries no secrets and no hard-wired checkout ----
src = TOOL.read_text(encoding='utf-8')
check('NO_HARD_WIRED_CHECKOUT_PATH', 'C:/tmp/' not in src and 'C:\\\\tmp\\\\\\\\' not in src,
      'the tool hard-wires a scratch checkout')
check('NO_KEY_LIKE_LITERALS', '0x' + '0' * 8 not in src and 'PRIVATE_KEY=' not in src and 'secret' not in src.lower(),
      'the tool appears to carry a key or secret literal')


# ---- the fixes the adversarial review demanded, each proved here ----
# a live_config with NO cursor is not a seed
st_nocursor = tmp / 'stack' / 'run95' / 'state_20260101'
st_nocursor.mkdir(parents=True)
(st_nocursor / 'live_config.json').write_text('{}', encoding='utf-8')
rc, out = run(['--checkout', str(fake), '--state', str(st_nocursor), '--ui-port', str(PORT), '--dry-run'])
check('A_CONFIG_WITHOUT_A_CURSOR_IS_NOT_A_SEED', rc == 1 and 'clean_core_runtime_state' in out,
      'rc=%s out=%s' % (rc, out[:240]))

# a zero cursor is the 2026-10-25 replay condition
st_zero = tmp / 'stack' / 'run94' / 'state_20260101'
st_zero.mkdir(parents=True)
(st_zero / 'live_config.json').write_text('{}', encoding='utf-8')
(st_zero / 'clean_core_runtime_state.json').write_text('{"last_leader_poll_cursor_ms": 0}', encoding='utf-8')
rc, out = run(['--checkout', str(fake), '--state', str(st_zero), '--ui-port', str(PORT), '--dry-run'])
check('A_ZERO_CURSOR_IS_REFUSED', rc == 1 and 'replays the retention window' in out,
      'rc=%s out=%s' % (rc, out[:240]))

# a short --expect-sha certifies nothing
rc, out = run(['--checkout', str(fake), '--state', str(state_ok), '--ui-port', str(PORT),
               '--expect-sha', '5', '--dry-run'])
check('A_SHORT_EXPECT_SHA_IS_REFUSED', rc == 1 and 'at least 7' in out,
      'rc=%s out=%s' % (rc, out[:200]))

# a wrong-depth --state would write the pointer where the monitor never looks
st_badshape = tmp / 'elsewhere' / 'state_20260101'
st_badshape.mkdir(parents=True)
(st_badshape / 'live_config.json').write_text('{}', encoding='utf-8')
(st_badshape / 'clean_core_runtime_state.json').write_text('{"last_leader_poll_cursor_ms": %d}' % (int(time.time()*1000) - 300_000),
                                                           encoding='utf-8')
rc, out = run(['--checkout', str(fake), '--state', str(st_badshape), '--ui-port', str(PORT), '--dry-run'])
check('A_WRONG_DEPTH_STATE_DIR_IS_REFUSED', rc == 1 and 'runNN/state_' in out,
      'rc=%s out=%s' % (rc, out[:240]))

# the pointer must be written only after the pair is proven: the write cannot precede the start calls
srcp = TOOL.read_text(encoding='utf-8')
write_at = srcp.find('os.replace(str(_tmp), str(pointer))')
first_popen = srcp.find('subprocess.Popen(')
check('THE_POINTER_IS_WRITTEN_AFTER_THE_START_IS_PROVEN', write_at > first_popen,
      'the pointer is written before anything is started (write at %d, first start at %d)' % (write_at, first_popen))
check('A_FAILED_START_REVERTS_THE_POINTER', 'previous_pointer' in srcp and 'revert' in srcp.lower(),
      'a failed start would leave the monitor pointing at a dead run')

# ---- the six adversarial findings, each proved here ----
# These import the tool in-process and stub every process primitive: nothing is spawned, no port is bound.
sys.path.insert(0, str(HERE))
import start_pair as M


class FakeProc(object):
    """A process that answers poll()/terminate()/kill() and records what was done to it."""

    def __init__(self, pid, ignore_terminate=0):
        self.pid = pid
        self.returncode = None
        self.terminated = 0
        self.killed = 0
        self.waits = 0
        self._ignore = ignore_terminate

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated += 1
        if self._ignore > 0:
            self._ignore -= 1
            return
        self.returncode = 0

    def kill(self):
        self.killed += 1
        self.returncode = -9

    def wait(self, timeout=None):
        self.waits += 1
        deadline = time.time() + (0 if timeout is None else timeout)
        while self.returncode is None:
            if time.time() >= deadline:
                raise subprocess.TimeoutExpired('fake', timeout)
            time.sleep(0.01)
        return self.returncode

    def die(self):
        self.returncode = 0


def seeded_state(prefix, root):
    d = tmp / root / 'run01' / 'state_20260101'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'live_config.json').write_text('{}', encoding='utf-8')
    (d / 'clean_core_runtime_state.json').write_text(
        '{"last_leader_poll_cursor_ms": %d}' % (int(time.time() * 1000) - 300_000), encoding='utf-8')
    return d


# 1. ONE TRY/FINALLY: a failing UI spawn must reap the engine that is already running
st_tf = seeded_state('tf', 'stack_tf')
real_pids, real_listener = M.SP.pids, M.SP.listener
eng = FakeProc(40001)
M.SETTLE_S = 0.0
M.SP.pids = lambda d: []
M.SP.listener = lambda p: None
M.spawn_engine = lambda f, e: eng


def _boom(port, f, env):
    raise RuntimeError('ui spawn failed on purpose')


M.spawn_ui = _boom
raised = False
try:
    M.main(['--checkout', str(fake), '--state', str(st_tf), '--ui-port', str(PORT)])
except RuntimeError:
    raised = True
check('A_FAILING_UI_SPAWN_PROPAGATES', raised, 'the exception was swallowed - a failed start looks like success')
check('A_FAILING_UI_SPAWN_TERMINATES_THE_ENGINE', eng.terminated >= 1,
      'the engine was left running after the UI spawn failed (terminated=%d)' % eng.terminated)
check('A_FAILING_UI_SPAWN_LEAVES_NO_POINTER', not (st_tf.parent.parent / 'CURRENT_AUDIT_DIR').exists(),
      'a failed start wrote the pointer')
M.SP.pids, M.SP.listener = real_pids, real_listener

# 2. POINTER: absent, unreadable and unreadable-is-never-deleted are three different things
check('AN_ABSENT_POINTER_READS_AS_ABSENT', M.read_pointer(tmp / 'nothing_here' / 'CURRENT_AUDIT_DIR') == ('absent', ''),
      'a missing pointer is not reported as absent')
pdir = tmp / 'ptr_is_a_dir'
pdir.mkdir()
pstate, pdetail = M.read_pointer(pdir)
check('A_DIRECTORY_IN_PLACE_OF_THE_POINTER_IS_UNREADABLE', pstate == 'unreadable',
      'a directory read as %r (%s) - it must be unreadable, not absent' % (pstate, pdetail))

st_pt = seeded_state('pt', 'stack_pt')
(st_pt.parent.parent / 'CURRENT_AUDIT_DIR').mkdir()
rc, out = run(['--checkout', str(fake), '--state', str(st_pt), '--ui-port', str(PORT), '--dry-run'])
check('AN_UNREADABLE_POINTER_IS_REFUSED', rc == 1 and 'unreadable' in out, 'rc=%s out=%s' % (rc, out[:240]))
check('AN_UNREADABLE_POINTER_IS_NOT_DELETED', (st_pt.parent.parent / 'CURRENT_AUDIT_DIR').is_dir(),
      'the run deleted a pointer it could not read')

st_pa = seeded_state('pa', 'stack_pa')
rc, out = run(['--checkout', str(fake), '--state', str(st_pa), '--ui-port', str(PORT), '--dry-run'])
check('AN_ABSENT_POINTER_IS_NAMED_IN_THE_PLAN', rc == 0 and '"pointer_state": "absent"' in out,
      'rc=%s out=%s' % (rc, out[:240]))

# 3. UI PROOF: a UI that has exited is never "up", whatever is listening on the port
eng_up = FakeProc(40002)
ui_dead = FakeProc(40003)
ui_dead.die()
real_listener2 = M.SP.listener
M.SP.listener = lambda p: 40003                     # someone IS listening on the port, as our pid
check('AN_EXITED_UI_IS_NOT_UP', not M.ui_proven(ui_dead, eng_up, PORT, st_pa, None),
      'an exited UI was reported as up - the false positive the review found')
M.SP.listener = lambda p: 40004                     # our live UI owns the port
ui_live = FakeProc(40004)
check('A_LIVE_UI_HOLDING_THE_PORT_IS_UP', M.ui_proven(ui_live, eng_up, PORT, st_pa, None),
      'a live UI on its own port was not proven')
M.SP.listener = lambda p: 40099                     # a listener, but not ours
check('A_FOREIGN_LISTENER_DOES_NOT_PROVE_OUR_UI', not M.ui_proven(ui_live, eng_up, PORT, st_pa, M.state_identity(st_pa)),
      'a listener with another pid proved our UI up')
M.SP.listener = real_listener2

# 4. LOCK: a live holder refuses, a dead holder is stale and is replaced
lock = tmp / 'lockdir' / '.start_pair.lock'
lock.parent.mkdir()
lock.write_text(str(os.getpid()), encoding='utf-8')
state, holder = M.acquire_lock(lock)
check('A_LIVE_LOCK_HOLDER_IS_REFUSED', state == 'held' and holder == os.getpid(),
      'a live holder did not refuse: %r %r' % (state, holder))
lock.write_text('2147483646', encoding='utf-8')     # a pid that cannot exist
state, holder = M.acquire_lock(lock)
check('A_STALE_LOCK_IS_RECOVERED', state == 'ok', 'a dead holder was not treated as stale: %r %r' % (state, holder))
if state == 'ok':
    check('THE_LOCK_NOW_NAMES_THIS_PROCESS', lock.read_text(encoding='utf-8').strip() == str(os.getpid()),
          'the recovered lock does not name us')
    M.release_lock(lock, holder)
check('RELEASING_THE_LOCK_REMOVES_IT', not lock.exists(), 'the lock file survived release')

st_lk = seeded_state('lk', 'stack_lk')
lk = st_lk.parent.parent / '.start_pair.lock'
lk.write_text(str(os.getpid()), encoding='utf-8')   # held by this very test process: alive
rc, out = run(['--checkout', str(fake), '--state', str(st_lk), '--ui-port', str(PORT)])
check('A_SECOND_START_REFUSES_WHILE_THE_LOCK_IS_HELD', rc == 1 and 'another start is in progress' in out,
      'rc=%s out=%s' % (rc, out[:240]))
lk.unlink()

# 5. STOP: terminate, then wait, then kill, and say which happened
M.STOP_WAIT_S = 0.2
p_ok = FakeProc(40005)
check('A_PROCESS_THAT_HONOURS_TERMINATE_IS_REPORTED_TERMINATED', M.stop_proc(p_ok) == 'terminated',
      'terminate path not reported: terminated=%d killed=%d' % (p_ok.terminated, p_ok.killed))
check('A_PROCESS_THAT_HONOURS_TERMINATE_IS_NOT_KILLED', p_ok.killed == 0, 'it was killed anyway')
p_stub = FakeProc(40006, ignore_terminate=1)
check('A_PROCESS_THAT_IGNORES_TERMINATE_ONCE_IS_KILLED', M.stop_proc(p_stub) == 'killed',
      'the escalate-to-kill path did not report killed')
check('THE_KILL_ACTUALLY_HAPPENED', p_stub.killed == 1, 'killed=%d' % p_stub.killed)
check('THE_TERMINATE_STAGE_WAITS_ON_THE_CHILD', p_ok.waits == 1, 'waits=%d' % p_ok.waits)
p_stuck = FakeProc(40007, ignore_terminate=99)
p_stuck.kill = lambda: None                          # ignores kill too
check('A_PROCESS_THAT_SURVIVES_KILL_IS_REPORTED_UNREAPED', M.stop_proc(p_stuck) == 'unreaped',
      'an unkillable process was reported as cleanly stopped')
check('AN_UNREAPED_PROCESS_IS_STILL_WAITED_FOR_AFTER_KILL', p_stuck.waits == 2,
      'waits=%d - the unreaped verdict came back without a final wait/reap' % p_stuck.waits)
check('AN_EXITED_PROCESS_IS_NOT_SIGNALLED', M.stop_proc(ui_dead) == 'already_exited', 'it was signalled again')
check('A_MISSING_PROCESS_IS_HANDLED', M.stop_proc(None) == 'none', 'None was not handled')

# 7. LOCK ORDER: the lock comes first, and a launcher that waited its turn re-checks and refuses
check('THE_LOCK_IS_TAKEN_BEFORE_THE_RUNNING_CHECKS',
      srcp.find('acquire_lock(lock)') < srcp.find('SP.pids(state)'),
      'the running-process check runs before the lock, so two launchers can both pass it')
st_lo = seeded_state('lo', 'stack_lo')
spawns = []
M.spawn_engine = lambda f, e: (spawns.append(f), FakeProc(40010))[1]
M.spawn_ui = lambda p, f, e: FakeProc(40011)
real_ui_proven = M.ui_proven
M.ui_proven = lambda *a: True
M.SETTLE_S = 0.0
M.SP.listener = lambda p: None
lo_lock = st_lo.parent.parent / '.start_pair.lock'
lo_lock.write_text(str(os.getpid()), encoding='utf-8')      # A is still inside its start
M.SP.pids = lambda d: []
rc = M.main(['--checkout', str(fake), '--state', str(st_lo), '--ui-port', str(PORT)])
check('A_LAUNCHER_THAT_WAITED_ON_THE_LOCK_IS_REFUSED_BY_IT', rc == 1 and not spawns,
      'rc=%s spawns=%d' % (rc, len(spawns)))
lo_lock.unlink()                                            # A finished and released its lock
M.SP.pids = lambda d: [40010]                               # ... and its pair is now running
rc = M.main(['--checkout', str(fake), '--state', str(st_lo), '--ui-port', str(PORT)])
check('A_LAUNCHER_RECHECKS_AFTER_THE_LOCK_AND_REFUSES_A_RUNNING_PAIR', rc == 1 and not spawns,
      'rc=%s spawns=%d - a second pair was started on a running dir' % (rc, len(spawns)))
M.ui_proven = real_ui_proven

# 8. EARLY ENGINE EXIT: still emits the structured report, and never spawns the UI
def _ui_must_not_spawn(port, f, env):
    raise AssertionError('the UI was spawned although the engine had already exited')

st_ee = seeded_state('ee', 'stack_ee')
dead_engine = FakeProc(40020)
dead_engine.die()
M.spawn_engine = lambda f, e: dead_engine
M.spawn_ui = _ui_must_not_spawn
M.SP.pids = lambda d: []
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = M.main(['--checkout', str(fake), '--state', str(st_ee), '--ui-port', str(PORT)])
try:
    rep = json.loads(buf.getvalue())
except ValueError:
    rep = {}
check('AN_EARLY_ENGINE_EXIT_STILL_EMITS_THE_STRUCTURED_REPORT',
      rc == 1 and rep.get('pair') == 'ENGINE_EXITED' and isinstance(rep.get('stopped_on_failure'), dict)
      and rep['stopped_on_failure'].get('engine') == 'already_exited',
      'rc=%s report=%s' % (rc, buf.getvalue()[:240]))

# 9. UI PROOF CANNOT BE FORGED BY AN MTIME
st_fu = seeded_state('fu', 'stack_fu')
sf_fu = st_fu / 'live_service_state.json'
sf_fu.write_text('{}', encoding='utf-8')
future = time.time() + 3600
os.utime(str(sf_fu), (future, future))
ui_alive = FakeProc(40012)
M.SP.listener = lambda p: 40099                             # a listener, but not ours
before_fu = M.state_identity(st_fu)
check('A_FUTURE_MTIME_ON_A_PRE_EXISTING_STATE_FILE_DOES_NOT_PROVE_THE_UI',
      not M.ui_proven(ui_alive, eng_up, PORT, st_fu, before_fu),
      'a pre-existing future-dated state file certified a hung UI')
st_rw = seeded_state('rw', 'stack_rw')
sf_rw = st_rw / 'live_service_state.json'
sf_rw.write_text('{"tick": 0}', encoding='utf-8')
past = time.time() - 600
os.utime(str(sf_rw), (past, past))
before_rw = M.state_identity(st_rw)
sf_rw.write_text('{"tick": 1, "started": true}', encoding='utf-8')     # the new UI process rewrites it
check('A_STATE_FILE_REWRITTEN_BY_THE_NEW_PROCESS_PROVES_THE_UI',
      M.ui_proven(ui_alive, eng_up, PORT, st_rw, before_rw),
      'a genuinely rewritten state file did not prove the UI')
st_nf = seeded_state('nf', 'stack_nf')
M.SP.listener = lambda p: 40012                             # ours holds the port
check('A_LISTENER_OWNED_BY_THE_SPAWNED_UI_STILL_PROVES_IT',
      M.ui_proven(ui_alive, eng_up, PORT, st_nf, M.state_identity(st_nf)),
      'listener-pid proof stopped working')
M.SP.listener = real_listener2

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
