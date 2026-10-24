#!/usr/bin/env python3
'''Env-injecting TESTNET Core start (controller order 6385158376).

Reads the pinned launch spec, builds the child environment from the spec's fields exactly as
launch_once does (lines ~956-964), and Popens the Core. Does NOT call launch_once or
prepare_account. Never prints, logs or commits any env value.
'''
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SPEC = Path(__file__).with_name('testnet_launch_spec.json')


def load_spec():
    spec = json.loads(SPEC.read_text(encoding='utf-8'))
    if spec.get('schema') != 1 or spec.get('follower_network') != 'testnet':
        raise SystemExit('REFUSED: spec is invalid or not TESTNET-only')
    return spec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    spec = load_spec()
    state_dir = Path(spec['state_dir'])
    core_script = Path(spec['checkout_root']) / spec['core_script']
    sha = str(spec['source_sha']).lower()

    if not core_script.is_file():
        raise SystemExit('REFUSED: core_script missing')
    if not state_dir.is_dir():
        raise SystemExit('REFUSED: state_dir missing')
    follower = str(spec['follower_account_address']).strip()
    if not (follower.startswith('0x') and len(follower) == 42):
        raise SystemExit('REFUSED: spec follower_account_address is not 42-char 0x')

    env = dict(os.environ)
    env.update({
        'HL_LIVE_AUDIT_DIR': str(state_dir),
        'HL_FOLLOWER_NETWORK': 'testnet',
        'HL_LIVE_WS_ENABLED': '1',
        'HL_BUILD_SHA': sha,
        'HL_APP_PORT': str(spec['ui_port']),
        'HL_USER_WALLET': follower,
        'HL_LIVE_GLOBAL_LOCK_FILE': str(spec['global_lock_path']),
    })

    # Pin the interpreter to the one PID 2880 used - it carries the hyperliquid SDK;
    # sys.executable is Hermes' own venv and lacks it.
    py = os.environ.get('HERMES_CORE_PYTHON') or 'C:/Users/wigmore/AppData/Local/Python/bin/pythonw.exe'
    if not Path(py).is_file():
        raise SystemExit('REFUSED: core interpreter missing: ' + py)
    cmd = [py, str(core_script)] + list(spec['core_args'])
    print('HL_USER_WALLET_LEN', len(env['HL_USER_WALLET']))
    print('CMD', ' '.join(cmd))
    print('CWD', core_script.parent)
    if args.dry_run:
        print('DRY_RUN: nothing started')
        return 0

    core = subprocess.Popen(
        cmd, cwd=str(core_script.parent), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000),
    )
    print('CORE_STARTED pid=%d build_sha=%s network=testnet state_dir=%s'
          % (core.pid, sha, state_dir))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
