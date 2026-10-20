#!/usr/bin/env python3
'''Core engine chaos suite: the four scenarios the register's engine rows name in negative_tests.

1 restart mid-sequence, 2 stale leader snapshot, 3 API 429/malformed/timeout, 4 duplicate and
reordered fills. Each runs clean (must hold) then with ONE mutation (must go RED).

Offline and deterministic: fakes only, injected clock, no network, no keys, no orders.

Module under test: _archive/hl_stage2/HL_Live_Copy_Service_Core.py imported as
HL_Live_Copy_Service_Core - the module the certification register names as the engine base
(HL_Live_Copy_Service_Core.py, 7,705-line, sha256 5bda57be) and the one the other offline Core
suites here import. Legacy HL_Live_Copy_Service.py is the convergence-shadow shell, not the engine.

Run: python test_core_chaos.py
'''
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

RESULTS = []
FOLLOWER = '0x' + 'c' * 40
LEADER = '0x' + 'd' * 40
CLOCK_MS = 1_000_000_000_000
ROOT = Path(tempfile.mkdtemp(prefix='chaos_'))
os.environ.update({
    'HL_LIVE_AUDIT_DIR': str(ROOT / 'import_only'),
    'HL_LEADER_NETWORK': 'mainnet', 'HL_FOLLOWER_NETWORK': 'testnet',
    'HL_LIVE_ENV_FILE': str(ROOT / 'none.env'),
    'HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS': '0',
    'HL_LIVE_MIDS_CACHE_TTL_SEC': '0', 'HL_LIVE_EXPOSURE_CACHE_TTL_SEC': '0',
    'HL_LIVE_PREWARM_SYMBOL_META': '0', 'HL_LIVE_PREWARM_SDK_CLIENT': '0',
})
for _k in ('HL_LIVE_MOCK_SEND', 'HL_LIVE_WS_ENABLED', 'HL_LIVE_AUTO_SEND_ENABLED'):
    os.environ.pop(_k, None)

import HL_Live_Copy_Service_Core as c  # noqa: E402
import exchange_truth as _XNET  # noqa: E402

c.utc_now_ms = lambda: CLOCK_MS
c.PROCESS_STARTED_AT_MS = CLOCK_MS
RESOLVED = {'ok': True, 'sdk_coin': 'BTC', 'sz_decimals': 3, 'price_max_decimals': 2, 'perp_dexs': [''],
            'sdk_order_compatible': True, 'min_order_value_usd': 1.0, 'min_size': 0.0, 'status': 'OK'}


class FakeExchange:
    def __init__(self):
        self.calls = []

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append({'coin': coin, 'is_buy': is_buy, 'size': size, 'px': px,
                           'tif': tif['limit']['tif'], 'reduce_only': reduce_only})
        return {'status': 'ok', 'response': {'type': 'order', 'data': {'statuses': [
            {'filled': {'totalSz': str(size), 'avgPx': str(px), 'oid': 1000 + len(self.calls)}}]}}}


def point_at(d):
    c.AUDIT_DIR = d
    c.APPEND_ONLY_DIR = d / 'append_only'
    for name in ('live_config', 'live_service_state', 'clean_core_runtime_state', 'live_ws_health',
                 'manual_live_positions', 'exchange_account_snapshot', 'live_integrity_status',
                 'asset_universe_snapshot', 'xyz_position_state'):
        setattr(c, name.upper() + '_FILE', d / (name + '.json'))
    for name in ('order_intents', 'send_attempts', 'live_fills', 'reconciliation', 'errors'):
        setattr(c, name.upper() + '_CSV', c.APPEND_ONLY_DIR / (name + '.csv'))


