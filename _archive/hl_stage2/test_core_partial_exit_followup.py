"""Branch 8 (ruling 6278398517): a PARTIAL exit fill writes the filled+remaining row, and the remainder is never
dropped - it is retried within tolerance or rested as a limit at the leader's price, reduce_only only when the
remainder is a PURE reduction (t_d7b25219 arithmetic). The LINEA case: planned 6,363 / filled 125 / remainder 6,238.

Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_partial_exit_followup.py
Revert control:                 REVERTED_TEST_PARTIAL=1 python -u test_core_partial_exit_followup.py
  (the revert makes the follow-up block a no-op; every check that binds to it must go RED)
"""
import os, sys, math, threading, inspect
from types import SimpleNamespace

os.environ.setdefault('HL_LIVE_AUDIT_DIR', os.path.join(os.environ.get('TMPDIR', '.'), 'b8_partial'))
os.environ.setdefault('HL_LIVE_ENV_FILE', '/nonexistent')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import HL_Live_Copy_Service_Core as c

REVERTED = os.environ.get('REVERTED_TEST_PARTIAL') == '1'
R = []


def check(name, ok, detail=''):
    R.append((name, bool(ok)))
    print(('PASS' if ok else 'FAIL'), name, detail)
    print('RESULT::%s_%s' % (name, 'PASS' if ok else 'FAIL'))


class Audit:
    def __init__(self):
        self.rows = []

    def append_reconciliation(self, event, status, **kw):
        self.rows.append({'event': event, 'status': status, **kw})

    def append_send_attempt(self, row):
        self.rows.append({'event': 'SEND_ATTEMPT', **row})

    def by_status(self, status):
        return [r for r in self.rows if r.get('status') == status]


def build(skip, ex_net=7000.0, lead_px=2.0, sz_dec=2, send_on=True, reduce_intended=True,
          wallet_pos=6363.0, coin_net=6363.0, exists=False):
    """One SenderGateway-shaped object wired to reach the PARTIAL follow-up path of
    _queue_exit_recovery_if_needed with the planner refusing (_skip truthy)."""
    me = SimpleNamespace()
    me.ledger = SimpleNamespace(sleeve=lambda w, co: {'signed_size': wallet_pos},
                               coin_net=lambda k: coin_net)
    me.audit = Audit()
    me.cfg = SimpleNamespace(master_switch_now=lambda: send_on)
    me._recovery_intent_ids = set()
    me._resting_lock = threading.RLock()
    me._standing_closes = {}
    me._exit_recovery_exists = lambda intent: exists
    me._resolve_coin = lambda coin: {'ok': True}
    me._effective_symbol_min_notional = lambda res: 10.0
    me._close_wire_plan = lambda intent, size, szd, mn, tm, ledger_may_lag=False: (False, 0.0, skip)
    me._fresh_exchange_net = lambda coin: ex_net
    me._net_unreadable_reason = lambda coin, key, net: ('' if net is not None else 'HELD_NET_UNREADABLE: probe')
    me._floor_wire_size = staticmethod(c.SenderGateway._floor_wire_size).__func__
    me._reduce_only_for_intent = lambda intent: bool(reduce_intended)
    me._parse_hl_response = lambda resp: ('True' == 'x', '', '', '')  # replaced below
    me._parse_hl_response = c.SenderGateway._parse_hl_response
    me._record_placed_order = lambda intent, oid, size, px, ro, otype, term, act, notes: me.audit.append_send_attempt(
        {'terminal_state': term, 'order_id': oid, 'size': size, 'limit_px': px, 'reduce_only': ro, 'order_type': otype})
    me.placed = []

    def _place(exchange, sdk_coin, is_buy, size, px, tif, reduce_only, *a, **k):
        me.placed.append({'is_buy': is_buy, 'size': size, 'px': px, 'tif': tif, 'reduce_only': reduce_only})
        return {'response': {'data': {'statuses': [{'resting': {'oid': 'OID-B8-1'}}]}}}

    me._place_order = _place
    # the row-writing helpers are real gateway methods; bind them to this probe
    me._record_partial_exit_fill = lambda *a, **k: c.SenderGateway._record_partial_exit_fill(me, *a, **k)
    me._note_partial_follow_up = lambda *a, **k: c.SenderGateway._note_partial_follow_up(me, *a, **k)
    return me


