#!/usr/bin/env python3
'''PASS-row provenance audit: RISK + WALLET + SETTLE + LIFECYCLE (READ-ONLY).

Reproduces the SAME criteria and output shape as the CI model
EVIDENCE/provenance/PASS_AUDIT_b142cf88d3.json (commit 8b8c114) and its refined
part-2 sibling EVIDENCE/provenance/PASS_AUDIT_UIPA2_b142cf88d3.json (commit 9a7ae8d),
extended to the remaining PASS rows: areas RISK, WALLET, SETTLE, LIFECYCLE.

Per row, from git show main:certification/certification_matrix.json:
  1. read the row's OWN execution_proof / independent_oracle / negative_tests /
     evidence_ref / tested_commit;
  2. hash the cited evidence blob, confirm it exists;
  3. does the cited file carry a record for THIS row id?
     Two evidence shapes occur in this scope:
       SHAPE A (flat keyed): checks is a dict keyed ``<ROWID>:<SUFFIX>``
         -- RISK_fa9d9f55.json, NET_LIFE_SETTLE_fa9d9f55ff.json
       SHAPE B (nested rows): rows is a dict keyed ``<ROWID>`` whose value holds
         ``result`` + a ``checks`` LIST of {name,pass,detail}
         -- WALLET_fa9d9f55ff.json, NLS_RESIDUAL_2a269ad226.json
  4. does that record say PASS and carry its OWN non-blank executed-proof detail?
     A blank detail field is a DEMOTE reason;
  5. are the checks owned by this row, or SHARED/carried from a sibling?  A check
     whose (name, detail) pair appears on more than one row is CARRIED.  A row
     left with <=1 owned check is DEMOTE;
  6. list every cited hash and whether it resolves (LOCAL repo).  Hashes must be
     re-checked against the J15 branch later; this run reports LOCAL only.

Never writes to the matrix, any evidence file, or apply_verified_results.py.
'''
import json, hashlib, subprocess, collections, os

REPO = 'C:/Users/wigmore/hyperliquid-build3-repair'
REG = 'main'
MATRIX = 'certification/certification_matrix.json'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'PASS_AUDIT_NONUI2_b142cf88d3.json')
AREAS = ('RISK', 'WALLET', 'SETTLE', 'LIFECYCLE')
HEX = set('0123456789abcdef')


def git_show(path):
    return subprocess.run(['git', '-C', REPO, 'show', REG + ':' + path],
                          capture_output=True).stdout


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def resolve(obj):
    out = subprocess.run(['git', '-C', REPO, 'cat-file', '-t', obj],
                         capture_output=True).stdout.decode().strip()
    return out or 'MISSING'


def is_hash(tok):
    return len(tok) == 64 and all(c in HEX for c in tok.lower())


def hashes_in(text):
    return [t for t in str(text or '').replace('=', ' ').split() if is_hash(t)]


# --- normalise an evidence file into {rowid: {result, checks:[{name,pass,detail}], negs:[...]}} ---
def normalise(ev):
    norm = {}
    checks = ev.get('checks')
    rows = ev.get('rows')
    if isinstance(rows, dict):
        # SHAPE B
        for rid, v in rows.items():
            if not isinstance(v, dict):
                continue
            norm[rid] = {
                'result': v.get('result'),
                'checks': [dict(c) for c in (v.get('checks') or [])],
                'negs': [dict(c) for c in (v.get('negative_tests') or [])],
            }
    elif isinstance(checks, dict):
        # SHAPE A -- key ``<ROWID>:<SUFFIX>``; group by row id
        for k, v in checks.items():
            if not isinstance(v, dict):
                continue
            rid = v.get('row_id') if v.get('row_id') else (k.split(':', 1)[0] if ':' in k else k)
            name = v.get('check_name') or (k.split(':', 1)[1] if ':' in k else k)
            norm.setdefault(rid, {'result': None, 'checks': [], 'negs': []})
            norm[rid]['checks'].append({'name': name, 'pass': v.get('pass'),
                                        'detail': v.get('detail')})
        negs = ev.get('negative_tests')
        if isinstance(negs, dict):
            for k, v in negs.items():
                if not isinstance(v, dict):
                    continue
                rid = v.get('row_id') if v.get('row_id') else (k.split(':', 1)[0] if ':' in k else k)
                name = v.get('test_name') or (k.split(':', 1)[1] if ':' in k else k)
                norm.setdefault(rid, {'result': None, 'checks': [], 'negs': []})
                norm[rid]['negs'].append({'name': name, 'pass': v.get('pass'),
                                          'detail': v.get('detail')})
    return norm


matrix_bytes = git_show(MATRIX)
matrix = json.loads(matrix_bytes.decode('utf-8-sig'))
main_commit = subprocess.run(['git', '-C', REPO, 'rev-parse', REG],
                             capture_output=True).stdout.decode().strip()

scope_rows = [r for r in matrix['records']
              if r['area'] in AREAS and r['result'] == 'PASS']

# load + normalise every distinct cited evidence blob in scope
ev_cache, ev_norm = {}, {}
for r in scope_rows:
    ref = r.get('evidence_ref')
    if ref and ref not in ev_cache:
        b = git_show(ref)
        ev_cache[ref] = b
        ev_norm[ref] = normalise(json.loads(b.decode('utf-8-sig'))) if b else {}

