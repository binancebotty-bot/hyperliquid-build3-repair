#!/usr/bin/env python3
'''PASS-row provenance audit, UI part 3 of 4 (READ-ONLY).

Reproduces the SAME criteria and output shape as the CI model
EVIDENCE/provenance/PASS_AUDIT_b142cf88d3.json (commit 8b8c114) and part 2
EVIDENCE/provenance/PASS_AUDIT_UIPA2_b142cf88d3.json (commit 9a7ae8d), extended
to the THIRD quarter (by id order) of the UI area's PASS rows of the register
of record.

Per row, from git show main:certification/certification_matrix.json:
  1. read the row's OWN execution_proof / independent_oracle / negative_tests /
     evidence_ref / tested_commit;
  2. hash the cited evidence blob, confirm it exists;
  3. does the cited file carry a record for THIS row id?  (UI evidence stores
     per-row proof as checks keyed ``<ROWID>:<SUFFIX>`` and negative_tests keyed
     ``<ROWID>:<SUFFIX>``);
  4. does that record say PASS and carry its OWN non-blank executed-proof detail?
     A blank detail field is a DEMOTE reason;
  5. are the checks owned by this row, or SHARED/carried from a sibling?  A check
     whose (suffix, detail) pair appears on more than one row is CARRIED.  A row
     left with <=1 owned check is DEMOTE;
  6. list every cited hash and whether it resolves (LOCAL repo).  Hashes must be
     re-checked against the J15 branch later; this run reports LOCAL only.

Never writes to the matrix, any evidence file, or apply_verified_results.py.
'''
import json, hashlib, subprocess, collections

REPO = 'C:/Users/wigmore/hyperliquid-build3-repair'
REG = 'main'
MATRIX = 'certification/certification_matrix.json'
OUT = 'EVIDENCE/provenance/PASS_AUDIT_UIPA3_b142cf88d3.json'
PART = 3
NPARTS = 4


def git_show(path):
    return subprocess.run(['git', '-C', REPO, 'show', REG + ':' + path],
                          capture_output=True).stdout


def sha256(b):
    return hashlib.sha256(b).hexdigest()


matrix_bytes = git_show(MATRIX)
matrix = json.loads(matrix_bytes.decode('utf-8-sig'))
main_commit = subprocess.run(['git', '-C', REPO, 'rev-parse', REG],
                             capture_output=True).stdout.decode().strip()

ui = [r for r in matrix['records'] if r['area'] == 'UI']
ui_pass = [r for r in ui if r['result'] == 'PASS']
q = len(ui_pass) // NPARTS
scope = ui_pass[(PART - 1) * q: PART * q]

# group cited evidence blobs
ev_cache = {}
shared = collections.Counter()
for r in scope:
    ref = r.get('evidence_ref')
    if ref not in ev_cache:
        ev_cache[ref] = git_show(ref)

ev = {ref: json.loads(b.decode('utf-8-sig')) for ref, b in ev_cache.items()}

# build the carried-check counter across the WHOLE evidence file (siblings included)
for ref, e in ev.items():
    for k, v in (e.get('checks') or {}).items():
        if ':' in k:
            shared[(k.split(':', 1)[1], str(v.get('detail')))] += 1

report = {
    'audit': 'PASS-row evidence provenance (UI, part %d of %d)' % (PART, NPARTS),
    'register_of_record_ref': REG,
    'register_of_record_commit': main_commit,
    'matrix_sha256': sha256(matrix_bytes),
    'read_only': True,
    'scope': {
        'area': 'UI',
        'part': PART,
        'of': NPARTS,
        'ui_pass_rows_total': len(ui_pass),
        'quarter_size': q,
        'first_row': scope[0]['id'] if scope else None,
        'last_row': scope[-1]['id'] if scope else None,
    },
    'areas': {},
    'demotion_list': [],
}

per_row = {}
kept = demoted = 0
reasons_tally = collections.Counter()

