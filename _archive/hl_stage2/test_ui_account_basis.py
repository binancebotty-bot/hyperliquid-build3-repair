#!/usr/bin/env python3
"""The account-value tile must state its basis, and the banner must not blank itself.

Controller order (2026-10-26 6411742556): show "Account value (spot + perp) $986.74" with "Perp equity $215,
margin available $0.00" beside it, because reading the spot+perp total as trading room overstates the perp equity by
about four times.

Why the second half of this test exists: the first attempt at that sub-line referenced `snap`, which is built in a
LATER function. The banner then threw `snap is not defined` and EVERY tile went to a dash - sending, health, account
change, open positions. A cosmetic improvement blanked the most-read strip on the page. So the test pins the rule: the
banner-update block may only read the audit object defensively, never a variable it does not own.
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = (HERE / "HL_Copy_App_SSOT.py").read_text(encoding="utf-8", errors="replace")
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:200]) if not ok else ''))


check('THE_TILE_STATES_ITS_BASIS', 'Account value (spot + perp)' in SRC,
      'the tile still claims a bare "Account value"')
check('THE_PERP_EQUITY_IS_SHOWN_BESIDE_IT', 'perp equity ' in SRC and 'margin available ' in SRC,
      'the perp equity / margin available sub-line is missing')

# the banner-update block: from the account-value set() call back to the function that owns it
m = re.search(r"set\('lcBannerAcct'", SRC)
assert m, 'the account-value banner call is missing'
block_start = max(0, m.start() - 2500)
block = SRC[block_start:m.end() + 500]
check('THE_BANNER_BLOCK_READS_THE_AUDIT_OBJECT_DEFENSIVELY',
      'lcAudit&&lcAudit.' in block or 'lcAudit && lcAudit.' in block,
      'the banner block does not read lcAudit defensively')
bare_snap = re.search(r'(?<![\w.])snap\s*[.&|]', block)
check('THE_BANNER_BLOCK_NEVER_TOUCHES_A_VARIABLE_IT_DOES_NOT_OWN', bare_snap is None,
      'the banner block references `snap`, which is defined later - this blanked every tile once: %r'
      % (bare_snap.group(0) if bare_snap else ''))
check('THE_BANNER_VALUE_CAN_FALL_BACK_TO_THE_FOLLOWER_TOTAL',
      'follower_account' in block,
      'with the banner account_value absent the tile would show a dash beside a real figure')
check('THE_SEED_WORDING_EXISTS', 'seeded at %s, not run start' in SRC or 'seeded at ' in SRC,
      'nothing labels a seeded point as a seed rather than a run start')


# ---- the chart must show ONE reading, not an empty box ----
check('THE_CHART_HAS_A_SINGLE_POINT_MARKER', 'id="lcExchangeDot"' in SRC,
      'there is no element to plot a single reading with')
_m = re.search(r"if\(points\.length<2\)\{(.{0,1600})", SRC, re.S)
_block = _m.group(1)[:1600] if _m else ''
check('ONE_POINT_IS_PLOTTED_WITH_A_NOTE', 'points.length===1' in _block and 'One reading so far' in _block,
      'a single point still falls through to the empty-box path')
check('THE_CHART_DOES_NOT_CLAIM_NO_DATA_FOR_ONE_POINT',
      'clearGraphText' in _block and _block.find('points.length===1') < _block.find('clearGraphText'),
      'the one-point case clears the chart instead of drawing it')

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
