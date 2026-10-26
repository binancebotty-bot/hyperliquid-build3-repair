#!/usr/bin/env python3
"""Two follower entry exclusions, one path, testnet only, never a close.

Boss (26 Oct, via the controller): on testnet, markets the follower network does not list and markets too thin to
trade are EXCLUDED and labelled - because "in this environment where we are testing we are just orphaning cash".
Mainnet keeps "if the leader trades it we trade it". And the thin-book cut had never been built at all: `ILLIQUID_SKIP`
did not exist anywhere in the engine, against a Boss order from 24 Oct.

The rules this pins:
  * decided on ENTRIES only, before any price or risk gate; a close or a reduction is never excluded
  * one terminal row per leader fill, no order and no diff
  * testnet only - on mainnet nothing is excluded, ever
  * threshold from persistent config (min_24h_notional_usd, 0 = off), so Boss can change it without code
  * an UNREADABLE volume fails OPEN: a skip needs evidence the book is thin, not the absence of a reading

FAILING FIRST on 24f3588: neither function exists.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as C  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:200]) if not ok else ''))


if not hasattr(C, 'follower_entry_exclusion'):
    for n in ('AN_UNLISTED_COIN_IS_EXCLUDED', 'A_THIN_BOOK_IS_EXCLUDED', 'A_HEALTHY_BOOK_IS_COPIED',
              'A_CLOSE_IS_NEVER_EXCLUDED', 'MAINNET_NEVER_EXCLUDES', 'AN_UNREADABLE_VOLUME_FAILS_OPEN',
              'A_ZERO_THRESHOLD_DISABLES_THE_FILTER', 'THE_ROW_CARRIES_THE_VOLUME_AND_THE_THRESHOLD'):
        check(n, False, 'no exclusion path exists on this build')
    print('TOTAL=8 FAILED=8')
    sys.exit(1)

GC = {'min_24h_notional_usd': 3000.0}
LISTED = {'BTC', 'HYPE', 'ETC', 'MERL'}   # MERL is LISTED but thin; that is the point of it
VOL = {'BTC': 85000.0, 'HYPE': 2733.0, 'ETC': 5475.0, 'MERL': 61.0}


def fake_volumes(ok=True, vol=None, listed=None):
    def _f(refresh=False):
        return ok, dict(VOL if vol is None else vol), set(LISTED if listed is None else listed)
    return _f


# 1. a market the follower does not list
C.follower_volumes_24h = fake_volumes()
st, note = C.follower_entry_exclusion('XYZ:EWZ', True, GC)
check('AN_UNLISTED_COIN_IS_EXCLUDED', st == 'EXCLUDED_NOT_LISTED_ON_FOLLOWER_NETWORK',
      'got %r' % (st,))
check('THE_UNLISTED_NOTE_NAMES_THE_COIN_AND_THE_SOURCE', 'coin=XYZ:EWZ' in note and 'metaAndAssetCtxs' in note,
      'note=%r' % (note,))

# 2. a thin book
C.follower_volumes_24h = fake_volumes()
st, note = C.follower_entry_exclusion('MERL', True, GC)
check('A_THIN_BOOK_IS_EXCLUDED', st == 'ILLIQUID_SKIP', 'got %r' % (st,))
check('THE_ROW_CARRIES_THE_VOLUME_AND_THE_THRESHOLD', '24h_notional_usd=61.00' in note and 'threshold_usd=3000.00' in note,
      'note=%r' % (note,))

# 3. a healthy book is copied
st, _ = C.follower_entry_exclusion('ETC', True, GC)
check('A_HEALTHY_BOOK_IS_COPIED', st == '', 'ETC at 5475 against a 3000 threshold was excluded: %r' % (st,))

# 4. closes are never excluded, even on an unlisted market
st, _ = C.follower_entry_exclusion('XYZ:EWZ', False, GC)
check('A_CLOSE_IS_NEVER_EXCLUDED', st == '', 'a close was excluded: %r' % (st,))

# 5. mainnet never excludes
_real = C.FOLLOWER_NETWORK
try:
    C.FOLLOWER_NETWORK = 'mainnet'
    C.follower_volumes_24h = fake_volumes()
    st, _ = C.follower_entry_exclusion('XYZ:EWZ', True, GC)
    check('MAINNET_NEVER_EXCLUDES', st == '', 'mainnet excluded a leader coin: %r' % (st,))
finally:
    C.FOLLOWER_NETWORK = _real

# 6. an unreadable volume fails open
C.follower_volumes_24h = fake_volumes(ok=False)
st, note = C.follower_entry_exclusion('MERL', True, GC)
check('AN_UNREADABLE_VOLUME_FAILS_OPEN', st == '' and note == '',
      'with no volume reading the engine still skipped: %r' % (st,))

# 7. threshold 0 = off
C.follower_volumes_24h = fake_volumes()
st, _ = C.follower_entry_exclusion('MERL', True, {'min_24h_notional_usd': 0})
check('A_ZERO_THRESHOLD_DISABLES_THE_FILTER', st == '', 'threshold 0 still skipped: %r' % (st,))

# 8. and it is wired before the price/risk gates, on the entry path only
src = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8', errors='replace')
fn = src.find('def _process_leader_fill_inner')
gate = src.find('follower_entry_exclusion(', fn)
idem = src.find('# PRE-SEND IDEMPOTENCY GUARD', fn)
check('THE_EXCLUSION_RUNS_BEFORE_THE_IDEMPOTENCY_AND_SEND_PATH', 0 < gate < idem,
      'the exclusion is not on the entry path ahead of the send guard (gate=%d idem=%d)' % (gate, idem))

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
