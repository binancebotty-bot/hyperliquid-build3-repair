'''EXIT path timing stamps: EMISSION tests, not source-presence tests.

Every stamp below is proved by DRIVING the code path with a stubbed exchange surface and reading the timing
record the call actually returns.  Per stamp the value must be:
  * PRESENT   -- the key exists on the timing record the call returned (a stamp removed from the source fails here);
  * ORDERED   -- finished_ms >= started_ms > 0 (a stamp that never writes a usable epoch fails here);
  * RESPONSIVE -- the delta MOVES when the instrumented step is made artificially slow (a stamp pinned to 0 or to
                  any constant passes a naive presence test and fails here).

What a FAILING value looks like, per stamp:
  standing_close_*  missing -> the standing-close cancel went untimed again; delta == 0 while the withdraw slept
                    60 ms -> the stamp is not actually bracketing the cancel round-trip.
  close_plan_*      missing -> the close plan (which reads the follower account) went untimed; delta == 0 while the
                    plan slept 60 ms -> the bracket is around the wrong thing.
  exchange_net_*    missing -> the fresh follower-account read inside the close plan went untimed; delta == 0 while
                    the read slept 60 ms -> the bracket does not cover the network read.

The mutation control lives in mutate_exit_timing_stamps.py, which deletes each pair from a copy of the module
(expects FAIL) and pins each pair to a constant (expects FAIL).

Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_exit_timing_stamps.py
Optional: HL_EXIT_STAMP_MODULE_DIR=<dir holding HL_Live_Copy_Service_Core.py to import instead> (mutation harness).
'''
import os
import sys
import time
import importlib.util
from types import SimpleNamespace

os.environ.setdefault('HL_LIVE_ENV_FILE', '/nonexistent')
os.environ.setdefault('HL_LIVE_HL_PRIVATE_KEY', 'test-only-not-a-key')
os.environ.setdefault('HL_LIVE_HL_ACCOUNT_ADDRESS', '0x0000000000000000000000000000000000000001')

HERE = os.path.dirname(os.path.abspath(__file__))
MOD_DIR = os.environ.get('HL_EXIT_STAMP_MODULE_DIR') or HERE
MOD_PATH = os.path.join(MOD_DIR, 'HL_Live_Copy_Service_Core.py')

_spec = importlib.util.spec_from_file_location('exit_stamp_core_under_test', MOD_PATH)
c = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = c
_spec.loader.exec_module(c)

R = []
DELAY_S = 0.06
DELAY_MS = int(DELAY_S * 1000)
FLOOR_MS = int(DELAY_MS * 0.8)  # tolerate Windows clock granularity, not a 0/constant stamp


def check(n, ok, d=''):
    R.append((n, bool(ok)))
    print(('PASS' if ok else 'FAIL'), n, d)
    print('RESULT::%s_%s' % (n, 'PASS' if ok else 'FAIL'))


# ---------------------------------------------------------------- registry checks (runtime values, not file text)
NEW_KEYS = ['standing_close_started_ms', 'standing_close_finished_ms',
            'close_plan_started_ms', 'close_plan_finished_ms',
            'exchange_net_started_ms', 'exchange_net_finished_ms']

for k in NEW_KEYS:
    check('FIELD_LISTED_SEND_ATTEMPT::' + k, k in c.SEND_ATTEMPT_FIELDS)
    check('FIELD_LISTED_SEND_TIMING::' + k, k in c.SEND_TIMING_FIELDS)


# ---------------------------------------------------------------- driving harness
def make_intent():
    return SimpleNamespace(
        fill=SimpleNamespace(leader_wallet='0xabc', leader_fill_id='lf-1', coin='RESOLV', price=100.0),
        copy_side='SELL', copy_size=10.0, copy_notional=1000.0, intent_id='intent-1', sleeve_id='sleeve-1')


def make_resolved():
    return {'ok': True, 'sdk_coin': 'RESOLV', 'sz_decimals': 2, 'price_max_decimals': 2,
            'perp_dexs': [], 'min_order_value_usd': 0.0, 'min_size': 0.0, 'sdk_order_compatible': True}


