import json
from pathlib import Path

RESULT = Path(__file__).with_name('B3G_e26c5f60d8.json')
EXPECTED = {'TN-T12', 'TN-T13', 'TN-T14', 'TN-T15', 'TN-T16', 'TN-T17'}


def validate():
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    assert data['register_ref'] == 'main:certification/certification_matrix.json'
    assert data['register_commit'] == 'b142cf88d389e791160f691aac3d936852b99975'
    rows = data['results']
    assert {row['row_id'] for row in rows} == EXPECTED
    assert len(rows) == len(EXPECTED)
    for row in rows:
        assert row['result'] == 'NOT_TESTED', row['row_id']
        assert row['execution_proof'] and row['independent_oracle']
        assert row['engine_commit'] == data['engine_commit']
        assert row['checks'], row['row_id']
        for check in row['checks']:
            assert check['result'] in {'PASS', 'FAIL', 'NOT_TESTED'}
            assert check['detail']
            if check['result'] == 'NOT_TESTED':
                assert 'MISSING ROUTE:' in check['detail']
    return len(rows), sum(len(row['checks']) for row in rows)


if __name__ == '__main__':
    print('VALID', validate())
