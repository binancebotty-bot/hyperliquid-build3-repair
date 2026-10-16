import json
from pathlib import Path


RESULT = Path(__file__).with_name('UILCC2_5b82026103.json')
EXPECTED_IDS = {
    'UI-LCC-CARD-07',
    'UI-LCC-WTBL-09',
    'UI-LCC-WTBL-10',
    'UI-LCC-WTBL-11',
    'UI-LCC-WTBL-12',
}


def validate_result():
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    records = data['records']
    ids = [record['id'] for record in records]
    assert set(ids) == EXPECTED_IDS, f'unexpected row inventory: {ids!r}'
    assert len(ids) == len(EXPECTED_IDS), 'duplicate row id'
    assert data['register_ref'] == 'main'
    assert data['tested_commit'] and data['engine_commit']
    assert data['overall_result'] == 'NOT_TESTED'
    for record in records:
        assert record['result'] == 'NOT_TESTED', record['id']
        assert len(record['checks']) == 3, record['id']
        assert all(check['result'] in {'PASS', 'FAIL', 'NOT_TESTED'} for check in record['checks'])
        assert record['evidence'].startswith('certification/results/UILCC2_'), record['evidence']
    return len(records)


if __name__ == '__main__':
    print(f'validated {validate_result()} row records; no certification PASS asserted')
