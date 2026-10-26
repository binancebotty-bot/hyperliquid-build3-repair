#!/usr/bin/env python3
"""The equity series must come from the engine's own read, not from somebody opening the page.

The graph had no series on a fresh state dir and the only sampler was a page render, so a quiet account and a quiet
dashboard looked identical, and a busy page drew a different shape from a quiet one. The engine already reads
clearinghouseState every cycle; this records one point per minute from that read. No extra HTTP call, no new process -
the standing ban on background pollers is respected because there is no new loop at all.

FAILING FIRST on 41d8aa9: append_account_history_point does not exist.
"""
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:200]) if not ok else ''))


if not hasattr(C, 'append_account_history_point'):
    for n in ('THE_ENGINE_RECORDS_A_POINT_FROM_ITS_OWN_READ', 'ONE_POINT_PER_MINUTE_AT_MOST',
              'A_ZERO_ACCOUNT_IS_NOT_A_POINT', 'THE_SERIES_IS_CAPPED', 'THE_POINT_IS_ENGINE_SOURCED',
              'THE_SAMPLER_MAKES_NO_HTTP_CALL'):
        check(n, False, 'no engine sampler exists on this build - the graph depends on page loads')
    print('TOTAL=6 FAILED=6')
    sys.exit(1)

tmp = Path(tempfile.mkdtemp(prefix='accthist_'))
_real_dir = C.AUDIT_DIR
try:
    C.AUDIT_DIR = tmp
    path = tmp / 'exchange_account_history.json'

    def snap(value=215.0, withdrawable=0.01, positions=2, ts=None):
        return {"created_at": ts or time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime()),
                "created_at_ms": int(time.time() * 1000),
                "raw": {"marginSummary": {"accountValue": str(value)},
                        "withdrawable": str(withdrawable),
                        "assetPositions": [{"position": {"coin": "A%d" % i, "positionValue": "10.0"}}
                                           for i in range(positions)]}}

    wrote = C.append_account_history_point(snap())
    hist = json.loads(path.read_text()) if path.exists() else []
    check('THE_ENGINE_RECORDS_A_POINT_FROM_ITS_OWN_READ', wrote and len(hist) == 1,
          'wrote=%r points=%d' % (wrote, len(hist)))
    check('THE_POINT_IS_ENGINE_SOURCED', bool(hist) and hist[0].get('source') == 'engine_cycle'
          and hist[0].get('seeded') is False,
          'entry=%r' % (hist[0] if hist else None,))

    again = C.append_account_history_point(snap())
    hist = json.loads(path.read_text())
    check('ONE_POINT_PER_MINUTE_AT_MOST', again is False and len(hist) == 1,
          'a second point landed inside the minute: wrote=%r points=%d' % (again, len(hist)))

    zero = C.append_account_history_point(snap(value=0.0))
    check('A_ZERO_ACCOUNT_IS_NOT_A_POINT', zero is False, 'a zero account value was recorded as a point')

    # cap: write past the limit with distinct timestamps
    C.append_account_history_point  # keep the reference used above
    for i in range(6):
        s = snap(value=200.0 + i)
        s['created_at'] = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime(time.time() - 120 * (i + 1)))
        s['raw']['marginSummary']['accountValue'] = str(100.0 + i)
        C.append_account_history_point(s, max_points=3)
    hist = json.loads(path.read_text())
    check('THE_SERIES_IS_CAPPED', len(hist) <= 3, 'the series grew to %d with max_points=3' % len(hist))
finally:
    C.AUDIT_DIR = _real_dir
    shutil.rmtree(tmp, ignore_errors=True)

src = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8', errors='replace')
i = src.find('def append_account_history_point')
body = src[i:i + 2600]
check('THE_SAMPLER_MAKES_NO_HTTP_CALL',
      not any(t in body for t in ('requests.post', 'urllib', '_XNET', 'fetch(')),
      'the sampler reaches for the network; it must use the read the cycle already made')

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
