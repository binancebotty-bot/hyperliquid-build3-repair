#!/usr/bin/env python3
'''OS oracle: python process command lines (read-only, no kills) + engine presence.'''
import json, subprocess, sys

PS = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' } | "
      "Select-Object ProcessId,Name,CommandLine | ConvertTo-Json -Compress")


def main():
    out = {}
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', PS],
                           capture_output=True, text=True, timeout=90)
        raw = (r.stdout or '').strip()
        data = json.loads(raw) if raw else []
        if isinstance(data, dict):
            data = [data]
        out['python_processes'] = [
            {'pid': d.get('ProcessId'), 'name': d.get('Name'), 'cmdline': d.get('CommandLine')}
            for d in data
        ]
    except Exception as e:
        out['error'] = '%s: %r' % (type(e).__name__, e)
    procs = out.get('python_processes') or []
    out['ui_on_8031'] = [p for p in procs if p.get('cmdline') and 'HL_Copy_App_SSOT' in p['cmdline']]
    out['engine_processes'] = [p for p in procs if p.get('cmdline') and 'HL_Live_Copy' in p['cmdline']]
    out['launcher_named_processes'] = [p for p in procs if p.get('cmdline') and
                                      ('launch' in p['cmdline'].lower() or 'release' in p['cmdline'].lower())]
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
