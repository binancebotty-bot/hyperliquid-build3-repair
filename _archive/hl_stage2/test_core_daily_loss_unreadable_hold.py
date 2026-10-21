#!/usr/bin/env python3
"""Daily-loss control, PnL UNREADABLE: an exposure-increasing order is HELD (and replayed once PnL is readable),
reductions pass, an alert row is written. Unreadable is a hold, never "no loss". A readable PnL over the cap is
still the operator's hard stop.

Run: python test_core_daily_loss_unreadable_hold.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix='dl_unreadable_'))
os.environ.update({'HL_LIVE_AUDIT_DIR': str(tmp), 'HL_LIVE_ENV_FILE': str(tmp / 'none.env'),
                   'HL_LIVE_MOCK_SEND': '1', 'HL_LIVE_DEFER_RETRY_SEC': '3600'})  # replay driven by hand; a live retry would race C6
os.environ.pop('HL_LIVE_GATES_ALERT_ONLY', None)   # default: alert-only ON; the daily-loss stop is what we test
os.environ.pop('HL_LIVE_DEFER_MAX_SEC', None)      # default: hold until readable

import requests
import HL_Live_Copy_Service_Core as c

R = []


def check(name, ok, detail=''):
    R.append(bool(ok))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)) if detail and not ok else ''))


LEADER = '0x' + 'd' * 40
FOLLOWER = '0x' + 'c' * 40
c.USER_WALLET = FOLLOWER


def offline(*a, **k):
    raise RuntimeError('offline test: no network')


requests.post = offline
c.requests.post = offline
c.MIDS_FETCHER = lambda payload: [] if payload.get('type') == 'perpDexs' else {'BTC': '100'}

pnl = {'rows': None, 'reads': 0}


def fetcher(payload):
    if payload.get('type') == 'portfolio':
        pnl['reads'] += 1
        if pnl['rows'] is None:
            raise RuntimeError('portfolio unavailable')
        return [['day', {'accountValueHistory': [], 'pnlHistory': pnl['rows']}]]
    return {'assetPositions': []}


c.EXPOSURE_FETCHER = fetcher
c.atomic_write_json(c.LIVE_CONFIG_FILE, {
    'auto_send_enabled': True,
    'global_controls': {'max_daily_loss_usd': 50},
    'wallets': {LEADER: {'enabled': True, 'mode': 'LIVE', 'copy_mode': 'fixed', 'fixed_notional': 100}},
})

core = c.LiveCopyCore(source_csv=tmp / 'none.csv')
core.sender.cfg.master_switch_now = lambda: True                  # sending on; the daily-loss control is under test
core.sender._pre_send_ownership_gate = lambda intent: (True, {})  # isolate the gate under test
seq = [0]


def fill(side='BUY'):
    seq[0] += 1
    return c.LeaderFill('dl%d' % seq[0], LEADER, 'BTC', side, 100.0, 1.0, c.utc_now_ms(), 'TEST')


def cycle_block(rows):
    """What run_cycle does: evaluate the gate, then offer the fill with the published reason."""
    pnl['rows'] = rows
    core._daily_pnl = None
    core._entry_sends_blocked_reason = core._daily_loss_block()
    return core._entry_sends_blocked_reason


def rows_of(fid):
    return [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get('leader_fill_id') == fid]


try:
    # ---- C1. the CYCLE keeps publishing the unreadable gate under alert-only (no GATE_WOULD_BLOCK pass-through)
    pnl['rows'] = None
    core._daily_pnl = None
    n0 = len(c.read_csv_rows(c.RECONCILIATION_CSV))
    core.run_cycle(use_source_csv=False)
    new_rows = c.read_csv_rows(c.RECONCILIATION_CSV)[n0:]
    check('C1_CYCLE_PUBLISHES_UNREADABLE_UNDER_ALERT_ONLY',
          core._entry_sends_blocked_reason == 'DAILY_LOSS_UNREADABLE', core._entry_sends_blocked_reason)
    check('C1_UNREADABLE_NOT_ALERT_ONLY',
          not any(r.get('event') == 'GATE_WOULD_BLOCK' and r.get('status') == 'DAILY_LOSS_UNREADABLE' for r in new_rows),
          [(r.get('event'), r.get('status')) for r in new_rows])

    # ---- C2. unreadable + increase: HELD, no send, alert row
    block = cycle_block(None)
    f1 = fill('BUY')
    sent, status, _i = core._process_leader_fill(f1, None, block)
    held = core._deferred.get(core._guard_key(f1))
    r1 = rows_of(f1.leader_fill_id)
    check('C2_UNREADABLE_INCREASE_HELD',
          sent is False and status == 'REPLAY_DEFERRED_DAILY_LOSS_UNREADABLE' and held is not None,
          '%s %s held=%s' % (sent, status, held is not None))
    check('C2_NO_ORDER_SENT', not any(r.get('terminal_state') in ('MOCK_ORDER_SENT', 'ORDER_FILLED') for r in r1),
          [r.get('terminal_state') for r in r1])
    check('C2_ALERT_ROW_WRITTEN',
          any(r.get('event') == 'REPLAY_DEFERRED' and r.get('terminal_state') == 'REPLAY_DEFERRED_DAILY_LOSS_UNREADABLE' for r in r1),
          [(r.get('event'), r.get('terminal_state')) for r in r1])

    # ---- C3. unreadable + reduction: passes
    block = cycle_block(None)
    core.ledger.sleeve(LEADER, 'BTC')['signed_size'] = 1.0     # follower holds 1 long: a SELL reduces
    f2 = fill('SELL')
    sent2, status2, _i2 = core._process_leader_fill(f2, None, block)
    check('C3_UNREADABLE_REDUCTION_PASSES',
          sent2 is True and status2 == 'MOCK_ORDER_SENT' and core._guard_key(f2) not in core._deferred,
          '%s %s' % (sent2, status2))

    # ---- C4. readable, under the cap: passes
    block = cycle_block([[0, '0'], [1, '-10']])
    f3 = fill('BUY')
    sent3, status3, _i3 = core._process_leader_fill(f3, None, block)
    check('C4_READABLE_UNDER_CAP_PASSES', sent3 is True and status3 == 'MOCK_ORDER_SENT', '%s %s' % (sent3, status3))

    # ---- C5. readable, over the cap: blocked (the operator's hard stop)
    block = cycle_block([[0, '0'], [1, '-60']])
    f4 = fill('BUY')
    sent4, status4, _i4 = core._process_leader_fill(f4, None, block)
    r4 = rows_of(f4.leader_fill_id)
    check('C5_READABLE_OVER_CAP_BLOCKS',
          sent4 is False and status4 == 'ENTRY_BLOCKED_DAILY_LOSS_LIMIT_REACHED'
          and core._guard_key(f4) not in core._deferred, '%s %s' % (sent4, status4))
    check('C5_BLOCK_IS_TERMINAL_ROW',
          any(r.get('terminal_state') == 'ENTRY_BLOCKED_DAILY_LOSS_LIMIT_REACHED' for r in r4),
          [(r.get('event'), r.get('terminal_state')) for r in r4])

    # ---- C6. a held order replays once the PnL is readable (fresh fill: C3 stamped the leader side on f1's coin)
    block = cycle_block(None)
    f5 = fill('BUY')
    held5 = core._process_leader_fill(f5, None, block)
    block = cycle_block([[0, '0'], [1, '-5']])
    replay = core._process_leader_fill(f5, None, block)
    again = core._process_leader_fill(f5, None, block)  # exactly one order: a re-read of the held fill is not sent again
    check('C6_HELD_ORDER_REPLAYS_WHEN_READABLE',
          held5[1] == 'REPLAY_DEFERRED_DAILY_LOSS_UNREADABLE' and replay[0] is True and replay[1] == 'MOCK_ORDER_SENT'
          and again[1] == 'DUPLICATE_BLOCKED',
          '%s %s %s %s' % (held5[1], replay[0], replay[1], again[1]))
finally:
    core.stop()

failed = R.count(False)
print('TOTAL=%d FAILED=%d' % (len(R), failed))
raise SystemExit(1 if failed else 0)
