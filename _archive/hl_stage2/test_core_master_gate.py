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
# C7-WO-1-R95: _place_order refuses unless the engine ALREADY owns the machine-wide lease.
# Acquire it exactly as the real engine does at start, in an ISOLATED temp lock path so the
# live machine lock is never opened.
import os as _os, tempfile as _tempfile
_LOCK_DIR = Path(_tempfile.mkdtemp(prefix="master_gate_lock_"))
_os.environ["HL_LIVE_GLOBAL_LOCK_FILE"] = str(_LOCK_DIR / "engine-global.lock")
import HL_Live_Copy_Service_Core as C  # noqa: E402
C.acquire_global_instance_lock(_LOCK_DIR / "state")

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

def attr_calls(tree_or_src, attrs):
    """EVERY attribute-call named in `attrs`, receiver-agnostic.

    The old version resolved the receiver via getattr(id/attr), so `get_client().order(...)`
    produced "" and the guard passed vacuously. The receiver is irrelevant to the invariant:
    one physical exchange order call is permitted in the whole module. Only genuine Call nodes
    with an Attribute func are matched, so docstrings, comments and string literals can never
    appear here, and a bare `order(...)` (Name, not Attribute) is not an SDK call.
    """
    tree = ast.parse(tree_or_src) if isinstance(tree_or_src, str) else tree_or_src
    return [(n.lineno, n.func.attr) for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in attrs]


calls_anywhere = attr_calls(tree, ORDER_PLACING)
calls_outside = [(ln, a) for ln, a in calls_anywhere if not (lo <= ln <= hi)]
withdrawals = attr_calls(tree, WITHDRAWAL)
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

# ---- NEGATIVE CONTROL: a call-expression receiver has no .id/.attr, so the old guard saw "". The
# receiver-agnostic walk must catch it, or EXACTLY_ONE_ORDER_CALL_IN_THE_AST stays vacuously green.
CONTROL_SRC = '''
class X:
    def a(self):
        return get_client().order("BTC", True, 1.0, 1.0)
    def b(self):
        return (self.ex or build_ex()).order("BTC", True, 1.0, 1.0)
'''
control_hits = attr_calls(CONTROL_SRC, ORDER_PLACING)
check('GUARD_CATCHES_A_CALL_EXPRESSION_RECEIVER',
      len(control_hits) == 2 and control_hits[0][1] == 'order' and control_hits[1][1] == 'order',
      control_hits)
control_src_real = SRC_PATH.read_text(encoding='utf-8-sig', errors='replace') + \
    chr(10) + 'def _smuggled():' + chr(10) + '    return something().order("BTC", True, 1.0, 1.0)' + chr(10)
control_real_hits = attr_calls(control_src_real, ORDER_PLACING)
control_real_outside = [(ln, a) for ln, a in control_real_hits if not (lo <= ln <= hi)]
check('GUARD_CATCHES_A_SMUGGLED_ORDER_IN_THE_REAL_CORE',
      len(control_real_hits) == 2 and control_real_outside != [], (control_real_hits, control_real_outside))
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

# ---- P2#3: the gate must precede the pacing slot AND the write-ahead row, not just the client call
inside = src.split(chr(10))[lo - 1:hi]
slot_at = next((lo + i for i, l in enumerate(inside) if '_reserve_exchange_order_slot(' in l), None)
presend_at = next((lo + i for i, l in enumerate(inside) if 'pre_send is not None' in l), None)
check('THE_GATE_RUNS_BEFORE_THE_PACING_SLOT', slot_at is not None and gate_line < slot_at, (gate_line, slot_at))
check('THE_GATE_RUNS_BEFORE_THE_WRITE_AHEAD_ROW', presend_at is not None and gate_line < presend_at,
      (gate_line, presend_at))

# ---- P1#3: the outcome must come from the exchange reply, not from the `take` flag
rest_start = src.index('def _missed_entry_rest_or_diff')
rest_src = src[rest_start:src.index('def ', src.index('terminal_state=outcome', rest_start))]
check('OUTCOME_IS_DERIVED_FROM_THE_EXCHANGE_REPLY',
      '"ORDER_FILLED"' in rest_src and '_blocked_reply' in rest_src,
      'the rest path still branches on take rather than on the parsed status')
check('FINALISATION_FAILURE_IS_LOUD',
      'finalise_missed_entry_rest_row' in rest_src
      and ('except Exception:' + chr(10) + '                pass') not in rest_src)


# ---- RACE: the mode changes DURING the pacing-slot wait (Codex 6406031822)
# The early gate runs before the wait; the point of the late recheck is that a change while the slot
# is being reserved cannot let the order through. Each of the 7 routes is exercised twice.
class FlippingCfg(FakeCfg):
    def __init__(self, flip_to):
        super().__init__(mode='ON')
        self._flip_to = flip_to

    def flip(self):
        self._mode = self._flip_to


race_failures = []
for route in ROUTES:
    for flip_to in ('OFF', 'CLOSE'):
        cfg = FlippingCfg(flip_to)
        s = sender(cfg)

        def slot(**k):
            cfg.flip()          # the operator changes the mode while the slot is being reserved
            return 0
        s._reserve_exchange_order_slot = slot
        ex = RecExchange()
        r = place(s, ex, intent(reason='ENTRY'), route)
        if ex.calls:
            race_failures.append((route, flip_to, r))
check('MODE_CHANGE_DURING_THE_SLOT_WAIT_BLOCKS_ALL_7_ROUTES', race_failures == [], race_failures)

# and a wallet disabled during the wait is caught by the same recheck
disable_failures = []
for route in ROUTES:
    cfg = FakeCfg(mode='ON')
    s = sender(cfg)

    def slot2(**k):
        cfg._enabled = False
        return 0
    s._reserve_exchange_order_slot = slot2
    ex = RecExchange()
    r = place(s, ex, intent(reason='ENTRY'), route)
    if ex.calls:
        disable_failures.append((route, r))
check('WALLET_DISABLED_DURING_THE_SLOT_WAIT_BLOCKS_ALL_7_ROUTES', disable_failures == [], disable_failures)


failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
