#!/usr/bin/env python3
"""The two near-static info reads must be cached: perpDexs (weight 20) and portfolio (weight 20) were
re-read ~5-6 times a minute each (~220 weight/min) and exhausted the shared testnet info budget.

FAILING FIRST: before the cache exists, SECOND_CALL_INSIDE_TTL_REUSES fails (fetch count 2).
No network: every fetcher is a local fake.
"""
import sys
import time as _real_time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import exchange_truth as xt  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:180]) if not ok else ''))


class FakeTime:
    """Module-local clock; everything else delegates to the real time module."""

    def __init__(self, now=1000.0):
        self.now = now

    def monotonic(self):
        return self.now

    def __getattr__(self, name):
        return getattr(_real_time, name)


class DexFetcher:
    def __init__(self, ok=True):
        self.calls = 0
        self.ok = ok

    def __call__(self, payload):
        self.calls += 1
        if not self.ok:
            raise RuntimeError('perpDexs unavailable')
        return [{'name': 'xyz'}]


class PortfolioFetcher:
    def __init__(self, ok=True):
        self.calls = 0
        self.ok = ok
        self.seen = []

    def __call__(self, payload):
        self.calls += 1
        self.seen.append(payload.get('user'))
        if not self.ok:
            raise RuntimeError('portfolio unavailable')
        return [['day', {'pnlHistory': [[0, '100.0'], [1, '110.0']],
                         'accountValueHistory': [[0, '500.0'], [1, '510.0']]}]]


def reset_cache():
    getattr(xt, '_CACHE', {}).clear()  # absent before the cache exists: the test must still run
    fake = FakeTime()
    xt.time = fake
    return fake


A, B = '0x' + 'a' * 40, '0x' + 'b' * 40

# ---- list_perp_dexes: TTL 3600 s
clock = reset_cache()
d1 = DexFetcher()
r1 = xt.list_perp_dexes(fetcher=d1)
check('FIRST_CALL_FETCHES', d1.calls == 1 and r1.get('ok') and r1.get('dexes') == ['', 'xyz'],
      'calls=%d r=%r' % (d1.calls, r1))

r2 = xt.list_perp_dexes(fetcher=d1)
check('SECOND_CALL_INSIDE_TTL_REUSES', d1.calls == 1 and r2 == r1,
      'calls=%d (2 = no cache) equal=%r' % (d1.calls, r2 == r1))

clock.now += 3601
r3 = xt.list_perp_dexes(fetcher=d1)
check('CALL_AFTER_TTL_REFETCHES', d1.calls == 2 and r3 == r1, 'calls=%d (1 = stale served)' % d1.calls)

# ---- a failed read must not be cached: an outage must not pin an error for an hour
clock = reset_cache()
bad = DexFetcher(ok=False)
f1 = xt.list_perp_dexes(fetcher=bad)
f2 = xt.list_perp_dexes(fetcher=bad)
check('FAILURE_IS_NOT_CACHED', not f1.get('ok') and bad.calls == 2,
      'ok=%r calls=%d (1 = the failure was cached)' % (f1.get('ok'), bad.calls))

# ---- rolling_day_pnl: TTL 60 s, keyed per address
clock = reset_cache()
p = PortfolioFetcher()
v1 = xt.rolling_day_pnl(A, fetcher=p)
v2 = xt.rolling_day_pnl(A, fetcher=p)
clock.now += 61
v3 = xt.rolling_day_pnl(A, fetcher=p)
check('PORTFOLIO_FIRST_FETCHES_TTL_REUSES_THEN_REFETCHES',
      p.calls == 2 and v1 == v2 == v3 and v1.get('ok') and v1.get('pnl_usd') == 10.0,
      'calls=%d (2 expected) v=%r' % (p.calls, v1))

clock = reset_cache()  # A is still warm from the block above; clear it so this proves the KEY, not the TTL
p2 = PortfolioFetcher()
xt.rolling_day_pnl(A, fetcher=p2)
xt.rolling_day_pnl(B, fetcher=p2)
check('DIFFERENT_ADDRESSES_DO_NOT_SHARE_A_CACHE_ENTRY', p2.calls == 2 and p2.seen == [A, B],
      'calls=%d seen=%r' % (p2.calls, p2.seen))

# ---- the two keys never collide
clock = reset_cache()
cross = PortfolioFetcher()
d_cross = DexFetcher()
xt.list_perp_dexes(fetcher=d_cross)
cv = xt.rolling_day_pnl(A, fetcher=cross)
check('PERPDEXS_AND_PORTFOLIO_KEYS_DO_NOT_COLLIDE', cross.calls == 1 and cv.get('ok'),
      'portfolio calls=%d cv=%r' % (cross.calls, cv))

# ---- a failed portfolio read is not cached either
clock = reset_cache()
pbad = PortfolioFetcher(ok=False)
xt.rolling_day_pnl(A, fetcher=pbad)
xt.rolling_day_pnl(A, fetcher=pbad)
check('PORTFOLIO_FAILURE_IS_NOT_CACHED', pbad.calls == 2, 'calls=%d (1 = failure cached)' % pbad.calls)

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
