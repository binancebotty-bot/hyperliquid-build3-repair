import json
from pathlib import Path

BASE = Path(__file__).parent
DATA = json.loads((BASE / 'B3A_7d6111e7c3.json').read_text(encoding='utf-8'))
EXPECTED = {'ENG-003', 'F25-P01', 'F25-P02', 'F25-P03', 'F25-P04', 'F25-P05'}
rows = DATA['rows']
assert len(rows) == 6 and {r['id'] for r in rows} == EXPECTED
assert all(r['result'] == 'NOT_TESTED' for r in rows)
assert all(r['engine_commit'] == DATA['engine_commit'] for r in rows)
assert all(r['missing_route'] and len(r['checks']) == 3 for r in rows)
progress = [json.loads(line) for line in (BASE / 'PROGRESS_B3A.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(progress) == 6 and {r['id'] for r in progress} == EXPECTED
assert all(r['result'] == 'NOT_TESTED' and r['missing_route'] for r in progress)
print('PASS: six scoped rows, per-row NOT_TESTED rationale, and progress entries validated')
