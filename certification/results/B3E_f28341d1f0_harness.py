import json
from pathlib import Path

RESULT = Path(__file__).with_name('B3E_f28341d1f0.json')
EXPECTED = {'TN-F25', 'TN-T1', 'TN-T2', 'TN-T3', 'TN-T4', 'TN-T5'}

def validate():
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    assert data['register_ref'] == 'main:certification/certification_matrix.json'
    rows = data['results']
    assert {row['row_id'] for row in rows} == EXPECTED
    assert len(rows) == len(EXPECTED)
    for row in rows:
        assert row['result'] == 'NOT_TESTED', row['row_id']
        assert row['execution_proof'] and row['independent_oracle']
        assert row['checks'], row['row_id']
        for check in row['checks']:
            assert check['result'] in {'PASS', 'FAIL', 'NOT_TESTED'}
            assert check['detail']
        assert all('MISSING ROUTE:' in c['detail'] for c in row['checks'] if c['result'] == 'NOT_TESTED')
    return len(rows), sum(len(row['checks']) for row in rows)

if __name__ == '__main__':
    print('VALID', validate())
