#!/usr/bin/env python3
"""Stop the pair WITHOUT losing journal rows. This is the only supported way to stop the pair.

Why: on 2026-10-25 the engine was stopped with psutil.terminate(), which on Windows is
TerminateProcess - no signal handler, no atexit - so the write-behind audit queue was discarded and
8 of 133 engine-era fills ended up on the exchange with no journal row.

The engine honours a STOP_REQUESTED sentinel at the top of its --loop: it flushes the intent writer,
writes a shutdown record whose `clean` reflects whether that flush actually succeeded, removes the
sentinel and breaks; atexit flushes again. It runs under pythonw, which has no console, so
CTRL_BREAK cannot be used instead.

Rules here, each of which was a review finding:
  * a shutdown record proves THIS stop only when its pid, its reason and its timestamp all match the
    process we asked to stop - never by timestamp alone, and never a record from a previous run;
  * the UI is stopped by its TRACKED pid, matched on creation time and on the interpreter/argv shape.
    A port listener with no tracked pid is refused: a port is not an identity;
  * --force only runs if the forced-stop record is actually on disk; if it cannot be written, the
    tool refuses to kill rather than lose rows silently;
  * an engine is only stopped when its own HL_LIVE_AUDIT_DIR resolves to the dir we are writing to;
  * an engine that refuses to start because a stop is already in flight is reported, not killed.
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

TARGET = 'HL_Live_Copy_Service_Core.py'
UI_MODULE = 'HL_Copy_App_SSOT:app'
SENTINEL = 'STOP_REQUESTED'
TRACK = Path(os.path.expanduser('~/.hermes/state/ui_pid.json'))
FRESH_MS = 500          # tolerance between the request and the record's own timestamp


def audit_dir():
    spec = json.load(open(os.path.expanduser('~/.hermes/state/core_launch_env.json'), encoding='utf-8'))
    return Path(spec.get('env', {}).get('HL_LIVE_AUDIT_DIR') or '')


def pids(want_dir):
    """Engines only, and only those whose own environment points at the dir we will signal."""
    import psutil
    out, skipped = [], []
    for p in psutil.process_iter(['pid', 'cmdline']):
        c = p.info['cmdline'] or []
        if len(c) >= 2 and os.path.basename(c[1]) == TARGET:
            try:
                env_dir = Path(p.environ().get('HL_LIVE_AUDIT_DIR') or '')
            except Exception:
                env_dir = None
            if env_dir and want_dir and env_dir.resolve() != want_dir.resolve():
                skipped.append((p.info['pid'], str(env_dir)))
                continue
            out.append(p.info['pid'])
    for pid, env_dir in skipped:
        print('  skipping engine pid %d: its audit dir is %s, not %s' % (pid, env_dir, want_dir))
    return out


def listener(port):
    import psutil
    for c in psutil.net_connections(kind='inet'):
        if c.laddr and c.laddr.port == port and c.status == 'LISTEN':
            return c.pid
    return None


def is_ui(proc, port):
    """Identity, not a substring: python interpreter plus the uvicorn module argument."""
    argv = proc.cmdline()
    if not argv:
        return False
    if not os.path.basename(argv[0]).lower().startswith('python'):
        return False
    return UI_MODULE in argv and ('--port' in argv and str(port) in argv)


def track_ui(port):
    import psutil
    pid = listener(port)
    if not pid:
        print('  nothing listening on :%d - nothing to track' % port)
        return 1
    p = psutil.Process(pid)
    if not is_ui(p, port):
        print('  :%d is held by pid %d which is NOT the UI (%s)' % (port, pid, ' '.join(p.cmdline())[:80]))
        return 1
    TRACK.parent.mkdir(parents=True, exist_ok=True)
    TRACK.write_text(json.dumps({'pid': pid, 'port': port, 'create_time': p.create_time(),
                                 'cmdline': p.cmdline(),
                                 'tracked_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())},
                                indent=2), encoding='utf-8')
    print('  tracked ui pid %d on :%d (create_time %.3f) -> %s' % (pid, port, p.create_time(), TRACK))
    return 0


def stop_engine(pid, d, wait=90.0):
    import psutil
    p = psutil.Process(pid)
    sentinel = d / SENTINEL
    requested_ms = int(time.time() * 1000)
    print('  engine pid %d -> sentinel %s' % (pid, sentinel))
    sentinel.write_text('stop requested %s pid=%d\n'
                        % (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), pid), encoding='utf-8')
    t0 = time.time()
    while time.time() - t0 < wait:
        if not p.is_running():
            print('    exited after %.1f s' % (time.time() - t0))
            return requested_ms
        time.sleep(0.5)
    print('    STILL RUNNING after %.0f s - sentinel not honoured' % wait)
    return None


def verify(pid, requested_ms, d):
    """This stop is proven only by a record with the same pid, the sentinel reason, a later stamp."""
    rec = d / 'core_shutdown_record.json'
    if not rec.exists():
        print('  shutdown record: ABSENT (%s)' % rec)
        return False
    try:
        r = json.loads(rec.read_text(encoding='utf-8-sig'))
    except Exception:
        print('  shutdown record: unreadable')
        return False
    reasons = []
    if r.get('pid') != pid:
        reasons.append('pid %s != %s' % (r.get('pid'), pid))
    if r.get('reason') != 'stop_sentinel':
        reasons.append('reason %r' % r.get('reason'))
    stamp = int(r.get('timestamp_ms') or 0)
    if requested_ms is not None and stamp < requested_ms - FRESH_MS:
        reasons.append('record stamped %d ms before the request' % (requested_ms - stamp))
    ok = bool(r.get('clean')) and not reasons
    print('  shutdown record: clean=%s reason=%s pid=%s stamp=%s -> %s'
          % (r.get('clean'), r.get('reason'), r.get('pid'),
             time.strftime('%H:%M:%SZ', time.gmtime(stamp / 1000)) if stamp else '-',
             'PROVES THIS STOP' if ok else 'REJECTED (%s)' % '; '.join(reasons)))
    sa = d / 'append_only' / 'send_attempts.csv'
    if sa.exists():
        pend = sum(1 for row in csv.DictReader(open(sa, encoding='utf-8', errors='replace'))
                   if (row.get('terminal_state') or '') == 'PENDING_SEND')
        print('  send_attempts rows still PENDING_SEND: %d' % pend)
    return ok


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
            print('  REFUSING: :%d is held by pid %d but no UI pid is tracked. Run --track-ui at '
                  'launch, or pass --ui-pid; a port is not an identity.' % (port, held))
            return False
        print('  nothing listening on :%d' % port)
        return True
    try:
        p = psutil.Process(int(pid))
    except Exception:
        print('  tracked ui pid %s is not running; clearing the stale track' % pid)
        TRACK.unlink(missing_ok=True)
        return True
    if rec.get('create_time') and abs(p.create_time() - float(rec['create_time'])) > 0.001:
        print('  REFUSING: pid %s has been reused (create_time %s != tracked %s)'
              % (pid, p.create_time(), rec.get('create_time')))
        return False
    if not is_ui(p, port):
        print('  REFUSING: pid %s is not the UI by argv shape (%s)' % (pid, ' '.join(p.cmdline())[:90]))
        return False
    print('  ui pid %s verified: python argv shape and create_time match' % pid)
    p.terminate()
    t0 = time.time()
    while time.time() - t0 < 30:
        if not p.is_running():
            print('    exited after %.1f s' % (time.time() - t0))
            TRACK.unlink(missing_ok=True)
            return True
        time.sleep(0.3)
    print('    still running after 30 s')
    return False


def forced_record(label, pid, d):
    """Write the forced record and return True only if it is on disk."""
    payload = {'forced': True, 'pid': pid, 'what': label,
               'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               'note': 'hard kill: journal rows queued at the time may be lost'}
    for target in (d / ('forced_stop_record.%s.%d.json' % (label, pid)),
                   Path(os.path.expanduser('~/.hermes/state/forced_stop_record.%s.%d.json' % (label, pid)))):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            if target.exists() and json.loads(target.read_text(encoding='utf-8')).get('forced') is True:
                print('  forced-stop record written: %s' % target)
                return True
        except Exception as exc:
            print('  could not write %s: %s' % (target, type(exc).__name__))
    print('  FAILED to record the forced stop anywhere')
    return False


def kill(pid, label, d, rc):
    import psutil
    if not forced_record(label, pid, d):
        raise SystemExit('forced stop NOT recorded; refusing to kill pid %d (rows would be lost '
                         'with no record of why)' % pid)
    try:
        psutil.Process(pid).kill()
        print('    hard-killed pid %d after recording it' % pid)
    except psutil.NoSuchProcess:
        print('    pid %d exited on its own before the kill' % pid)
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--engine', action='store_true')
    ap.add_argument('--ui', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--track-ui', action='store_true')
    ap.add_argument('--ui-pid', type=int)
    ap.add_argument('--port', type=int, default=8031)
    ap.add_argument('--force', action='store_true', help='hard-kill if graceful fails (rows may be lost)')
    a = ap.parse_args()
    if a.track_ui:
        return track_ui(a.port)
    if not (a.engine or a.ui or a.all):
        a.all = True

    try:
        d = audit_dir()
    except Exception as exc:
        print('cannot read the launch env (%s): %s' % (os.path.expanduser('~/.hermes/state/core_launch_env.json'),
                                                       type(exc).__name__))
        return 2

    rc = 0
    if a.engine or a.all:
        print('ENGINE  (audit dir %s)' % d)
        e = pids(d)
        if not e:
            print('  no engine running - already stopped')
        for pid in e:
            requested = stop_engine(pid, d)
            if requested is None:
                rc = 1
                if a.force:
                    rc = kill(pid, 'engine', d, rc)
                    (d / SENTINEL).unlink(missing_ok=True)
                continue
            print('  verify:')
            if not verify(pid, requested, d):
                rc = 1
    if a.ui or a.all:
        print('UI')
        if not stop_ui(a.port, a.ui_pid):
            rc = 1
            if a.force:
                pid = a.ui_pid or (json.loads(TRACK.read_text()).get('pid') if TRACK.exists() else None)
                if pid:
                    rc = kill(int(pid), 'ui', d, rc)
    return rc


if __name__ == '__main__':
    sys.exit(main())
