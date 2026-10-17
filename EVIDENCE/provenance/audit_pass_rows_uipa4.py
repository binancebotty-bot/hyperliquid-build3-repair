#!/usr/bin/env python3
"""
PASS-row evidence provenance audit — UI part 4 (of 4)
Scope: UI-FP-091 .. UI-FP-197 (78 rows, fourth quarter by id order)

Criteria (from CI model PASS_AUDIT_b142cf88d3.json):
1. Record present in evidence file for this row id?
2. Record says PASS?
3. Detail non-blank (executed-proof detail present)?
4. Checks owned by this row (not byte-identical to a sibling's detail)?

Read-only: does NOT modify any evidence file, matrix, or apply_verified_results.py.
"""
import json, subprocess, hashlib, sys, os

REPO = os.environ.get('REPO', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def git_show(ref, path):
    r = subprocess.run(['git', 'show', f'{ref}:{path}'], capture_output=True, cwd=REPO)
    if r.returncode != 0:
        return None
    return r.stdout.decode('utf-8')

def main():
    # 1. Read register of record
    matrix_json = git_show('main', 'certification/certification_matrix.json')
    if not matrix_json:
        print("ERROR: cannot read certification_matrix.json from main")
        sys.exit(1)
    matrix = json.loads(matrix_json)
    matrix_sha256 = hashlib.sha256(matrix_json.encode('utf-8')).hexdigest()
    records = matrix.get('records', [])

    # 2. Get UI PASS rows and extract quarter 4
    ui_pass = [r for r in records if r.get('area') == 'UI' and r.get('result') == 'PASS']
    q4_rows = ui_pass[236:]  # 78 rows
    q4_ids = [r['id'] for r in q4_rows]

    # 3. Read evidence file
    evidence_json = git_show('main', 'certification/results/UI_CORRECTION_2d29211.json')
    if not evidence_json:
        print("ERROR: cannot read UI_CORRECTION_2d29211.json from main")
        sys.exit(1)
    evidence = json.loads(evidence_json)
    checks = evidence.get('checks', {})
    evidence_sha256 = hashlib.sha256(evidence_json.encode('utf-8')).hexdigest()

    # 4. Build detail -> set of row_ids (for shared/carried detection)
    detail_to_rows = {}
    for key, val in checks.items():
        row_id = key.split(':')[0]
        detail = val.get('detail', '')
        if detail not in detail_to_rows:
            detail_to_rows[detail] = set()
        detail_to_rows[detail].add(row_id)

    # 5. Build row -> checks map
    row_checks = {}
    for key, val in checks.items():
        row_id = key.split(':')[0]
        if row_id not in row_checks:
            row_checks[row_id] = []
        row_checks[row_id].append((key, val))

    # 6. Audit each Q4 row
    per_row = {}
    demote_reasons_tally = {}

    for row in q4_rows:
        rid = row['id']
        evidence_ref = row.get('evidence_ref', '')
        tested_commit = row.get('tested_commit', '')
        execution_proof = row.get('execution_proof', '')
        independent_oracle = row.get('independent_oracle', '')

        row_check_list = row_checks.get(rid, [])
        record_present = len(row_check_list) > 0

        if not record_present:
            per_row[rid] = {
                'evidence_ref': evidence_ref,
                'record_present': False,
                'record_says_pass': False,
                'detail_blank': True,
                'checks': 0,
                'checks_shared_with_other_rows': 0,
                'checks_owned_by_this_row': 0,
                'declared_execution_proof': execution_proof,
                'declared_independent_oracle': independent_oracle,
                'tested_commit': tested_commit,
                'verdict': 'DEMOTE',
                'reasons': ['no record in evidence file for this row id']
            }
            demote_reasons_tally['no_record'] = demote_reasons_tally.get('no_record', 0) + 1
            continue

        all_pass = True
        any_blank = False
        details = []
        for key, val in row_check_list:
            if not val.get('pass', False):
                all_pass = False
            detail = val.get('detail', '')
            if not detail or detail.strip() == '':
                any_blank = True
            details.append(detail)

        # Determine owned vs shared
        shared_count = 0
        owned_count = 0
        for detail in details:
            rows_using = detail_to_rows.get(detail, set())
            if len(rows_using) > 1:
                shared_count += 1
            else:
                owned_count += 1

        # Determine verdict
        reasons = []
        if not all_pass:
            reasons.append('record does not say PASS')
        if any_blank:
            reasons.append('record present but carries NO executed-proof detail (blank)')
        if shared_count > 0 and owned_count == 0:
            reasons.append(f'all {shared_count} check(s) carried/shared (byte-identical to sibling)')
        elif shared_count > 0:
            reasons.append(f'{shared_count} of {shared_count + owned_count} checks carried/shared')

        if reasons:
            verdict = 'DEMOTE'
            for r in reasons:
                key = r.split('(')[0].strip()
                demote_reasons_tally[key] = demote_reasons_tally.get(key, 0) + 1
        else:
            verdict = 'KEEP'

        per_row[rid] = {
            'evidence_ref': evidence_ref,
            'record_present': True,
            'record_says_pass': all_pass,
            'detail_blank': any_blank,
            'checks': len(row_check_list),
            'checks_shared_with_other_rows': shared_count,
            'checks_owned_by_this_row': owned_count,
            'declared_execution_proof': execution_proof,
            'declared_independent_oracle': independent_oracle,
            'tested_commit': tested_commit,
            'verdict': verdict,
            'reasons': reasons
        }

    keep_count = sum(1 for r in per_row.values() if r['verdict'] == 'KEEP')
    demote_count = sum(1 for r in per_row.values() if r['verdict'] == 'DEMOTE')
    demote_ids = [rid for rid, r in per_row.items() if r['verdict'] == 'DEMOTE']

    # 7. Output results
    print(f"UI PASS-row evidence audit — part 4 (of 4)")
    print(f"Scope: {q4_ids[0]}..{q4_ids[-1]} ({len(q4_ids)} rows)")
    print(f"Register of record: main @ b142cf88d389e791160f691aac3d936852b99975")
    print(f"Matrix sha256: {matrix_sha256}")
    print(f"Evidence: certification/results/UI_CORRECTION_2d29211.json")
    print(f"Evidence blob sha256: {evidence_sha256}")
    print(f"Evidence rows in file: {len(checks)}")
    print(f"")
    print(f"Results: {keep_count} KEEP / {demote_count} DEMOTE")
    print(f"Demote reasons tally: {json.dumps(demote_reasons_tally)}")
    print(f"")
    print(f"DEMOTE IDs ({len(demote_ids)}):")
    for rid in demote_ids:
        r = per_row[rid]
        print(f"  {rid}: {r['reasons']}")
    print(f"")
    print(f"KEEP IDs ({keep_count}):")
    for rid in q4_ids:
        if per_row[rid]['verdict'] == 'KEEP':
            print(f"  {rid}: checks={per_row[rid]['checks']}, owned={per_row[rid]['checks_owned_by_this_row']}")

    # 8. Hash resolution (local only)
    tested_commit = '2d29211148c9ba8498bade2d5791ed908f193708'
    r = subprocess.run(['git', 'cat-file', '-t', tested_commit], capture_output=True, cwd=REPO)
    tc_type = r.stdout.decode().strip() if r.returncode == 0 else 'MISSING_local'
    print(f"")
    print(f"Hash resolution (LOCAL ONLY — re-check against origin/cert/local-main-b142cf8 after J15):")
    print(f"  tested_commit {tested_commit}: {tc_type}")
    engine_sha = evidence.get('engine_sha256', '')
    r2 = subprocess.run(['git', 'cat-file', '-t', engine_sha], capture_output=True, cwd=REPO)
    es_type = r2.stdout.decode().strip() if r2.returncode == 0 else 'MISSING_local (content hash, not a git object)'
    print(f"  engine_sha256 {engine_sha}: {es_type}")

if __name__ == '__main__':
    main()
