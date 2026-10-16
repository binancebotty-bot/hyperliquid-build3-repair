#!/usr/bin/env python3
"""Read-only evidence harness for TN-F20, TN-F25, and INC-18.
No deployment transition, process termination, or exchange action is performed.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IDS = ('TN-F20', 'TN-F25', 'INC-18')


def main():
    commit = subprocess.check_output(
        ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True
    ).strip()
    matrix = json.loads(subprocess.check_output(
        ['git', '-C', str(ROOT), 'show', 'b142cf8:certification/certification_matrix.json'],
        text=True,
    ))
    by_id = {row['id']: row for row in matrix['records']}
    selected = sys.argv[1:]
    if len(selected) != 1 or selected[0] not in IDS:
        raise SystemExit(f'usage: {Path(__file__).name} <one of {", ".join(IDS)}>')
    row_id = selected[0]
    source = by_id[row_id]
    check_names = ['execution_proof', *source['negative_tests']]
    reason = (
        'STILL_NOT_TESTED: exercising this proof requires an authorized testnet '
        'deployment/control transition and contemporaneous process, port, and '
        'exchange observation. This read-only run did not initiate transitions, '
        'terminate processes, or interact with the exchange.'
    )
    rows = [{
        'id': row_id,
        'status': 'STILL_NOT_TESTED',
        'execution_proof': source['execution_proof'],
        'independent_oracle': source['independent_oracle'],
        'checks': [{'check': name, 'status': 'STILL_NOT_TESTED', 'reason': reason}
                   for name in check_names],
        'negative_tests_non_vacuous': False,
        'reason': reason,
    }]
    print(json.dumps({'tested_commit': commit, 'source_matrix_commit': 'b142cf88d389e791160f691aac3d936852b99975', 'rows': rows}, indent=2))


if __name__ == '__main__':
    main()
