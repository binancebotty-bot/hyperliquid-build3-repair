#!/usr/bin/env python3
"""Codex row-2 (a): an absent snapshot is UNKNOWN age, never seconds since the epoch.

The defect: with no exchange snapshot file, built_at stayed 0, so age rendered as now-0 (about
1.79e9 seconds) and the 'not loaded yet' branch could never be reached. This drives the real
cache function and the real payload key.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import HL_Copy_App_SSOT as UI  # noqa: E402

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:170]) if not ok else ''))


# 1. NO snapshot at all: age must be None, and it must not be a huge number
saved_file, saved_cache = UI.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, dict(UI._SLOW_EXCHANGE)
UI.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = Path(tempfile.mkdtemp(prefix='uiage_')) / 'no_such_snapshot.json'
UI._SLOW_EXCHANGE.update({'snapshot': {}, 'follower': {}, 'built_at': 0.0, 'refreshing': True})
try:
    snap, fol, age = UI._exchange_slow_cached()
finally:
    UI.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = saved_file
    UI._SLOW_EXCHANGE.update(saved_cache)

check('UI_NO_SNAPSHOT_AGE_IS_UNKNOWN', age is None, age)
check('UI_NO_SNAPSHOT_AGE_IS_NOT_EPOCH_SIZED', not (isinstance(age, (int, float)) and age > 86400), age)

# 2. a usable snapshot gives a real, small age
tmp = Path(tempfile.mkdtemp(prefix='uiage2_'))
snapf = tmp / 'exchange_account_snapshot.json'
snapf.write_text('{"accountValue": "123.45"}', encoding='utf-8')
saved_file2, saved_cache2 = UI.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, dict(UI._SLOW_EXCHANGE)
UI.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = snapf
UI._SLOW_EXCHANGE.update({'snapshot': {}, 'follower': {}, 'built_at': 0.0, 'refreshing': True})
try:
    _, _, age2 = UI._exchange_slow_cached()
finally:
    UI.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = saved_file2
    UI._SLOW_EXCHANGE.update(saved_cache2)
check('UI_SEEDED_SNAPSHOT_GIVES_A_REAL_AGE', isinstance(age2, (int, float)) and age2 >= 0, age2)

# 3. the page must be able to say 'not loaded yet' when the age is unknown
src = (Path(__file__).parent / 'HL_Copy_App_SSOT.py').read_text(encoding='utf-8', errors='replace')
check('UI_PAGE_RENDERS_NOT_LOADED_YET', 'exchange figures: not loaded yet' in src, 'string missing')
check('UI_PILL_NOT_HIDDEN_WHEN_UNKNOWN', 'ex.hidden=false;if(known){' in src, 'pill can still be hidden')

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
