#!/usr/bin/env python3
"""Validate the REGR3 evidence package for t_6f378dc2 (5 rows).

Deterministic, offline. Confirms schema, register ref, engine commit, row set,
and that every NOT_TESTED check names a MISSING ROUTE (no silent non-evidence).
"""
import json
from pathlib import Path

p = Path(__file__).with_name('REGR3_52a16149e3.json')
d = json.loads(p.read_text(encoding='utf-8'))

EXPECTED_ROWS = {'F-VERIFY-008', 'F-PRODUCT-001', 'F-TEST-001', 'F-TEST-010', 'TN-F07'}

assert d['schema'] == 'b3_regression_net_row_evidence_v1', d['schema']
assert d['register_ref'] == 'main:certification/certification_matrix.json'
assert d['register_commit'] == 'b142cf88d389e791160f691aac3d936852b99975'
assert d['engine_commit'] == '52a16149e370732bb3162d69cb2f9ce4a43509bb'

rows = d['rows']
ids = {r['id'] for r in rows}
assert ids == EXPECTED_ROWS, ids
assert len(rows) == 5

for r in rows:
    assert r['result'] == 'NOT_TESTED', (r['id'], r['result'])
    assert r['applicability'] == 'OPEN_DECISION', (r['id'], r['applicability'])
    assert r['open_decisions'], r['id']
    assert len(r['checks']) >= 1
    for c in r['checks']:
        assert c['result'] in {'PASS', 'FAIL', 'NOT_TESTED'}, (r['id'], c)
        if c['result'] == 'NOT_TESTED':
            # every NOT_TESTED check must name WHY: a missing route or an unruled open decision
            detail = c['detail']
            assert ('MISSING ROUTE:' in detail) or ('OD-' in detail), (r['id'], c['name'], detail)
    assert r['missing_routes'], r['id']

s = d['summary']
assert s == {'rows': 5, 'pass': 0, 'fail': 0, 'not_tested': 5, 'blocked': 0}, s

print('PASS: REGR3 evidence schema, register/engine refs, 5-row set, and named missing routes verified')