for r in scope:
    rid = r['id']
    ref = r.get('evidence_ref')
    e = ev.get(ref)
    checks = (e.get('checks') or {}) if e else {}
    neg = (e.get('negative_tests') or {}) if e else {}
    own = {k: v for k, v in checks.items() if k == rid or k.startswith(rid + ':')}
    own_neg = {k: v for k, v in neg.items() if k == rid or k.startswith(rid + ':')}

    rec_present = bool(own) or bool(own_neg)
    rec_pass = bool(own) and all(v.get('pass') is True for v in own.values())
    blank = (not own) or all(not (v.get('detail') or '').strip() for v in own.values())
    n_shared = sum(1 for k, v in own.items()
                   if shared[(k.split(':', 1)[1], str(v.get('detail')))] > 1)
    n_own = len(own) - n_shared

    reasons = []
    if not rec_present:
        reasons.append('no record for this row id in the cited file')
    elif not rec_pass:
        reasons.append('cited record does not say PASS')
    elif blank:
        reasons.append('record present but carries NO executed-proof detail (blank)')
    if rec_pass and n_shared and n_own <= 1:
        reasons.append('per-row proof is CARRIED: %d of %d checks are '
                       'byte-identical boilerplate shared across rows'
                       % (n_shared, len(own)))

    verdict = 'DEMOTE' if reasons else 'KEEP'
    if verdict == 'DEMOTE':
        demoted += 1
        for x in reasons:
            reasons_tally[x.split(':')[0]] += 1
        report['demotion_list'].append({'area': 'UI', 'id': rid, 'reasons': reasons})
    else:
        kept += 1

    # cited hashes: tested_commit and every 64-hex token in the row's own evidence checks
    hashes = {}
    tc = r.get('tested_commit') or ''
    if tc:
        hashes[tc] = subprocess.run(['git', '-C', REPO, 'cat-file', '-t', tc],
                                    capture_output=True).stdout.decode().strip() or 'MISSING'
    for v in own.values():
        for tok in str(v.get('detail') or '').replace('=', ' ').split():
            if len(tok) == 64 and all(c in '0123456789abcdef' for c in tok.lower()):
                hashes[tok] = subprocess.run(['git', '-C', REPO, 'cat-file', '-t', tok],
                                             capture_output=True).stdout.decode().strip() or 'MISSING'

    per_row[rid] = {
        'evidence_ref': ref,
        'record_present': rec_present,
        'record_says_pass': rec_pass,
        'detail_blank': blank,
        'checks': len(own),
        'negative_tests': len(own_neg),
        'checks_shared_with_other_rows': n_shared,
        'checks_owned_by_this_row': n_own,
        'declared_execution_proof': r.get('execution_proof', ''),
        'declared_independent_oracle': r.get('independent_oracle', ''),
        'declared_negative_tests': r.get('negative_tests', []),
        'tested_commit': tc,
        'cited_hashes': hashes,
        'verdict': verdict,
        'reasons': reasons,
    }

# global (non-row-bound) checks in the cited evidence file: recorded proof that no
# single row owns. Listed for completeness + hash resolution.
global_checks = {}
for ref, e in ev.items():
    for k, v in (e.get('checks') or {}).items():
        if ':' not in k or not any(k.startswith(r['id'] + ':') for r in ui_pass):
            toks = [t for t in str(v.get('detail') or '').replace('=', ' ').split()
                    if len(t) == 64 and all(c in '0123456789abcdef' for c in t.lower())]
            global_checks[k] = {
                'evidence_ref': ref,
                'pass': v.get('pass'),
                'detail': v.get('detail'),
                'cited_hashes': {t: (subprocess.run(['git', '-C', REPO, 'cat-file', '-t', t],
                                                    capture_output=True).stdout.decode().strip() or 'MISSING')
                                 for t in toks},
            }

report['areas']['UI'] = {
    'matrix_rows': len(ui),
    'matrix_pass_rows': len(ui_pass),
    'scope_rows': len(scope),
    'evidence_refs': sorted({r.get('evidence_ref') for r in scope}),
    'evidence_blob_sha256': {ref: sha256(b) for ref, b in ev_cache.items()},
    'pass_rows_kept': kept,
    'pass_rows_demoted': demoted,
    'demote_reasons_tally': dict(reasons_tally),
    'global_checks': global_checks,
    'per_row': per_row,
}

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=1)

print('UI part %d/%d: %d rows in scope (%s .. %s)'
      % (PART, NPARTS, len(scope), report['scope']['first_row'], report['scope']['last_row']))
print('KEEP: %d   DEMOTE: %d' % (kept, demoted))
print('demote reason tally:', dict(reasons_tally))
print('wrote', OUT)
