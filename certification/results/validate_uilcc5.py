#!/usr/bin/env python3
"""Validate bounded UI-LCC evidence against the main register."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / 'UILCC5_31e599c5f5.json'
EXPECTED = {f'UI-LCC-WTBL-{n:02d}' for n in range(9, 15)}

def main():
    evidence = json.loads(EVIDENCE.read_text(encoding='utf-8'))
    register_text = subprocess.check_output(
        ['git', 'show', 'main:certification/certification_matrix.json'], text=True)
    register = json.loads(register_text)
    records = {r['id']: r for r in register['records']}
    rows = {r['id']: r for r in evidence['rows']}
    assert set(rows) == EXPECTED, f'wrong evidence rows: {sorted(rows)}'
    assert EXPECTED <= records.keys(), 'register missing requested rows'
    for row_id in sorted(EXPECTED):
        source = records[row_id]
        outcome = rows[row_id]
        assert source['result'] == 'NOT_TESTED', f'{row_id}: register changed; review fresh'
        assert outcome['feature'] == source['feature'], f'{row_id}: feature mismatch'
        assert outcome['result'] == 'NOT_TESTED', f'{row_id}: uncertified status must remain honest'
        assert set(outcome['checks']) == {'served_ui', 'declared_execution_proof', 'independent_oracle', 'negative'}
    assert evidence['register_ref'] == 'main:certification/certification_matrix.json'
    print(f'PASS harness structure: {len(rows)} exact rows; all retain NOT_TESTED')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'FAIL: {exc}', file=sys.stderr)
        raise
