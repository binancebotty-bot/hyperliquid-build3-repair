#!/usr/bin/env python3
"""The stop tool's own safety rules, each of which was a review finding.

A clean shutdown record only counts if it is NEWER than the stop request; a UI is stopped only when
its pid is tracked and its command line proves it; --force leaves a record saying rows may be lost.
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('stop_pair', HERE / 'stop_pair.py')
SP = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SP)

results = []


def check(name, ok, detail=''):
    results.append((name, bool(ok)))
    print('RESULT::%s_%s%s' % (name, 'PASS' if ok else 'FAIL', (' | ' + str(detail)[:170]) if not ok else ''))


tmp = Path(tempfile.mkdtemp(prefix='stoppair_'))
SP.audit_dir = lambda: tmp                      # point the tool at a scratch dir

# a clean record written BEFORE the request must never be accepted
rec = tmp / 'core_shutdown_record.json'
rec.write_text(json.dumps({'clean': True, 'reason': 'process_exit'}), encoding='utf-8')
old = time.time() - 600
os.utime(rec, (old, old))
requested_at = time.time()
check('STALE_CLEAN_RECORD_IS_REJECTED', SP.verify(requested_at) is False)

# a clean record written AFTER the request is accepted
rec.write_text(json.dumps({'clean': True, 'reason': 'stop_sentinel'}), encoding='utf-8')
os.utime(rec, None)
check('FRESH_CLEAN_RECORD_IS_ACCEPTED', SP.verify(requested_at) is True)

# an unclean record is refused even when fresh
rec.write_text(json.dumps({'clean': False, 'reason': 'signal_15'}), encoding='utf-8')
os.utime(rec, None)
check('FRESH_UNCLEAN_RECORD_IS_REFUSED', SP.verify(requested_at) is False)

# --force leaves a record that says rows may be lost
SP.forced_record(4242, 'engine')
fr = tmp / 'forced_stop_record.json'
ok_forced = fr.exists() and json.loads(fr.read_text(encoding='utf-8')).get('forced') is True \
    and 'lost' in json.loads(fr.read_text(encoding='utf-8')).get('note', '')
check('FORCED_STOP_IS_RECORDED', ok_forced)

# a port listener with no tracked pid must be refused, never stopped by port alone
SP.TRACK = tmp / 'ui_pid.json'
SP.listener = lambda port: 31337
check('UI_BY_PORT_ALONE_IS_REFUSED', SP.stop_ui(8031) is False)

# nothing on the port and nothing tracked is the benign case
SP.listener = lambda port: None
check('UI_ABSENT_IS_NOT_AN_ERROR', SP.stop_ui(8031) is True)

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
