#!/usr/bin/env python3
"""GAP-5 (disk-full robustness) OFFLINE append-failure check.

The live half of GAP-5 is a real ENOSPC on a bounded VHD (elevated; the J4 spec
forbids filling C:). The offline half is the invariant the whole gap exists for:

    an audit append that fails must fail LOUDLY, and no order may go out whose
    record could not be written.

That is testable with no engine and no admin, by pointing an audit dir at COPIES of
the audit CSVs, denying write+append on one file with icacls, and exercising the
engine's OWN append path (HL_Live_Copy_Service_Core.append_csv) plus its error path
(log_error -> errors.csv). The order-send guard itself is the product's, not
re-implemented here: the Core's sender returns SEND_NOT_ATTEMPTED_AUDIT_WRITE_FAILED
when _begin_pending_send raises (HL_Live_Copy_Service_Core.py L5480-5488); this
script proves the write raises in the first place, which is the precondition of
that guard, and that nothing partial is left behind.

Steps (all on a scratch copy; the input dir is never modified):
  1. baseline append to order_intents.csv                    -> must succeed
  2. deny (WD,AD) on order_intents.csv (icacls)              -> append must RAISE
  3. log_error(context, exc)                                 -> errors.csv gets the record
  4. restore the ACL, append again                           -> must succeed, file parses
Verdict: PASS iff 2 raised, 3 recorded, 4 recovered, and the row counts are exact
(the denied append wrote nothing, no partial line, no duplicate).

Inputs: --audit-dir DIR (copy of an engine state dir with append_only/*.csv; a
directory with the three CSVs directly also works), --core-dir DIR (checkout with
HL_Live_Copy_Service_Core.py), --work-dir DIR (scratch, default a temp dir).
NEVER run this with --audit-dir pointing at the live checkout.

Pass line (last line, exit 0):
  GAP5_RESULT:: PASS append_failed_loudly=yes error_logged=yes recovered=yes rows_exact=yes
FAIL exits 1; INCONCLUSIVE (no icacls / not Windows / no fixture CSV) exits 3.

Offline: no network, no engine, no keys, no orders, no volume is filled.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cert_common as cc  # noqa: E402

TAG = 'GAP5_RESULT'
DEFAULT_CORE_DIR = Path(__file__).resolve().parents[2] / '_archive' / 'hl_stage2'
DEFAULT_AUDIT_DIR = Path(__file__).resolve().parent / 'fixtures' / 'audit_small'
CREATE_NO_WINDOW = 0x08000000


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', CREATE_NO_WINDOW))


def icacls_available():
    try:
        return _run(['icacls', '/?']).returncode in (0, 1)
    except Exception:
        return False


def whoami():
    try:
        out = _run(['whoami']).stdout.strip()
    except Exception:
        out = ''
    return out or os.environ.get('USERNAME') or ''


def deny_write(path, user):
    return _run(['icacls', str(path), '/deny', '%s:(WD,AD)' % user]).returncode == 0


def restore_write(path, user):
    _run(['icacls', str(path), '/remove:d', user])


def decide(appended_before, raised, logged, recovered, rows_ok):
    return bool(appended_before and raised and logged and recovered and rows_ok)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Offline audit-append failure check (GAP-5).')
    ap.add_argument('--audit-dir', default=str(DEFAULT_AUDIT_DIR))
    ap.add_argument('--core-dir', default=str(DEFAULT_CORE_DIR))
    ap.add_argument('--work-dir', default='')
    ap.add_argument('--keep', action='store_true', help='keep the scratch dir for inspection')
    args = ap.parse_args(argv)

    if not icacls_available():
        return cc.emit(TAG, cc.INCONCLUSIVE, 'icacls_unavailable (needs Windows; --help had no exit 0/1)')

    src = Path(args.audit_dir).resolve()
    src_append = src / 'append_only' if (src / 'append_only').is_dir() else src
    if not (src_append / 'order_intents.csv').is_file():
        return cc.emit(TAG, cc.INCONCLUSIVE, 'no_order_intents.csv_in=%s' % src_append)

    work = Path(args.work_dir).resolve() if args.work_dir else Path(tempfile.mkdtemp(prefix='gap5_'))
    scratch = work / 'state'
    if scratch.exists():
        shutil.rmtree(scratch)
    (scratch / 'append_only').mkdir(parents=True, exist_ok=True)
    for name in ('order_intents.csv', 'reconciliation.csv', 'send_attempts.csv', 'errors.csv'):
        if (src_append / name).is_file():
            shutil.copy2(src_append / name, scratch / 'append_only' / name)

    # AUDIT_DIR is read from the environment at import time -> set it BEFORE importing the Core
    os.environ['HL_LIVE_AUDIT_DIR'] = str(scratch)
    core = cc.core_import(args.core_dir)

    intents = core.ORDER_INTENTS_CSV
    errors = core.ERRORS_CSV
    core.ensure_csv_header(intents, core.ORDER_INTENT_FIELDS)

    def rows(path):
        return cc.load_rows(path)

    n0 = len(rows(intents))
    n_err0 = len(rows(errors))
    try:
        core.append_csv(intents, core.ORDER_INTENT_FIELDS, {'intent_id': 'k2-baseline', 'coin': 'BTC', 'notes': 'gap5 baseline'})
        appended_before = len(rows(intents)) == n0 + 1
        print('1. baseline append              -> rows %d -> %d  %s' % (n0, len(rows(intents)), 'ok' if appended_before else 'FAILED'))

        user = whoami()
        if not user or not deny_write(intents, user):
            return cc.emit(TAG, cc.INCONCLUSIVE, 'icacls_deny_failed user=%r' % user)
        raised = False
        exc = None
        try:
            core.append_csv(intents, core.ORDER_INTENT_FIELDS, {'intent_id': 'k2-denied', 'coin': 'ETH', 'notes': 'must not land'})
        except OSError as e:
            raised = True
            exc = e
        n_after_deny = len(rows(intents))
        print('2. denied append (WD,AD)        -> raised=%s %r  rows=%d' % (raised, exc, n_after_deny))
        if exc is None:
            restore_write(intents, user)
            return cc.emit(TAG, cc.FAIL, 'append_succeeded_while_denied rows=%d' % n_after_deny)

        core.log_error('k2_disk_guard', exc)
        logged = len(rows(errors)) == n_err0 + 1 and any(
            'k2_disk_guard' in (r.get('context') or '') for r in rows(errors))
        print('3. log_error -> errors.csv      -> rows %d -> %d  recorded=%s' % (n_err0, len(rows(errors)), logged))

        restore_write(intents, user)
        core.append_csv(intents, core.ORDER_INTENT_FIELDS, {'intent_id': 'k2-after-restore', 'coin': 'SOL', 'notes': 'gap5 recovered'})
        recovered = len(rows(intents)) >= n_after_deny + 1
        parsed = rows(intents)
        rows_ok = (len(parsed) == n0 + 2 and {r.get('intent_id') for r in parsed} >= {'k2-baseline', 'k2-after-restore'}
                   and all(len(r) >= len(core.ORDER_INTENT_FIELDS) - 2 for r in parsed))
        print('4. restored append              -> rows=%d parseable=%s rows_exact=%s' % (len(parsed), bool(parsed), rows_ok))

        try:
            free = shutil.disk_usage(str(scratch)).free / (1024 ** 3)
            print('GAP5_GAP:: scratch_volume_free_gb=%.1f rotating=%s rotate_bytes=%d (live half still needs the '
                  'elevated bounded-VHD ENOSPC run)' % (free, sorted(core.AUDIT_ROTATING_NAMES), core.AUDIT_ROTATE_BYTES))
        except Exception:
            pass

        ok = decide(appended_before, raised, logged, recovered, rows_ok)
        detail = 'append_failed_loudly=%s error_logged=%s recovered=%s rows_exact=%s scratch=%s' % (
            'yes' if raised else 'no', 'yes' if logged else 'no', 'yes' if recovered else 'no',
            'yes' if rows_ok else 'no', scratch)
        return cc.emit(TAG, cc.PASS if ok else cc.FAIL, detail)
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    raise SystemExit(main())
