#!/usr/bin/env python3
'''Env-injecting TESTNET Core start (controller order 6385158376, hardened per 6385875605).

Reads the pinned launch spec, reuses the launcher's own pinned-source and state-folder checks,
builds the child environment from the spec's fields exactly as launch_once does, and Popens the
Core. Does NOT call launch_once or prepare_account (residual positions and reduce-only orders
survive). A successful spawn is NOT reported as a successful start: the child's fresh engine
state is verified before this exits 0. Never prints an env value.
'''
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SPEC = Path(__file__).with_name('testnet_launch_spec.json')
sys.path.insert(0, str(Path(__file__).resolve().parent))
import testnet_startup as TS          # the launcher that owns the pinned-source checks


def load_spec():
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    if spec.get('schema') != 1 or spec.get('follower_network') != 'testnet':
        raise SystemExit('REFUSED: spec is invalid or not TESTNET-only')
    return spec


def verify_identity(spec):
    '''checkout HEAD == source_sha, state_dir inside the TESTNET state root, core inside the checkout.
    Reuses testnet_startup's own checks so a changed checkout or a mispointed spec cannot start
    code while HL_BUILD_SHA still advertises the declared pin.'''
    sha = str(spec['source_sha']).lower()
    head = str(TS.check_source(spec)).lower()
    if head != sha:
        raise SystemExit('REFUSED: checkout HEAD %s != pinned source_sha %s' % (head, sha))
    state_dir = TS.state_dir_for(spec)                       # abs + inside testnet_state_root + run*/state*
    checkout = Path(spec['checkout_root']).resolve()
    core_script = (checkout / spec['core_script']).resolve()
    if not str(core_script).startswith(str(checkout) + os.sep):
        raise SystemExit('REFUSED: core_script escapes the pinned checkout: %s' % core_script)
    if not core_script.is_file():
        raise SystemExit('REFUSED: core_script missing: %s' % core_script)
    follower = str(spec['follower_account_address']).strip()
    if not (follower.startswith('0x') and len(follower) == 42):
        raise SystemExit('REFUSED: spec follower_account_address is not 42-char 0x')
    return sha, state_dir, core_script


def wait_ready(core, state_dir, sha, deadline_s):
    '''Fresh engine state, not a live PID: the child must be alive AND report itself configured.
    Without this a wrong interpreter (SDK_UNAVAILABLE) printed CORE_STARTED and returned 0.'''
    deadline = time.monotonic() + deadline_s
    last = ''
    while time.monotonic() < deadline:
        if core.poll() is not None:
            print('CORE_FAILED: exited rc=%s before verifying identity' % core.returncode)
            return False
        try:
            st = json.loads((state_dir / 'live_service_state.json').read_text(encoding='utf-8'))
        except Exception:
            last = 'no engine state yet'
            time.sleep(1.0)
            continue
        status = str(st.get('copy_account_status') or '')
        age_ms = int(st.get('last_copy_poll_age_ms') or 0)
        ws = str(st.get('ws_status') or '')
        last = 'copy_account_status=%s poll_age_ms=%s ws=%s' % (status, age_ms, ws)
        if status == 'COPY_ACCOUNT_POLLED' and age_ms < 5000 and ws == 'WS_OK':
            return True
        time.sleep(1.0)
    print('CORE_FAILED: identity not verified within %ss (%s)' % (int(deadline_s), last))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    spec = load_spec()
    sha, state_dir, core_script = verify_identity(spec)

    env = dict(os.environ)
    env.update({
        'HL_LIVE_AUDIT_DIR': str(state_dir),
        'HL_FOLLOWER_NETWORK': 'testnet',
        'HL_LIVE_WS_ENABLED': '1',
        'HL_BUILD_SHA': sha,
        'HL_APP_PORT': str(spec['ui_port']),
        'HL_USER_WALLET': str(spec['follower_account_address']).strip(),
        'HL_LIVE_GLOBAL_LOCK_FILE': str(spec['global_lock_path']),
    })

    # HL_LIVE_ENV_FILE is a PATH, never a secret: the Core loads HL_LIVE_HL_PRIVATE_KEY from it at
    # import (:74-75, :105). Only inject it when it actually exists, so a missing file cannot
    # override the Core's own default.
    env_file = spec.get('env_file')
    if env_file and os.path.isfile(env_file):
        env['HL_LIVE_ENV_FILE'] = env_file

    # Pin the interpreter to the one the Core needs: it carries the hyperliquid SDK, and
    # sys.executable (Hermes' venv) does not.
    py = os.environ.get('HERMES_CORE_PYTHON') or 'C:/Users/wigmore/AppData/Local/Python/bin/pythonw.exe'
    if not Path(py).is_file():
        raise SystemExit('REFUSED: core interpreter missing: ' + py)
    cmd = [py, str(core_script)] + list(spec['core_args'])
    print('SHA_OK', sha)
    print('STATE_DIR_OK', state_dir)
    print('CORE_SCRIPT_OK', core_script)
    print('HL_USER_WALLET_LEN', len(env['HL_USER_WALLET']))
    print('CMD', ' '.join(cmd))
    print('CWD', core_script.parent)
    if args.dry_run:
        print('DRY_RUN: nothing started')
        return 0

    # Child output goes to a log inside the state dir; never printed, never parsed for values.
    log = state_dir / 'core_child_stderr.log'
    with open(log, 'ab') as fh:
        fh.write(('%s core_child_start sha=%s\n' % (time.strftime('%Y-%m-%dT%H:%M:%SZ'), sha)).encode())
        core = subprocess.Popen(
            cmd, cwd=str(core_script.parent), env=env,
            stdout=fh, stderr=fh, stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000),
        )
    print('CORE_STARTED pid=%d build_sha=%s network=testnet state_dir=%s child_log=%s'
          % (core.pid, sha, state_dir, log))
    if not wait_ready(core, state_dir, sha, float(spec.get('state_max_age_seconds', 600))):
        return 1
    print('CORE_VERIFIED pid=%d' % core.pid)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
