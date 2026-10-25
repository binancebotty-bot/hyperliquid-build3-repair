#!/usr/bin/env python3
"""Stop the pair WITHOUT losing journal rows.

Why this exists: on 2026-10-25 the engine was stopped with psutil.terminate(), which on Windows is
TerminateProcess - it runs neither the engine's signal handler nor its atexit hooks, so the
write-behind audit queue was discarded. Measured cost: 8 of 133 engine-era fills had an exchange
fill and no journal row, i.e. positions the engine had opened and did not know it had opened.

The engine could not be signalled into a clean exit either: it runs under pythonw, which has no
console, so CTRL_BREAK_EVENT cannot reach it. So the engine now honours a sentinel file at the top
of its cycle loop (Core, --loop): it flushes the intent writer, writes a clean shutdown record,
removes the sentinel and breaks. Atexit then drains the status workers.

    python ops/stop_pair.py --engine      # sentinel, wait, verify the clean record
    python ops/stop_pair.py --ui          # UI by exact PID (uvicorn exits on terminate)
    python ops/stop_pair.py --all --force # last resort: hard kill, says so, may lose rows
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

TARGET = 'HL_Live_Copy_Service_Core.py'
SENTINEL = 'STOP_REQUESTED'


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


def stop_engine(pid, wait=90.0):
    import psutil
    p = psutil.Process(pid)
    d = audit_dir()
    sentinel = d / SENTINEL
    print('  engine pid %d -> sentinel %s' % (pid, sentinel))
    sentinel.write_text('stop requested %s\n' % time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        encoding='utf-8')
    t0 = time.time()
    while time.time() - t0 < wait:
        if not p.is_running():
            print('    exited cleanly after %.1f s' % (time.time() - t0))
            return True
        time.sleep(0.5)
    print('    STILL RUNNING after %.0f s - sentinel not honoured (does this build have the stop hook?)' % wait)
    return False


def stop_ui(port, wait=30.0):
    import psutil
    pid = listener(port)
    if not pid:
        print('  nothing listening on :%d' % port)
        return True
    p = psutil.Process(pid)
    print('  ui pid %d on :%d' % (pid, port))
    p.terminate()
    t0 = time.time()
    while time.time() - t0 < wait:
        if not p.is_running():
            print('    exited after %.1f s' % (time.time() - t0))
            return True
        time.sleep(0.3)
    print('    still running after %.0f s' % wait)
    return False


def verify():
    d = audit_dir()
    rec = d / 'core_shutdown_record.json'
    ok = True
    if rec.exists():
        try:
            r = json.loads(rec.read_text(encoding='utf-8-sig'))
            print('  shutdown record: clean=%s reason=%s at=%s'
                  % (r.get('clean'), r.get('reason'), str(r.get('at'))[:19]))
            ok = bool(r.get('clean'))
        except Exception as exc:
            print('  shutdown record unreadable: %s' % type(exc).__name__)
            ok = False
    else:
        print('  shutdown record: ABSENT (%s) - atexit never ran' % rec)
        ok = False
    sa = d / 'append_only' / 'send_attempts.csv'
    if sa.exists():
        pend = sum(1 for row in csv.DictReader(open(sa, encoding='utf-8', errors='replace'))
                   if (row.get('terminal_state') or '') == 'PENDING_SEND')
        print('  send_attempts rows still PENDING_SEND: %d' % pend)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--engine', action='store_true')
    ap.add_argument('--ui', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--port', type=int, default=8031)
    ap.add_argument('--force', action='store_true', help='hard-kill if graceful fails (may lose journal rows)')
    a = ap.parse_args()
    if not (a.engine or a.ui or a.all):
        a.all = True

    rc = 0
    if a.engine or a.all:
        print('ENGINE')
        e = pids()
        if not e:
            print('  none running')
        for pid in e:
            if not stop_engine(pid):
                rc = 1
                if a.force:
                    import psutil
                    print('    --force: hard kill pid %d (queued journal rows may be lost)' % pid)
                    psutil.Process(pid).kill()
                    try:
                        (audit_dir() / SENTINEL).unlink()
                    except OSError:
                        pass
        print('  verify:')
        if not verify():
            rc = 1
    if a.ui or a.all:
        print('UI')
        if not stop_ui(a.port):
            rc = 1
            if a.force:
                import psutil
                pid = listener(a.port)
                if pid:
                    psutil.Process(pid).kill()
    return rc


if __name__ == '__main__':
    sys.exit(main())
