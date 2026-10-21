#!/usr/bin/env python3
"""Command Centre snapshot must aggregate EVERY perp DEX scope, not just the default one.

RED on base (default-scope only): a HIP-3/builder position (xyz:*) is invisible and the header
under-reports. GREEN on candidate: totals are the sum over scopes, and one unreadable scope fails
closed instead of silently returning the smaller default-only number.

Run: python test_g4_ui_scope_aggregation.py     # RESULT:: markers, exit 0/1
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if cond else 'FAIL', (' | ' + detail) if (detail and not cond) else ''))


def _pos(coin, szi, value, upnl='0.0'):
    return {'position': {'coin': coin, 'szi': str(szi), 'positionValue': str(value),
                         'entryPx': '1', 'unrealizedPnl': upnl, 'marginUsed': '1'}}


def _state(account_value, notional, positions, withdrawable='10.0'):
    return {'marginSummary': {'accountValue': str(account_value), 'totalNtlPos': str(notional),
                              'totalMarginUsed': '1.5', 'totalRawUsd': str(account_value)},
            'withdrawable': withdrawable, 'assetPositions': positions}


DEF_STATE = _state(1967.94, 1967.94, [_pos('BTC', 0.01, 1000.0), _pos('ETH', 0.5, 967.94)])
XYZ_STATE = _state(183.89, 183.89, [_pos('XYZ:COPPER', 100, 120.0), _pos('XYZ:HOOD', 20, 63.89)])


def fetcher_ok(payload):
    if payload.get('type') == 'perpDexs':
        return [{'name': 'xyz'}]
    return XYZ_STATE if payload.get('dex') == 'xyz' else DEF_STATE


def fetcher_missing_scope(payload):
    if payload.get('type') == 'perpDexs':
        return [{'name': 'xyz'}]
    return DEF_STATE if not payload.get('dex') else {}


def main():
    tmp = Path(tempfile.mkdtemp(prefix='g4scope_'))
    os.environ['HL_LIVE_AUDIT_DIR'] = str(tmp)
    os.environ['HL_LIVE_AUTO_SEND_ENABLED'] = '0'
    os.environ['HL_LIVE_POLL_ENABLED'] = '0'
    os.environ['HL_LIVE_HL_ACCOUNT_ADDRESS'] = '0x7717a7a245d9f950e586822b8c9b46863ed7bd7e'

    import HL_Copy_App_SSOT as ui

    ui.SNAPSHOT_FETCHER = fetcher_ok
    snap = ui._fetch_exchange_account_snapshot(max_age_sec=0)
    total = snap.get('total_notional_position')
    check('A_SNAPSHOT_OK', snap.get('ok') and snap.get('available'), str(snap.get('reason'))[:200])
    check('B_TOTAL_IS_SUM_OF_SCOPES', total is not None and abs(total - (1967.94 + 183.89)) <= 0.01,
          'total_notional_position=%r expected=2151.83' % (total,))
    coins = snap.get('positions_by_coin') or {}
    check('C_XYZ_KEYS_PRESENT', all(k in coins for k in ('XYZ:COPPER', 'XYZ:HOOD')), 'coins=%r' % (sorted(coins)[:12],))
    check('D_SCOPE_PROVENANCE', snap.get('scope_dexes') == ['', 'xyz'] and len(snap.get('scope_breakdown') or []) == 2,
          'scope_dexes=%r' % (snap.get('scope_dexes'),))
    check('E_ACCOUNT_VALUE_SUMMED', abs((snap.get('account_value') or 0) - (1967.94 + 183.89)) <= 0.01,
          'account_value=%r' % (snap.get('account_value'),))
    check('F_HONEST_TOTAL_STILL_NULL', snap.get('total_account_value') is None
          and 'unavailable' in str(snap.get('total_account_value_status', '')),
          str(snap.get('total_account_value_status')))

    # cache-cold: with no previous snapshot on disk there is nothing to carry over, so a failed scope
    # read must produce no number at all (not the default-only one)
    ui.EXCHANGE_ACCOUNT_SNAPSHOT_FILE.unlink(missing_ok=True)
    ui.SNAPSHOT_FETCHER = fetcher_missing_scope
    bad = ui._fetch_exchange_account_snapshot(max_age_sec=0)
    check('G_MISSING_SCOPE_FAILS_CLOSED', not bad.get('ok') and not bad.get('available')
          and 'SCOPE_UNAVAILABLE' in str(bad.get('reason')),
          'ok=%r available=%r reason=%r' % (bad.get('ok'), bad.get('available'), str(bad.get('reason'))[:160]))
    check('H_NO_UNDER_REPORTED_TOTAL', bad.get('total_notional_position') is None,
          'total=%r' % (bad.get('total_notional_position'),))

    failed = [n for n, ok in RESULTS if not ok]
    print('RESULT::TOTAL_%d_FAILED_%d' % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
