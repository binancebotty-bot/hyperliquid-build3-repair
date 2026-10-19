#!/usr/bin/env python3
# Offline TOCTOU race-injection test for the disarmed fill fast path.
#
# THE REACHABLE RACE (verified in send_mode_now): an engine that BOOTED disarmed latches OFF for its
# whole life (send_mode_now early-returns when self.send_mode == 'OFF'), so arming is only reachable
# for an engine that booted ARMED and is then disarmed from the config file. That engine's
# send_mode_now() follows the file through _switch_mode, so this is the real window:
#
#   boot ON -> operator writes OFF -> fill checks send_mode_now()==OFF -> operator writes ON ->
#   fill records itself as skipped. On pre-fix code that fill is consumed silently.
#
# The test must FAIL on the pre-fix core and PASS on the fix.
from __future__ import annotations

import os
import sys
import tempfile
import time
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
    tmp = Path(tempfile.mkdtemp(prefix='toctou_race_'))
    os.environ.update({
        'HL_LIVE_AUDIT_DIR': str(tmp), 'HL_LEADER_NETWORK': 'testnet', 'HL_FOLLOWER_NETWORK': 'testnet',
        'HL_LIVE_ENV_FILE': str(tmp / 'none.env'), 'HL_LIVE_SCOPE_SWEEP_THREAD': '0',
        'HL_LIVE_MOCK_SEND': '1', 'HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS': '0',
        'HL_LIVE_HOT_SEND_WORKERS': '1', 'HL_LIVE_STACK_SAMPLE_SEC': '0',
        'HL_LIVE_DEFER_RETRY_SEC': '0.5', 'HL_LIVE_AUDIT_KEEP_OPEN': '0',
    })
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*_a, **_k):
        raise AssertionError('test attempted network I/O')

    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get('type') == 'perpDexs' else {'BTC': '100'}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

    def config(mode):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            'auto_send_enabled': mode != 'OFF',
            'global_controls': {'send_mode': mode},
            'wallets': {LEADER: {'enabled': True, 'mode': 'LIVE', 'copy_mode': 'fixed', 'fixed_notional': 12}},
        })
        # a distinct mtime per write so send_mode_now()/_arm_generation see a NEW file
        os.utime(c.LIVE_CONFIG_FILE, None)

    def fill(fid):
        return c.LeaderFill(fid, LEADER, 'BTC', 'BUY', 100.0, 0.1, c.utc_now_ms(), 'TEST', 0, {'dir': 'Open Long'})

    # Boot ARMED, then disarm: the engine's send_mode_now() now follows the file.
    config('ON')
    core = c.LiveCopyCore(source_csv=tmp / 'none.csv')
    config('OFF')
    check('ENGINE_READS_FILE_AS_OFF_AFTER_DISARM', core.cfg.send_mode_now() == 'OFF', core.cfg.send_mode_now())

    calls = {'build': 0, 'prewarm': 0, 'cancel': 0, 'read': 0, 'send': 0}

    def unexpected(n, bucket=None):
        def f(*_a, **_k):
            (bucket if bucket is not None else calls)[n] += 1
            raise AssertionError('reached ' + n)
        return f

    core.intent_builder.build = unexpected('build')
    core._prewarm_with_parity = unexpected('prewarm')
    core.sender.cancel_resting_entries_against = unexpected('cancel')
    core._read_fills_of_withdrawn_limits = unexpected('read')
    core.sender.send_if_allowed = unexpected('send')

    # ---- RACE INJECTION: re-arm exactly between the OFF decision and the marking point.
    armed = {'done': False}
    real_invalidate = core._invalidate_disarmed_fill_caches

    def invalidate_then_arm(f):
        real_invalidate(f)
        if not armed['done']:
            armed['done'] = True
            config('ON')

    core._invalidate_disarmed_fill_caches = invalidate_then_arm

    f1 = fill('race-1')
    res = core._process_leader_fill(f1, c.CycleSummary(), '')
    check('RACE_WAS_INJECTED', armed['done'])
    check('REARM_IS_VISIBLE_TO_THE_ENGINE', core.cfg.send_mode_now() == 'ON', core.cfg.send_mode_now())
    check('RACE_FILL_NOT_TERMINALISED_AS_OFF', res[1] != 'MASTER_REAL_ORDERS_OFF', str(res[:2]))
    check('RACE_FILL_RECORDED_AS_DEFERRED', res[1] == 'DISARMED_DEFERRED_ARM_MOVED', str(res[:2]))
    key = core._guard_key(f1)
    check('RACE_FILL_HELD_FOR_ARMED_PATH', key in core._deferred, str(list(core._deferred)))
    check('HELD_KIND_IS_DISARMED', core.__dict__.get('_deferred_kind', {}).get(key) == 'disarmed')
    check('GUARD_RELEASED_FOR_REOFFER', key not in core._idem_accepted)
    check('DEDUPE_ROLLED_BACK', f1.leader_fill_id not in core.dedupe.processed)
    check('NO_NETWORK_IN_RACE_PATH', not any(calls.values()), str(calls))

    race_rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get('leader_fill_id') == 'race-1']
    off_rows = [r for r in race_rows if r.get('reject_category') == 'MASTER_REAL_ORDERS_OFF'
                or r.get('terminal_state') == 'SEND_NOT_ATTEMPTED_AUTO_SEND_DISABLED']
    check('NO_DISARMED_TERMINAL_ROW_FOR_RACED_FILL', not off_rows, str(off_rows[:1]))
    defer_rows = [r for r in race_rows if r.get('terminal_state') == 'REPLAY_DEFERRED_DISARMED_RACE']
    check('ONE_AUDIT_ROW_WITH_REASON_AND_LEADER_FILL_ID', len(defer_rows) == 1
          and defer_rows[0].get('leader_fill_id') == 'race-1'
          and 'never silently dropped' in str(defer_rows[0].get('notes')), str(defer_rows[:1]))

    # ---- Stage 2: the now-ARMED engine picks the held fill up and resolves it.
    core.intent_builder.build = lambda f, *a, **k: c.Intent(
        intent_id='intent-race-1', fill=f, copy_side='BUY', copy_size=0.12, copy_notional=12.0,
        wallet_mode='LIVE', copy_mode='fixed', decision='ENTRY_ALLOWED',
        reason='offline deterministic test', sleeve_id='s', position_id='p',
        position_direction_before='FLAT', wallet_position_before=0.0, coin_net_before=0.0,
        reduce_only_intended=False, reduce_only_sent_planned=False)
    core._prewarm_with_parity = lambda *a, **k: None
    core.sender.cancel_resting_entries_against = lambda *a, **k: []
    core.copy_ingestor.poll_copy_account_fills = lambda *a, **k: ([], 'COPY_ACCOUNT_POLLED')
    core._read_fills_of_withdrawn_limits = lambda *a, **k: ([], 'COPY_ACCOUNT_POLLED')
    core._apply_fills_of_withdrawn_limits = lambda *a, **k: 0
    def mock_send(intent, *a, **k):
        # the engine's own mock writer: real send_attempts row, real terminal state, no exchange call
        core.sender._append_mock_attempt(intent, 'ORDER_FILLED')
        return True, 'ORDER_FILLED'

    core.sender.send_if_allowed = mock_send
    offered = []

    def dispatch_armed(f):
        offered.append(f.leader_fill_id)
        return core._process_leader_fill(f)

    core._dispatch_fill = dispatch_armed
    deadline = time.time() + 5.0
    while key in core._deferred and time.time() < deadline:
        time.sleep(0.1)
    check('HELD_FILL_REOFFERED_TO_ARMED_PATH', offered == ['race-1'], str(offered))
    check('DEFERRED_QUEUE_DRAINED', key not in core._deferred)

    sends = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV) if r.get('leader_fill_id') == 'race-1']
    send_states = [str(r.get('status')) for r in sends]
    check('RACED_FILL_RESOLVED_WITH_A_SEND_ROW',
          any(s in {'ORDER_FILLED', 'ORDER_PARTIAL', 'ORDER_RESTING', 'MOCK_ORDER_SENT'} for s in send_states),
          str(send_states))

    # ---- Stage 3: the real classifier agrees the fill is resolved (not MISSING / DEFERRED_OPEN).
    import outage_classify
    verdicts = outage_classify.classify(tmp / 'append_only', ['race-1'])
    check('CLASSIFIER_UNRESOLVED_ZERO_FOR_RACED_FILL',
          verdicts.get('race-1') not in (None, 'MISSING', 'DEFERRED_OPEN'), str(verdicts))

    # ---- Stage 4: a genuinely disarmed engine keeps the fast path (performance win intact).
    config('OFF')
    core2 = c.LiveCopyCore(source_csv=tmp / 'none.csv')
    calls2 = {'build': 0, 'prewarm': 0, 'cancel': 0, 'read': 0, 'send': 0}
    core2.intent_builder.build = unexpected('build', calls2)
    core2._prewarm_with_parity = unexpected('prewarm', calls2)
    core2.sender.cancel_resting_entries_against = unexpected('cancel', calls2)
    core2._read_fills_of_withdrawn_limits = unexpected('read', calls2)
    core2.sender.send_if_allowed = unexpected('send', calls2)
    r2 = core2._process_leader_fill(fill('genuine-off'), c.CycleSummary(), '')
    check('GENUINE_OFF_STILL_TAKES_FAST_PATH', r2[1] == 'MASTER_REAL_ORDERS_OFF' and not any(calls2.values()), str(r2[:2]))
    check('GENUINE_OFF_WRITES_ITS_TERMINAL_ROW', bool([r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
          if r.get('leader_fill_id') == 'genuine-off' and r.get('reject_category') == 'MASTER_REAL_ORDERS_OFF']))

    failed = [n for n, ok in RESULTS if not ok]
    print('TOTAL=%d FAILED=%d' % (len(RESULTS), len(failed)))
    print('AUDIT_DIR=%s' % tmp)
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
