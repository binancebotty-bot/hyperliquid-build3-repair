#!/usr/bin/env python3
"""Validate NET_S4 artifact shape without claiming unavailable runtime evidence."""
import json
from pathlib import Path

RESULT = Path(__file__).with_name('NET_S4_b3e6d66651.json')
EXPECTED = {'TN-T16', 'TN-T17', 'TN-A1', 'TN-A2', 'TN-A3'}

def main():
    data = json.loads(RESULT.read_text(encoding='utf-8'))
    assert data['suite'] == 'NET_S4'
    assert data['result'] == 'NOT_TESTED'
    rows = data['rows']
    assert len(rows) == 5
    assert {row['id'] for row in rows} == EXPECTED
    assert all(row['result'] == 'NOT_TESTED' and row.get('missing') for row in rows)
    assert data['checks'] == []
    print('NET_S4 artifact shape verified: 5 requested rows remain NOT_TESTED; no fabricated checks.')

if __name__ == '__main__':
    main()
