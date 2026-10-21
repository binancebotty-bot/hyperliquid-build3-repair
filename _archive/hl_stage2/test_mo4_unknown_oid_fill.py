#!/usr/bin/env python3
"""MO#4: an unknown-OID copy fill must not be attributed via fallback matching.

Run:  python test_mo4_unknown_oid_fill.py     # PASS/FAIL lines, exit 0/1
Pure/offline: temp audit dir, no network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

_tmp = Path(tempfile.mkdtemp(prefix='mo4_'))
os.environ['HL_LIVE_AUDIT_DIR'] = str(_tmp)
os.environ['HL_LIVE_AUTO_SEND_ENABLED'] = '0'
os.environ['HL_LIVE_POLL_ENABLED'] = '0'

import HL_Live_Copy_Service_Core as core  # noqa: E402

_fails = 0


def check(name, cond):
    global _fails
    if not cond:
        _fails += 1
    print(('  PASS: ' if cond else '  FAIL: ') + name)


def intent(iid, ts):
    fill = core.LeaderFill(
        leader_fill_id='lf-' + iid, leader_wallet='0xleader', coin='BTC', side='BUY',
        price=100.0, size=1.0, timestamp_ms=ts, source='TEST', raw={},
    )
    return core.Intent(
        intent_id=iid, fill=fill, copy_side='BUY', copy_size=0.1, copy_notional=10.0,
        wallet_mode='LIVE', copy_mode='proportional', decision='ENTRY_ALLOWED', reason='t',
        sleeve_id='s1', position_id='p1', position_direction_before='FLAT',
        wallet_position_before=0.0, coin_net_before=0.0,
        reduce_only_intended=False, reduce_only_sent_planned=False,
    )


def matcher():
    return core.CopyFillMatcher(core.ManualLedger(), core.AuditLogWriter())


def fill(ts, oid=None):
    raw = {'coin': 'BTC', 'side': 'B', 'px': 100.0, 'sz': 0.1, 'time': ts}
    if oid is not None:
        raw['oid'] = oid
    return raw


TS = 1700000000000

# control 1: no OID at all -> fallback matching still attributes
m = matcher()
got = m._choose_intent(fill(TS), {'i1': intent('i1', TS)})
check('no-OID fill still attributed by fallback (control)', got is not None and got.intent_id == 'i1')

# control 2: KNOWN OID -> attributed through the OID index
m = matcher()
m.sent_oid_index = {'4242': {'intent_id': 'i1'}}
got = m._choose_intent(fill(TS, 4242), {'i1': intent('i1', TS)})
check('known-OID fill still attributed via OID index (control)', got is not None and got.intent_id == 'i1')

# the behaviour: UNKNOWN OID -> no attribution, no fallback
m = matcher()
m.sent_oid_index = {}
m.recovery_oid_index = {}
got = m._choose_intent(fill(TS, 999999), {'i1': intent('i1', TS)})
check('unknown-OID fill NOT attributed (no fallback)', got is None)

print('\nRESULT:: ' + ('PASS' if _fails == 0 else 'FAIL') + ' fails=%d' % _fails)
sys.exit(0 if _fails == 0 else 1)
