#!/usr/bin/env python3
"""A cached cooldown block must not leave a trade with neither an order nor a named diff.

Live evidence (run13/run14): 12 `SKIPPED_IOC_NO_IMMEDIATE_MATCH` fills and 12 `SKIPPED_INSUFFICIENT_MARGIN`
fills ended with NO order and NO `MISSED_ENTRY_DIFF_*` row. Cause: `known_dispatch_reject` (Core:5420-5434)
returns a cached block BEFORE the fill is queued, `_dispatch_fill` (Core:11732-11735) records a terminal skip
and returns, so the fill never reaches the send lane where `_apply_missed_entry_rule_on_refusal`
(Core:12280-12306) turns a refusal into a resting limit at the leader's price.

Controller ruling 6409748448:
  * remove the dispatch early return ONLY for halted, IOC-no-match and insufficient-margin;
  * LIQ_PARITY_BLOCKED keeps its dispatch block exactly as it is - it is a Boss-ordered skip and must stay a
    named skip (testnet is handled by liq_parity=false in config, not by code);
  * add cause branches so IOC-no-match and insufficient-margin reach `_missed_entry_rest_or_diff`;
  * entries only - a reduction can never rest a limit and must keep going through the close path.

FAILING FIRST: on the deployed engine these cases return True/None where they should return False/"" - the
fill is skipped at dispatch and the cause mapping returns None.
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


def fill(dir_='Open Long', coin='BTC', wallet='0xabc'):
    return types.SimpleNamespace(raw={'dir': dir_}, coin=coin, side='BUY', leader_wallet=wallet,
                                 leader_fill_id='f-1', timestamp_ms=C.utc_now_ms(), price=100.0, size=1.0)


def sender_stub(halted=0, ioc=0, margin=0, parity=0):
    s = types.SimpleNamespace(
        _market_halted_until_ms={'btc': halted},
        _ioc_no_match_until_ms={'btc': ioc},
        _margin_reject_until_ms={'btc': margin},
        _liq_parity_until_ms={'btc': parity})
    s.known_dispatch_reject = lambda f: C.SenderGateway.known_dispatch_reject(s, f)
    return s


FAR = C.utc_now_ms() + 600000  # a cooldown that is definitely active

# ---- 1. dispatch no longer terminal-skips the three tradable-coin cases ----
for label, kwargs in (('HALTED', {'halted': FAR}), ('IOC_NO_MATCH', {'ioc': FAR}),
                      ('INSUFFICIENT_MARGIN', {'margin': FAR})):
    got = sender_stub(**kwargs).known_dispatch_reject(fill())
    check('DISPATCH_LETS_%s_THROUGH_TO_THE_SEND_LANE' % label, got == '',
          'known_dispatch_reject returned %r - the fill is skipped before the remedy can run' % (got,))

# ---- 2. parity keeps its skip, exactly as ruled ----
got = sender_stub(parity=FAR).known_dispatch_reject(fill())
check('PARITY_STAYS_A_NAMED_SKIP_AT_DISPATCH', got == 'LIQ_PARITY_BLOCKED',
      'parity block changed to %r - it must stay LIQ_PARITY_BLOCKED' % (got,))

# ---- 3. reductions never take this route ----
got = sender_stub(ioc=FAR).known_dispatch_reject(fill(dir_='Close Long'))
check('A_REDUCTION_IS_NEVER_DISPATCH_BLOCKED', got == '',
      'a close fill was dispatch-blocked with %r - reductions must use the close path' % (got,))

# ---- 4. the cause mapping now hands IOC / margin refusals to the missed-entry rule ----
def core_stub():
    calls = []
    s = types.SimpleNamespace(
        _market_halted_until_ms={},
        _missed_entry_rest_or_diff=lambda intent, cause: (calls.append(cause),
                                                          {'outcome': 'MISSED_ENTRY_LIMIT_RESTED',
                                                           'notes': 'stub rest', 'wallet_alias': 'w'})[1],
        _resolve_coin=lambda c: {'snapshot_only': False})
    audit = types.SimpleNamespace(append_reconciliation=lambda *a, **k: None)
    core = types.SimpleNamespace(sender=s, audit=audit, cfg=types.SimpleNamespace())
    return core, calls


ENTRY_INTENT = types.SimpleNamespace(reason='', notes='lifecycle=ENTRY', intent_id='i-1',
                                     fill=fill(), copy_side='BUY', copy_size=1.0,
                                     wallet_position_before=0.0)

for label, status in (('IOC_NO_MATCH', 'SKIPPED_IOC_NO_IMMEDIATE_MATCH'),
                      ('INSUFFICIENT_MARGIN', 'SKIPPED_INSUFFICIENT_MARGIN')):
    core, calls = core_stub()
    try:
        out = C.LiveCopyCore._apply_missed_entry_rule_on_refusal(core, fill(), ENTRY_INTENT, status)
    except Exception as exc:
        out = '%s: %s' % (type(exc).__name__, str(exc)[:80])
    check('REFUSAL_%s_REACHES_THE_MISSED_ENTRY_RULE' % label, bool(calls) and isinstance(out, dict),
          'rule_calls=%r out=%r' % (calls, out))

# ---- 5. a reduction refusal still never reaches the rule ----
core, calls = core_stub()
out = C.LiveCopyCore._apply_missed_entry_rule_on_refusal(
    core, fill(dir_='Close Long'), types.SimpleNamespace(reason='', notes='lifecycle=EXIT', intent_id='i-2',
                                                         fill=fill(), copy_side='SELL', copy_size=1.0,
                                                         wallet_position_before=1.0),
    'SKIPPED_IOC_NO_IMMEDIATE_MATCH')
check('A_REDUCTION_REFUSAL_NEVER_RESTS_A_LIMIT', not calls and out is None,
      'the rule ran for a reduction: calls=%r out=%r' % (calls, out))

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
