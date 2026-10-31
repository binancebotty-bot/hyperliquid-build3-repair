#!/usr/bin/env python3
"""Sending OFF must not attempt orders at all, and a gate refusal must not look like an exchange call.

Run 11 (2026-10-26) held the line: zero orders reached the exchange. It also attempted ~140 orders a
minute for twelve minutes, each refused at the gate and each journalled, which spent the shared info
budget. Two invariants are asserted here:

  (a) with send_mode OFF the missed-entry rest is never attempted - the fill still ends with exactly ONE
      terminal row (the caller writes it), while ENG-017 is untouched when sending is ON;
  (b) a refusal at the physical call is exchange_called False with reject_category
      BLOCKED_AT_PLACE_ORDER and no exchange_call_started_ms stamp, so no journal row can claim the
      exchange was contacted.

FAILING FIRST: neither guard exists before this branch. (a) raises AttributeError on an empty stub because
the function goes on to classify the intent, and (b) omits exchange_called, so a row built from the result
would default to True.
"""
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

SRC = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8-sig', errors='replace')
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:180]) if not ok else ''))


class Audit:
    def __init__(self):
        self.rows = []

    def append_reconciliation(self, kind, state, **kw):
        self.rows.append((kind, state, kw))

    def append_send_attempt(self, row):
        self.rows.append(('SEND_ATTEMPT', row.get('status'), row))


class Boom(Exception):
    pass


# ---- (a) OFF never reaches the rest path
def rest_path_called():
    raise Boom('the missed-entry rest path was attempted while send_mode is OFF')


stub = types.SimpleNamespace(
    sender=types.SimpleNamespace(_market_halted_until_ms={}, _missed_entry_rest_or_diff=rest_path_called),
    audit=Audit())
try:
    out = C.LiveCopyCore._apply_missed_entry_rule_on_refusal(
        stub, types.SimpleNamespace(coin='BTC', timestamp_ms=0), types.SimpleNamespace(reason=''), 'MASTER_REAL_ORDERS_OFF')
    check('OFF_REFUSAL_NEVER_REACHES_THE_REST_PATH', out is None, 'returned %r instead of None' % (out,))
except Boom as exc:
    check('OFF_REFUSAL_NEVER_REACHES_THE_REST_PATH', False, exc)
except Exception as exc:
    check('OFF_REFUSAL_NEVER_REACHES_THE_REST_PATH', False, '%s: %s' % (type(exc).__name__, str(exc)[:120]))

# the caller writes the ONE row per fill when the rule declines to act
check('ONE_ROW_PER_FILL_IS_THE_CALLERS', 'if _refusal_outcome is None:' in SRC
      and '_append_send_terminal(fill, intent, send_status)' in SRC)

# ---- (a) ENG-017 stays live when sending is ON: the guard names that one status, nothing else
guard = SRC[SRC.find('if str(send_status) == "MASTER_REAL_ORDERS_OFF":'):]
guard_block = guard[:guard.find('return None')] if 'return None' in guard else ''
check('GUARD_IS_EXACTLY_MASTER_OFF_ONLY',
      'MASTER_REAL_ORDERS_OFF' in guard_block and guard_block.count('send_status) ==') == 1,
      'guard block: %r' % guard_block[:120])

# ---- (a) ENG-017 must still ACT when sending is ON. This is the check that was missing: the first
# version of this commit deleted the `reason` assignment this path reads, so the freshness and snapshot
# causes raised NameError, the caller swallowed it, and the rule was silently dead for exactly the two
# refusal causes it exists to serve. A sending-ON refusal must reach the rest path with a named cause.
reached = []
stub_on = types.SimpleNamespace(
    sender=types.SimpleNamespace(
        _market_halted_until_ms={},
        _missed_entry_rest_or_diff=lambda i, c: (reached.append(c),
                                                 {'outcome': 'MISSED_ENTRY_REST_PLACED', 'notes': ''})[1]),
    audit=Audit())
on_fill = types.SimpleNamespace(coin='BTC', leader_wallet='0xabc', leader_fill_id='f1', timestamp_ms=0)
on_intent = types.SimpleNamespace(reason='no fresh follower-network price', notes='lifecycle=ENTRY',
                                  intent_id='i1', fill=on_fill)
try:
    out = C.LiveCopyCore._apply_missed_entry_rule_on_refusal(stub_on, on_fill, on_intent, 'INTENT_NOT_SEND_ALLOWED')
    check('ENG017_STILL_ACTS_WHEN_SENDING_IS_ON', reached == ['FOLLOWER_PRICE_FRESHNESS_GATE'],
          'rest cause(s)=%r outcome=%r' % (reached, out))
