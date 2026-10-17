#!/usr/bin/env python3
"""Validate the NET_S1 artifact shape without claiming unavailable runtime evidence."""
import json
from pathlib import Path

RESULT = Path(__file__).with_name('NET_S1_b3e6d66651.json')
EXPECTED = {'TN-T1', 'TN-T2', 'TN-T3', 'TN-T4', 'TN-T5'}

def main():
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    assert data['suite'] == 'NET_S1'
    assert data['result'] == 'NOT_TESTED'
    rows = data['rows']
    assert len(rows) == 5
    assert {r['id'] for r in rows} == EXPECTED
    assert all(r['result'] == 'NOT_TESTED' and r.get('missing') for r in rows)
    for r in rows:
        assert r['checks'], r['id']
        assert all(c['status'] == 'STILL_NOT_TESTED' for c in r['checks']), r['id']
        assert r['negative_tests_non_vacuous'] is False, r['id']
        assert len(r['negative_tests']) == 3, r['id']
        assert all(n['status'] == 'STILL_NOT_TESTED' for n in r['negative_tests']), r['id']
    assert data['checks'] == []
    print('NET_S1 artifact shape verified: 5 rows remain NOT_TESTED; no fabricated checks or PASS claims.')

if __name__ == '__main__':
    main()
