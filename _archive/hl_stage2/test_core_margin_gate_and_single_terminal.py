#!/usr/bin/env python3
"""P1: the send lane must gate the margin cooldown itself. P2: one terminal row per intent.

Codex review 5648503401 (relayed in 6410278479) on branch tip 25ab627:

[P1] `send_if_allowed` checks the halted and IOC cooldowns (Core:7959-7963) but NOT `_margin_reject_until_ms`.
Removing the dispatch early return means a fill inside an active margin cooldown walks to `_place_order` and
`exchange.order` - a doomed order sent, exactly what the cache exists to prevent. My earlier line cite covered
two of the three statuses I removed; it said nothing about margin. This test proves it, per status.

[P2] Double terminal row: `_place_order` journals `SEND_TERMINAL/BLOCKED_AT_PLACE_ORDER` through
`_gate_refusal_row` (Core:5606), and `_apply_missed_entry_rule_on_refusal` then appends its own SEND_TERMINAL
for the same intent when the gate flips between the send-lane refusal and the remedy's physical call.

FAILING FIRST on 25ab627: the margin case returns None/allowed instead of the refusal status, and the wrapper
writes a terminal row even when the gate already wrote one.
"""
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:200]) if not ok else ''))


FAR = C.utc_now_ms() + 600000
NOW = C.utc_now_ms()


def entry_intent(coin='BTC'):
    fill = types.SimpleNamespace(raw={'dir': 'Open Long', 'created_at_ms': NOW}, coin=coin, side='B',
                                 leader_wallet='0xabc', leader_fill_id='f-'+coin, timestamp_ms=NOW,
                                 price=100.0, size=1.0)
    return types.SimpleNamespace(fill=fill, intent_id='i-'+coin, reason='', notes='lifecycle=ENTRY',
                                 copy_side='BUY', copy_size=1.0, decision='SEND_ALLOWED', cap_detail=None,
                                 send_allowed=True, wallet_mode='LIVE')


def gateway_stub(**cooldowns):
    s = types.SimpleNamespace(
        cfg=types.SimpleNamespace(master_switch_now=lambda: True, send_mode_now=lambda: "ON",
                                  marketable_bps=lambda: 20.0),
        sender_key_invalid=False,
        _market_halted_until_ms=cooldowns.get('halted', {}),
        _ioc_no_match_until_ms=cooldowns.get('ioc', {}),
        _margin_reject_until_ms=cooldowns.get('margin', {}),
        _liq_parity_until_ms={},
        # the cooldown checks now sit AFTER the ownership gate, so this path passes the leader-reduced check first
        leader_reduced_since=lambda fill: False,
        _base_timing=lambda intent: {},
        _pre_send_ownership_gate=lambda intent: (True, {}))
    return s


# ---- P1: every status I removed from dispatch needs its own pre-order gate in the send lane ----
for label, kw in (('MARKET_HALTED', {'halted': {'btc': FAR}}),
                  ('IOC_NO_IMMEDIATE_MATCH', {'ioc': {'btc': FAR}}),
                  ('INSUFFICIENT_MARGIN', {'margin': {'btc': FAR}})):
    try:
        res = C.SenderGateway.send_if_allowed(gateway_stub(**kw), entry_intent())
        ok, status = res[0], res[1]
    except Exception as exc:
        ok, status = None, '%s: %s' % (type(exc).__name__, str(exc)[:70])
    check('SEND_LANE_GATES_%s_BEFORE_ANY_ORDER' % label, ok is False,
          'send_if_allowed returned %r / %r - the doomed order would reach _place_order' % (ok, status))

# and the margin refusal must carry the same named status the remedy maps
try:
    res = C.SenderGateway.send_if_allowed(gateway_stub(margin={'btc': FAR}), entry_intent())
    st = res[1]
except Exception as exc:
    st = '%s: %s' % (type(exc).__name__, str(exc)[:70])
check('MARGIN_REFUSAL_CARRIES_THE_MAPPED_STATUS', st == 'SKIPPED_INSUFFICIENT_MARGIN',
      'got %r - the remedy maps SKIPPED_INSUFFICIENT_MARGIN, so any other name silently breaks the remedy' % (st,))

# a reduction must never be gated by an entry cooldown
close = entry_intent()
close.fill.raw = {'dir': 'Close Long', 'created_at_ms': NOW}
close.notes = 'lifecycle=EXIT'
try:
    res = C.SenderGateway.send_if_allowed(gateway_stub(margin={'btc': FAR}), close)
    gate_st = res[1] if res[0] is False else None
except Exception as exc:
    gate_st = '%s: %s' % (type(exc).__name__, str(exc)[:70])
check('A_REDUCTION_IS_NOT_GATED_BY_AN_ENTRY_COOLDOWN', gate_st != 'SKIPPED_INSUFFICIENT_MARGIN',
      'a close was refused by the entry margin cooldown: %r' % (gate_st,))

# ---- P2: exactly one terminal row when the gate flips ----
def core_stub(place_outcome):
    rows = []
    def gate_row(intent, path, reason):
        # the real _gate_refusal_row calls append_reconciliation("SEND_TERMINAL", "BLOCKED_AT_PLACE_ORDER", ...)
        rows.append(('SEND_TERMINAL', 'BLOCKED_AT_PLACE_ORDER'))

    def rest_or_diff(intent, cause):
        # the real path reaches _place_order, whose gate refusal journals the row itself before returning
        if place_outcome == 'BLOCKED_AT_PLACE_ORDER':
            gate_row(intent, 'rest_entry', 'master gate refused at the physical call')
        return dict({'outcome': place_outcome, 'notes': 'gate refused at the physical call',
                     'wallet_alias': 'w'}, exchange_response=place_outcome, exchange_called=False)

    s = types.SimpleNamespace(
        _market_halted_until_ms={},
        _missed_entry_rest_or_diff=rest_or_diff,
        _gate_refusal_row=gate_row)
    audit = types.SimpleNamespace(append_reconciliation=lambda *a, **k: rows.append(
        (a[0] if a else k.get('event'), a[1] if len(a) > 1 else k.get('status'))))
    return types.SimpleNamespace(sender=s, audit=audit, cfg=types.SimpleNamespace()), rows


core, rows = core_stub('BLOCKED_AT_PLACE_ORDER')
try:
    C.LiveCopyCore._apply_missed_entry_rule_on_refusal(core, entry_intent().fill, entry_intent(),
                                                       'SKIPPED_IOC_NO_IMMEDIATE_MATCH')
except Exception as exc:
    print('   (wrapper raised %s: %s)' % (type(exc).__name__, str(exc)[:80]))
terminal_rows = [r for r in rows if r[0] == 'SEND_TERMINAL']
check('GATE_FLIP_WRITES_EXACTLY_ONE_TERMINAL_ROW', len(terminal_rows) == 1,
      'the wrapper wrote %d SEND_TERMINAL rows on top of the gate refusal: %r' % (len(terminal_rows), terminal_rows))

# and the normal remedy path still writes exactly one
core2, rows2 = core_stub('MISSED_ENTRY_LIMIT_RESTED')
try:
    C.LiveCopyCore._apply_missed_entry_rule_on_refusal(core2, entry_intent().fill, entry_intent(),
                                                       'SKIPPED_IOC_NO_IMMEDIATE_MATCH')
except Exception:
    pass
check('NORMAL_REMEDY_STILL_WRITES_ONE_TERMINAL_ROW',
      len([r for r in rows2 if r[0] == 'SEND_TERMINAL']) == 1,
      'rows=%r' % (rows2,))

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