except Exception as exc:
    check('ENG017_STILL_ACTS_WHEN_SENDING_IS_ON', False, '%s: %s' % (type(exc).__name__, str(exc)[:140]))

# ---- (b) a gate refusal is not an exchange call
gw = types.SimpleNamespace(
    cfg=types.SimpleNamespace(send_mode_now=lambda: 'OFF', wallet_enabled=lambda w: True, wallet_mode=lambda w: 'LIVE'),
    sender_key_invalid=False, audit=Audit(), _gate_journal_failures=0)
# the gate is a method: bind the real ones to the stub so this tests the engine, not a re-implementation
gw._master_gate_reason = lambda intent, path='': C.SenderGateway._master_gate_reason(gw, intent, path)
gw._gate_refusal_row = lambda intent, path, reason: C.SenderGateway._gate_refusal_row(gw, intent, path, reason)
try:
    res = C.SenderGateway._place_order(gw, None, 'BTC', True, 0.001, 100.0, 'Ioc', False, intent=types.SimpleNamespace())
    check('GATE_REFUSAL_SAYS_THE_EXCHANGE_WAS_NOT_CALLED', res.get('exchange_called') is False, res)
    check('GATE_REFUSAL_CARRIES_BLOCKED_AT_PLACE_ORDER', res.get('reject_category') == 'BLOCKED_AT_PLACE_ORDER', res)
    timing = res.get('timing') or {}
    check('GATE_REFUSAL_HAS_NO_CALL_STAMP', 'exchange_call_started_ms' not in timing, timing)
except Exception as exc:
    check('GATE_REFUSAL_SAYS_THE_EXCHANGE_WAS_NOT_CALLED', False, '%s: %s' % (type(exc).__name__, str(exc)[:140]))
    check('GATE_REFUSAL_CARRIES_BLOCKED_AT_PLACE_ORDER', False, 'unreached')
    check('GATE_REFUSAL_HAS_NO_CALL_STAMP', False, 'unreached')


# ---- (b2) POST-WAIT refusal: the late gate runs AFTER the pacing slot and the write-ahead row, so a mode
# change during those seconds must not leave a call stamp behind. Codex found this on ce54ab2e: the stamp
# was written BEFORE the late gate, so a late refusal still carried exchange_call_started_ms.
_seq = {'n': 0}


def _mode_flips_after_the_wait():
    _seq['n'] += 1
    return 'ON' if _seq['n'] == 1 else 'OFF'   # allowed by the early gate, refused by the post-wait one


gw2 = types.SimpleNamespace(
    cfg=types.SimpleNamespace(send_mode_now=_mode_flips_after_the_wait, wallet_enabled=lambda w: True,
                              wallet_mode=lambda w: 'LIVE'),
    sender_key_invalid=False, audit=Audit(), _gate_journal_failures=0,
    _reserve_exchange_order_slot=lambda **kw: C.utc_now_ms(),
    _open_orders_send_begin=lambda: None, _open_orders_send_end=lambda: None,
    _note_sender_key_rejection=lambda r: None)
gw2._master_gate_reason = lambda intent, path='': C.SenderGateway._master_gate_reason(gw2, intent, path)
gw2._gate_refusal_row = lambda intent, path, reason: C.SenderGateway._gate_refusal_row(gw2, intent, path, reason)
_post_timing = {}
_post_intent = types.SimpleNamespace(fill=types.SimpleNamespace(leader_wallet='0xabc', coin='BTC'),
                                     intent_id='i-post', notes='lifecycle=ENTRY',
                                     wallet_position_before=0, copy_side='BUY', copy_size=1)
try:
    _post = C.SenderGateway._place_order(gw2, None, 'BTC', True, 0.001, 100.0, 'Ioc', False,
                                         timing=_post_timing, started_key='exchange_call_started_ms',
                                         intent=_post_intent, path='send_other')
    check('POST_WAIT_REFUSAL_CALLS_NO_EXCHANGE', _post.get('exchange_called') is False, _post)
    check('POST_WAIT_REFUSAL_HAS_NO_CALL_STAMP',
          'exchange_call_started_ms' not in (_post.get('timing') or {})
          and 'exchange_call_started_ms' not in _post_timing,
          'timing=%r' % (_post.get('timing'),))
except Exception as exc:
    check('POST_WAIT_REFUSAL_CALLS_NO_EXCHANGE', False, '%s: %s' % (type(exc).__name__, str(exc)[:140]))
    check('POST_WAIT_REFUSAL_HAS_NO_CALL_STAMP', False, 'unreached')

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