class World:
    def __init__(self, name):
        self.dir = ROOT / name
        shutil.rmtree(self.dir, ignore_errors=True)
        self.dir.mkdir(parents=True)
        point_at(self.dir)
        c.ensure_dirs()
        c._FOLLOWER_MIDS = {'px': {}, 'ms': 0, 'dexes': [''], 'dexes_ms': CLOCK_MS}
        self.fake = FakeExchange()
        self.orders = self.fake.calls
        self.truth_fault = ''
        self._install_truth()
        c.MIDS_FETCHER = lambda payload: [] if payload.get('type') == 'perpDexs' else {'BTC': '100'}
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            'auto_send_enabled': True, 'global_controls': {},
            'wallets': {LEADER: {'enabled': True, 'mode': 'LIVE', 'copy_mode': 'fixed',
                                 'fixed_notional': 1000.0}}})
        c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE,
                            {'created_at': 't', 'created_at_ms': CLOCK_MS,
                             'raw': {'assetPositions': []}, 'positions_by_coin': {}})
        c.USER_WALLET = FOLLOWER
        self.core = self.new_core()
        self._seq = 0

    def new_core(self):
        core = c.LiveCopyCore(source_csv=self.dir / 'none.csv')
        self.wire(core)
        return core

    def _install_truth(self):
        w = self

        def fetch(payload):
            kind, fault = payload.get('type'), w.truth_fault
            if fault in ('429', 'timeout'):
                raise (TimeoutError('read timed out') if fault == 'timeout'
                       else RuntimeError('ClientError(429, Too Many Requests)'))
            if kind == 'perpDexs':
                return []
            if kind == 'clearinghouseState':
                return {'nonsense': True} if fault == 'malformed' else {
                    'assetPositions': [], 'marginSummary': {'accountValue': '10000'}}
            if kind == 'portfolio':
                return [['day', {'accountValueHistory': [[0, '10000']], 'pnlHistory': [[0, '0']]}]]
            return {}
        c.EXPOSURE_FETCHER = fetch
        c.LEADER_FETCHER = fetch

    def wire(self, core):
        fake = self.fake
        core.sender._resolve_coin = lambda coin: dict(RESOLVED)
        core.sender._get_exchange_client = lambda *a, **k: fake
        core.sender._exchange_client_has_symbol = lambda *a, **k: True
        core.sender._validate_final_wire_order = lambda *a, **k: (True, {})
        core.sender._pre_exchange_asset_safety = lambda *a, **k: (True, {})

    def fill(self, side='BUY', ts=None, source='WS_CAPTURED', raw=None):
        self._seq += 1
        return c.LeaderFill('fill%d' % self._seq, LEADER, 'BTC', side, 100.0, 1.0,
                            CLOCK_MS if ts is None else ts, source, raw=dict(raw or {}))

    def deliver(self, core, fill):
        # same entry-gate argument the cycle hot path passes
        return core._process_leader_fill(fill, None, core._entry_sends_blocked_reason)

    def rows(self, path):
        return c.read_csv_rows(path) if path.exists() else []

    def events(self):
        return [r.get('event') for r in self.rows(c.RECONCILIATION_CSV)]

    def seed_sleeve(self, size):
        self.core.ledger.sleeve(LEADER, 'BTC')['signed_size'] = size
        self.core.ledger.save()


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if cond else 'FAIL',
                               (' | ' + str(detail)[:400]) if detail and not cond else ''))


def pair(name, clean_ok, clean_detail, mutated_still_ok, mut_detail):
    check(name + '_CLEAN', clean_ok, clean_detail)
    check(name + '_MUTATION_RED', not mutated_still_ok, mut_detail)


def restart_case():
    w = World('s1_restart')
    fill = w.fill('BUY')
    sent, status, _ = w.deliver(w.core, fill)
    orders_before = len(w.orders)
    intents_before = len(w.rows(c.ORDER_INTENTS_CSV))
    print('NOTE::S1_BEFORE_RESTART sent=%s status=%s orders=%s attempts=%s intents=%s'
          % (sent, status, orders_before, len(w.rows(c.SEND_ATTEMPTS_CSV)), intents_before))
    restarted = w.new_core()
    resent, resend_status, _ = w.deliver(restarted, c.LeaderFill(
        fill.leader_fill_id, LEADER, 'BTC', 'BUY', 100.0, 1.0, fill.timestamp_ms, 'WS_CAPTURED'))
    clean = (orders_before == 1 and len(w.orders) == 1 and not resent
             and resend_status == 'DUPLICATE_BLOCKED'
             and len(w.rows(c.ORDER_INTENTS_CSV)) == intents_before
             and 'DUPLICATE_LEADER_FILL_SKIPPED' in w.events())
    detail = 'orders=%s resent=%s status=%s intents=%s/%s events=%s' % (
        w.orders, resent, resend_status, len(w.rows(c.ORDER_INTENTS_CSV)), intents_before, w.events())

    m = World('s1_restart_mut')
    f2 = m.fill('BUY')
    m.deliver(m.core, f2)
    restarted2 = m.new_core()
    restarted2._idem_accepted.clear()
    resent2, status2, _ = m.deliver(restarted2, c.LeaderFill(
        f2.leader_fill_id, LEADER, 'BTC', 'BUY', 100.0, 1.0, f2.timestamp_ms, 'WS_CAPTURED'))
    return clean, detail, len(m.orders) == 1, 'orders=%s resent=%s status=%s' % (m.orders, resent2, status2)


