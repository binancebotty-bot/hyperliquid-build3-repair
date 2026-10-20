#!/usr/bin/env python3
"""Readiness 4: an exchange 429 / JSON error body is a FAILED read, never a clean empty inventory.

Failure mode: exchange_truth._post accepted any dict/list as a good read, so an error body
({"error": ...}) - including the JSON body of an HTTP 429 - counted as a successful read carrying
no positions. list_perp_dexes then returned ok=True with only the default scope, master_exposure
returned an empty by_coin, and the all-DEX inventory looked clean-and-empty -> sends unblocked on
an account that was never read.

Run: python test_core_429_is_failed_read.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = '0x' + 'c' * 40
ERR_BODY = {'error': '429 Too Many Requests'}


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if cond else 'FAIL', (' | ' + detail) if (detail and not cond) else ''))


class _Resp:
    def __init__(self, body, status_code=200):
        self._body, self.status_code = body, status_code

    def json(self):
        return self._body


def main():
    tmp = Path(tempfile.mkdtemp(prefix='r4_'))
    os.environ['HL_LIVE_AUDIT_DIR'] = str(tmp)
    os.environ['HL_LIVE_ENV_FILE'] = '/nonexistent.env'
    os.environ['HL_LIVE_SCOPE_SWEEP_MAX_AGE_SEC'] = '900'
    os.environ['HL_LIVE_SCOPE_SWEEP_THREAD'] = '0'
    os.environ['HL_LIVE_SCOPE_FAIL_ROW_AFTER'] = '1'
    import exchange_truth as X

    err_fetcher = lambda payload: dict(ERR_BODY)

    got = X._post(err_fetcher, {'type': 'clearinghouseState', 'user': FOLLOWER}, 'https://x/info', 1.0)
    check('R4_1_ERROR_BODY_IS_NOT_A_GOOD_READ', not got.get('ok'), json.dumps(got)[:200])

    enum = X.list_perp_dexes(fetcher=err_fetcher, info_url='https://x/info', timeout=1.0)
    check('R4_2_ERROR_BODY_DOES_NOT_LOOK_LIKE_NO_DEXES', not enum.get('ok'), json.dumps(enum)[:200])

    exp = X.master_exposure(FOLLOWER, ['', 'test'], fetcher=err_fetcher, info_url='https://x/info', timeout=1.0)
    check('R4_3_ALL_DEX_INVENTORY_HOLDS_ON_ERROR_BODY', (not exp.get('ok')) and ('by_coin' not in exp), json.dumps(exp)[:200])

    import requests
    real_post = requests.post
    try:
        requests.post = lambda url, json=None, timeout=None, **kw: _Resp(dict(ERR_BODY), 429)
        live = X._post(None, {'type': 'perpDexs'}, 'https://x/info', 1.0)
        check('R4_4_HTTP_429_IS_NOT_A_GOOD_READ', not live.get('ok'), json.dumps(live)[:200])
        live_enum = X.list_perp_dexes(fetcher=None, info_url='https://x/info', timeout=1.0)
        check('R4_5_HTTP_429_NEVER_EMPTY_ENUM', not live_enum.get('ok'), json.dumps(live_enum)[:200])
    finally:
        requests.post = real_post

    ok_fetcher = lambda payload: ([] if payload.get('type') == 'perpDexs' else {'assetPositions': [], 'marginSummary': {'accountValue': '0'}})
    enum_ok = X.list_perp_dexes(fetcher=ok_fetcher, info_url='https://x/info', timeout=1.0)
    check('R4_6_HEALTHY_ENUM_STILL_OK', bool(enum_ok.get('ok')) and enum_ok.get('dexes') == [''], json.dumps(enum_ok)[:200])
    exp_ok = X.master_exposure(FOLLOWER, [''], fetcher=ok_fetcher, info_url='https://x/info', timeout=1.0)
    check('R4_7_HEALTHY_EMPTY_ACCOUNT_STILL_CLEAN', bool(exp_ok.get('ok')) and exp_ok.get('by_coin') == {}, json.dumps(exp_ok)[:200])

    import HL_Live_Copy_Service_Core as c
    cfg_file = tmp / 'live_config.json'
    cfg_file.write_text(json.dumps({'global_controls': {'send_mode': 'ON'}, 'wallets': {FOLLOWER: {'enabled': True, 'mode': 'ON'}}}), encoding='utf-8')
    mode_before = c.ConfigManager(config_path=cfg_file).send_mode
    try:
        requests.post = lambda url, json=None, timeout=None, **kw: _Resp(dict(ERR_BODY), 429)
        X._post(None, {'type': 'perpDexs'}, 'https://x/info', 1.0)
        X.list_perp_dexes(fetcher=None, info_url='https://x/info', timeout=1.0)
        X.master_exposure(FOLLOWER, [''], fetcher=None, info_url='https://x/info', timeout=1.0)
    finally:
        requests.post = real_post
    mode_after = c.ConfigManager(config_path=cfg_file).send_mode
    check('R4_8A_429_DOES_NOT_FLIP_SEND_MODE', mode_before == 'ON' and mode_after == 'ON', 'before=%r after=%r' % (mode_before, mode_after))
    paused = [p.name for p in tmp.rglob('*') if p.is_file() and 'pause' in p.name.lower()]
    check('R4_8B_429_DOES_NOT_WRITE_A_PAUSE_STATE', not paused, str(paused))

    core = c.LiveCopyCore.__new__(c.LiveCopyCore)
    core._hot_stop_event = threading.Event()
    core.audit = c.AuditLogWriter()
    core._scope_fail_row_ms = 0
    c.EXPOSURE_FETCHER = err_fetcher
    try:
        res = core.run_scope_sweep()
    finally:
        c.EXPOSURE_FETCHER = None
    state_path = Path(c.CORE_RUNTIME_STATE_FILE).parent / 'scope_sweep_state.json'
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    check('R4_9_UNREADABLE_BODY_HOLDS_THE_SWEEP', (not res.get('ok')) and state.get('ok') is False, json.dumps(res)[:200] + ' state=' + json.dumps(state)[:120])

    failed = [n for n, ok in RESULTS if not ok]
    print('\nTOTAL=%d FAILED=%d' % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
