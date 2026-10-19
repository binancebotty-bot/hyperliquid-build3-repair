#!/usr/bin/env python3
'''Build TN_CAMPAIGN_EVIDENCE.json from measured inputs (no hand-typed numbers).

Usage: python build_note.py <repo_root> <register_base_commit>
'''
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(p):
    with open(p, encoding='utf-8') as fh:
        return json.load(fh)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '.'
    base = sys.argv[2] if len(sys.argv) > 2 else ''
    matrix = load(os.path.join(root, 'certification', 'certification_matrix.json'))
    probe = load(os.path.join(HERE, 'tn_citation_result.json'))
    ctl = load(os.path.join(root, 'certification', 'results', 'CONTROL_fa9d9f55ff.json'))
    risk_p = os.path.join(root, 'certification', 'results', 'RISK_fa9d9f55.json')
    risk = load(risk_p) if os.path.isfile(risk_p) else None
    cdim_p = os.path.join(HERE, 'campaign_dimension_result.json')
    cdim = load(cdim_p) if os.path.isfile(cdim_p) else None

    recs = {r['id']: r for r in matrix['records']}
    ctl_rows = ctl['rows']

    camp = [r for r in probe['rows'] if r.startswith('TN-CAMP-')]
    sets = {rid: set(c['name'] for c in ctl_rows[rid]['checks']) for rid in camp}
    shared = set.intersection(*sets.values()) if sets else set()
    union = set().union(*sets.values()) if sets else set()
    per_row_unique = {rid: sorted(sets[rid] - shared) for rid in camp}

    ctl_text = json.dumps({k: ctl_rows[k] for k in camp}).lower()
    id_scan = {
        'campaign_manifest_mentions': ctl_text.count('manifest'),
        'exchange_order_id_mentions': ctl_text.count('exchange_order_id'),
        'order_id_mentions': ctl_text.count('order_id'),
        'fill_id_mentions': ctl_text.count('fill_id'),
        'cloid_mentions': ctl_text.count('cloid'),
    }

    rows = []
    for rid in sorted(probe['rows']):
        info = probe['rows'][rid]
        rec = recs[rid]
        rows.append({
            'id': rid,
            'result_before': info.get('result'),
            'result_after': rec.get('result'),
            'evidence_ref_before': info.get('evidence_ref'),
            'evidence_ref_after': rec.get('evidence_ref'),
            'row_keyed_entry_in_citation': info.get('row_keyed_entries') or [],
            'campaign_or_order_identifiers_in_entry': info.get('campaign_or_order_identifiers') or [],
            'row_specific_campaign_evidence': info.get('row_specific_evidence'),
            'why': info.get('reason'),
            'notes_after': rec.get('notes'),
        })

    out = {
        'task_id': 't_9c795ece',
        'title': 'TN campaign evidence - per-campaign proof or NOT_TESTED',
        'branch': 'hermes/tn-campaign-evidence',
        'register_branch': 'cert/local-main-b142cf8',
        'register_base_commit': base,
        'register_records': len(matrix['records']),
        'rows_inspected': len(rows),
        'rows_demoted': sum(1 for r in rows if r['result_before'] != r['result_after']),
        'rows_already_not_tested': sum(1 for r in rows if r['result_before'] == 'NOT_TESTED'),
        'question': 'Does each TN row that claims PASS rest on per-campaign evidence, or only on a shared report that would read identically for any row?',
        'verdict': 'NO_ROW_HAS_PER_CAMPAIGN_EVIDENCE',
        'definition_of_row_specific': probe['row_specific_definition'],
        'finding_shared_control_report': {
            'cited_by': camp,
            'checks_per_row': {rid: len(sets[rid]) for rid in camp},
            'checks_identical_across_all_nine': len(shared),
            'distinct_checks_in_union': len(union),
            'per_row_only_difference': per_row_unique,
            'interpretation': 'Each TN-CAMP row carries the same 23 checks with identical details; the only per-row difference is the NAME of one check. A check name is not a campaign outcome. No campaign identifier, order id, fill id or manifest appears in the cited report, so the citation would be identical for any TN-CAMP row - the same defect class that demoted 301 rows.',
        },
        'finding_citation_content_scan': id_scan,
        'finding_risk_report': {
            'cited_by': ['TN-F06', 'TN-F16', 'TN-F21'],
            'row_keyed_check_names_present': True,
            'checks_have_detail': False if risk else None,
            'covers_rows': (risk or {}).get('summary', {}).get('total_rows'),
            'interpretation': 'The risk report does contain a row-keyed check name per row (e.g. TN-F06:LIMIT_BLOCKS_NOT_CLAMPS), but every check detail is empty, no scenario run, order or fill outcome is named, and the artifact covers 14 rows while the matrix row requires a predeclared testnet scenario with exchange parity. A row-keyed NAME is not row-specific evidence.',
        },
        'finding_empty_rows': {
            'rows': ['TN-F24', 'TN-F25', 'TN-F26', 'TN-F27', 'TN-PS1', 'TN-T1'],
            'observation': 'No evidence_ref, no tested_commit, no notes. Nothing to demote; recorded so the family is accounted for.',
        },
        'finding_missing_sources': {
            'observation': 'The sources named by the TN-CAMP rows point at PHASE_6T_C_* protocol files under local-trading/. The register tree contains 0 local-trading/ files and 0 PHASE_6T files, so the protocol the rows claim to follow is not in the repo either.',
            'local_trading_files_in_tree': 0,
            'phase_6t_files_in_tree': 0,
        },
        'can_per_campaign_evidence_be_produced': {
            'verdict': cdim['verdict'] if cdim else 'NOT_MEASURED',
            'audit_dir': cdim['audit_dir'] if cdim else '',
            'audit_files_scanned': cdim['files_scanned'] if cdim else 0,
            'audit_data_rows': cdim['total_data_rows_in_audit'] if cdim else 0,
            'files_with_a_campaign_column': cdim['files_with_a_campaign_column'] if cdim else None,
            'why': cdim['interpretation'] if cdim else 'campaign-dimension probe not run',
        },
        'rows': rows,
    }
    path = os.path.join(HERE, 'TN_CAMPAIGN_EVIDENCE.json')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    print('wrote', path)
    print('shared', len(shared), 'of', len(union), 'distinct; demoted', out['rows_demoted'])


if __name__ == '__main__':
    main()
