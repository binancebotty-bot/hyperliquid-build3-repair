#!/usr/bin/env python3
"""Register-aware NET_S4 evidence projection; no engine or exchange mutation."""
import json
import subprocess
import sys
from pathlib import Path
ENGINE_COMMIT = '52a16149e370732bb3162d69cb2f9ce4a43509bb'
ENGINE_BLOB_SHA_MAIN = '1ba069f2d74c5f4922cb0bdd173b7eadc17d3fd9'
REGISTER_COMMIT = 'b142cf88d389e791160f691aac3d936852b99975'
ROWS = ('TN-F22', 'TN-F23', 'TN-F26', 'TN-F27', 'TN-PS1')
ARTIFACT = Path(__file__).with_name('NET_S4_f28341d1.json')
MISSING = ('Active Build-3 testnet production-engine scenario with fresh row-specific exchange-parity '
           'capture and independent captured request-packet/exchange orders-and-fills oracle. The '
           'available UI HTTP 200 does not establish those prerequisites.')
def build():
    raw = subprocess.check_output(['git', 'show', f'{REGISTER_COMMIT}:certification/certification_matrix.json'])
    matrix = json.loads(raw)
    records = {r['id']: r for r in matrix['records'] if r['id'] in ROWS}
    assert set(records) == set(ROWS), 'register rows missing'
    rows = []
    for row_id in ROWS:
        reg = records[row_id]
        result = 'BLOCKED' if reg['result'] == 'BLOCKED' else 'NOT_TESTED'
        missing = MISSING
        if row_id in ('TN-F26', 'TN-F27', 'TN-PS1'):
            missing += '; register applicability is OPEN_DECISION and the applicable OD remains unresolved.'
        rows.append({'id': row_id, 'result': result,
            'checks': [{'name': name, 'result': 'NOT_TESTED'} for name in ('declared_testnet_production_engine_scenario','independent_exchange_or_packet_oracle','negative_tests')],
            'missing_runtime': missing, 'register_result': reg['result'],
            'register_row_applicability': reg['applicability'], 'register_open_decisions': reg['open_decisions'],
            'engine_commit': ENGINE_COMMIT})
    return {'suite':'NET_S4','register_of_record':f'main:{REGISTER_COMMIT}:certification/certification_matrix.json',
        'engine_commit_under_test':ENGINE_COMMIT,'engine_blob_sha_main':ENGINE_BLOB_SHA_MAIN,
        'mutations':'none; GET only; no engine started and no order submitted','rows':rows}
def main():
    expected=build()
    if '--write' in sys.argv:
        ARTIFACT.write_text(json.dumps(expected,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    actual=json.loads(ARTIFACT.read_text(encoding='utf-8'))
    assert actual==expected, 'artifact does not match register-aware harness output'
    print(json.dumps(expected,indent=2,sort_keys=True))
if __name__=='__main__': main()
