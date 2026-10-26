#!/usr/bin/env python3
"""The follower mid cache must actually be used - including when a caller asks for a forced read.

Run 12 (2026-10-26) went over the info budget with ZERO send attempts. The largest single cause was not
the leader polls: `follower_mid(force=True)` on the missed-entry refusal path refetched `allMids` on every
call (562 of them), bypassing the 2 s cache that already existed. `force` means "do not accept a mid older
than the TTL", not "refetch always": OD-01 allows a mid up to 5 s old and the TTL is 2 s, so a forced read
serving a <=2 s value is inside the rule.

FAILING FIRST: before the fix, the second (forced) call refetches, so NO_CALL_SITE_CAN_BYPASS_THE_CACHE
fails with fetch count 2.
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
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:180]) if not ok else ''))


class Fetcher:
    """Counts allMids reads and serves a fixed price."""

    def __init__(self):
        self.calls = 0

    def __call__(self, name, payloads, url, timeout):
        self.calls += 1
        return [{'ok': True, 'data': {'BTC': '100.0'}} for _ in payloads]


clock = {'ms': 1_000_000}
fetcher = Fetcher()
C._XNET.post_many = fetcher
C.follower_dex_scope = lambda: ['']
C.utc_now_ms = lambda: clock['ms']
# a clean cache per run
if hasattr(C, '_FOLLOWER_MIDS'):
    C._FOLLOWER_MIDS.update({'px': {}, 'ms': 0, 'scope': None})

p1 = C.follower_mid('BTC')
check('FIRST_READ_FETCHES', fetcher.calls == 1, 'calls=%d' % fetcher.calls)
check('FIRST_READ_PRICED', p1 == 100.0, p1)

p2 = C.follower_mid('BTC')
check('CACHED_READ_DOES_NOT_FETCH', fetcher.calls == 1 and p2 == 100.0, 'calls=%d p=%r' % (fetcher.calls, p2))

# the refusal path: forced, but the cached value is 1 s old - inside the 2 s TTL, so it must reuse it
clock['ms'] += 1_000
p3 = C.follower_mid('BTC')  # the refusal path no longer has a bypass to call
check('NO_CALL_SITE_CAN_BYPASS_THE_CACHE', fetcher.calls == 1 and p3 == 100.0,
      'calls=%d (2 = something refetched inside the TTL) p=%r' % (fetcher.calls, p3))

# past the TTL the value is no longer fresh: a forced call MUST refetch
clock['ms'] += 2_500
p4 = C.follower_mid('BTC')
check('PAST_THE_TTL_IT_REFETCHES', fetcher.calls == 2 and p4 == 100.0, 'calls=%d p=%r' % (fetcher.calls, p4))

# and a value older than OD-01's 5 s limit is never returned, even from cache
clock['ms'] += 5_100
C._FOLLOWER_MIDS.update({'ms': clock['ms'] - 5_100})
p5 = C.follower_mid('DOGE')
check('STALE_BEYOND_MAX_AGE_IS_NONE', p5 == 0.0, 'p=%r' % (p5,))

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
