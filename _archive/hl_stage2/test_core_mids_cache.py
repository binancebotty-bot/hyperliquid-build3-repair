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



class FailingFetcher:
    """The info endpoint is unreachable: the refresh raises."""

    def __init__(self):
        self.calls = 0

    def __call__(self, name, payloads, url, timeout):
        self.calls += 1
        raise RuntimeError('refresh failed')


class EmptyFetcher:
    """The refresh succeeds but carries no price for the coin."""

    def __init__(self):
        self.calls = 0

    def __call__(self, name, payloads, url, timeout):
        self.calls += 1
        return [{'ok': True, 'data': {}} for _ in payloads]


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

# ---- Codex 6407326445: the max-age check must be proved directly. An over-age cached value that the
# refresh cannot replace must NOT be served - not even as a sizing input.
C._FOLLOWER_MIDS.update({'px': {'BTC': 100.0}, 'ms': clock['ms'] - 6_000, 'scope': ['']})   # 6 s old > 5 s limit
C._XNET.post_many = FailingFetcher()
try:
    p6 = C.follower_mid('BTC')
    check('OVER_AGE_VALUE_IS_NOT_SERVED_WHEN_THE_REFRESH_FAILS', p6 == 0.0, 'returned %r, expected 0.0' % (p6,))
except Exception as exc:
    check('OVER_AGE_VALUE_IS_NOT_SERVED_WHEN_THE_REFRESH_FAILS', False,
          'the refresh failure escaped follower_mid as %s: %s' % (type(exc).__name__, str(exc)[:100]))

# same, but the refresh succeeds and simply has no price for the coin
C._FOLLOWER_MIDS.update({'px': {'BTC': 100.0}, 'ms': clock['ms'] - 6_000, 'scope': ['']})
C._XNET.post_many = EmptyFetcher()
p7 = C.follower_mid('BTC')
check('OVER_AGE_VALUE_IS_NOT_SERVED_WHEN_THE_REFRESH_IS_EMPTY', p7 == 0.0, 'returned %r, expected 0.0' % (p7,))

# ---- Codex 6407419352: a DEX is learned while the refresh is failing. The cached prices cover the OLD
# scope and are only 1 s old, so an age-only check would serve them and price an order from a market the
# engine has not read. Scope must be part of the final check, not just the refresh trigger.
C._FOLLOWER_MIDS.update({'px': {'BTC': 100.0}, 'ms': clock['ms'] - 1_000, 'scope': ['']})   # 1 s old: fresh
C._XNET.post_many = FailingFetcher()
C.follower_dex_scope = lambda: ['', 'hip3test']       # the scope changed since those prices were read
p8 = C.follower_mid('BTC')
check('OLD_SCOPE_PRICE_IS_NOT_SERVED_WHEN_THE_REFRESH_FAILS', p8 == 0.0,
      'returned %r - an old-scope price would have priced an order' % (p8,))
C.follower_dex_scope = lambda: ['']                    # restore for the cases below

# ---- The cache must not change the PRICE the sizing path reads. A full production-path equivalence is not
# testable at this level: Core floors `intent.copy_size` before it reads the follower mid, so quantity
# equality is established upstream of this function, and re-deriving a formula in the test proved nothing
# (Codex 6407419352). What this function must guarantee is that a warm cache returns the SAME mid as a
# fresh read - if it ever did not, every downstream size would differ.
C._FOLLOWER_MIDS.update({'px': {}, 'ms': 0, 'scope': None})
fresh_fetch = Fetcher()
C._XNET.post_many = fresh_fetch
clock['ms'] += 10_000
mid_fresh = C.follower_mid('BTC')                  # cold: fetches
clock['ms'] += 500
mid_cached = C.follower_mid('BTC')                 # warm: reuses
check('CACHED_MID_EQUALS_FRESH_MID_SO_SIZING_IS_UNCHANGED',
      mid_fresh == mid_cached == 100.0 and fresh_fetch.calls == 1,
      'fresh=%r cached=%r fetches=%d' % (mid_fresh, mid_cached, fresh_fetch.calls))

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
