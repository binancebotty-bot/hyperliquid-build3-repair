import hashlib
import json
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / '_archive' / 'hl_stage2' / 'HL_Copy_App_SSOT.py'
COMMIT = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
ENGINE_BLOB = subprocess.check_output(['git', 'show', f'{COMMIT}:_archive/hl_stage2/HL_Copy_App_SSOT.py'], cwd=ROOT)
ENGINE_SHA256 = hashlib.sha256(ENGINE_BLOB).hexdigest()
PORT = 8000
sock = socket.socket()
sock.settimeout(2)
try:
    sock.connect(('127.0.0.1', PORT))
    port_probe = {'reachable': True, 'address': '127.0.0.1:8000'}
except OSError as exc:
    port_probe = {'reachable': False, 'address': '127.0.0.1:8000', 'error_type': type(exc).__name__, 'error': str(exc)}
finally:
    sock.close()

missing = (
    'A reachable UI-LCC runtime URL/HL_APP_PORT binding is unavailable to this run; the source default '
    '127.0.0.1:8000 timed out on a TCP connection attempt. The contemporaneous independent exchange/engine '
    'truth input (raw exchange position/fill data plus attribution state) was not supplied or retrieved. '
    'Therefore no API payload, rendered DOM, independent recomputation, or persistence/validation '
    'round-trip was executed.'
)
rows = [
    ('UI-LCC-DETAIL-02', 'Wallet open-positions detail: Coin/Side/Size/Entry/Mark/uPnL/Exposure/Exchange match'),
    ('UI-LCC-DETAIL-03', 'Wallet Lead vs Copy / Friction detail'),
    ('UI-LCC-DETAIL-04', 'Wallet Execution Audit detail'),
    ('UI-LCC-ADD-06', 'Add-wallet Leader equity base field'),
    ('UI-LCC-ADD-07', 'Add-wallet Max diff % field'),
    ('UI-LCC-ADD-10', 'Add-wallet submit'),
]
register = json.loads(subprocess.check_output(
    ['git', 'show', 'b142cf88:certification/certification_matrix.json'], cwd=ROOT, text=True
))
register_rows = {row['id']: row for row in register['records']}
now = datetime.now(timezone.utc).isoformat()
results = []
for row_id, feature in rows:
    source_row = register_rows[row_id]
    row_missing = missing
    if row_id in {'UI-LCC-ADD-06', 'UI-LCC-ADD-07', 'UI-LCC-ADD-10'}:
        row_missing += ' The row is additionally constrained by unresolved OD-07 and OD-10 in the register, so no live configuration write was attempted.'
    results.append({
        'id': row_id,
        'feature': feature,
        'register_result_at_b142cf88': source_row['result'],
        'expected_behaviour': source_row['expected_behaviour'],
        'row_execution_proof': source_row['execution_proof'],
        'row_independent_oracle': source_row['independent_oracle'],
        'result': 'NOT_TESTED',
        'tested_commit': COMMIT,
        'engine_sha256': ENGINE_SHA256,
        'tested_at_utc': now,
        'execution_proof': 'NOT EXECUTED: live API payload -> rendered DOM was unavailable.',
        'independent_oracle': 'NOT EXECUTED: independent contemporaneous exchange/engine truth input was unavailable; no engine/UI import was used as an oracle.',
        'runtime_probe': port_probe,
        'exact_missing_prerequisites': row_missing,
        'negative_tests': 'NOT EXECUTED: no live UI/API was available to verify unavailable/stale/API-error rendering.',
        'notes': 'No PASS claimed. No live configuration was mutated.'
    })
artifact = {
    'task_id': 't_59968de6',
    'title': 'B3-CERT UI-LCC DETAIL-02..04 + ADD-06/07/10',
    'register_of_record': 'git show b142cf88:certification/certification_matrix.json',
    'register_ref_resolved': subprocess.check_output(['git', 'rev-parse', 'b142cf88'], cwd=ROOT, text=True).strip(),
    'tested_commit': COMMIT,
    'engine_sha256': ENGINE_SHA256,
    'tested_at_utc': now,
    'runtime_probe_method': 'Python TCP connect, loopback 127.0.0.1:8000 (HL_Copy_App_SSOT.py source default APP_PORT)',
    'runtime_probe': port_probe,
    'rows': results,
    'status': 'NOT_TESTED_ALL_ROWS'
}
out = ROOT / 'certification' / 'results' / 'UI_LCC_DETAIL02_04_ADD06_07_10_NOT_TESTED.json'
out.write_text(json.dumps(artifact, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'artifact': str(out), 'tested_commit': COMMIT, 'engine_sha256': ENGINE_SHA256, 'port_probe': port_probe, 'row_count': len(results), 'row_ids': [r['id'] for r in results], 'all_not_tested': all(r['result'] == 'NOT_TESTED' for r in results)}, indent=2))
