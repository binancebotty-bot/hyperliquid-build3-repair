#!/usr/bin/env python3
"""Stop the pair WITHOUT losing journal rows. This is the only supported way to stop the pair.

Why: on 2026-10-25 the engine was stopped with psutil.terminate(), which on Windows is
TerminateProcess - no signal handler, no atexit - so the write-behind audit queue was discarded.
8 of 133 engine-era fills ended up with an exchange fill and no journal row.

The engine honours a STOP_REQUESTED sentinel at the top of its --loop: it flushes the intent
writer, writes a clean shutdown record, removes the sentinel and breaks; atexit drains the rest.
It runs under pythonw, which has no console, so CTRL_BREAK cannot be used instead.

Rules this tool enforces, because each one was a defect found in review:
  * a clean shutdown record only counts if it is NEWER than the stop request. An old record from a
    previous run must never be read as proof that this stop was clean.
  * the UI is stopped by its TRACKED PID, verified against its command line. Stopping whatever
    happens to hold port 8031 could stop someone else's process.
  * --force writes a forced_stop_record.json saying rows may have been lost, then hard-kills.
  * the engine itself quarantines a stale STOP_REQUESTED at startup, so a crashed stop cannot kill
    the next run.

    python ops/stop_pair.py --track-ui          # record the live UI pid (launcher does this)
    python ops/stop_pair.py --all               # graceful engine + tracked UI
    python ops/stop_pair.py --engine --force     # last resort, recorded as forced
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

TARGET = 'HL_Live_Copy_Service_Core.py'
UI_MARK = 'HL_Copy_App_SSOT:app'
SENTINEL = 'STOP_REQUESTED'
TRACK = Path(os.path.expanduser('~/.hermes/state/ui_pid.json'))


def pids():
    import psutil
    out = []
    for p in psutil.process_iter(['pid', 'cmdline']):
        c = p.info['cmdline'] or []
        if len(c) >= 2 and os.path.basename(c[1]) == TARGET:
            out.append(p.info['pid'])
    return out


def listener(port):
    import psutil
    for c in psutil.net_connections(kind='inet'):
        if c.laddr and c.laddr.port == port and c.status == 'LISTEN':
            return c.pid
    return None


def audit_dir():
    spec = json.load(open(os.path.expanduser('~/.hermes/state/core_launch_env.json'), encoding='utf-8'))
    return Path(spec.get('env', {}).get('HL_LIVE_AUDIT_DIR') or '')


def track_ui(port):
    import psutil
    pid = listener(port)
    if not pid:
        print('  nothing listening on :%d - nothing to track' % port)
        return 1
    cmd = ' '.join(psutil.Process(pid).cmdline())
    if UI_MARK not in cmd:
        print('  :%d is held by pid %d which is NOT the UI (%s)' % (port, pid, cmd[:80]))
        return 1
    TRACK.parent.mkdir(parents=True, exist_ok=True)
    TRACK.write_text(json.dumps({'pid': pid, 'port': port, 'cmdline': cmd,
                                 'tracked_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
                                indent=2), encoding='utf-8')
    print('  tracked ui pid %d on :%d -> %s' % (pid, port, TRACK))
    return 0


def stop_engine(pid, wait=90.0):
    import psutil
    p = psutil.Process(pid)
    d = audit_dir()
    sentinel = d / SENTINEL
    requested_at = time.time()
    print('  engine pid %d -> sentinel %s' % (pid, sentinel))
    sentinel.write_text('stop requested %s\n' % time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        encoding='utf-8')
    t0 = requested_at
    while time.time() - t0 < wait:
        if not p.is_running():
            print('    exited after %.1f s' % (time.time() - t0))
            return requested_at
        time.sleep(0.5)
    print('    STILL RUNNING after %.0f s - sentinel not honoured' % wait)
    return None


def verify(requested_at):
    """A clean record counts only if it was written AFTER the request."""
    d = audit_dir()
    rec = d / 'core_shutdown_record.json'
    if not rec.exists():
        print('  shutdown record: ABSENT (%s) - atexit never ran' % rec)
        return False
    age_of_record = rec.stat().st_mtime
    fresh = requested_at is not None and age_of_record >= requested_at - 1.0
    try:
        r = json.loads(rec.read_text(encoding='utf-8-sig'))
    except Exception:
        r = {}
    print('  shutdown record: clean=%s reason=%s written=%s (%s)'
          % (r.get('clean'), r.get('reason'),
             time.strftime('%H:%M:%SZ', time.gmtime(age_of_record)),
             'AFTER the request' if fresh else 'STALE - predates this stop'))
    sa = d / 'append_only' / 'send_attempts.csv'
    if sa.exists():
        pend = sum(1 for row in csv.DictReader(open(sa, encoding='utf-8', errors='replace'))
                   if (row.get('terminal_state') or '') == 'PENDING_SEND')
        print('  send_attempts rows still PENDING_SEND: %d' % pend)
    return bool(r.get('clean')) and fresh


def stop_ui(port, explicit_pid=None):
    import psutil
    rec = {}
    if TRACK.exists():
        try:
            rec = json.loads(TRACK.read_text(encoding='utf-8'))
        except Exception:
            rec = {}
    pid = explicit_pid or rec.get('pid')
    if not pid:
        held = listener(port)
        if held:
            print('  REFUSING: :%d is held by pid %d but no UI pid is tracked. Run --track-ui at launch, '
                  'or pass --ui-pid; port alone is not proof of identity.' % (port, held))
            return False
        print('  nothing listening on :%d' % port)
        return True
    try:
        p = psutil.Process(int(pid))
    except Exception:
        print('  tracked ui pid %s is not running' % pid)
        return True
    cmd = ' '.join(p.cmdline())
    if UI_MARK not in cmd or ('--port' in cmd and str(port) not in cmd):
        print('  REFUSING: pid %s does not look like the UI (%s)' % (pid, cmd[:90]))
        return False
    print('  ui pid %s verified by command line' % pid)
    p.terminate()
    t0 = time.time()
    while time.time() - t0 < 30:
        if not p.is_running():
            print('    exited after %.1f s' % (time.time() - t0))
            if TRACK.exists():
                TRACK.unlink()
            return True
        time.sleep(0.3)
    print('    still running after 30 s')
    return False


def forced_record(pid, label):
    d = audit_dir()
    try:
        (d / 'forced_stop_record.json').write_text(json.dumps({
            'forced': True, 'pid': pid, 'what': label,
            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'note': 'hard kill: journal rows queued at the time may be lost'}, indent=2), encoding='utf-8')
        print('  wrote forced_stop_record.json (rows may be lost)')
    except Exception as exc:
        print('  could not write the forced record: %s' % type(exc).__name__)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--engine', action='store_true')
    ap.add_argument('--ui', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--track-ui', action='store_true')
    ap.add_argument('--ui-pid', type=int)
    ap.add_argument('--port', type=int, default=8031)
    ap.add_argument('--force', action='store_true', help='hard-kill if graceful fails (may lose rows)')
    a = ap.parse_args()

    if a.track_ui:
        return track_ui(a.port)
    if not (a.engine or a.ui or a.all):
        a.all = True

    rc = 0
    if a.engine or a.all:
        print('ENGINE')
        e = pids()
        requested_at = None
        if not e:
            print('  none running')
        for pid in e:
            requested_at = stop_engine(pid)
            if requested_at is None:
                rc = 1
                if a.force:
                    import psutil
                    forced_record(pid, 'engine')
                    print('    --force: hard kill pid %d' % pid)
                    psutil.Process(pid).kill()
                    try:
                        (audit_dir() / SENTINEL).unlink()
                    except OSError:
                        pass
        print('  verify:')
        if not verify(requested_at):
            rc = 1
    if a.ui or a.all:
        print('UI')
        if not stop_ui(a.port, a.ui_pid):
            rc = 1
            if a.force:
                import psutil
                pid = a.ui_pid or (json.loads(TRACK.read_text()).get('pid') if TRACK.exists() else None)
                if pid:
                    forced_record(pid, 'ui')
                    psutil.Process(int(pid)).kill()
    return rc


if __name__ == '__main__':
    sys.exit(main())
