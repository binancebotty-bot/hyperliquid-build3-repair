#!/usr/bin/env python3
"""NO_MANUAL_POSITION_TO_CLOSE is a conclusion, not a pending state.

Controller ruling 6410240211 / 6410136847: move it to TERMINAL_ROW_NAMES. The sets drive only a diagnostic list
(Core:3466 `_unclassified_names`), so this changes no trading decision and no written row - but the engine's own
proof function `_has_no_manual_position_terminal_proof` (Core:2917-2924) ALREADY treats the status as terminal
proof for the hard-copy counts. The reporting set was simply out of step with that, and the offline join inherited
the gap: 1,926 of 2,141 "group 2" fills were this one status.

FAILING FIRST on 2e44573: classify_terminal_row returns NON_TERMINAL.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:160]) if not ok else ''))


NAME = 'NO_MANUAL_POSITION_TO_CLOSE'

check('NMP_IS_CLASSIFIED_TERMINAL', C.classify_terminal_row(NAME) == 'TERMINAL',
      'got %r' % (C.classify_terminal_row(NAME),))
check('NMP_IS_IN_THE_TERMINAL_SET', NAME in C.TERMINAL_ROW_NAMES,
      'absent from TERMINAL_ROW_NAMES')
check('NMP_IS_NO_LONGER_NON_TERMINAL', NAME not in C.NON_TERMINAL_ROW_NAMES,
      'still present in NON_TERMINAL_ROW_NAMES - the two sets must not both claim it')
check('THE_TWO_SETS_STAY_DISJOINT', not (C.TERMINAL_ROW_NAMES & C.NON_TERMINAL_ROW_NAMES),
      'overlap: %r' % (sorted(C.TERMINAL_ROW_NAMES & C.NON_TERMINAL_ROW_NAMES)[:5],))
check('AN_UNKNOWN_NAME_IS_STILL_UNCLASSIFIED', C.classify_terminal_row('SOMETHING_THE_SENDER_NEVER_WROTE') == 'UNCLASSIFIED',
      'exact-set matching loosened')

# the semantic consumer must be untouched: the proof path reads the literal, so it keeps working either way
src = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8', errors='replace')
check('THE_PROOF_FUNCTION_STILL_NAMES_IT', '_has_no_manual_position_terminal_proof' in src
      and src.count('status == "NO_MANUAL_POSITION_TO_CLOSE"') >= 1,
      'the proof path lost its literal')
check('SEND_LANE_STILL_EMITS_THE_NAME', src.count('terminal_state="NO_MANUAL_POSITION_TO_CLOSE"') >= 1,
      'the writer no longer emits the status this change classifies')

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
