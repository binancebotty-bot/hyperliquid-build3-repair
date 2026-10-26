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
import json
import sys
import tempfile
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

# the threshold is HOT-RELOADED from live_config.json, so the fixture writes a real config and points Core at it
_CFG_DIR = Path(tempfile.mkdtemp(prefix='excl_cfg_'))
_CFG = _CFG_DIR / 'live_config.json'
_REAL_CFG = C.LIVE_CONFIG_FILE


def set_threshold(value):
    _CFG.write_text(json.dumps({'global_controls': {'min_24h_notional_usd': value}}), encoding='utf-8')
    C.LIVE_CONFIG_FILE = _CFG
    C._THRESHOLD_CACHE.update({'mtime': None, 'value': 0.0})   # force a re-read


set_threshold(3000.0)

LISTED = {'BTC', 'HYPE', 'ETC', 'MERL'}   # MERL is LISTED but thin; that is the point of it
VOL = {'BTC': 85000.0, 'HYPE': 2733.0, 'ETC': 5475.0, 'MERL': 61.0}


def fake_volumes(ok=True, vol=None, listed=None):
    def _f(refresh=False):
        return ok, dict(VOL if vol is None else vol), set(LISTED if listed is None else listed)
    return _f


# 1. a market the follower does not list
C.follower_volumes_24h = fake_volumes()
st, note = C.follower_entry_exclusion('XYZ:EWZ', True, GC, held_net=0.0)
check('AN_UNLISTED_COIN_IS_EXCLUDED', st == 'EXCLUDED_NOT_LISTED_ON_FOLLOWER_NETWORK',
      'got %r' % (st,))
check('THE_UNLISTED_NOTE_NAMES_THE_COIN_AND_THE_SOURCE', 'coin=XYZ:EWZ' in note and 'metaAndAssetCtxs' in note,
      'note=%r' % (note,))

# 2. a thin book
C.follower_volumes_24h = fake_volumes()
st, note = C.follower_entry_exclusion('MERL', True, GC, held_net=0.0)
check('A_THIN_BOOK_IS_EXCLUDED', st == 'ILLIQUID_SKIP', 'got %r' % (st,))
check('THE_ROW_CARRIES_THE_VOLUME_AND_THE_THRESHOLD', '24h_notional_usd=61.00' in note and 'threshold_usd=3000.00' in note,
      'note=%r' % (note,))

# 3. a healthy book is copied
st, _ = C.follower_entry_exclusion('ETC', True, GC, held_net=0.0)
check('A_HEALTHY_BOOK_IS_COPIED', st == '', 'ETC at 5475 against a 3000 threshold was excluded: %r' % (st,))

# 4. closes are never excluded, even on an unlisted market
st, _ = C.follower_entry_exclusion('XYZ:EWZ', False, GC)
check('A_CLOSE_IS_NEVER_EXCLUDED', st == '', 'a close was excluded: %r' % (st,))

# 5. mainnet never excludes
_real = C.FOLLOWER_NETWORK
try:
    C.FOLLOWER_NETWORK = 'mainnet'
    C.follower_volumes_24h = fake_volumes()
    st, _ = C.follower_entry_exclusion('XYZ:EWZ', True, GC, held_net=0.0)
    check('MAINNET_NEVER_EXCLUDES', st == '', 'mainnet excluded a leader coin: %r' % (st,))
finally:
    C.FOLLOWER_NETWORK = _real

# 6. an unreadable volume fails open
C.follower_volumes_24h = fake_volumes(ok=False)
st, note = C.follower_entry_exclusion('MERL', True, GC, held_net=0.0)
check('AN_UNREADABLE_VOLUME_FAILS_OPEN', st == '' and note == '',
      'with no volume reading the engine still skipped: %r' % (st,))

# 7. threshold 0 = off
C.follower_volumes_24h = fake_volumes()
set_threshold(0.0)                       # 0 = off, read from the file like the live switch
st, _ = C.follower_entry_exclusion('MERL', True, {}, held_net=0.0)
check('A_ZERO_THRESHOLD_DISABLES_THE_FILTER', st == '', 'threshold 0 still skipped: %r' % (st,))

# ---- the kill switch: an edit to the file must apply to the NEXT fill, with no restart ----
set_threshold(3000.0)
st_on, _ = C.follower_entry_exclusion('MERL', True, {}, held_net=0.0)
set_threshold(0.0)                       # the operator edits the config while the process runs
st_off, _ = C.follower_entry_exclusion('MERL', True, {}, held_net=0.0)
check('THE_FILTER_IS_HOT_RELOADABLE', st_on == 'ILLIQUID_SKIP' and st_off == '',
      'on=%r off=%r - a config edit did not take effect without a restart' % (st_on, st_off))

# a BAD value must keep the last good one, not silently disable or invent a threshold
set_threshold(3000.0)
C.follower_entry_exclusion('MERL', True, {}, held_net=0.0)      # load the good value first: the LAST GOOD is what
_CFG.write_text(json.dumps({'global_controls': {'min_24h_notional_usd': 'not-a-number'}}), encoding='utf-8')
st_bad, _ = C.follower_entry_exclusion('MERL', True, {}, held_net=0.0)   # the bad value must not replace it
check('A_BAD_THRESHOLD_KEEPS_THE_LAST_GOOD', st_bad == 'ILLIQUID_SKIP',
      'a bad value changed the filter instead of holding the last good one: %r' % (st_bad,))

# an ABSENT key means OFF, never a guessed ceiling
_CFG.write_text(json.dumps({'global_controls': {}}), encoding='utf-8')
C._THRESHOLD_CACHE.update({'mtime': None, 'value': 0.0})
st_absent, _ = C.follower_entry_exclusion('MERL', True, {}, held_net=0.0)
check('AN_ABSENT_KEY_MEANS_OFF', st_absent == '', 'an absent threshold still excluded: %r' % (st_absent,))
set_threshold(3000.0)

# 8. and it is wired before the price/risk gates, on the entry path only
src = (HERE / 'HL_Live_Copy_Service_Core.py').read_text(encoding='utf-8', errors='replace')
_fn = src.find('def _process_leader_fill_inner')
_build = src.find('intent_builder.build(', _fn)
_call = src.find('follower_entry_exclusion(', _build)
check('THE_EXCLUSION_RUNS_ON_THE_BUILT_INTENT_NOT_ON_THE_FILL_METADATA', 0 < _build < _call,
      'the exclusion does not run after the intent is built (build=%d call=%d)' % (_build, _call))
_block = src[max(0, _call-1600):_call]
check('THE_EXCLUSION_IS_GATED_BY_THE_ENGINE_LIFECYCLE_CLASSIFIER',
      'classify_send_lifecycle(intent)' in _block and '_life in {"ENTRY", "ADD"}' in _block,
      'the exclusion is not gated on the engine lifecycle classifier')
check('NO_RAW_DIRECTION_IN_THE_EXCLUSION_DECISION',
      "_fill_dir(" not in _block and 'raw.dir' not in _block and "raw.get(\"dir\")" not in _block,
      'the exclusion still consults the fill direction metadata')

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
if failed:
    print('FAILED: ' + ', '.join(failed))
sys.exit(1 if failed else 0)
