#!/usr/bin/env python3
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
RESULT = Path(__file__).with_name('NET_S3_b3e6d66.json')
BASE = ROOT / '_archive' / 'hl_stage2' / 'test_core_network_and_global_controls.py'
def main() -> int:
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    expected = {'TN-T11', 'TN-T12', 'TN-T13', 'TN-T14', 'TN-T15'}
    assert {r['id'] for r in data['rows']} == expected
    assert all(r['result'] == 'NOT_TESTED' and all(c['result'] == 'NOT_TESTED' for c in r['checks']) for r in data['rows'])
    proc = subprocess.run([sys.executable, str(BASE)], cwd=BASE.parent, capture_output=True, text=True, timeout=300)
    print(proc.stdout, end='')
    if proc.returncode:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode
    assert [line for line in proc.stdout.splitlines() if line.startswith('TOTAL=')] == ['TOTAL=62 FAILED=0']
    print('CERT_BOUNDARY=PASS rows=5 statuses=NOT_TESTED live_oracle=ABSENT')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