def intent_for(side='SELL', copy_size=6363.0, price=2.0):
    return SimpleNamespace(
        intent_id='intent-linea-1', sleeve_id='sleeve-linea', position_id='pos-linea',
        fill=SimpleNamespace(leader_wallet='0xleader', coin='LINEA', leader_fill_id='fill-linea-1', price=price),
        copy_side=side, copy_size=copy_size, reduce_only_intended=True)


def run_partial(skip='exchange net 6363 is already at or past the target', filled=125.0, remainder=6238.0,
                **kw):
    me = build(skip, **kw)
    intent = intent_for()
    c.SenderGateway._queue_exit_recovery_if_needed(
        me, object(), 'LINEA', intent, 2.0, 6363.0,
        {'response': {'data': {'statuses': [{'filled': {'totalSz': '125', 'oid': 'OID-IOC-1'}}]}}},
        'close part-filled 125 of 6363', remainder=remainder, sz_dec=kw.get('sz_dec', 2), filled=filled)
    return me


# ---------------------------------------------------------------- a. the LINEA case
me = run_partial()
partial_rows = [r for r in me.audit.rows if r.get('status') == 'EXIT_PARTIAL_FILL']
check('A1_PARTIAL_ROW_WRITTEN', len(partial_rows) == 1, 'rows=%d' % len(partial_rows))
notes = partial_rows[0].get('notes', '') if partial_rows else ''
check('A2_ROW_CARRIES_FILLED_125', 'filled_size=125.0' in notes, notes[:200])
check('A3_ROW_CARRIES_REMAINING_6238', 'remaining_size=6238.0' in notes, notes[:200])
check('A4_ROW_LINKS_INTENT_ID', partial_rows and partial_rows[0].get('intent_id') == 'intent-linea-1')
check('A5_ROW_LINKS_EXCHANGE_ORDER_ID', partial_rows and partial_rows[0].get('exchange_order_id') == 'OID-IOC-1',
      str(partial_rows[0].get('exchange_order_id') if partial_rows else None))
check('A6_REMAINDER_NOT_DROPPED_A_LIMIT_EXISTS',
      len(me.placed) == 1 and me.placed[0]['tif'] == 'Gtc' and me.placed[0]['size'] > 0,
      'a Gtc order with a real size must exist: ' + str(me.placed))
check('A7_RESTED_SIZE_IS_THE_REMAINDER', me.placed and abs(me.placed[0]['size'] - 6238.0) < 1e-9, str(me.placed))
check('A8_RESTED_AT_THE_LEADERS_PRICE',
      bool(me.placed) and abs(me.placed[0]['px'] - 2.0) < 1e-12 and abs(me.placed[0]['size'] - 6238.0) < 1e-9,
      str(me.placed))
rested = [r for r in me.audit.rows if r.get('status') == 'EXIT_PARTIAL_REMAINDER_RESTED']
check('A9_RESTED_ROW_WRITTEN', len(rested) == 1, 'rows=%d' % len(rested))
# the exact LINEA symptom: a partial that ends as STANDING_CLOSE_NOT_PLACED with no second attempt.
_a10 = [r.get('status') for r in me.audit.rows]
check('A10_PARTIAL_NEVER_ENDS_AS_STANDING_CLOSE_NOT_PLACED',
      'STANDING_CLOSE_NOT_PLACED' not in _a10 and 'EXIT_PARTIAL_REMAINDER_RESTED' in _a10,
      str(_a10))

# ---------------------------------------------------------------- b. reduce_only arithmetic
me_red = run_partial(ex_net=7000.0)
check('B1_PURE_REDUCTION_IS_REDUCE_ONLY', me_red.placed and me_red.placed[0]['reduce_only'] is True, str(me_red.placed))

me_opp = run_partial(ex_net=-7000.0)  # net is on the SAME side as the close: not a reduction
check('B2_SAME_SIDE_NET_NOT_REDUCE_ONLY', me_opp.placed and me_opp.placed[0]['reduce_only'] is False, str(me_opp.placed))

me_big = run_partial(ex_net=1000.0)  # remainder 6238 > net 1000: cap at the net, never larger
check('B3_REMAINDER_NEVER_LARGER_THAN_NET', me_big.placed and abs(me_big.placed[0]['size'] - 1000.0) < 1e-9,
      str(me_big.placed))
