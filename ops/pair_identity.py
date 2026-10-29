#!/usr/bin/env python3
"""Print ONE identity block for the pair: engine and UI, from files and process truth only.

    python ops/pair_identity.py [--port 8031]

Every field names its source. Nothing is inferred silently: a field that cannot be established
prints UNKNOWN and says why, because the whole point is that a reader can tell which code is
answering without asking anyone.
Exit code 0 when the pair is up and consistent, 1 when it is degraded, 2 when it is not running.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

TARGET = 'HL_Live_Copy_Service_Core.py'
ROW = '  %-22s %s'


def utc(ms=None):
    t = time.time() if ms is None else ms / 1000.0
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))


def build_from_path(path):
    """The build id lives in a folder like v33_6c69310 anywhere in the path; take the first
    7-hex tail found walking up from the file's own directory."""
    cur = Path(path)
    for _ in range(6):
        tail = cur.name.rsplit('_', 1)[-1]
        if len(tail) == 7 and all(c in '0123456789abcdef' for c in tail.lower()):
            return tail
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def sha7(path):
    try:
        out = subprocess.run(['git', '-C', str(path), 'rev-parse', '--short=7', 'HEAD'],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or 'UNKNOWN'
    except Exception:
        return 'UNKNOWN'


def listening(port):
    try:
        import psutil
    except Exception:
        return None
    for c in psutil.net_connections(kind='inet'):
        if c.laddr and c.laddr.port == port and c.status == 'LISTEN':
            return c.pid
    return None


def proc(pid):
    try:
        import psutil
        p = psutil.Process(pid)
        return {'pid': pid, 'cmdline': ' '.join(p.cmdline()), 'cwd': p.cwd(),
                'started': utc(p.create_time() * 1000)}
    except Exception:
        return None


def engines():
    try:
        import psutil
    except Exception:
        return []
    out = []
    for p in psutil.process_iter(['pid', 'cmdline']):
        c = p.info['cmdline'] or []
        if len(c) >= 2 and os.path.basename(c[1]) == TARGET:
            out.append(p.info['pid'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8031)
    a = ap.parse_args()

    spec = json.load(open(os.path.expanduser('~/.hermes/state/core_launch_env.json'), encoding='utf-8'))
    audit = Path(spec.get('env', {}).get('HL_LIVE_AUDIT_DIR') or '')
    print('PAIR IDENTITY  %s' % utc())
    print('  audit dir (spec):      %s' % audit)

    # --- engine
    rec = {}
    for name in ('core_start_record.json', 'live_service_state.json'):
        p = audit / name
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding='utf-8-sig'))
                if isinstance(d, dict):
                    rec.update({k: v for k, v in d.items() if k not in rec})
            except Exception:
                pass
    running = engines()
    pid = rec.get('pid') or rec.get('process_id')
    print('  ENGINE')
    print(ROW % ('pids running', '%d %s' % (len(running), running)))
    if pid:
        alive = bool(proc(pid))
        print(ROW % ('pid in state', '%s (%s)' % (pid, 'RUNNING' if alive else 'NOT RUNNING')))
    else:
        print(ROW % ('pid in state', 'UNKNOWN (no pid recorded)'))
    script = rec.get('script') or spec.get('cwd') or ''
    folder = Path(script).parent if script else Path(spec.get('cwd') or '')
    tail = build_from_path(folder)
    print(ROW % ('folder', str(folder)))
    print(ROW % ('build', '%s (inferred from a folder name in the path)' % (tail or 'UNKNOWN')))
    print(ROW % ('started', rec.get('started_at') or 'UNKNOWN'))
    print(ROW % ('audit dir', audit.name))

    # --- ui
    port_pid = listening(a.port)
    print('  UI')
    print(ROW % ('pid on :%d' % a.port, port_pid if port_pid else 'NONE'))
    if port_pid:
        u = proc(port_pid)
        if u:
            ufolder = Path(u['cwd'])
            print(ROW % ('folder', str(ufolder)))
            print(ROW % ('build', sha7(ufolder)))
            print(ROW % ('started', u['started']))
            try:
                with urllib.request.urlopen('http://127.0.0.1:%d/' % a.port, timeout=8) as r:
                    body = r.read().decode('utf-8', 'replace')
                marks = ('partial: older rows not counted', 'exchange figures:', 'as of ')
                print(ROW % ('page', 'http %s, %d bytes, new-build markers %d/3'
                             % (r.status, len(body), sum(m in body for m in marks))))
            except Exception as exc:
                print(ROW % ('page', 'UNREACHABLE (%s)' % type(exc).__name__))

    # --- consistency
    print('  CONSISTENCY')
    same_dir = bool(port_pid) and proc(port_pid) and Path(proc(port_pid)['cwd']).exists()
    eng_sha, ui_sha = (tail or None), (sha7(Path(proc(port_pid)['cwd'])) if port_pid and proc(port_pid) else None)
    if not running and not port_pid:
        print(ROW % ('pair', 'DOWN (neither half is running)'))
        return 2
    if not running:
        print(ROW % ('pair', 'DEGRADED (no engine is running; the UI alone is not the product)'))
        return 1
    if len(running) > 1:
        print(ROW % ('pair', 'DEGRADED (%d engines running)' % len(running)))
        return 1
    if running and not port_pid:
        print(ROW % ('pair', 'DEGRADED (engine up, no UI on :%d)' % a.port))
        return 1
    if eng_sha and ui_sha:
        mb = subprocess.run(['git', '-C', str(Path(proc(port_pid)['cwd'])), 'merge-base', '--is-ancestor', eng_sha, 'HEAD'],
                            capture_output=True, text=True)
        fam = 'YES' if mb.returncode == 0 else 'NO'
        print(ROW % ('engine build in UI', fam))
        if fam == 'NO':
            print(ROW % ('pair', 'UP but the UI does not contain the engine build - rebuild the UI on the engine history'))
            return 1
    print(ROW % ('pair', 'UP and consistent'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