def stale_case():
    w = World('s2_stale')
    stale_ts = CLOCK_MS - 60_000
    sent, status, intent = w.deliver(w.core, w.fill('BUY', ts=stale_ts, source='REBUILD'))
    clean = (not sent and status == 'STALE_REPLAY_IGNORED' and not w.orders and intent is None
             and 'STALE_SNAPSHOT_REPLAY_SKIPPED' in w.events()
             and not w.rows(c.SEND_ATTEMPTS_CSV) and not w.rows(c.ORDER_INTENTS_CSV))
    detail = 'sent=%s status=%s orders=%s events=%s' % (sent, status, w.orders, w.events())

    m = World('s2_stale_mut')
    real = c.stale_snapshot_replay_reason
    c.stale_snapshot_replay_reason = lambda fill, core_started_at_ms=CLOCK_MS: ''
    try:
        sent2, status2, _ = m.deliver(m.core, m.fill('BUY', ts=stale_ts, source='REBUILD'))
    finally:
        c.stale_snapshot_replay_reason = real
    return (clean, detail, (not sent2 and not m.orders),
            'sent=%s status=%s orders=%s' % (sent2, status2, m.orders))


def api_case():
    seen, clean = {}, True
    for fault in ('429', 'malformed', 'timeout'):
        w = World('api_' + fault)
        w.truth_fault = fault
        exp = c.IntentBuilder(c.ConfigManager(), w.core.ledger).follower_exposure()
        unreadable = exp.get('ok') is False and bool(exp.get('status'))
        sent, status, intent = w.deliver(w.core, w.fill('BUY'))
        held = not sent and not w.orders
        seen[fault] = {'exp_ok': exp.get('ok'), 'exp_status': exp.get('status'), 'sent': sent,
                       'status': status, 'decision': intent.decision if intent else None,
                       'reason': (intent.reason if intent else '')[:90]}
        clean = clean and unreadable and held
    detail = str(seen)

    m = World('api_mut')
    m.truth_fault = '429'
    def empty(payload):
        kind = payload.get('type')
        if kind == 'perpDexs':
            return []
        if kind == 'allMids':            # the mids path is not the fault under test; keep it readable
            return {'BTC': '100'}
        return {'assetPositions': [], 'marginSummary': {'accountValue': '0'}}
    real_fetcher, real_post = c.EXPOSURE_FETCHER, _XNET._post
    c.EXPOSURE_FETCHER = empty
    _XNET._post = lambda fetcher, payload, info_url, timeout: {'ok': True, 'data': empty(payload)}
    try:
        sent2, status2, _ = m.deliver(m.core, m.fill('BUY'))
    finally:
        c.EXPOSURE_FETCHER, _XNET._post = real_fetcher, real_post
    return (clean, detail, (not sent2 and not m.orders),
            'sent=%s status=%s orders=%s' % (sent2, status2, m.orders))


def duplicate_case():
    w = World('s4_dup')
    fill = w.fill('BUY')
    sent1, status1, _ = w.deliver(w.core, fill)
    sent2, status2, _ = w.deliver(w.core, c.LeaderFill(
        fill.leader_fill_id, LEADER, 'BTC', 'BUY', 100.0, 1.0, fill.timestamp_ms, 'WS_CAPTURED'))
    clean = (sent1 and len(w.orders) == 1 and not sent2 and status2 == 'DUPLICATE_BLOCKED'
             and len(w.rows(c.ORDER_INTENTS_CSV)) == 1
             and 'DUPLICATE_LEADER_FILL_SKIPPED' in w.events())
    detail = 'sent1=%s sent2=%s status2=%s orders=%s intents=%s events=%s' % (
        sent1, sent2, status2, w.orders, len(w.rows(c.ORDER_INTENTS_CSV)), w.events())

    m = World('s4_dup_mut')
    f2 = m.fill('BUY')
    m.deliver(m.core, f2)
    m.core._idem_accepted.clear()
    m.core.dedupe.processed.clear()
    m.deliver(m.core, c.LeaderFill(f2.leader_fill_id, LEADER, 'BTC', 'BUY', 100.0, 1.0,
                                   f2.timestamp_ms, 'WS_CAPTURED'))
    return clean, detail, len(m.orders) <= 1, 'orders=%s' % (m.orders,)


