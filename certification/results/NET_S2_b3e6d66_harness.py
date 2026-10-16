#!/usr/bin/env python3
"""Reproduce the bounded local network checks and guard the live-evidence boundary.

This harness intentionally does not contact Hyperliquid or access credentials. The
existing test_core_network_and_global_controls.py stubs requests and the exchange,
so none of its green assertions is treated as exchange-side independent-oracle proof.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULT = Path(__file__).with_name('NET_S2_b3e6d66.json')
BASE = ROOT / '_archive' / 'hl_stage2' / 'test_core_network_and_global_controls.py'


def main() -> int:
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    rows = data.get('rows', [])
    expected = {'TN-T6', 'TN-T7', 'TN-T8', 'TN-T9', 'TN-T10'}
    assert {r['id'] for r in rows} == expected, 'row coverage mismatch'
    assert all(r['result'] == 'NOT_TESTED' for r in rows), 'local mocks must never certify live network claims'
    proc = subprocess.run([sys.executable, str(BASE)], cwd=BASE.parent, capture_output=True, text=True, timeout=300)
    print(proc.stdout, end='')
    if proc.returncode:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode
    final = [line for line in proc.stdout.splitlines() if line.startswith('TOTAL=')]
    assert final == ['TOTAL=62 FAILED=0'], f'unexpected test summary: {final}'
    print('CERT_BOUNDARY=PASS rows=5 statuses=NOT_TESTED live_oracle=ABSENT')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
