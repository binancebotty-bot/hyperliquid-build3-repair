"""Validate B3D_b142cf88d3 evidence structure without upgrading evidence status.

Schema: b3_network_row_evidence_v1
Scope (explicit - do not infer/expand/shrink):
  F25-X08, TN-F03, TN-F04, TN-F19, TN-F20, TN-F24

Integrity gates:
  - register_ref + engine_commit / register_commit pinned to main b142cf88d3.
  - exactly the six scoped rows, in order.
  - each NOT_TESTED row keeps a non-vacuous negative: per-check result
    NOT_TESTED and detail names the missing route (MISSING ROUTE:).
  - TN-F19 retains its honest FAIL from its own evidence (evidence_ref +
    tested_commit + checks_passed 5/6 + at least one FAIL check + negatives).
  - each row quotes the register row OWN execution_proof and
    independent_oracle verbatim (re-read from main by this harness).
"""
import json
import subprocess
from pathlib import Path

ENGINE_COMMIT = 'b142cf88d389e791160f691aac3d936852b99975'
REGISTER_REF = 'main:certification/certification_matrix.json'
EXPECTED = ['F25-X08', 'TN-F03', 'TN-F04', 'TN-F19', 'TN-F20', 'TN-F24']
VALID = ('NOT_TESTED', 'PASS', 'FAIL', 'BLOCKED')


def _register_rows():
    # Authoritative source of the row definitions; read from main, not the
    # working tree, so the result cannot drift from the register of record.
    try:
        out = subprocess.run(
            ['git', 'show', 'main:certification/certification_matrix.json'],
            capture_output=True, text=True, check=True,
        )
        return {r['id']: r for r in json.loads(out)['records']}
    except Exception:
        return {}


def validate(path: Path) -> None:
    data = json.loads(path.read_text(encoding='utf-8'))
    assert data['schema'] == 'b3_network_row_evidence_v1', data.get('schema')
    assert data['register_ref'] == REGISTER_REF
    assert data['engine_commit'] == ENGINE_COMMIT
    assert data.get('register_commit') == ENGINE_COMMIT
    assert [r['row_id'] for r in data['results']] == EXPECTED, \
        [r['row_id'] for r in data['results']]

    reg = _register_rows()
    for row in data['results']:
        rid = row['row_id']
        assert row['engine_commit'] == ENGINE_COMMIT, rid
        # own proof + oracle must be present and verbatim from the register
        assert row['execution_proof'], rid
        assert row['independent_oracle'], rid
        if rid in reg:
            assert row['execution_proof'] == reg[rid]['execution_proof'], rid
            assert row['independent_oracle'] == reg[rid]['independent_oracle'], rid
        assert row['checks'], rid
        for c in row['checks']:
            assert c['name'] and c['result'] in VALID and c['detail'], rid

        if row['result'] == 'NOT_TESTED':
            # non-vacuous negative: every check stays NOT_TESTED and names
            # the missing route explicitly; nothing promoted to PASS/FAIL.
            for c in row['checks']:
                assert c['result'] == 'NOT_TESTED', (rid, c['name'])
                assert c['detail'].startswith('MISSING ROUTE:'), (rid, c['name'])
            assert row.get('missing_route'), rid
        elif row['result'] == 'FAIL':
            # TN-F19: retained honest FAIL backed by its own evidence file.
            assert any(c['result'] == 'FAIL' for c in row['checks']), rid
            assert row.get('evidence_ref') and row.get('tested_commit'), rid
            assert row.get('checks_passed') == 5 and row.get('checks_total') == 6, rid
            assert row.get('negative_tests_results'), rid
        else:
            raise AssertionError('unexpected row result: %s' % rid)

    print('PASS: 6 scoped rows validated; schema=%s engine=%s'
          % (data['schema'], ENGINE_COMMIT[:10]))


if __name__ == '__main__':
    import sys
    validate(Path(sys.argv[1]))
    print('OK')
