#!/usr/bin/env python3
# Consolidate the UIFA3 verdicts for t_770ce423 into the card write target
# certification/results/UIFA3_b142cf88d3.json.
# Base = uifa3_harness_v3.py (all 17 rows, live DOM + independent oracle joins).
# Overrides: v7 (UI-FP-133 PASS after settle-window join fix) and v9
# (UI-FP-115 / UI-FP-119 non-vacuous 29-sample column-shift proof).
import json
from datetime import datetime, timezone
from pathlib import Path

RES = Path(__file__).resolve().parent
IDS = ['UI-FP-076', 'UI-FP-078', 'UI-FP-079', 'UI-FP-084', 'UI-FP-088', 'UI-FP-089',
       'UI-FP-090', 'UI-FP-107', 'UI-FP-109', 'UI-FP-110', 'UI-FP-115', 'UI-FP-119',
       'UI-FP-120', 'UI-FP-133', 'UI-FP-137', 'UI-FP-139', 'UI-FP-140']


def load(name):
    d = json.loads((RES / name).read_text(encoding='utf-8'))
    rows = d['rows']
    return {r['row_id']: r for r in rows} if isinstance(rows, list) else rows


base = load('UIFA3_v3_b142cf88d3.json')
v7 = load('UIFA3_v7_retest_b142cf88d3.json')
v9 = load('UIFA3_v9_retest_b142cf88d3.json')
v10 = load('UIFA3_v10_retest_b142cf88d3.json')

rows = {}
for rid in IDS:
    r = dict(base[rid])
    r['verdict_stage'] = 'v3 baseline (live DOM + independent oracle)'
    rows[rid] = r
r = dict(v7['UI-FP-133'])
r['verdict_stage'] = 'v7 retest: 7/7 matched once young attempts were excluded (v3 was vacuous 0-sample)'
rows['UI-FP-133'] = r
for rid in ('UI-FP-115', 'UI-FP-119'):
    r = dict(v9[rid])
    r['verdict_stage'] = 'v9 retest: 29 terminal rows, 0 matched under labelled header, 29 matched at index+1'
    rows[rid] = r
for rid in ('UI-FP-107', 'UI-FP-110', 'UI-FP-120'):
    r = dict(v10[rid])
    r['verdict_stage'] = 'v10 retest: 15 terminal rows, 0 under labelled header, 15 at index+1'
    rows[rid] = r
r = dict(v10['UI-FP-109'])
r['verdict_stage'] = 'v10 retest: 15 terminal rows, 0 under labelled header, 0 at index+1 - value mismatch beyond the column shift'
rows['UI-FP-109'] = r

out_rows = [rows[i] for i in IDS]
npass = sum(1 for r in out_rows if r['result'] == 'PASS')
nfail = sum(1 for r in out_rows if r['result'] == 'FAIL')

out = {
    'task_id': 't_770ce423',
    'card': 'B3-CERT UI FAIL small (17 rows): UI-FP-076..140',
    'ssot_commit': '5223ce257fe504636967a50f7064630bdc8e0ab0',
    'ssot_path': '_archive/hl_stage2/HL_Copy_App_SSOT.py',
    'register_commit': 'b142cf8',
    'certified_at_utc': datetime.now(timezone.utc).isoformat(),
    'served_surface': 'http://127.0.0.1:8031/live-copy (DOM captured live; oracle = append_only CSVs under state_dir from /api/global-controls)',
    'harnesses': [
        'certification/results/uifa3_harness_v3.py',
        'certification/results/uifa3_harness_v7_retest.py',
        'certification/results/uifa3_harness_v9_retest.py',
        'certification/results/uifa3_harness_v10_retest.py',
        'certification/results/consolidate_uifa3.py'],
    'summary': {'total_rows': len(out_rows), 'pass': npass, 'fail': nfail, 'not_tested': 0},
    'root_cause': {
        'row_family': 'UI-FP-107/109/110/115/119/120 (Execution Quality table)',
        'defect': 'SSOT line 7144 declares 18 <th>; renderExecQuality (SSOT 7595) emits 19 <td> because an unlabelled truth_state pill is written at body index 4. Every header from Status onward labels the neighbouring cell.',
        'proof': 'v9: 29 terminal rows, 0/29 matched under the labelled header index, 29/29 matched at index+1 for Leader->send ms (12->13) and Exchange ms (16->17). v10 (independent capture, 15 terminal rows): same shift proven for Status (4->5), Reject category (7->8), Error (17->18) at 15/15; UI-FP-109 Operator action matched 0/15 at BOTH positions, i.e. a second, value-level defect sits behind the shift.',
        'status': 'UNFIXED in authoritative SSOT commit; FAIL kept, no accept-set widening.'},
    'rows': out_rows,
}
(RES / 'UIFA3_b142cf88d3.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')

with open(RES / 'PROGRESS_UIFA3.jsonl', 'w', encoding='utf-8') as f:
    for r in out_rows:
        f.write(json.dumps({'row_id': r['row_id'], 'result': r['result'],
                            'stage': r.get('verdict_stage', ''), 'final': True,
                            'at_utc': out['certified_at_utc']}, ensure_ascii=False) + '\n')

print('rows=%d pass=%d fail=%d' % (len(out_rows), npass, nfail))
for r in out_rows:
    print(' ', r['row_id'], r['result'], '|', r.get('verdict_stage', ''))
