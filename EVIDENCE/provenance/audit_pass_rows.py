#!/usr/bin/env python3
'''PASS-row provenance audit (READ-ONLY).

Answers, per PASS row in the REGRESSION and CONTROL areas of the register of
record, whether the cited evidence file actually records THAT row as PASS with
its OWN executed proof matching the row's declared execution_proof +
independent_oracle -- or whether the status is carried / unbound.

Reads the register of record via `git show main:certification/certification_matrix.json`
and the cited evidence blobs via `git show main:<evidence_ref>`.
Never writes to the matrix, the evidence files, or apply_verified_results.py.
'''
import json, hashlib, subprocess, collections, sys

REPO = 'C:/Users/wigmore/hyperliquid-build3-repair'
REG = 'main'
MATRIX = 'certification/certification_matrix.json'
OUT = 'evidence/provenance/PASS_AUDIT_b142cf88d3.json'

def git_show(path):
    return subprocess.run(['git', '-C', REPO, 'show', REG + ':' + path],
                          capture_output=True).stdout

def sha256(b):
    return hashlib.sha256(b).hexdigest()

matrix_bytes = git_show(MATRIX)
matrix = json.loads(matrix_bytes.decode('utf-8-sig'))
records = {r['id']: r for r in matrix['records']}
main_commit = subprocess.run(['git','-C',REPO,'rev-parse','main'],capture_output=True).stdout.decode().strip()

report = {
    'audit': 'PASS-row evidence provenance (REGRESSION + CONTROL)',
    'register_of_record_ref': 'main',
    'register_of_record_commit': main_commit,
    'matrix_sha256': sha256(matrix_bytes),
    'read_only': True,
    'areas': {},
    'demotion_list': [],
}

for area, ev_ref in (('REGRESSION','certification/results/REGRESSION_fa9d9f55ff.json'),
                     ('CONTROL','certification/results/CONTROL_fa9d9f55ff.json')):
    rows = [r for r in matrix['records'] if r['area'] == area]
    pass_rows = [r for r in rows if r['result'] == 'PASS']
    ev_bytes = git_show(ev_ref)
    ev = json.loads(ev_bytes.decode('utf-8-sig'))
    ev_rows = ev.get('results') or ev.get('rows')
    per_row = {}
    shared = collections.Counter()
    for rid, v in ev_rows.items():
        for c in v.get('checks', []):
            shared[(c.get('name'), str(c.get('detail')))] += 1
    carried = 0
    for r in pass_rows:
        rid = r['id']
        rec = ev_rows.get(rid)
        rec_pass = bool(rec and rec.get('result', rec.get('pass')) in ('PASS', True))
        checks = rec.get('checks', []) if rec else []
        blank = all((c.get('detail') or '') == '' for c in checks) if checks else True
        # a check is 'carried' if its (name,detail) pair is identical across >1 row
        n_shared = sum(1 for c in checks if shared[(c.get('name'), str(c.get('detail')))] > 1)
        n_own = len(checks) - n_shared
        verdict = 'BOUND'
        reasons = []
        if rec is None:
            verdict = 'DEMOTE'; reasons.append('no record for this row id in the cited file')
        elif not rec_pass:
            verdict = 'DEMOTE'; reasons.append('cited record does not say PASS')
        elif blank:
            verdict = 'DEMOTE'; reasons.append('record present but carries NO executed-proof detail (blank)')
        if rec_pass and n_shared and n_own <= 1:
            verdict = 'DEMOTE'; reasons.append(
                'per-row proof is CARRIED: %d of %d checks are byte-identical boilerplate shared across rows'
                % (n_shared, len(checks)))
        if verdict == 'DEMOTE':
            carried += 1
            report['demotion_list'].append({'area': area, 'id': rid, 'reasons': reasons})
        per_row[rid] = {
            'evidence_ref': ev_ref,
            'record_present': rec is not None,
            'record_says_pass': rec_pass,
            'detail_blank': blank,
            'checks': len(checks),
            'checks_shared_with_other_rows': n_shared,
            'checks_owned_by_this_row': n_own,
            'declared_execution_proof': r.get('execution_proof', ''),
            'declared_independent_oracle': r.get('independent_oracle', ''),
            'tested_commit': r.get('tested_commit', ''),
            'verdict': verdict,
            'reasons': reasons,
        }
    report['areas'][area] = {
        'matrix_rows': len(rows),
        'matrix_pass_rows': len(pass_rows),
        'evidence_ref': ev_ref,
        'evidence_blob_sha256': sha256(ev_bytes),
        'evidence_rows_in_file': len(ev_rows),
        'pass_rows_demoted': carried,
        'per_row': per_row,
    }

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=1)

for area, a in report['areas'].items():
    print('%s: %d PASS rows, %d demoted' % (area, a['matrix_pass_rows'], a['pass_rows_demoted']))
print('demotion_list total:', len(report['demotion_list']))
print('wrote', OUT)
