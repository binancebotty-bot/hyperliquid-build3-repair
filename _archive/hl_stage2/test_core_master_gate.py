#!/usr/bin/env python3
"""Nothing reaches the exchange while the engine is not permitted to send.

On 2026-10-25 1,549 GTC limits were placed with send_mode OFF: send_if_allowed checked the switch and
refused, then the missed-entry rest path called _place_order directly and nothing below
send_if_allowed consulted it. The gate now lives INSIDE _place_order and re-reads the modes at the
call, so a mode change while an IOC is in flight stops the retry or rest that follows.

FAILING FIRST: _master_gate_reason did not exist before this branch, and the AST check fails on any
build where an exchange order call exists outside the gated function.
"""
import ast
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

SRC_PATH = HERE / 'HL_Live_Copy_Service_Core.py'
results = []
ROUTES = ['missed_entry_rest', 'exit_recovery', 'rate_limit_recovery', 'send_other',
          'send_retry', 'send_rest', 'send_after_rest']
# order-PLACING calls must sit inside the gated function; withdrawals are the opposite - sending OFF
# must withdraw resting orders (Core:454), so cancel lives in its own function and is asserted apart
ORDER_PLACING = {'order', 'bulk_orders', 'modify', 'bulk_modify'}
WITHDRAWAL = {'cancel', 'cancel_by_cloid', 'bulk_cancel'}


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:170]) if not ok else ''))


tree = ast.parse(SRC_PATH.read_text(encoding='utf-8-sig', errors='replace'))
place_order = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_place_order')
lo = place_order.lineno
hi = max(getattr(n, 'lineno', lo) for n in ast.walk(place_order))

def client_calls(attrs):
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in attrs:
            recv = node.func.value
            recv_name = str(getattr(recv, 'id', None) or getattr(recv, 'attr', '') or '')
            if 'exchange' in recv_name.lower() or recv_name.lower() in {'ex', 'client', 'sdk'}:
                found.append((node.lineno, node.func.attr))
    return found


calls_anywhere = client_calls(ORDER_PLACING)
calls_outside = [(ln, a) for ln, a in calls_anywhere if not (lo <= ln <= hi)]
withdrawals = client_calls(WITHDRAWAL)
cancel_fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == '_cancel_order')
clo = cancel_fn.lineno
chi = max(getattr(n, 'lineno', clo) for n in ast.walk(cancel_fn))
withdrawals_outside = [(ln, a) for ln, a in withdrawals if not (clo <= ln <= chi)]

check('EXACTLY_ONE_ORDER_CALL_IN_THE_AST', len(calls_anywhere) == 1, calls_anywhere)
check('NO_ORDER_CALL_OUTSIDE_PLACE_ORDER', calls_outside == [], calls_outside)
check('WITHDRAWALS_LIVE_IN_ONE_PLACE_TOO', len(withdrawals) == 1 and withdrawals_outside == [],
      (withdrawals, withdrawals_outside))
check('PLACE_ORDER_CONTAINS_THE_ONE_CALL', bool(calls_anywhere) and lo <= calls_anywhere[0][0] <= hi,
      (calls_anywhere, lo, hi))