def make_gateway(net=10.0):
    gw = object.__new__(c.SenderGateway)
    gw.cfg = SimpleNamespace(marketable_bps=lambda: 0.0, max_close_adverse_diff_pct=lambda: 0.0,
                             min_notional=lambda: 0.0, max_order_notional=lambda: 0.0)
    gw.ledger = SimpleNamespace(coin_net=lambda key: net)
    gw._reduce_only_for_intent = lambda intent: True
    gw._resolve_coin = lambda coin: dict(make_resolved())
    gw._pre_exchange_asset_safety = lambda intent, resolved, px, size: (True, {})
    gw._validate_final_wire_order = lambda *a, **k: (True, {})
    gw._get_exchange_client = lambda *a, **k: object()
    gw._exchange_client_has_symbol = lambda exchange, coin: True
    gw._ensure_margin_mode = lambda *a, **k: None
    gw._repair_ledger_if_exchange_flat = lambda intent, err: ''
    gw._begin_pending_send = lambda *a, **k: None
    gw._place_order = lambda *a, **k: (_ for _ in ()).throw(AssertionError('no order may be placed in this test'))
    return gw


def drive_send_real(delay_withdraw=0.0, delay_plan=0.0, net=10.0):
    '''Drive the real _send_real through the EXIT branch. The close plan returns a skip, so the run returns
    SEND_NOT_ATTEMPTED_CLOSE_AT_TARGET carrying the timing record before any order would be placed.'''
    gw = make_gateway(net)
    seen = []

    def _withdraw(exchange, intent, wire_size, sz_dec, timing):
        if delay_withdraw:
            time.sleep(delay_withdraw)
        seen.append('withdraw')
        return wire_size, None

    def _plan(intent, size, sz_dec, min_notional_ok, timing=None, ledger_may_lag=False):
        if delay_plan:
            time.sleep(delay_plan)
        seen.append('plan')
        return True, size, 'exchange net 10.0 is already at or past the target'

    gw._withdraw_standing_close = _withdraw
    gw._close_wire_plan = _plan
    old_net = c.LEADER_NETWORK, c.FOLLOWER_NETWORK
    c.LEADER_NETWORK, c.FOLLOWER_NETWORK = 'TESTNET', 'TESTNET'  # same network: no follower price lookup needed
    c.classify_send_lifecycle = lambda intent: 'EXIT'
    if c.HLAccount is None:
        c.HLAccount = type('HLAccount', (), {})
    if c.HLExchange is None:
        c.HLExchange = type('HLExchange', (), {})
    try:
        ok, status, res = gw._send_real(make_intent(), {})
    finally:
        c.LEADER_NETWORK, c.FOLLOWER_NETWORK = old_net
    return ok, status, res, seen


def span(timing, key):
    a = timing.get(key + '_started_ms')
    b = timing.get(key + '_finished_ms')
    if not isinstance(a, int) or not isinstance(b, int):
        return None
    return b - a


# ---------------------------------------------------------------- A. standing-close + close-plan stamps, via _send_real
ok, status, res, seen = drive_send_real()
t = res.get('timing') or {}
check('DRIVE_REACHED_EXIT_BRANCH', seen == ['withdraw', 'plan'] and status == 'SEND_NOT_ATTEMPTED_CLOSE_AT_TARGET',
      'status=%s seen=%s' % (status, seen))

sc = span(t, 'standing_close')
cp = span(t, 'close_plan')
check('STANDING_CLOSE_STAMP_EMITTED', 'standing_close_started_ms' in t and 'standing_close_finished_ms' in t,
      'keys=%s' % sorted(k for k in t if k.startswith('standing_close')))
check('CLOSE_PLAN_STAMP_EMITTED', 'close_plan_started_ms' in t and 'close_plan_finished_ms' in t,
      'keys=%s' % sorted(k for k in t if k.startswith('close_plan')))
check('STANDING_CLOSE_STAMP_ORDERED', sc is not None and sc >= 0 and t.get('standing_close_started_ms', 0) > 0,
      'span=%s' % sc)
check('CLOSE_PLAN_STAMP_ORDERED', cp is not None and cp >= 0 and t.get('close_plan_started_ms', 0) > 0, 'span=%s' % cp)

# mutation control 1: make only the standing-close cancel slow -> only its span must move
ok2, status2, res2, _ = drive_send_real(delay_withdraw=DELAY_S)
t2 = res2.get('timing') or {}
sc2 = span(t2, 'standing_close')
cp2 = span(t2, 'close_plan')
check('STANDING_CLOSE_STAMP_RESPONDS_TO_SLOW_CANCEL', sc2 is not None and sc2 >= FLOOR_MS,
      'span=%s floor=%s (a constant/0 stamp fails here)' % (sc2, FLOOR_MS))
check('STANDING_CLOSE_STAMP_NOT_BLEEDING_INTO_CLOSE_PLAN', cp2 is not None and cp2 < FLOOR_MS,
      'close_plan span=%s while only the cancel slept' % cp2)

