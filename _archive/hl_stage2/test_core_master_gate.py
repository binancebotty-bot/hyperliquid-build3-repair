#!/usr/bin/env python3
"""Nothing may reach the exchange while the master switch is OFF - enforced at the physical call.

On 2026-10-25 1,549 GTC limit orders were placed with send_mode OFF, because the switch was checked
by send_if_allowed and by nothing below it: the missed-entry rest path called _place_order directly.
The gate now lives INSIDE _place_order, so a new call site cannot forget it.

FAILING FIRST: `_master_gate_reason` did not exist before this branch, and the static check below
fails on any build where `exchange.order(` appears anywhere but inside the gated function.
"""
import re
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:170]) if not ok else ''))


class RecExchange:
    def __init__(self):
        self.calls = []

    def order(self, *a, **k):
        self.calls.append((a, k))
        return {'status': 'ok', 'response': {'data': {'statuses': [{'resting': {'oid': 1}}]}}}


class FakeCfg:
    def __init__(self, switch=True, modes=None):
        self._switch, self._modes = switch, modes or {}

    def master_switch_now(self):
        return self._switch

    def wallet_mode(self, w):
        return self._modes.get(str(w).lower(), 'LIVE')


def sender(switch=True, modes=None, key_invalid=False):
    s = types.SimpleNamespace()
    s.cfg = FakeCfg(switch, modes)
    s.sender_key_invalid = key_invalid
    s._reserve_exchange_order_slot = lambda **k: 0
    s._note_sender_key_rejection = lambda r: None
    s._parse_hl_response = lambda r: (True, 'ORDER_RESTING', '1', '')
    rows = []
    s.audit = types.SimpleNamespace(append_reconciliation=lambda *a, **k: rows.append((a, k)))
    s._rows = rows
    s._master_gate_reason = types.MethodType(C.SenderGateway._master_gate_reason, s)
    return s


def intent(wallet='0xabc', side='BUY', reason='ENTRY'):
    # lifecycle comes from notes/reason first (Core:908-916), then from the position delta
    return types.SimpleNamespace(intent_id='i1', copy_side=side, copy_size=1.0, reason=reason,
                                 wallet_position_before=0.0 if reason == 'ENTRY' else 1.0,
                                 fill=types.SimpleNamespace(coin='BTC', side=side,
                                                            leader_wallet=wallet, price=100.0,
                                                            timestamp_ms=0))


def place(s, ex, it=None):
    return C.SenderGateway._place_order(s, ex, 'BTC', True, 1.0, 100.0, 'Gtc', False,
                                        intent=it, path='test')


# ---- the structural guard: one physical call, inside the gated function only
src = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8', errors='replace')
lines_src = src.split('\n')
call_lines = [i + 1 for i, l in enumerate(lines_src) if re.search(r'=\s*exchange\.order\(', l)]
def_line = next(i + 1 for i, l in enumerate(lines_src) if l.strip().startswith('def _place_order'))
check('ONLY_ONE_PHYSICAL_ORDER_CALL_IN_THE_FILE', len(call_lines) == 1, call_lines)
check('THAT_CALL_IS_INSIDE_PLACE_ORDER', bool(call_lines) and call_lines[0] > def_line, (call_lines, def_line))
gate_at = next(i + 1 for i, l in enumerate(lines_src) if '_blocked = self._master_gate_reason(' in l)
check('THE_GATE_RUNS_BEFORE_THE_CALL', gate_at < (call_lines[0] if call_lines else 10 ** 9), (gate_at, call_lines))

# ---- master OFF: no exchange call at all
ex = RecExchange()
r = place(sender(switch=False), ex, intent())
check('MASTER_OFF_MAKES_NO_EXCHANGE_CALL', ex.calls == [], ex.calls)
check('MASTER_OFF_RETURNS_A_NAMED_REFUSAL',
      isinstance(r, dict) and 'BLOCKED_AT_PLACE_ORDER' in str(r.get('response')), r)

# ---- and it journals the refusal rather than failing silently
s = sender(switch=False)
place(s, RecExchange(), intent())
check('MASTER_OFF_WRITES_A_JOURNAL_ROW', len(s._rows) == 1, s._rows)

# ---- wallet modes
ex2 = RecExchange()
r2 = place(sender(modes={'0xoff': 'OFF'}), ex2, intent(wallet='0xoff'))
check('WALLET_OFF_BLOCKS', ex2.calls == [] and 'WALLET_OFF' in str(r2), (ex2.calls, r2))

ex3 = RecExchange()
r3 = place(sender(modes={'0xclo': 'CLO'}), ex3, intent(wallet='0xclo'))
check('CLO_BLOCKS_AN_ENTRY', ex3.calls == [] and 'CLO_BLOCKS_ENTRY' in str(r3), (ex3.calls, r3))

# ---- ENG-017 intact: with sends ON, a LIVE wallet entry and a CLO close are both allowed through
ex4 = RecExchange()
r4 = place(sender(), ex4, intent(wallet='0xlive'))
check('SENDS_ON_ALLOWS_A_LIVE_ENTRY', len(ex4.calls) == 1, (ex4.calls, r4))

ex5 = RecExchange()
r5 = place(sender(modes={'0xclo': 'CLO'}), ex5, intent(wallet='0xclo', side='SELL', reason='EXIT'))
check('CLO_STILL_FOLLOWS_A_CLOSE', len(ex5.calls) == 1, (ex5.calls, r5))

# ---- the gate reason is also callable on its own (used by the per-site checks)
check('GATE_REASON_REPORTS_MASTER_OFF',
      C.SenderGateway._master_gate_reason(sender(switch=False), intent()) == 'MASTER_REAL_ORDERS_OFF')
check('GATE_REASON_IS_EMPTY_WHEN_ALLOWED',
      C.SenderGateway._master_gate_reason(sender(), intent()) == '')

# ---- item 6: the missed-entry rest path must record its own order, not leave a pending_send row
body_start = src.index('def _missed_entry_rest_or_diff')
body_end = src.index('def ', src.index('terminal_state=outcome', body_start))
rest_body = src[body_start:body_end]
check('REST_PATH_FINALISES_ITS_SEND_ROW',
      'update_send_attempt_row(_aid' in rest_body and 'finalised by the missed-entry rest path' in rest_body,
      'the rest path still leaves its pending_send row unresolved')


failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
