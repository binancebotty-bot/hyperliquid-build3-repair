#!/usr/bin/env python3
# ENG-INV-09 (offline half): EXCHANGE TRUTH OUTRANKS LOCAL REPLAY.
#
# Requirement: exchange truth outranks local replay; the manual follower-position file is not
# authoritative. Proven here, offline, for the close/sizing path only:
#   P  precedence        - exchange and the manual sleeve disagree on size => exchange sizes the close
#   M  not authoritative - manual sleeve non-zero while clearinghouseState is flat => close refused
#   F  fail closed       - exchange read unavailable => HOLD, never adopt the manual value as truth
#
# Run: python test_eng_inv_09_offline.py   # RESULT:: markers, exit 0/1. No network, no orders.
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
LEADER = '0x' + 'd' * 40
FOLLOWER = '0x' + 'c' * 40


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if cond else 'FAIL', (' | ' + detail) if (detail and not cond) else ''))


def main():
    tmp = Path(tempfile.mkdtemp(prefix='enginv09_'))
    os.environ.update({'HL_LIVE_AUDIT_DIR': str(tmp), 'HL_LEADER_NETWORK': 'mainnet',
                       'HL_FOLLOWER_NETWORK': 'testnet', 'HL_LIVE_ENV_FILE': str(tmp / 'none.env')})
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    book = {'positions': [], 'down': False}

    def fetcher(payload):
        if payload.get('type') == 'perpDexs':
            return []
        if book['down']:
            raise RuntimeError('clearinghouseState unavailable')
        return {'assetPositions': [{'position': p} for p in book['positions']]}
    c.EXPOSURE_FETCHER = fetcher

    def mids_fetcher(payload):
        if payload.get('type') == 'perpDexs':
            return []
        return {'BTC': '100'}
    c.MIDS_FETCHER = mids_fetcher
    c._FOLLOWER_MIDS.update(px={}, ms=0)

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {'auto_send_enabled': True, 'global_controls': {}, 'wallets': {
        LEADER: {'enabled': True, 'mode': 'LIVE', 'copy_mode': 'fixed', 'fixed_notional': 1000}}})
    os.environ.pop('HL_LIVE_MOCK_SEND', None)

    seq = [0]

    def fill(side='SELL'):
        seq[0] += 1
        return c.LeaderFill('f%d' % seq[0], LEADER, 'BTC', side, 100.0, 1.0, c.utc_now_ms(), 'TEST')

    def build(manual_size, side='SELL'):
        led = c.ManualLedger(path=tmp / ('led%d.json' % seq[0]))
        if manual_size:
            led.sleeve(LEADER, 'BTC')['signed_size'] = manual_size
        return c.IntentBuilder(c.ConfigManager(), led).build(fill(side))

    # M: the manual file is NOT authoritative (local sleeve vs exchange flat)
    book['positions'] = []
    book['down'] = False
    i = build(10.0)
    check('M1_MANUAL_SLEEVE_NOT_AUTHORITATIVE_WHEN_EXCHANGE_FLAT',
          i.decision == 'SEND_BLOCKED_RISK' and 'EXCHANGE' in str(i.reason).upper(),
          '%s | %s | size=%s' % (i.decision, i.reason, i.copy_size))
    check('M2_NO_CLOSE_SIZED_FROM_A_STALE_MANUAL_SLEEVE', abs(i.copy_size) < 1e-9, str(i.copy_size))

    # P: precedence on a size disagreement (exchange wins)
    book['positions'] = [{'coin': 'BTC', 'szi': '4', 'positionValue': '400'}]
    i = build(10.0)
    check('P1_EXCHANGE_SIZE_SIZES_THE_CLOSE', abs(i.copy_size - 4.0) < 1e-9,
          '%s | %s | size=%s' % (i.decision, i.reason, i.copy_size))
    check('P2_CLOSE_STILL_ALLOWED_ON_DISAGREEMENT', i.decision == 'EXIT_ALLOWED', '%s | %s' % (i.decision, i.reason))
    check('P3_CLOSE_STAYS_REDUCE_ONLY', i.reduce_only_intended is True, str(i.reduce_only_intended))

    # F: exchange unreadable => HOLD, never fall back to the manual value
    book['down'] = True
    i = build(10.0)
    check('F1_UNREADABLE_EXCHANGE_HOLDS_THE_CLOSE', i.decision == 'SEND_BLOCKED_RISK',
          '%s | %s' % (i.decision, i.reason))
    check('F2_NO_FALLBACK_TO_THE_LOCAL_REPLAY_VALUE', abs(i.copy_size) < 1e-9,
          '%s | %s | size=%s' % (i.decision, i.reason, i.copy_size))
    check('F3_HOLD_REASON_NAMES_EXCHANGE_TRUTH', 'EXCHANGE' in str(i.reason).upper(), str(i.reason))
    book['down'] = False

    # control: agreement between all three sources is unchanged
    book['positions'] = [{'coin': 'BTC', 'szi': '10', 'positionValue': '1000'}]
    i = build(10.0)
    check('C1_AGREEMENT_UNCHANGED', i.decision == 'EXIT_ALLOWED' and abs(i.copy_size - 10.0) < 1e-9,
          '%s | %s | size=%s' % (i.decision, i.reason, i.copy_size))

    # control: a manual file that merely ANNOTATES does not change sizing
    led = c.ManualLedger(path=tmp / 'annot.json')
    sleeve = led.sleeve(LEADER, 'BTC')
    sleeve['signed_size'] = 10.0
    sleeve['note'] = 'operator annotation'
    sleeve['avg_entry_px'] = 99.5
    led.save()
    i = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / 'annot.json')).build(fill('SELL'))
    check('C2_ANNOTATION_DOES_NOT_CHANGE_SIZING', i.decision == 'EXIT_ALLOWED' and abs(i.copy_size - 10.0) < 1e-9,
          '%s | %s | size=%s' % (i.decision, i.reason, i.copy_size))

    # control: a reduction still passes when the exchange holds MORE than the sleeve
    book['positions'] = [{'coin': 'BTC', 'szi': '14', 'positionValue': '1400'}]
    i = build(10.0)
    check('C3_REDUCTION_STILL_PASSES_WITH_SLEEVE_SIZE', i.decision == 'EXIT_ALLOWED' and abs(i.copy_size - 10.0) < 1e-9,
          '%s | %s | size=%s' % (i.decision, i.reason, i.copy_size))

    # guard: manual long + exchange long => closing SELL is a sign conflict
    book['positions'] = [{'coin': 'BTC', 'szi': '-10', 'positionValue': '1000'}]
    i = build(10.0)
    check('C4_SIGN_CONFLICT_NOT_CLOSED', i.decision == 'SEND_BLOCKED_RISK' and abs(i.copy_size) < 1e-9,
          '%s | %s | size=%s' % (i.decision, i.reason, i.copy_size))

    # control: the ENTRY path is untouched by this rule
    book['positions'] = []
    i_entry = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / 'entry.json')).build(
        c.LeaderFill('e1', LEADER, 'BTC', 'BUY', 100.0, 1.0, c.utc_now_ms(), 'TEST'))
    check('C5_ENTRY_PATH_UNCHANGED', i_entry.decision == 'ENTRY_ALLOWED',
          '%s | %s' % (i_entry.decision, i_entry.reason))

    failed = [n for n, ok in RESULTS if not ok]
    print('TOTAL=%d FAILED=%d' % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
