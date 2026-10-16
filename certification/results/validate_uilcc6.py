#!/usr/bin/env python3
"""Validate structural completeness of a UILCC6 evidence artifact."""
import json
import sys
from pathlib import Path

EXPECTED = {
    'UI-LCC-DETAIL-01', 'UI-LCC-DETAIL-02', 'UI-LCC-DETAIL-03',
    'UI-LCC-DETAIL-04', 'UI-LCC-ADD-06', 'UI-LCC-ADD-07',
}

def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).with_name('UILCC6_b142cf88d3.json'))
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['schema'] == 'hl_certification_result_v1'
    rows = data['rows']
    assert len(rows) == 6, f'expected 6 rows, got {len(rows)}'
    assert {row['id'] for row in rows} == EXPECTED, 'row ID set mismatch'
    for row in rows:
        assert row['result'] in {'PASS', 'FAIL', 'BLOCKED', 'NOT_TESTED'}
        assert row['evidence_ref'] == f'certification/results/{path.name}'
        assert row['execution_proof'] and row['independent_oracle']
        assert isinstance(row['negative_tests'], dict)
    print(f'PASS: structurally valid artifact; {len(rows)} exact requested rows')
    print('Outcomes:', ', '.join(f"{r['id']}={r['result']}" for r in rows))

if __name__ == '__main__':
    main()
