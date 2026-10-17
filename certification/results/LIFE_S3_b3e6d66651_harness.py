import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / 'LIFE_S3_b3e6d66651.json'
EXPECTED = ['F25-X01', 'F25-X02', 'F25-X03', 'F25-X04']


def validate():
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    assert data['suite'] == 'LIFE_S3'
    assert data['register_commit'] == 'b142cf8'
    rows = data['rows']
    assert [row['id'] for row in rows] == EXPECTED
    assert len(set(row['id'] for row in rows)) == len(EXPECTED)
    assert data['summary'] == {
        'rows': 4,
        'checks': 16,
        'checks_pass': 0,
        'checks_fail': 0,
        'checks_still_not_tested': 16,
        'negative_cases_executed': 0,
    }
    for row in rows:
        assert row['result'] == 'STILL_NOT_TESTED'
        assert row['execution_proof'] and row['independent_oracle']
        assert row['evidence']
        assert len(row['checks']) == 4
        assert all(check['status'] == 'STILL_NOT_TESTED' for check in row['checks'])
    print('ARTIFACT_BOUNDARY=PASS rows=4 checks=16 pass=0 fail=0 still_not_tested=16 negatives_executed=0')


if __name__ == '__main__':
    validate()
