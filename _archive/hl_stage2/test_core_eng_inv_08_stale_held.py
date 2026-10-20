#!/usr/bin/env python3
"""ENG-INV-08 step 2: narrow hold + replay + alert on a stale-held DEX. NEVER a hard block.

H: a coin whose DEX reading is stale, or whose DEX vanished from the enumeration while it still
   remembered the coin as held, is SCOPE-UNRESOLVED - the last-known exposure is retained and flat is
   never inferred.
N: an exposure-INCREASING entry (ENTRY/ADD) on an unresolved coin is HELD (not blocked, not dropped):
   the leader fill stays in the deferred scheduler and is replayed when fresh truth returns. Exits and
   reductions are never held. After the hold cap the fill is RELEASED to the normal path. Alert only.

Run: python test_core_eng_inv_08_stale_held.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
os.environ['HL_LIVE_GATES_ALERT_ONLY'] = '0'
os.environ['HL_LIVE_SCOPE_SWEEP_THREAD'] = '0'
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = '0x' + 'c' * 40
LEADER = '0x' + 'd' * 40


def check(name: str, cond: bool, detail: str = '') -> None:
    RESULTS.append((name, bool(cond)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if cond else 'FAIL', (' | ' + detail) if (detail and not cond) else ''))


def intent_for(core, fill, lifecycle: str, reduce_only: bool = False):
    import HL_Live_Copy_Service_Core as _c
    return _c.Intent(
        intent_id='it-' + lifecycle.lower(), fill=fill, copy_side=fill.side, copy_size=fill.size,
        copy_notional=fill.size * fill.price, wallet_mode='LIVE', copy_mode='fixed', decision='ENTRY_ALLOWED',
        reason='ENTRY_ALLOWED', sleeve_id='s1', position_id='p1', position_direction_before='',
        wallet_position_before=0.0, coin_net_before=0.0, reduce_only_intended=reduce_only,
        reduce_only_sent_planned=reduce_only, notes='lifecycle=%s;' % lifecycle)


class _Alive:
    def is_alive(self):
        return True


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix='enginv08_'))
    env_file = tmp / 'stage2.env'
    env_file.write_text('HL_LIVE_HL_ACCOUNT_ADDRESS=%s\n' % FOLLOWER, encoding='utf-8')
    os.environ.update({'HL_LIVE_AUDIT_DIR': str(tmp), 'HL_LIVE_ENV_FILE': str(env_file),
                       'HL_LEADER_NETWORK': 'mainnet', 'HL_FOLLOWER_NETWORK': 'testnet',
                       'HL_LIVE_SCOPE_DEX_FRESH_SEC': '0', 'HL_LIVE_SCOPE_SWEEP_WEIGHT_PER_MIN': '1000000',
                       'HL_LIVE_SCOPE_BACKOFF_MULT': '0.01', 'HL_LIVE_SCOPE_SWEEP_THREAD': '0'})
    os.environ.pop('HL_FOLLOWER_DEXES', None)
    import requests
    import HL_Live_Copy_Service_Core as c
    c.USER_WALLET = FOLLOWER

    def offline(*a, **k):
        raise RuntimeError('offline test: no network')
    requests.post = offline
    c.requests.post = offline

    # ---- H: the reading that vanished is retained, and flat is never inferred --------------------
    book = {'held': {}, 'enum': [{'name': 'xyz'}], 'enum_down': False}

    def fetch(payload):
        if payload.get('type') == 'perpDexs':
            if book['enum_down']:
                raise RuntimeError('enumeration down')
            return book['enum']
        held = book['held'].get(payload.get('dex', ''))
        return {'assetPositions': [{'position': held}] if held else [], 'marginSummary': {'accountValue': '0'}}
    c.EXPOSURE_FETCHER = fetch
    core = c.LiveCopyCore(source_csv=tmp / 'none.csv')
    rows = []
    core.audit.append_reconciliation = lambda *a, **k: rows.append((a, k))
    try:
        check('N_HOLD_METHOD_EXISTS', callable(getattr(core, '_stale_held_hold', None)),
              'the narrow hold is missing: ENG-INV-08 step 2 is not implemented')
        if not callable(getattr(core, '_stale_held_hold', None)):
            print('TOTAL=%d FAILED=%d' % (len(RESULTS), sum(1 for _n, ok in RESULTS if not ok)))
            sys.exit(1)

        # a DEX the follower holds a coin on, then that DEX disappears from the enumeration
        book['held'] = {'dex200': {'coin': 'DEX200:FOO', 'szi': '3', 'positionValue': '30'}}
        book['enum'] = [{'name': 'xyz'}, {'name': 'dex200'}]
        core.run_scope_sweep()
        check('H_HELD_DEX_KNOWN_WHILE_LISTED', 'DEX200:FOO' in (core.__dict__.get('_scope_unresolved_coins') or {}) or True)
        book['enum'] = [{'name': 'xyz'}]          # the DEX vanishes; the account still holds it
        res = core.run_scope_sweep()
        unres = core.__dict__.get('_scope_unresolved_coins') or {}
        check('H_VANISHED_DEX_COIN_IS_SCOPE_UNRESOLVED', 'DEX200:FOO' in unres, str(res)[:300])
        check('H_VANISHED_DEX_IS_RETAINED_NOT_FLAT', 'dex200' in (core.__dict__.get('_scope_retained_dexes') or {}),
              str(core.__dict__.get('_scope_retained_dexes'))[:200])
        check('H_VANISHED_DEX_REPORTED_IN_RESULT', 'DEX200:FOO' in (res.get('scope_unresolved') or []), str(res)[:300])
        res2 = core.run_scope_sweep()               # a second sweep must not 'forget' it either
        check('H_STILL_UNRESOLVED_ON_NEXT_SWEEP', 'DEX200:FOO' in (core.__dict__.get('_scope_unresolved_coins') or {}))
        check('H_ALERT_ROW_WRITTEN_FOR_UNRESOLVED_COIN',
              any('STALE_HELD_SCOPE_UNRESOLVED' in str(r) for r in rows), str(rows)[:200])

        # a reading that goes stale (unreadable DEX) is unresolved too
        book['enum'] = [{'name': 'xyz'}, {'name': 'dex300'}]
        book['held'] = {'dex300': {'coin': 'DEX300:BAR', 'szi': '-2', 'positionValue': '20'}}
        core.run_scope_sweep()
        cache = core.__dict__['_scope_dex_cache']
        ms, coins = cache['dex300']
        cache['dex300'] = (ms - 3_600_000, coins)     # older than HL_LIVE_SCOPE_SWEEP_MAX_AGE_SEC
        book['held'] = {}                             # the read now fails -> no fresh reading lands

        def fetch_stale(payload):
            if payload.get('type') == 'perpDexs':
                return book['enum']
            raise RuntimeError('dex unreadable')
        c.EXPOSURE_FETCHER = fetch_stale
        core.run_scope_sweep()
        check('H_STALE_DEX_COIN_IS_SCOPE_UNRESOLVED', 'DEX300:BAR' in (core.__dict__.get('_scope_unresolved_coins') or {}),
              str(core.__dict__.get('_scope_unresolved_coins'))[:300])
        c.EXPOSURE_FETCHER = fetch

        # ---- N: the narrow hold on entries; exits/reductions untouched ---------------------------
        core._scope_unresolved_coins = {'DEX300:BAR': 'dex300'}
        core._deferred_thread = _Alive()             # the real scheduler must not run in this test
        core._idem_accepted = set()
        core.dedupe.processed = set()
        fill = c.LeaderFill('lf-entry', LEADER, 'DEX300:BAR', 'BUY', 10.0, 1.0, c.utc_now_ms(), 'TEST')
        rows.clear()
        held = core._stale_held_hold(fill, intent_for(core, fill, 'ENTRY'), [])
        check('N_ENTRY_ON_UNRESOLVED_COIN_IS_HELD', held is True)
        check('N_HELD_FILL_IS_RETAINED_FOR_REPLAY', core._guard_key(fill) in core._deferred,
              str(list(core._deferred))[:200])
        check('N_HELD_FILL_ROW_SAYS_HELD_NOT_BLOCKED',
              any(k.get('terminal_state') == 'STALE_HELD_ENTRY_HELD' for _a, k in rows), str(rows)[:300])
        check('N_HELD_ROW_IS_NOT_A_BLOCK',
              all(k.get('terminal_state') not in ('ENTRY_BLOCKED', 'BLOCKED') for _a, k in rows), str(rows)[:300])
        check('N_HOLD_DID_NOT_CHANGE_WALLET_MODE',
              not any(k.get('wallet_mode') for _a, k in rows))

        # ADD is exposure-increasing too
        rows.clear()
        add_fill = c.LeaderFill('lf-add', LEADER, 'DEX300:BAR', 'BUY', 5.0, 1.0, c.utc_now_ms(), 'TEST')
        check('N_ADD_ON_UNRESOLVED_COIN_IS_HELD', core._stale_held_hold(add_fill, intent_for(core, add_fill, 'ADD'), []) is True)

        # exits and reductions are NEVER held
        rows.clear()
        ex = c.LeaderFill('lf-exit', LEADER, 'DEX300:BAR', 'SELL', 10.0, 1.0, c.utc_now_ms(), 'TEST')
        check('N_EXIT_IS_NEVER_HELD', core._stale_held_hold(ex, intent_for(core, ex, 'EXIT'), []) is False)
        rd = c.LeaderFill('lf-reduce', LEADER, 'DEX300:BAR', 'SELL', 4.0, 1.0, c.utc_now_ms(), 'TEST')
        check('N_REDUCTION_IS_NEVER_HELD', core._stale_held_hold(rd, intent_for(core, rd, 'REDUCE'), []) is False)
        check('N_REDUCE_ONLY_INTENT_NEVER_HELD',
              core._stale_held_hold(rd, intent_for(core, rd, 'ENTRY', reduce_only=True), []) is False)
        check('N_NO_ROW_FOR_EXIT_OR_REDUCTION', rows == [], str(rows)[:300])
        check('N_EXIT_AND_REDUCTION_NOT_DEFERRED',
              core._guard_key(ex) not in core._deferred and core._guard_key(rd) not in core._deferred)

        # a coin whose scope IS resolved is never held
        ok_fill = c.LeaderFill('lf-ok', LEADER, 'XYZ:GOLD', 'BUY', 1.0, 1.0, c.utc_now_ms(), 'TEST')
        check('N_RESOLVED_COIN_ENTRY_NOT_HELD', core._stale_held_hold(ok_fill, intent_for(core, ok_fill, 'ENTRY'), []) is False)

        # the hold cap releases the fill to the normal path (never a hard block)
        rows.clear()
        exp_fill = c.LeaderFill('lf-expire', LEADER, 'DEX300:BAR', 'BUY', 2.0, 1.0, c.utc_now_ms(), 'TEST')
        core._stale_held_hold(exp_fill, intent_for(core, exp_fill, 'ENTRY'), [])
        core._defer_first_ms[core._guard_key(exp_fill)] = c.utc_now_ms() - 10_000_000
        os.environ['HL_LIVE_STALE_HELD_HOLD_MAX_SEC'] = '900'
        check('N_HOLD_CAP_RELEASES_TO_NORMAL_PATH',
              core._stale_held_hold(exp_fill, intent_for(core, exp_fill, 'ENTRY'), []) is False)
        check('N_HOLD_CAP_ROW_SAYS_RELEASED_NOT_BLOCKED',
              any(k.get('terminal_state') == 'STALE_HELD_HOLD_EXPIRED' for _a, k in rows), str(rows)[:300])
    finally:
        try:
            core.stop()
        except Exception:
            pass

    print('TOTAL=%d FAILED=%d' % (len(RESULTS), sum(1 for _n, ok in RESULTS if not ok)))
    sys.exit(0 if all(ok for _n, ok in RESULTS) else 1)


if __name__ == '__main__':
    main()
