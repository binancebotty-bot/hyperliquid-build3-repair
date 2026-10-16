import json
from pathlib import Path

EXPECTED = [f'PRICE-{number:03}' for number in range(1, 9)]
PATH = Path(__file__).with_name('PROGRESS_PRICING.jsonl')

rows = [json.loads(line) for line in PATH.read_text(encoding='utf-8').splitlines()]
assert [row['row'] for row in rows] == EXPECTED
for row in rows:
    assert row['result'] == 'NOT_TESTED'
    assert row['checks'] == {
        'execution_proof': 'NOT_TESTED',
        'independent_oracle': 'NOT_TESTED',
        'negative_tests': 'NOT_TESTED',
    }
    assert row['tested_commit'] == 'b3e6d6665116510f8a9ceaa5254b060bf4d73998'
print(f'Validated {len(rows)} row-specific NOT_TESTED progress records; no execution/oracle/negative check claimed as passing.')
