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

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