gate_line = next(n.lineno for n in ast.walk(place_order)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == '_master_gate_reason')
stmts = [n for n in place_order.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
first_stmt_line = stmts[0].lineno if stmts else lo
check('THE_GATE_IS_THE_FIRST_THING_PLACE_ORDER_DOES', gate_line == first_stmt_line, (gate_line, first_stmt_line))


class RecExchange:
    def __init__(self):
        self.calls = []

    def order(self, *a, **k):
        self.calls.append((a, k))
        return {'status': 'ok', 'response': {'data': {'statuses': [{'resting': {'oid': 1}}]}}}


class FakeCfg:
    def __init__(self, mode='ON', wallet_mode='LIVE', enabled=True):
        self._mode, self._wm, self._enabled = mode, wallet_mode, enabled

    def send_mode_now(self):
        return self._mode

    def master_switch_now(self):
        return self._mode != 'OFF'

    def wallet_mode(self, w):
        return self._wm

    def wallet_enabled(self, w):
        return self._enabled


def sender(cfg, journal_ok=True):
    s = types.SimpleNamespace()
    s.cfg = cfg
    s.sender_key_invalid = False
    s._reserve_exchange_order_slot = lambda **k: 0
    s._note_sender_key_rejection = lambda r: None
    s._parse_hl_response = lambda r: (True, 'ORDER_RESTING', '1', '')
    s._rows = []

    def append(*a, **k):
        if not journal_ok:
            raise OSError('journal unavailable')
        s._rows.append((a, k))
    s.audit = types.SimpleNamespace(append_reconciliation=append)
    s._master_gate_reason = types.MethodType(C.SenderGateway._master_gate_reason, s)
    s._gate_refusal_row = types.MethodType(C.SenderGateway._gate_refusal_row, s)
    return s


def intent(wallet='0xabc', reason='ENTRY'):
    return types.SimpleNamespace(intent_id='i1', copy_side='BUY', copy_size=1.0, reason=reason,
                                 wallet_position_before=0.0 if reason == 'ENTRY' else 1.0,
                                 fill=types.SimpleNamespace(coin='BTC', side='BUY', leader_wallet=wallet,
                                                            price=100.0, timestamp_ms=0))


def place(s, ex, it, path):
    return C.SenderGateway._place_order(s, ex, 'BTC', True, 1.0, 100.0, 'Gtc', False, intent=it, path=path)


CASES = [
    ('master_off', dict(mode='OFF'), 'ENTRY', True),
    ('global_close_entry', dict(mode='CLOSE'), 'ENTRY', True),
    ('wallet_disabled_midflight', dict(mode='ON', enabled=False), 'ENTRY', True),
    ('wallet_off', dict(mode='ON', wallet_mode='OFF'), 'ENTRY', True),
    ('clo_entry', dict(mode='ON', wallet_mode='CLO'), 'ENTRY', True),
    ('clo_close_allowed', dict(mode='ON', wallet_mode='CLO'), 'EXIT', False),
    ('on_entry_allowed', dict(mode='ON'), 'ENTRY', False),
]
matrix_failures = []
for route in ROUTES:
    for name, cfg_kw, reason, blocked in CASES:
        ex = RecExchange()
        r = place(sender(FakeCfg(**cfg_kw)), ex, intent(reason=reason), route)
        got_blocked = ex.calls == []
        if got_blocked != blocked:
            matrix_failures.append((route, name, got_blocked, r))
        if blocked and 'BLOCKED_AT_PLACE_ORDER' not in str(r):
            matrix_failures.append((route, name, 'no named refusal', r))
check('MATRIX_7_ROUTES_X_7_CASES', matrix_failures == [], matrix_failures)

ex = RecExchange()
r = place(sender(FakeCfg(mode='OFF')), ex, intent(), 'send_retry')
check('MASTER_OFF_MAKES_NO_EXCHANGE_CALL', ex.calls == [], ex.calls)
check('MASTER_OFF_RETURNS_A_NAMED_REFUSAL', 'BLOCKED_AT_PLACE_ORDER' in str(r), r)

s = sender(FakeCfg(mode='OFF'))
place(s, RecExchange(), intent(), 'send_retry')
check('MASTER_OFF_WRITES_A_JOURNAL_ROW', len(s._rows) == 1, s._rows)

ex = RecExchange()
r = place(sender(FakeCfg(mode='CLOSE')), ex, intent(), 'send_rest')
check('GLOBAL_CLOSE_BLOCKS_AN_ENTRY_AT_THE_CALL',
      ex.calls == [] and 'ENTRY_BLOCKED_GLOBAL_CLOSE_ONLY' in str(r), (ex.calls, r))

ex = RecExchange()
r = place(sender(FakeCfg(mode='CLOSE')), ex, intent(reason='EXIT'), 'exit_recovery')
check('GLOBAL_CLOSE_ALLOWS_A_CLOSE', len(ex.calls) == 1, (ex.calls, r))

ex = RecExchange()
r = place(sender(FakeCfg(mode='ON', enabled=False)), ex, intent(), 'send_rest')
check('WALLET_DISABLED_MIDFLIGHT_BLOCKS', ex.calls == [] and 'WALLET_DISABLED_AT_SEND' in str(r), (ex.calls, r))

ex = RecExchange()
r = C.SenderGateway._place_order(sender(FakeCfg(mode='ON')), ex, 'BTC', True, 1.0, 100.0, 'Gtc', False,
                                 intent=None, path='send_retry')
check('MISSING_INTENT_FAILS_CLOSED', ex.calls == [] and 'MISSING_INTENT_CONTEXT' in str(r), (ex.calls, r))

before = C.SenderGateway._gate_journal_failures
ex = RecExchange()
r = place(sender(FakeCfg(mode='OFF'), journal_ok=False), ex, intent(), 'send_retry')
check('JOURNAL_FAILURE_STILL_REFUSES', ex.calls == [] and 'BLOCKED_AT_PLACE_ORDER' in str(r), (ex.calls, r))
check('JOURNAL_FAILURE_IS_COUNTED', C.SenderGateway._gate_journal_failures == before + 1,
      (before, C.SenderGateway._gate_journal_failures))

src = SRC_PATH.read_text(encoding='utf-8-sig', errors='replace')
rest_body = src[src.index('def _missed_entry_rest_or_diff'):src.index('def ', src.index('terminal_state=outcome'))]
check('REST_PATH_FINALISES_ITS_SEND_ROW',
      'update_send_attempt_row(_aid' in rest_body and 'finalised by the missed-entry rest path' in rest_body)

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
