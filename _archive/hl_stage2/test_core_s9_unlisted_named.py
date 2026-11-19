#!/usr/bin/env python3
"""S9 cut-down: the unlisted-coin diagnosis must be truthful.

Controller ruling 6403484386: an unlisted coin gets the named reason "not listed on this
network"; the old remedy string named build_hl_asset_universe_cache.py, a script that does
not exist anywhere on this host. These checks pin that down and would fail if the phantom
name came back or if a resolution failure were ever labelled as a margin problem.

Text-level assertions are the right tool here because the defect WAS the message text.
"""
import re
import sys
from pathlib import Path

CORE = Path(__file__).parent / 'HL_Live_Copy_Service_Core.py'
src = CORE.read_text(encoding='utf-8', errors='replace')
lines = src.splitlines()
results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:160]) if not ok else ''))


# 1. the phantom builder must never be named again
check('S9_NO_PHANTOM_BUILDER_SCRIPT',
      'build_hl_asset_universe_cache' not in src,
      [l for l in lines if 'build_hl_asset_universe_cache' in l][:2])

# 2. the stale-cache reason must name the real mechanism
reason_block = '\n'.join(l for l in lines if 'refresh_asset_universe' in l or 'HL_LIVE_ASSET_META_REFRESH_SEC' in l)
check('S9_CACHE_MISS_NAMES_REAL_MECHANISM',
      'refresh_asset_universe' in reason_block and 'HL_LIVE_ASSET_META_REFRESH_SEC' in reason_block,
      reason_block[:160])

# 3. an absent coin says "not listed on this network"
check('S9_UNRESOLVED_SAYS_NOT_LISTED_ON_THIS_NETWORK',
      'not listed on this network' in src,
      'string absent from Core')

# 4. neither reason may carry a margin label
idx = [i for i, l in enumerate(lines) if 'reason = ("symbol absent from the local asset universe' in l]
if not idx:
    check('S9_RESOLUTION_REASON_IS_NOT_A_MARGIN_LABEL', False, 'reason block not found')
else:
    block = '\n'.join(lines[idx[0]:idx[0] + 5])
    check('S9_RESOLUTION_REASON_IS_NOT_A_MARGIN_LABEL',
          'MARGIN_MODE_UNSET' not in block and 'MARGIN_MODE' not in block,
          block[:160])

# 5. the reason must not promise an action the operator cannot take
check('S9_REASON_HAS_NO_UNRUNNABLE_INSTRUCTION',
      not re.search(r'margin_mode_background.*run \S+\.py', src),
      'a .py remedy string still appears in the margin lane')

failed = [n for n, ok, _ in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
