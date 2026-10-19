#!/usr/bin/env python3
'''Apply UI-FP-113..127 artifact verdicts into the certification register.
Reads the artifact; writes only certification_matrix.json + .csv.
Run after the probe and verify_refs are green.
'''
import csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.dirname(HERE)
ART = os.path.join(HERE, 'UI-FP-113-127.json')
MXJ = os.path.join(CERT, 'certification_matrix.json')
MXC = os.path.join(CERT, 'certification_matrix.csv')
REL = 'certification/results/UI-FP-113-127.json'
FIELDS = ['id', 'area', 'feature', 'expected_behaviour', 'sources',
          'applicability', 'proof_network', 'open_decisions', 'execution_proof',
          'independent_oracle', 'negative_tests', 'prior_evidence', 'result',
          'evidence_ref', 'tested_commit', 'tested_at_utc', 'notes']

art = json.load(open(ART, encoding='utf-8'))
cap = art['captured_at_utc']
tc = '%s (serving checkout HEAD, dirty - bound by served HTML sha256 %s)' % (
    art['serving_commit'], art['serving_html_sha256'])

upd = {}
for rid, row in art['rows'].items():
    obs = row.get('observed') or {}
    upd[rid] = dict(
        result=row['verdict'],
        evidence_ref='%s#/rows/%s' % (REL, rid),
        tested_commit=tc,
        tested_at_utc=cap,
        note=('row-bound certification %s: %s. Column %r (index %s) of %s; binding %s'
              % (cap, row.get('verdict_reason'), row.get('column'),
                 row.get('column_index'), row.get('table'), obs.get('binding'))))

mx = json.load(open(MXJ, encoding='utf-8'))
seen = set()
for rec in mx['records']:
    u = upd.get(rec.get('id'))
    if not u:
        continue
    seen.add(rec['id'])
    for k in ('result', 'evidence_ref', 'tested_commit', 'tested_at_utc'):
        rec[k] = u[k]
    rec['notes'] = ((rec.get('notes') or '') + ' | ' + u['note']).strip(' |')
miss = sorted(set(upd) - seen)
if miss:
    raise SystemExit('MATRIX_ROW_NOT_FOUND: %s' % miss)
json.dump(mx, open(MXJ, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)

rows = list(csv.DictReader(open(MXC, encoding='utf-8', newline='')))
for r in rows:
    u = upd.get(r.get('id'))
    if not u:
        continue
    for k in ('result', 'evidence_ref', 'tested_commit', 'tested_at_utc'):
        r[k] = u[k]
    r['notes'] = ((r.get('notes') or '') + ' | ' + u['note']).strip(' |')
with open(MXC, 'w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, '') for k in FIELDS})

by = {}
for k, v in upd.items():
    by.setdefault(v['result'], []).append(k)
print(json.dumps({'applied': sorted(upd),
                  'counts': {k: sorted(v) for k, v in sorted(by.items())}}, indent=1))
