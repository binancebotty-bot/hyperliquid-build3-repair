#!/usr/bin/env python3
"""The stop tool's own safety rules, each of which was a review finding.

A shutdown record proves THIS stop only when its pid, reason and timestamp all match; the UI is
stopped only by a tracked pid whose creation time and argv shape agree; --force refuses to kill when
it cannot record the kill; an already-stopped pair is not an error.
"""
import importlib.util
import json
import os
import sys
import tempfile
import time
import types
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
rec = tmp / 'core_shutdown_record.json'


def write_rec(clean=True, reason='stop_sentinel', pid=4242, ms=None):
    rec.write_text(json.dumps({'clean': clean, 'reason': reason, 'pid': pid,
                               'timestamp_ms': ms if ms is not None else int(time.time() * 1000)}),
                   encoding='utf-8')


now_ms = int(time.time() * 1000)

write_rec(ms=now_ms - 600_000)                       # a record ten minutes before the request
check('RECORD_OLDER_THAN_THE_REQUEST_IS_REJECTED', SP.verify(4242, now_ms, tmp) is False)

write_rec()                                          # fresh, matching pid and reason
check('MATCHING_FRESH_RECORD_PROVES_THE_STOP', SP.verify(4242, now_ms, tmp) is True)

write_rec(pid=999)                                   # fresh, but a different process
check('RECORD_FOR_A_DIFFERENT_PID_IS_REJECTED', SP.verify(4242, now_ms, tmp) is False)

write_rec(reason='signal_15')                        # fresh and same pid, but not our sentinel
check('RECORD_WITH_A_DIFFERENT_REASON_IS_REJECTED', SP.verify(4242, now_ms, tmp) is False)

write_rec(clean=False)                               # fresh, matching, but unclean
check('UNCLEAN_RECORD_IS_REJECTED', SP.verify(4242, now_ms, tmp) is False)

# --force must refuse to kill when it cannot record why
_real_forced = SP.forced_record
SP.forced_record = lambda label, pid, d: False
try:
    SP.kill(4242, 'engine', tmp, 1)
    refused = False
except SystemExit as exc:
    refused = 'refusing to kill' in str(exc)
check('FORCE_REFUSES_TO_KILL_WITHOUT_A_RECORD', refused)

# and it does record when it can
SP.forced_record = _real_forced
ok_forced = SP.forced_record('engine', 4242, tmp)
fr = list(tmp.glob('forced_stop_record.engine.4242.json'))
check('FORCED_STOP_IS_RECORDED_WITH_LABEL_AND_PID', ok_forced and len(fr) == 1, [p.name for p in tmp.glob('forced*')])

# UI identity
SP.TRACK = tmp / 'ui_pid.json'
SP.listener = lambda port: 31337
check('UI_BY_PORT_ALONE_IS_REFUSED', SP.stop_ui(8031) is False)

SP.listener = lambda port: None
check('UI_ABSENT_IS_NOT_AN_ERROR', SP.stop_ui(8031) is True)


class FakeProc:
    def __init__(self, argv, ct=1000.0):
        self._argv, self._ct = argv, ct

    def cmdline(self):
        return self._argv

    def create_time(self):
        return self._ct


# a tracked pid whose argv is not python+uvicorn must be refused
try:
    import psutil
    real = psutil.Process
    SP.TRACK.write_text(json.dumps({'pid': 4242, 'port': 8031, 'create_time': 1000.0}), encoding='utf-8')
    psutil.Process = lambda pid: FakeProc(['C:/other/editor.exe', 'HL_Copy_App_SSOT:app', '--port', '8031'])
    check('UI_WITH_WRONG_ARGV_SHAPE_IS_REFUSED', SP.stop_ui(8031) is False)
    # correct shape but reused pid (different create_time) must be refused
    psutil.Process = lambda pid: FakeProc(['C:/py/python.exe', '-m', 'uvicorn', 'HL_Copy_App_SSOT:app',
                                           '--port', '8031'], ct=2000.0)
    check('UI_WITH_REUSED_PID_IS_REFUSED', SP.stop_ui(8031) is False)
    psutil.Process = real
finally:
    SP.TRACK.unlink(missing_ok=True)

# an already-stopped pair is success, not failure
SP.audit_dir = lambda: tmp
SP.pids = lambda d: []
SP.stop_ui = lambda port, pid=None: True
sys.argv = ['stop_pair.py', '--all']
check('ALREADY_STOPPED_IS_NOT_AN_ERROR', SP.main() == 0)

failed = [n for n, ok in results if not ok]
print('TOTAL=%d FAILED=%d' % (len(results), len(failed)))
sys.exit(1 if failed else 0)
