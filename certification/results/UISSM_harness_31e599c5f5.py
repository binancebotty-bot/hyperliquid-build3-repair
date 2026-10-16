#!/usr/bin/env python3
"""Validate UISSM evidence integrity against the main-branch register.

This harness validates status and evidence integrity; it does not execute UI
actions or infer PASS from a reachable page.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = Path(__file__).with_name('UISSM_31e599c5f5.json')
EXPECTED = {
    'UI-LCC-ADD-10', 'UI-SSOT-TOP-06', 'UI-SSOT-TOP-07',
    'UI-SSOT-TOP-09', 'UI-SSOT-TBL-25', 'UI-SSOT-PAGE-01',
}


def main() -> None:
    data = json.loads(ARTIFACT.read_text(encoding='utf-8'))
    assert data['register_ref'] == 'main:certification/certification_matrix.json'
    assert data['overall'] == 'NOT_TESTED'
    rows = data['rows']
    assert len(rows) == 6
    assert {r['id'] for r in rows} == EXPECTED
    assert all(r['verdict'] == 'NOT_TESTED' for r in rows)
    assert all(r['engine_commit'] == '52a16149e370732bb3162d69cb2f9ce4a43509bb' for r in rows)
    register = json.loads(subprocess.check_output(
        ['git', 'show', 'main:certification/certification_matrix.json'], cwd=ROOT
    ))
    source = {r['id']: r for r in register['records'] if r['id'] in EXPECTED}
    assert set(source) == EXPECTED
    for row in rows:
        expected = source[row['id']]
        assert row['register_result'] == expected['result'], row['id']
        assert row['execution_proof'] == expected['execution_proof'], row['id']
        assert row['independent_oracle'] == expected['independent_oracle'], row['id']
        assert row['negative_tests'] == expected['negative_tests'], row['id']
        assert {'PASS', 'FAIL', 'NOT_TESTED'} >= {c['result'] for c in row['checks']}
        assert any(c['result'] == 'NOT_TESTED' for c in row['checks']), row['id']
    assert data['surface_probe']['http_status'] == 200
    assert data['audit_endpoint_probe']['http_status'] == 200
    print(f'UISSM_ARTIFACT_VALID rows={len(rows)} verdicts=6xNOT_TESTED register=main')


if __name__ == '__main__':
    main()
