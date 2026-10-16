#!/usr/bin/env python3
"""Evidence harness for F25-X05..X08. No deployment or exchange actions."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IDS = ('F25-X05', 'F25-X06', 'F25-X07', 'F25-X08')
CHECKS = ('execution_proof', 'second start attempt', 'crash mid-transition', 'stale lock/PID', 'config from previous version')


def main():
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    rows = []
    for row_id in IDS:
        checks = [{'check': name, 'status': 'STILL_NOT_TESTED',
                   'reason': 'Requires an authorized deployment transition and contemporaneous process/port/exchange observation; not run by this read-only certification.'}
                  for name in CHECKS]
        rows.append({'id': row_id, 'status': 'STILL_NOT_TESTED', 'checks': checks,
                     'negative_tests_non_vacuous': False,
                     'reason': 'No deployment transition was initiated; therefore none of the negative cases is claimed as exercised.'})
    print(json.dumps({'tested_commit': commit, 'rows': rows}, indent=2))

if __name__ == '__main__':
    main()
