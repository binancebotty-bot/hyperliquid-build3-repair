#!/usr/bin/env python3
"""UI: a read that raises must set the partial marker and name the failure.

Codex FAIL row 1 was that bounded or failed reads were hidden behind ok:true. The bounded case
is exercised by real run8 data; the FAILED case is not, because run8 has no unreadable file.
This injects the failure instead of waiting for one, against a directory that really holds a
journal so the read is actually attempted.
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


base = UI._symbol_not_listed_summary()
check('UI_BASELINE_HAS_NO_FALSE_FAILURE',
      [e for e in (base.get('partial_reads') or []) if 'read failed' in e] == [],
      base.get('partial_reads'))
check('UI_PAYLOAD_ALWAYS_CARRIES_PARTIAL_KEYS',
      'partial' in base and 'partial_reads' in base, sorted(base)[:12])

real = UI._read_csv_incremental
tmp = Path(tempfile.mkdtemp(prefix='uipartial_'))
(tmp / 'reconciliation.20261025.1.csv').write_text('created_at,status\n', encoding='utf-8')
saved_dir, saved_err = UI.APPEND_ONLY_DIR, UI.ERRORS_CSV
UI.APPEND_ONLY_DIR = tmp
UI.ERRORS_CSV = tmp / 'errors.csv'


def boom(*a, **k):
    raise PermissionError('injected: file is locked')


UI._read_csv_incremental = boom
try:
    bad = UI._symbol_not_listed_summary()
finally:
    UI._read_csv_incremental = real
    UI.APPEND_ONLY_DIR, UI.ERRORS_CSV = saved_dir, saved_err

fails = [e for e in (bad.get('partial_reads') or []) if 'read failed' in e]
check('UI_FAILED_READ_SETS_PARTIAL_TRUE', bad.get('partial') is True, bad.get('partial'))
check('UI_FAILED_READ_IS_NAMED_NOT_SWALLOWED', len(fails) >= 1, bad.get('partial_reads'))
check('UI_FAILED_READ_NAMES_THE_ERROR_CLASS', any('PermissionError' in e for e in fails), fails)
check('UI_FAILED_READ_STILL_RETURNS_OK_TRUE', bad.get('ok') is True, bad.get('ok'))
check('UI_OK_TRUE_AND_PARTIAL_TRUE_COEXIST',
      bad.get('ok') is True and bad.get('partial') is True, (bad.get('ok'), bad.get('partial')))

empty = Path(tempfile.mkdtemp(prefix='uiempty_'))
UI.APPEND_ONLY_DIR = empty
UI.ERRORS_CSV = empty / 'errors.csv'
try:
    none_found = UI._symbol_not_listed_summary()
finally:
    UI.APPEND_ONLY_DIR, UI.ERRORS_CSV = saved_dir, saved_err
check('UI_NO_JOURNAL_IS_PARTIAL_NOT_SILENT',
      none_found.get('partial') is True and any('none found' in e for e in (none_found.get('partial_reads') or [])),
      none_found.get('partial_reads'))

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
