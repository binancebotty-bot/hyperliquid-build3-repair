import json, subprocess, sys, pathlib

ROOT = pathlib.Path('.').resolve()
MATRIX = ROOT / 'certification' / 'certification_matrix.json'
BR = 'origin/hermes/eng-inv-03-05-rowbound-t_ff1af604'
SIX = ['ENG-INV-0%d' % i for i in range(1, 7)]
STAMP = 'Row-bound re-earn (t_ff1af604)'

raw = subprocess.run(['git', 'show', BR + ':certification/certification_matrix.json'], capture_output=True)
if raw.returncode != 0:
    sys.exit('FATAL: cannot read branch matrix')
src = {r['id']: r for r in json.loads(raw.stdout.decode('utf-8-sig'))['records']}

doc = json.loads(MATRIX.read_text(encoding='utf-8-sig'))
by_id = {r['id']: r for r in doc['records']}
before = {r['id']: json.loads(json.dumps(r)) for r in doc['records']}
for k in SIX:
    s = src.get(k)
    rec = by_id.get(k)
    if not s or not rec:
        sys.exit('FATAL: %s missing on one side' % k)
    if s['result'] != 'PASS':
        sys.exit('FATAL: %s branch result %s' % (k, s['result']))
    rec['result'] = s['result']
    rec['evidence_ref'] = s['evidence_ref']
    rec['tested_commit'] = s['tested_commit']
    rec['tested_at_utc'] = s['tested_at_utc']
    prev = rec.get('notes') or ''
    if STAMP not in prev:
        rec['notes'] = (prev + ' | ' if prev else '') + STAMP + ': ' + (s.get('notes') or '')

after = {r['id']: r for r in doc['records']}
changed = [k for k in after if before.get(k) != after[k]]
stray = [k for k in changed if k not in SIX]
if stray:
    sys.exit('FATAL: out-of-scope rows changed: %s' % stray)

text = json.dumps(doc, indent=1, ensure_ascii=False) + '\n'
MATRIX.write_text(text, encoding='utf-8', newline='\n')
print('changed rows:', changed)
for k in SIX:
    print('%-11s %-5s -> %-5s %s' % (k, before[k]['result'], after[k]['result'], after[k]['evidence_ref']))
print('records total:', len(doc['records']))
