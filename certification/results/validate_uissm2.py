#!/usr/bin/env python3
"""Validate the bounded UISSM2 evidence artifact without upgrading outcomes."""
import json
import sys
from pathlib import Path

EXPECTED = {
    'UI-SSOT-PAGE-11', 'UI-SSOT-PAGE-13', 'UI-SSOT-PAGE-14',
    'UI-SSOT-PAGE-15', 'UI-TRUTH-003', 'UI-TRUTH-005',
}


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name('UISSM2_31e599c5f5.json')
    data = json.loads(path.read_text(encoding='utf-8'))
    rows = data.get('rows')
    assert isinstance(rows, list), 'rows must be a list'
    ids = [row.get('id') for row in rows]
    assert len(ids) == len(EXPECTED), f'expected 6 rows, got {len(ids)}'
    assert set(ids) == EXPECTED, f'id set mismatch: {set(ids) ^ EXPECTED}'
    assert len(ids) == len(set(ids)), 'duplicate row id'
    assert data.get('register_ref') == 'main:certification/certification_matrix.json'
    assert data.get('engine_commit') is None, 'must not claim unknown served commit'
    for row in rows:
        assert row.get('outcome') in {'NOT_TESTED', 'PASS', 'FAIL', 'BLOCKED'}
        assert row.get('register_result') in {'NOT_TESTED', 'PASS', 'FAIL', 'BLOCKED'}
        assert row.get('declared_execution_proof')
        assert row.get('declared_independent_oracle')
        assert row.get('checks'), f"{row['id']}: missing checks"
        if row['outcome'] == 'PASS':
            assert all(value == 'PASS' for value in row['checks'].values()), f"{row['id']}: unjustified PASS"
    print(f'UISSM2 artifact validation PASS: {len(rows)} unique rows; no unjustified PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
