#!/usr/bin/env python3
'''Write the TN campaign evidence note and apply the verdicts to the register.

Deterministic. Reads certification/certification_matrix.json, sets
result/evidence_ref/tested_commit/tested_at_utc/notes for the 15 TN rows that
claim PASS, and rewrites the CSV from the JSON so the two cannot drift.
Only TN-prefixed rows are touched.

Usage: python apply_tn_campaign_verdicts.py <repo_root>
'''
import csv
import json
import os
import sys

ART = 'EVIDENCE/TN_CAMPAIGN_EVIDENCE/TN_CAMPAIGN_EVIDENCE.json'
NOTE = 'EVIDENCE/TN_CAMPAIGN_EVIDENCE/note.json'

CAMP = ['TN-CAMP-0%d' % i for i in range(1, 10)]
SCEN = ['TN-F06', 'TN-F16', 'TN-F21']
EMPTY = ['TN-F24', 'TN-F25', 'TN-F26', 'TN-F27', 'TN-PS1', 'TN-T1']

CAMP_NOTE = (
    'TN-CAMPAIGN-EVIDENCE: no campaign-specific evidence. Citation is the shared '
    'control-surface semantics report: 23 of its 24 checks are identical across all nine '
    'TN-CAMP rows and the 24th differs only in check NAME, not in any campaign outcome. '
    'No campaign manifest exists in the tree and the PHASE_6T_C protocol files named as '
    'sources are absent (0 local-trading/, 0 PHASE_6T files). Requires a committed campaign '
    'manifest plus exchange order/fill history for the campaign window.'
)
SCEN_NOTE = (
    'TN-CAMPAIGN-EVIDENCE: no campaign-specific evidence. Citation is a shared risk-gate '
    'semantics report covering 14 rows; it has a row-keyed check name but every check has '
    'an empty detail and names no scenario, order or fill outcome. Required proof is a '
    'predeclared testnet scenario with exchange parity.'
)
EMPTY_NOTE = (
    'TN-CAMPAIGN-EVIDENCE: not tested. No evidence existed: no evidence_ref, no '
    'tested_commit, no campaign/order/fill record. Needs a predeclared testnet scenario '
    'or a documented unblock.'
)

VERDICT = {rid: CAMP_NOTE for rid in CAMP}
VERDICT.update({rid: SCEN_NOTE for rid in SCEN})
VERDICT.update({rid: EMPTY_NOTE for rid in EMPTY})


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    jpath = os.path.join(root, 'certification', 'certification_matrix.json')
    cpath = os.path.join(root, 'certification', 'certification_matrix.csv')
    with open(jpath, encoding='utf-8') as fh:
        matrix = json.load(fh)

    touched = []
    for rec in matrix['records']:
        rid = rec['id']
        if rid not in VERDICT:
            continue
        if rec.get('result') != 'NOT_TESTED':
            touched.append((rid, rec.get('result')))
        rec['result'] = 'NOT_TESTED'
        rec['evidence_ref'] = ART
        rec['tested_commit'] = ''
        rec['tested_at_utc'] = ''
        rec['notes'] = VERDICT[rid]

    with open(jpath, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(matrix, fh, indent=1, ensure_ascii=False)
        fh.write('\n')

    by_id = {r['id']: r for r in matrix['records']}
    with open(cpath, encoding='utf-8', newline='') as fh:
        rows = list(csv.reader(fh))
    idx = {n: i for i, n in enumerate(rows[0])}
    for row in rows[1:]:
        rid = row[idx['id']]
        if rid not in VERDICT:
            continue
        rec = by_id[rid]
        for f in ('result', 'evidence_ref', 'tested_commit', 'tested_at_utc', 'notes'):
            if f in idx:
                row[idx[f]] = str(rec.get(f) or '')
    with open(cpath, 'w', encoding='utf-8', newline='') as fh:
        csv.writer(fh, lineterminator='\n').writerows(rows)

    print('demoted:', len(touched))
    for rid, old in touched:
        print('  ', rid, old, '-> NOT_TESTED')
    print('rows unchanged that were already NOT_TESTED:', len(VERDICT) - len(touched))


if __name__ == '__main__':
    main()
