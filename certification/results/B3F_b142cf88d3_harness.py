"""Validate B3F evidence structure without upgrading evidence status."""
import json
from pathlib import Path


def validate(path: Path) -> None:
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['register_ref'] == 'main:certification/certification_matrix.json'
    expected = {'TN-T6', 'TN-T7', 'TN-T8', 'TN-T9', 'TN-T10', 'TN-T11'}
    rows = data['results']
    assert {r['row_id'] for r in rows} == expected
    assert len(rows) == len(expected)
    for row in rows:
        assert row['result'] == 'NOT_TESTED'
        assert row['execution_proof'] and row['independent_oracle']
        assert row['engine_commit'] == data['engine_commit']
        assert row['checks']
        for check in row['checks']:
            assert check['result'] == 'NOT_TESTED'
            assert 'MISSING ROUTE:' in check['detail']


if __name__ == '__main__':
    import sys
    validate(Path(sys.argv[1]))
    print('PASS: exactly six scoped rows; declared proof/oracle, engine commit, and explicit missing-route checks present; no row promoted.')