# mutation control 2: make only the close plan slow -> only its span must move
ok3, status3, res3, _ = drive_send_real(delay_plan=DELAY_S)
t3 = res3.get('timing') or {}
sc3 = span(t3, 'standing_close')
cp3 = span(t3, 'close_plan')
check('CLOSE_PLAN_STAMP_RESPONDS_TO_SLOW_PLAN', cp3 is not None and cp3 >= FLOOR_MS,
      'span=%s floor=%s (a constant/0 stamp fails here)' % (cp3, FLOOR_MS))
check('CLOSE_PLAN_STAMP_NOT_BLEEDING_INTO_STANDING_CLOSE', sc3 is not None and sc3 < FLOOR_MS,
      'standing_close span=%s while only the plan slept' % sc3)


# ---------------------------------------------------------------- B. exchange_net stamp, inside the real close plan
def drive_close_plan(delay_read=0.0, ex=10.0, led=10.0):
    gw = make_gateway(led)

    def _fresh(coin):
        if delay_read:
            time.sleep(delay_read)
        return ex

    gw._fresh_exchange_net = _fresh
    intent = make_intent()
    old = os.environ.get('HL_LIVE_CLOSE_TO_TARGET')
    os.environ['HL_LIVE_CLOSE_TO_TARGET'] = '1'
    try:
        return gw._close_wire_plan(intent, 10.0, 2, lambda s: True, {})
    finally:
        if old is None:
            os.environ.pop('HL_LIVE_CLOSE_TO_TARGET', None)
        else:
            os.environ['HL_LIVE_CLOSE_TO_TARGET'] = old


def close_plan_timing(**kw):
    gw = make_gateway(kw.get('led', 10.0))

    def _fresh(coin):
        if kw.get('delay_read'):
            time.sleep(kw['delay_read'])
        return kw.get('ex', 10.0)

    gw._fresh_exchange_net = _fresh
    old = os.environ.get('HL_LIVE_CLOSE_TO_TARGET')
    os.environ['HL_LIVE_CLOSE_TO_TARGET'] = '1'
    tm = {}
    try:
        gw._close_wire_plan(make_intent(), 10.0, 2, lambda s: True, tm)
    finally:
        if old is None:
            os.environ.pop('HL_LIVE_CLOSE_TO_TARGET', None)
        else:
            os.environ['HL_LIVE_CLOSE_TO_TARGET'] = old
    return tm


tm = close_plan_timing()
en = span(tm, 'exchange_net')
check('EXCHANGE_NET_STAMP_EMITTED', 'exchange_net_started_ms' in tm and 'exchange_net_finished_ms' in tm,
      'keys=%s' % sorted(k for k in tm if k.startswith('exchange_net')))
check('EXCHANGE_NET_STAMP_ORDERED', en is not None and en >= 0 and tm.get('exchange_net_started_ms', 0) > 0, 'span=%s' % en)
tm_slow = close_plan_timing(delay_read=DELAY_S)
en_slow = span(tm_slow, 'exchange_net')
check('EXCHANGE_NET_STAMP_RESPONDS_TO_SLOW_ACCOUNT_READ', en_slow is not None and en_slow >= FLOOR_MS,
      'span=%s floor=%s (a constant/0 stamp fails here)' % (en_slow, FLOOR_MS))

# the stamp must not be satisfied by a lookup that never ran: with the close-to-target path off, no read happens
old_env = os.environ.get('HL_LIVE_CLOSE_TO_TARGET')
os.environ['HL_LIVE_CLOSE_TO_TARGET'] = '0'
tm_off = {}
gw_off = make_gateway(10.0)
ran = []
gw_off._fresh_exchange_net = lambda coin: ran.append(coin) or 10.0
try:
    gw_off._close_wire_plan(make_intent(), 10.0, 2, lambda s: True, tm_off)
finally:
    if old_env is None:
        os.environ.pop('HL_LIVE_CLOSE_TO_TARGET', None)
    else:
        os.environ['HL_LIVE_CLOSE_TO_TARGET'] = old_env
check('EXCHANGE_NET_STAMP_ABSENT_WHEN_READ_NOT_MADE', not ran and 'exchange_net_started_ms' not in tm_off,
      'ran=%s keys=%s' % (ran, sorted(k for k in tm_off if k.startswith('exchange_net'))))


bad = [n for n, ok in R if not ok]
print('\n%d checks, %d failed' % (len(R), len(bad)))
if bad:
    for n in bad:
        print('  FAILED:', n)
    sys.exit(1)
print('ALL_EXIT_TIMING_STAMP_CHECKS_PASS')
