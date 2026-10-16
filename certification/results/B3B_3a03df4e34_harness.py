import json
from pathlib import Path
BASE=Path(__file__).parent
DATA=json.loads((BASE / 'B3B_3a03df4e34.json').read_text(encoding='utf-8'))
EXPECTED={'F25-P06', 'F25-P07', 'F25-P08', 'F25-P09', 'F25-P10', 'F25-X01'}
assert DATA['register_ref']=='main:certification/certification_matrix.json'
assert len(DATA['rows'])==6 and {r['id'] for r in DATA['rows']}==EXPECTED
assert all(r['result']=='NOT_TESTED' and r['engine_commit']==DATA['engine_commit'] for r in DATA['rows'])
assert all(len(r['checks'])==3 and all(c['result']=='NOT_TESTED' and c['detail'] for c in r['checks']) and r['missing_route'] for r in DATA['rows'])
progress=[json.loads(x) for x in (BASE / 'PROGRESS_B3B.jsonl').read_text(encoding='utf-8').splitlines()]
assert len(progress)==6 and {r['id'] for r in progress}==EXPECTED and all(r['result']=='NOT_TESTED' and r['missing_route'] for r in progress)
print('PASS: 6 scoped rows, declared three checks each NOT_TESTED with specific missing route, progress coverage verified')
