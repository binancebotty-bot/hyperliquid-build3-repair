#!/usr/bin/env python3
"""One terminal row per fill: a classified block must not also be called unclassified.

Controller ruling 6403650321. The catch-all at Core ~12214 writes SEND_TERMINAL /
BLOCKED_SEND_UNCLASSIFIED for any send_allowed status it does not recognise. LIQ_PARITY_BLOCKED
was missing from its handled set, so every liquidation-parity block produced TWO terminal rows
for one fill: the true reason from the parity gate, plus a shrug claiming the engine could not
classify it (31 of 31 fills measured in run8).

This drives the real predicate the catch-all now delegates to, so it fails if the prefix match
is removed or if the safety net is widened until it swallows genuinely unknown statuses.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import HL_Live_Copy_Service_Core as Core  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:160]) if not ok else ''))


fn = Core.send_status_reaches_catchall

# 1. the reported defect: a classified parity block must NOT reach the catch-all
check('S9_LIQ_PARITY_BLOCKED_DOES_NOT_REACH_CATCHALL', fn('LIQ_PARITY_BLOCKED') is False,
      'returns True, so a second row would be written')

# 2. prefix, not a literal: a parity mode added later must behave the same
check('S9_FUTURE_LIQ_PARITY_MODE_ALSO_EXCLUDED', fn('LIQ_PARITY_SOME_NEW_MODE') is False,
      'a new LIQ_PARITY_* mode would reintroduce the double row')

# 3. the safety net still works for genuinely unknown statuses
check('S9_UNKNOWN_STATUS_STILL_REACHES_CATCHALL', fn('SOMETHING_NOBODY_DEFINED') is True,
      'the net stopped catching unknown statuses')

# 4-7. the statuses that were already handled stay handled
for st in ('ORDER_REJECTED', 'ORDER_FILLED', 'ORDER_RESTING', 'ORDER_UNKNOWN', 'EXCHANGE_ERROR'):
    check('S9_%s_STILL_HANDLED' % st, fn(st) is False, st)

# 8-9. the prefixed and special-cased families stay handled
check('S9_OWNERSHIP_GATE_STILL_HANDLED', fn('OWNERSHIP_GATE_NO_SLEEVE') is False, 'gate prefix')
check('S9_SEND_NOT_ATTEMPTED_STILL_HANDLED', fn('SEND_NOT_ATTEMPTED_NO_MANUAL_POSITION') is False, 'not-attempted prefix')
check('S9_PENDING_EXIT_GUARD_STILL_HANDLED', fn('PENDING_EXIT_GUARD_ACTIVE') is False, 'exit guard')

# 10. structural: BLOCKED_SEND_UNCLASSIFIED has exactly one writer, inside the catch-all,
#     so "predicate false" really does mean "no second row" rather than merely "one fewer".
src = (Path(__file__).parent / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8', errors='replace')
writers = [i + 1 for i, l in enumerate(src.splitlines()) if '"BLOCKED_SEND_UNCLASSIFIED"' in l and 'SEND_TERMINAL' in l]
check('S9_UNCLASSIFIED_ROW_HAS_ONE_WRITER', len(writers) == 1, 'writers at lines %s' % writers)

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
