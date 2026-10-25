#!/usr/bin/env python3
"""Entries approved between snapshots must stay counted until a snapshot proves them.

The defect (Core:4921): a fresh follower read REPLACES self._exposure_pending with [], so an entry
approved moments earlier, whose fill is not yet visible in the snapshot just taken, stops counting
against the cap. During the 2026-10-25 burst that let ~132 entries through a $900 cap on a $928
account while the cap itself refused nine times.

This drives the REAL IntentBuilder.follower_exposure and the REAL _exposure_cap_block through the
module's own test seam (EXPOSURE_FETCHER), so the pending list is cleared by the production code
path rather than by a stub that cannot reproduce it.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import HL_Live_Copy_Service_Core as C  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:180]) if not ok else ''))


class FakeCfg:
    def max_total_exposure(self):
        return 900.0

    def max_asset_directional_exposure(self):
        return 5000.0

    def min_notional(self):
        return 5.0


def snapshot(value_usd):
    """The RAW /info answer: the seam hands the fetcher's return straight into master_exposure."""
    return {'marginSummary': {'accountValue': '928.0'},
            'assetPositions': [{'position': {'coin': 'BTC', 'szi': '0.001',
                                             'positionValue': str(value_usd)}}]}


def make_sender(exposure_usd, visible):
    """visible: what the exchange snapshot reports for BTC, which may lag an approved entry."""
    s = types.SimpleNamespace()
    s.cfg = FakeCfg()
    s._exposure_pending = []
    s._exposure = None
    s._exposure_ms = 0
    s._exposure_gen = 0
    s._exposure_prefetched = None
    s._exposure_fail = None
    s._resting = lambda: {'total_usd': 0.0, 'buy_units': {}, 'sell_units': {}}
    return s, visible


fill = types.SimpleNamespace(coin='BTC', price=50000.0, side='BUY')

C.USER_WALLET = '0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205'
C.follower_dex_scope = lambda: ['']

state = {'visible': 0.0}


def fetcher(payload):
    return snapshot(state['visible'])


C.EXPOSURE_FETCHER = fetcher


def make():
    """A stub with the REAL follower_exposure bound, so the production refresh path runs."""
    st = types.SimpleNamespace(cfg=FakeCfg(), _exposure_pending=[], _exposure=None, _exposure_ms=0,
                               _exposure_gen=0, _exposure_prefetched=None, _exposure_fail=None,
                               _resting=lambda: {'total_usd': 0.0, 'buy_units': {}, 'sell_units': {}})
    st.follower_exposure = types.MethodType(C.IntentBuilder.follower_exposure, st)
    return st


def refresh(s):
    s._exposure_ms = 0            # expire the cache so the next call really reads
    return C.IntentBuilder.follower_exposure(s)


def approve(s, notional):
    return C.IntentBuilder._exposure_cap_block(s, fill, notional, 50000.0)


# ---- 1. pending counts within one snapshot window
state['visible'] = 800.0
s = make()
refresh(s)
r1 = approve(s, 100.0)
r2 = approve(s, 100.0)
check('SECOND_ENTRY_BLOCKED_INSIDE_ONE_SNAPSHOT', r1 == '' and r2 != '', 'first=%r second=%r' % (r1, r2))

# ---- 2. THE DEFECT: a refresh that does not yet show the approved fill must not clear the pending
state['visible'] = 800.0
s2 = make()
refresh(s2)
approve(s2, 100.0)                 # pending holds 100; the exchange still reports 800
refresh(s2)                        # TTL expiry, snapshot unchanged: the fill is not visible yet
r3 = approve(s2, 100.0)            # 800 real + 100 pending must still hit the 900 cap
check('PENDING_SURVIVES_A_REFRESH_THAT_HIDES_ITS_FILL', r3 != '',
      'allowed again -> pending was wiped by the refresh; pending now %s' % s2._exposure_pending)

# ---- 3. a snapshot that DOES show the fill must not cause a double release: the entry is held
#      until its TTL, which over-counts (safe) rather than under-counts (the incident)
state['visible'] = 900.0
refresh(s2)
held = len(s2._exposure_pending)
r4 = approve(s2, 100.0)
check('VISIBLE_FILL_DOES_NOT_DOUBLE_RELEASE', held == 1 and r4 != '', 'held=%d r4=%r' % (held, r4))

# ---- 4. and the hold is released by age, not forever
s2._exposure_pending = [(c, u, px, at - 3600.0) for (c, u, px, at) in s2._exposure_pending]
refresh(s2)
check('PENDING_IS_RELEASED_BY_AGE', len(s2._exposure_pending) == 0, s2._exposure_pending)

# ---- 5. an unreadable exposure fails closed
C.EXPOSURE_FETCHER = lambda payload: (_ for _ in ()).throw(RuntimeError('boom'))
s5 = make()
r5 = approve(s5, 10.0)
check('UNREADABLE_EXPOSURE_FAILS_CLOSED', r5 != '', r5)

# ---- TTL BOUNDARY, deterministically: pin time so "exactly the limit" is exact
C.EXPOSURE_FETCHER = fetcher          # an earlier check replaced it with a raising stub
_real_mono = C.time.monotonic
try:
    C.time.monotonic = lambda: 1000.0
    state['visible'] = 800.0
    sb = make()
    sb._exposure = {'ok': True, 'status': 'TRUTH_OK', 'total_usd': 800.0, 'by_coin': {}, 'equity_usd': 928.0}
    sb._exposure_ms = int(1000.0 * 1000)
    ttl = float(__import__('os').getenv('HL_LIVE_EXPOSURE_PENDING_TTL_SEC', '30'))
    at_boundary = [(  # age == TTL exactly -> still counted
        'BTC', 0.002, 50000.0, 1000.0 - ttl)]
    sb._exposure_pending = list(at_boundary)
    r_kept = approve(sb, 120.0)          # 800 + 100 pending = 900 -> a 120 entry must be refused
    just_over = [('BTC', 0.002, 50000.0, 1000.0 - ttl - 0.001)]
    sb._exposure_pending = list(just_over)
    r_released = approve(sb, 120.0)      # pending expired -> 800 + 120 <= 900 -> allowed
finally:
    C.time.monotonic = _real_mono
check('TTL_BOUNDARY_AGE_EQUAL_TO_LIMIT_IS_KEPT', r_kept != '', r_kept)
check('TTL_BOUNDARY_JUST_OVER_THE_LIMIT_IS_RELEASED', r_released == '', r_released)


failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