# carried-check counter across the WHOLE evidence file (siblings included)
shared = collections.Counter()
for ref, norm in ev_norm.items():
    for rid, rec in norm.items():
        for c in rec['checks']:
            shared[(c.get('name'), str(c.get('detail')))] += 1

report = {
    'audit': 'PASS-row evidence provenance (RISK + WALLET + SETTLE + LIFECYCLE)',
    'register_of_record_ref': REG,
    'register_of_record_commit': main_commit,
    'matrix_sha256': sha256(matrix_bytes),
    'read_only': True,
    'scope': {'areas': list(AREAS), 'pass_rows_in_scope': len(scope_rows)},
    'areas': {},
    'demotion_list': [],
}

per_row = {}
kept = demoted = 0
reasons_tally = collections.Counter()

for r in scope_rows:
    rid = r['id']
    ref = r.get('evidence_ref')
    rec = (ev_norm.get(ref) or {}).get(rid)
    own = rec['checks'] if rec else []
    own_neg = rec['negs'] if rec else []

    rec_present = rec is not None and (bool(own) or bool(own_neg))
    explicit = rec.get('result') if rec else None
    rec_pass = bool(own) and all(c.get('pass') is True for c in own)
    if explicit is not None:
        rec_pass = rec_pass and str(explicit).upper() == 'PASS'
    blank = (not own) or all(not (c.get('detail') or '').strip() for c in own)

    n_shared = sum(1 for c in own if shared[(c.get('name'), str(c.get('detail')))] > 1)
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
        report['demotion_list'].append({'area': r['area'], 'id': rid, 'reasons': reasons})
    else:
        kept += 1

    # cited hashes: tested_commit + every 64-hex token in this row's own check details
    hashes = {}
    tc = r.get('tested_commit') or ''
    if tc:
        hashes[tc] = resolve(tc)
    for c in own:
        for tok in hashes_in(c.get('detail')):
            hashes[tok] = resolve(tok)

    per_row[rid] = {
        'area': r['area'],
        'evidence_ref': ref,
        'record_present': rec_present,
        'record_says_pass': rec_pass,
        'explicit_result': explicit,
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

# per-area rollup
for area in AREAS:
    rows = [r for r in scope_rows if r['area'] == area]
    refs = sorted({r.get('evidence_ref') for r in rows})
    arows = {rid: v for rid, v in per_row.items() if v['area'] == area}
    report['areas'][area] = {
        'matrix_pass_rows': len(rows),
        'evidence_refs': refs,
        'evidence_blob_sha256': {ref: sha256(ev_cache[ref]) for ref in refs if ref in ev_cache},
        'pass_rows_kept': sum(1 for v in arows.values() if v['verdict'] == 'KEEP'),
        'pass_rows_demoted': sum(1 for v in arows.values() if v['verdict'] == 'DEMOTE'),
        'per_row': arows,
    }

# file-level cited hashes (engine_sha256 etc.) + resolution.
# NOTE: engine_sha256 is a CONTENT hash of the engine source, not a git object
# id, so cat-file will always report it MISSING. Verify it as content: hash the
# engine file at the file's own tested_commit. Same distinction applies to the
# 64-hex tokens in check details.
def engine_content_sha(tested_commit):
    if not tested_commit:
        return None
    for p in ('_archive/hl_stage2/HL_Live_Copy_Service_Core.py',
              'HL_Live_Copy_Service_Core.py'):
        b = subprocess.run(['git', '-C', REPO, 'show', tested_commit + ':' + p],
                           capture_output=True).stdout
        if b:
            return sha256(b), p
    return None, None


ev_files = {}
for ref, b in ev_cache.items():
    if not b:
        ev_files[ref] = {'exists': False}
        continue
    e = json.loads(b.decode('utf-8-sig'))
    eng = e.get('engine_sha256')
    tc = e.get('tested_commit')
    content_sha, content_path = engine_content_sha(tc)
    ev_files[ref] = {
        'exists': True,
        'blob_sha256': sha256(b),
        'tested_commit': tc,
        'tested_commit_resolves': resolve(tc) if tc else None,
        'engine_sha256': eng,
        'engine_sha256_as_git_object': resolve(eng) if eng else None,
        'engine_sha256_as_content':
            ('MATCH' if (eng and content_sha and eng == content_sha)
             else ('MISMATCH' if (eng and content_sha) else 'UNVERIFIED')),
        'engine_content_path': content_path,
        'engine_content_sha256': content_sha,
    }
report['evidence_files'] = ev_files
report['totals'] = {'pass_rows_in_scope': len(scope_rows), 'kept': kept,
                    'demoted': demoted, 'demote_reasons_tally': dict(reasons_tally)}

with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(report, f, indent=1)

print('scope: %d PASS rows (%s)' % (len(scope_rows), ', '.join(AREAS)))
for area in AREAS:
    a = report['areas'][area]
    print('  %-10s kept=%d demoted=%d' % (area, a['pass_rows_kept'], a['pass_rows_demoted']))
print('TOTAL kept=%d demoted=%d' % (kept, demoted))
print('demote reason tally:', dict(reasons_tally))
print('wrote', OUT)