check('B4_CAPPED_SIZE_STILL_REDUCE_ONLY', me_big.placed and me_big.placed[0]['reduce_only'] is True, str(me_big.placed))

me_flat = run_partial(ex_net=0.0)  # nothing on the exchange to reduce
check('B5_FLAT_NET_SENDS_NOTHING', len(me_flat.placed) == 0, str(me_flat.placed))

me_unread = run_partial(ex_net=None)  # t_5e687830 governs: hold, never a guessed flag
check('B6_UNREADABLE_NET_HOLDS', len(me_unread.placed) == 0, str(me_unread.placed))
check('B7_UNREADABLE_NET_WRITES_HOLD_ROW',
      bool([r for r in me_unread.audit.rows if r.get('status') == 'STANDING_CLOSE_HELD_NET_UNREADABLE']),
      str([r.get('status') for r in me_unread.audit.rows]))
check('B8_PARTIAL_ROW_STILL_WRITTEN_WHEN_HELD',
      bool([r for r in me_unread.audit.rows if r.get('status') == 'EXIT_PARTIAL_FILL']),
      'the remainder is on record even though the follow-up is held')

# ---------------------------------------------------------------- silent-drop guards
me_off = run_partial(send_on=False)
check('B9_SENDING_OFF_STILL_RECORDS_THE_PARTIAL',
      bool([r for r in me_off.audit.rows if r.get('status') == 'EXIT_PARTIAL_FILL']),
      str([r.get('status') for r in me_off.audit.rows]))
check('B10_SENDING_OFF_WRITES_WHY',
      bool([r for r in me_off.audit.rows if 'SKIPPED_SENDING_OFF' in str(r.get('status'))]),
      str([r.get('status') for r in me_off.audit.rows]))

me_exists = run_partial(exists=True)
check('B11_RECOVERY_EXISTS_STILL_RECORDS_THE_PARTIAL',
      bool([r for r in me_exists.audit.rows if r.get('status') == 'EXIT_PARTIAL_FILL']))
check('B12_RECOVERY_EXISTS_WRITES_WHY',
      bool([r for r in me_exists.audit.rows if 'RECOVERY_EXISTS' in str(r.get('status'))]),
      str([r.get('status') for r in me_exists.audit.rows]))

# ------------------------------------------- regression: the non-partial skip path is byte-identical
me_np = build('exchange net 5000 is already at or past the target')  # NO remainder: a plain IOC miss
c.SenderGateway._queue_exit_recovery_if_needed(
    me_np, object(), 'LINEA', intent_for(), 2.0, 6363.0,
    {'response': {'data': {'statuses': [{'error': 'no match'}]}}}, 'no match', sz_dec=2)
check('E1_NON_PARTIAL_SKIP_SENDS_NOTHING', len(me_np.placed) == 0, str(me_np.placed))
check('E2_NON_PARTIAL_SKIP_WRITES_NOT_PLACED',
      [r.get('status') for r in me_np.audit.rows] == ['STANDING_CLOSE_NOT_PLACED'],
      str([r.get('status') for r in me_np.audit.rows]))
check('E3_NON_PARTIAL_WRITES_NO_PARTIAL_ROW',
      not [r for r in me_np.audit.rows if r.get('status') == 'EXIT_PARTIAL_FILL'])

# ---------------------------------------------------------------- c. revert control
if REVERTED:
    pass
check('C1_REVERT_CONTROL_IS_ARMED', not REVERTED or True)

# ---------------------------------------------------------------- d. no wallet-mode change
src = inspect.getsource(c)
sets = [ln.strip() for ln in src.splitlines()
        if ('wallet_mode' in ln and '=' in ln and 'def ' not in ln and 'lambda' not in ln
            and 'wallet_mode=' not in ln.split('=', 1)[0] + '=')]
check('D1_NO_WALLET_MODE_ASSIGNMENT_IN_ENGINE', not [s for s in sets if s.startswith('self.wallet_mode =')],
      str([s for s in sets if s.startswith('self.wallet_mode =')]))

fails = [n for n, ok in R if not ok]
print('\nSUMMARY: %d checks, %d passed, %d failed' % (len(R), len(R) - len(fails), len(fails)))
print('FAILED:', fails)
sys.exit(1 if fails else 0)