def reorder_case():
    # timestamps must be at/after live_start_ms or the engine (correctly) treats them as PRE_CUTOVER history
    w = World('s4_order')
    w.deliver(w.core, w.fill('BUY', ts=CLOCK_MS, raw={'dir': 'Open Long'}))
    w.seed_sleeve(1.0)
    w.deliver(w.core, w.fill('SELL', ts=CLOCK_MS + 1000, raw={'dir': 'Close Long'}))
    clean = (len(w.orders) == 2 and w.orders[0]['is_buy'] and not w.orders[1]['is_buy']
             and w.orders[1]['reduce_only'] is True)
    detail = 'orders=%s' % (w.orders,)

    m = World('s4_order_rev')
    b2 = m.fill('BUY', ts=CLOCK_MS - 2000, raw={'dir': 'Open Long'})
    s2 = m.fill('SELL', ts=CLOCK_MS - 1000, raw={'dir': 'Close Long'})
    for f in (s2, b2):
        m.deliver(m.core, f)
    clean = clean and not [o for o in m.orders if not o['is_buy'] and not o['reduce_only']]
    detail += ' reordered=%s' % (m.orders,)

    m2 = World('s4_order_rev_mut')
    b3 = m2.fill('BUY', ts=CLOCK_MS, raw={'dir': 'Open Long'})
    s3 = m2.fill('SELL', ts=CLOCK_MS + 1000, raw={'dir': 'Close Long'})
    real = c.IntentBuilder._is_leader_close_fill
    c.IntentBuilder._is_leader_close_fill = staticmethod(lambda fill: False)
    try:
        for f in (s3, b3):
            m2.deliver(m2.core, f)
    finally:
        c.IntentBuilder._is_leader_close_fill = staticmethod(real)
    flip2 = [o for o in m2.orders if not o['is_buy'] and not o['reduce_only']]
    return clean, detail, not flip2, 'orders=%s' % (m2.orders,)


def restart_retry_probe():
    '''Finding probe (not a scenario): does a safety-blocked entry burn the fill's send authority?'''
    w = World('probe_retry')
    cfg = c.load_json(c.LIVE_CONFIG_FILE, {})
    cfg['global_controls'] = {'max_daily_loss_usd': 10}
    c.atomic_write_json(c.LIVE_CONFIG_FILE, cfg)
    w.core.cfg = c.ConfigManager()
    real_pnl = _XNET.rolling_day_pnl
    _XNET.rolling_day_pnl = lambda *a, **k: {'ok': True, 'status': 'TRUTH_OK', 'pnl_usd': -99.0,
                                             'account_value_usd': 10000.0}
    try:
        w.core._entry_sends_blocked_reason = w.core._daily_loss_block()
        fill = w.fill('BUY')
        blocked_sent, blocked_status, _ = w.deliver(w.core, fill)
    finally:
        _XNET.rolling_day_pnl = real_pnl
    blocked_orders = len(w.orders)
    cfg['global_controls'] = {}
    c.atomic_write_json(c.LIVE_CONFIG_FILE, cfg)
    w.core.cfg = c.ConfigManager()
    w.core._entry_sends_blocked_reason = ''
    w.core._daily_pnl = (None, 0)
    retry_sent, retry_status, _ = w.deliver(w.core, c.LeaderFill(
        fill.leader_fill_id, LEADER, 'BTC', 'BUY', 100.0, 1.0, fill.timestamp_ms, 'WS_CAPTURED'))
    # Same-instance only: SEND_ATTEMPTS_CSV is the restart seed (Core 6018), and a blocked entry
    # writes no row there, so a restart recovers the fill. Probe both so the print is not alarmist.
    r = w.new_core()
    boot_sent, boot_status, _ = w.deliver(r, c.LeaderFill(
        fill.leader_fill_id, LEADER, 'BTC', 'BUY', 100.0, 1.0, fill.timestamp_ms, 'WS_CAPTURED'))
    return {'blocked_sent': blocked_sent, 'blocked_status': blocked_status,
            'blocked_orders': blocked_orders, 'retry_sent': bool(retry_sent),
            'retry_status': retry_status,
            'missed_in_session': bool(blocked_orders == 0 and not retry_sent),
            'recovers_on_restart': bool(boot_sent and boot_status == 'ORDER_FILLED')}


def main():
    c.HLAccount, c.HLExchange = object, object
    os.environ['HL_LIVE_HL_PRIVATE_KEY'] = '0x' + '1' * 64
    try:
        pair('S1_RESTART_MID_SEQUENCE', *restart_case())
        pair('S2_STALE_LEADER_SNAPSHOT', *stale_case())
        pair('S3_API_429_MALFORMED_TIMEOUT', *api_case())
        pair('S4_DUPLICATE_FILL', *duplicate_case())
        pair('S4_REORDERED_FILL_NO_NET_FLIP', *reorder_case())
        print('PROBE::RESTART_RETRY_AUTHORITY %s' % restart_retry_probe())
    finally:
        os.environ.pop('HL_LIVE_HL_PRIVATE_KEY', None)
    failed = [n for n, ok in RESULTS if not ok]
    print('TOTAL=%d FAILED=%d' % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
