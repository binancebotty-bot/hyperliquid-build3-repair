#!/usr/bin/env python3
'''Measure, per TN row, whether the cited evidence is row-specific.

Row-specific means: the cited artifact contains an entry keyed by that row id
AND that entry names a campaign / order / fill identifier. A citation whose
content would be identical for any row is NOT row-specific.

Read-only. Writes one JSON result file.

Usage: python probe_tn_citation.py <matrix.json> <result_root> <out.json>
'''
import json
import os
import re
import sys

TN_ROWS = (
    ['TN-CAMP-0%d' % i for i in range(1, 10)]
    + ['TN-F06', 'TN-F16', 'TN-F21']
    + ['TN-F24', 'TN-F25', 'TN-F26', 'TN-F27']
    + ['TN-PS1', 'TN-T1']
)

IDENT = re.compile(r'(B3-[A-Za-z0-9-]+|cloid|oid\b|order_id|exchange_order_id|fill_id|copy_fill_id)')


def entries_for(doc, row_id):
    '''Return [(key, value)] for dict keys that embed the row id.'''
    found = []

    def rec(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(k, str) and row_id in k:
                    found.append((k, v))
                rec(v)
        elif isinstance(node, list):
            for v in node:
                rec(v)

    rec(doc)
    return found


def check_names(entry):
    v = entry
    if isinstance(v, dict) and isinstance(v.get('checks'), list):
        return [c.get('name') for c in v['checks'] if isinstance(c, dict)]
    return []


def main():
    matrix_path, result_root, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    with open(matrix_path, encoding='utf-8') as fh:
        matrix = json.load(fh)
    recs = {r['id']: r for r in matrix['records']}

    cache = {}
    rows = {}
    for rid in TN_ROWS:
        r = recs.get(rid)
        if r is None:
            rows[rid] = {'present_in_matrix': False}
            continue
        ref = (r.get('evidence_ref') or '').strip()
        info = {
            'present_in_matrix': True,
            'result': r.get('result'),
            'evidence_ref': ref,
            'tested_commit': r.get('tested_commit') or '',
            'cited_file_exists': False,
            'row_keyed_entries': [],
            'campaign_or_order_identifiers': [],
            'row_specific_evidence': False,
            'reason': '',
        }
        if not ref:
            info['reason'] = 'no evidence_ref at all'
            rows[rid] = info
            continue
        path = os.path.join(result_root, ref.replace('/', os.sep))
        if not os.path.isfile(path):
            path = os.path.join(result_root, os.path.basename(ref))
        info['cited_path_checked'] = path
        if not os.path.isfile(path):
            info['reason'] = 'cited file not found under result root'
            rows[rid] = info
            continue
        info['cited_file_exists'] = True
        if path not in cache:
            with open(path, encoding='utf-8') as fh:
                cache[path] = json.load(fh)
        doc = cache[path]
        ents = entries_for(doc, rid)
        info['row_keyed_entries'] = [k for k, _ in ents]
        idents = sorted(set(IDENT.findall(json.dumps([v for _, v in ents]))))
        info['campaign_or_order_identifiers'] = idents
        info['row_specific_evidence'] = bool(ents) and bool(idents)
        if not ents:
            info['reason'] = 'cited artifact has no entry keyed by this row id (citation would be identical for any row)'
        elif not idents:
            info['reason'] = 'cited artifact has a row-keyed entry but it names no campaign/order/fill identifier'
        else:
            info['reason'] = 'row-keyed entry naming: ' + ', '.join(idents)
        rows[rid] = info

    camp = [rid for rid in TN_ROWS if rid.startswith('TN-CAMP-')]
    per_row = {}
    for rid in camp:
        ref = recs[rid].get('evidence_ref') or ''
        path = os.path.join(result_root, ref.replace('/', os.sep))
        if path not in cache:
            path = os.path.join(result_root, os.path.basename(ref))
        doc = cache.get(path)
        ents = entries_for(doc, rid) if doc else []
        per_row[rid] = check_names(ents[0][1]) if ents else []

    shared = set(per_row[camp[0]]) if camp and per_row[camp[0]] else set()
    for rid in camp[1:]:
        shared &= set(per_row[rid])
    union = set()
    for rid in camp:
        union |= set(per_row[rid])

    out = {
        'task_id': 't_9c795ece',
        'matrix_measured': matrix_path,
        'result_root': result_root,
        'row_specific_definition': 'cited artifact contains an entry keyed by the row id AND that entry names a campaign/order/fill identifier',
        'rows': rows,
        'tn_camp_shared_checks': {
            'rows': camp,
            'shared_by_all_nine': sorted(shared),
            'shared_count': len(shared),
            'per_row_check_count': {rid: len(per_row[rid]) for rid in camp},
            'row_unique_checks': {rid: sorted(set(per_row[rid]) - shared) for rid in camp},
            'union_count': len(union),
        },
        'verdict_counts': {
            'row_specific_true': sum(1 for v in rows.values() if v.get('row_specific_evidence')),
            'row_specific_false': sum(1 for v in rows.values() if v.get('present_in_matrix') and not v.get('row_specific_evidence')),
        },
    }
    with open(out_path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
        fh.write('\n')
    print('wrote', out_path)
    print('row_specific true/false:', out['verdict_counts'])
    print('shared checks across all nine TN-CAMP rows:', len(shared), 'of', len(union), 'distinct')


if __name__ == '__main__':
    main()
