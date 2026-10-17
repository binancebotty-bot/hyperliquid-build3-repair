import json
from pathlib import Path

RESULT = Path(__file__).with_name('LIFE_S1_b3e6d66651.json')
EXPECTED = {'F25-P01', 'F25-P02', 'F25-P03', 'F25-P04', 'F25-P05'}


def verify():
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    rows = data['rows']
    assert {row['id'] for row in rows} == EXPECTED
    assert len(rows) == 5
    assert all(row['status'] == 'STILL_NOT_TESTED' for row in rows)
    assert all(row['oracle_status'] == 'NOT_OBSERVED' for row in rows)
    assert all(row['negative_tests_non_vacuous'] is False for row in rows)
    assert all(all(check['status'] == 'NOT_RUN' for check in row['checks']) for row in rows)
    assert sum(len(row['checks']) for row in rows) == 25
    assert data['summary'] == {
        'rows': 5,
        'still_not_tested': 5,
        'checks_not_run': 25,
        'pass': 0,
        'negative_tests_non_vacuous': 0,
    }
    print('PASS: artifact boundary verified; 5 rows, 25 NOT_RUN checks, zero PASS claims')


if __name__ == '__main__':
    verify()
