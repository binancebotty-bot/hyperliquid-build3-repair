#!/usr/bin/env python3
'''Narrow overlay: apply the ENG-INV-03/04/05 row-bound re-earn ONLY.

Why a separate file instead of editing apply_verified_results.py:
  apply_verified_results.py is a hardcoded table (V) read from no external input --
  'for rid, v in sorted(V.items())' with no argv and no json.load. Task t_ff1af604
  forbids editing it. To honour the overlay PATH (programmatic, idempotent,
  re-runnable, never a hand-edit) without touching the forbidden file, this overlay
  applies exactly three rows and refuses to touch anything else.

Rules:
  - Reads verdicts from the committed resolution JSON, so evidence and applied
    value cannot drift apart.
  - Idempotent: a re-run is a byte-identical no-op.
  - Asserts the matrix changed ONLY the three target rows.

Run: python certification/results/apply_eng_inv_03_05_t_ff1af604.py
'''
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MATRIX = ROOT / 'certification' / 'certification_matrix.json'
RES = ROOT / 'certification' / 'results' / 'ENG-INV-03-05_resolution_t_ff1af604.json'
TARGETS = ('ENG-INV-03', 'ENG-INV-04', 'ENG-INV-05')
STAMP = 'Row-bound re-earn (t_ff1af604)'


def load_resolution():
    if not RES.exists():
        sys.exit('FATAL: resolution missing: %s' % RES)
    found = {r['row_id']: r for r in json.loads(RES.read_text(encoding='utf-8'))}
    miss = [t for t in TARGETS if t not in found]
    if miss:
        sys.exit('FATAL: resolution missing rows: %s' % miss)
    for t in TARGETS:
        for f in ('verdict', 'evidence_ref', 'tested_commit', 'why'):
            if not found[t].get(f):
                sys.exit('FATAL: %s empty %s' % (t, f))
    return found


def main():
    doc = json.loads(MATRIX.read_text(encoding='utf-8'))
    before = {r['id']: json.loads(json.dumps(r)) for r in doc['records']}
    res = load_resolution()
    by_id = {r['id']: r for r in doc['records']}
    for t in TARGETS:
        rec = by_id.get(t)
        if rec is None:
            sys.exit('FATAL: row %s absent from matrix' % t)
        r = res[t]
        prev = rec.get('notes') or ''
        rec['result'] = r['verdict']
        rec['evidence_ref'] = r['evidence_ref']
        rec['tested_commit'] = r['tested_commit']
        rec['tested_at_utc'] = r.get('tested_at_utc') or '2026-10-17T11:15:00Z'
        if STAMP not in prev:
            rec['notes'] = (prev + ' | ' if prev else '') + STAMP + ': ' + r['why']
    after = {r['id']: r for r in doc['records']}
    changed = [i for i in after if after[i] != before[i]]
    stray = [i for i in changed if i not in TARGETS]
    if stray:
        sys.exit('FATAL: overlay changed out-of-scope rows: %s' % stray)
    MATRIX.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print('changed rows:', changed)
    for t in TARGETS:
        print('%-11s %-5s -> %-5s  %s' % (t, before[t]['result'], after[t]['result'],
                                           after[t]['evidence_ref'][:70]))
    print('tested_commit:', after[TARGETS[0]]['tested_commit'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
