"""Validate B3J evidence structure without upgrading evidence status.

Card t_3cdb4e1a: INC-18 + UI-FP-149/150/165/167/168 (6 rows).
Checks the artifact declares, per row, the row's OWN execution_proof and
independent_oracle, carries an engine commit, and that every non-PASS check
names a MISSING ROUTE. No row may be promoted by this harness.
"""
import json
import sys
from pathlib import Path

EXPECTED = {'INC-18', 'UI-FP-149', 'UI-FP-150', 'UI-FP-165', 'UI-FP-167', 'UI-FP-168'}
REGISTER_REF = 'main:certification/certification_matrix.json'


def validate(path: Path) -> None:
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['register_ref'] == REGISTER_REF, data['register_ref']
    assert data.get('register_commit'), 'register_commit missing'
    assert data.get('engine_commit'), 'engine_commit missing'
    assert data.get('tested_at_utc'), 'tested_at_utc missing'
    rows = data['results']
    assert {r['row_id'] for r in rows} == EXPECTED, sorted(r['row_id'] for r in rows)
    assert len(rows) == len(EXPECTED), len(rows)
    for row in rows:
        assert row['result'] == 'NOT_TESTED', (row['row_id'], row['result'])
        assert row['execution_proof'], row['row_id']
        assert row['independent_oracle'], row['row_id']
        assert row['engine_commit'] == data['engine_commit'], row['row_id']
        assert row['prior_result'], row['row_id']
        assert row['checks'], row['row_id']
        for check in row['checks']:
            assert check['result'] in ('PASS', 'FAIL', 'NOT_TESTED'), check
            if check['result'] != 'PASS':
                assert 'MISSING ROUTE:' in check['detail'], (row['row_id'], check['name'])


if __name__ == '__main__':
    validate(Path(sys.argv[1]))
    print('PASS: exactly six scoped rows; declared proof/oracle, register+engine commit, and '
          'explicit MISSING ROUTE on every non-PASS check present; no row promoted.')
