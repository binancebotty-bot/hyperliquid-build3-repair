import json
from pathlib import Path

ARTIFACT = Path(__file__).with_name('RISK2_f28341d1f0.json')
EXPECTED = {'RISK-009', 'RISK-010', 'RISK-011', 'RISK-012', 'RISK-013', 'TN-F01', 'TN-F02'}
ALLOWED = {'NOT_TESTED', 'PASS', 'FAIL', 'BLOCKED'}


def validate():
    data = json.loads(ARTIFACT.read_text(encoding='utf-8'))
    rows = data['rows']
    assert {r['id'] for r in rows} == EXPECTED
    assert len(rows) == len(EXPECTED)
    assert data['overall'] == 'NOT_TESTED'
    for row in rows:
        assert row['result'] in ALLOWED
        assert row['tested_commit'] == data['tested_engine_commit']
        assert row['evidence_ref']
        if row['result'] == 'NOT_TESTED':
            assert row.get('missing_route')
    return len(rows)


if __name__ == '__main__':
    print(f'VALID rows={validate()} overall=NOT_TESTED')
