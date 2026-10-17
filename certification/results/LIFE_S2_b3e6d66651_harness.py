"""Validate the bounded LIFE_S2 artifact without touching live runtime."""
import json
from pathlib import Path

RESULT = Path(__file__).with_name('LIFE_S2_b3e6d66651.json')
EXPECTED = ['F25-P06', 'F25-P07', 'F25-P08', 'F25-P09', 'F25-P10']
REQUIRED_CHECKS = {
    'execution_proof',
    'second start attempt',
    'crash mid-transition',
    'stale lock/PID',
    'config from previous version',
}


def main():
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    rows = data['rows']
    assert [row['id'] for row in rows] == EXPECTED
    for row in rows:
        assert row['status'] == 'STILL_NOT_TESTED', row['id']
        assert row['negative_tests_non_vacuous'] is False, row['id']
        checks = row['checks']
        assert {check['check'] for check in checks} == REQUIRED_CHECKS, row['id']
        assert len(checks) == len(REQUIRED_CHECKS), row['id']
        assert all(check['status'] == 'STILL_NOT_TESTED' for check in checks), row['id']
        assert all(check.get('reason') for check in checks), row['id']
    print(f'PASS: {len(rows)} exact rows; {len(rows) * len(REQUIRED_CHECKS)} checks remain explicitly STILL_NOT_TESTED; no negative case claimed exercised.')


if __name__ == '__main__':
    main()
