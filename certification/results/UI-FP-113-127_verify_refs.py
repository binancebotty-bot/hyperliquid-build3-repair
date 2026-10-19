#!/usr/bin/env python3
"""Verify every evidence_ref in UI-FP-113-127.json resolves (READ-ONLY).

Reviewer-facing proof the artifact is self-contained: each ref is a JSON
Pointer into a file committed beside it. Exits 1 on any failure.

  python3 certification/results/UI-FP-113-127_verify_refs.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
ART = os.path.join(HERE, 'UI-FP-113-127.json')
LEGAL = ('PASS', 'FAIL', 'PARTIAL', 'NOT_TESTED')


def resolve(doc, pointer):
    cur = doc
    for tok in pointer.split('/')[1:]:
        tok = tok.replace('~1', '/').replace('~0', '~')
        cur = cur[int(tok)] if isinstance(cur, list) else cur[tok]
    return cur


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def main():
    art = load(ART)
    problems = []
    cache = {}
    checked = 0
    for rid, row in art['rows'].items():
        ref = row.get('evidence_ref') or ''
        if '#' not in ref:
            problems.append('%s: evidence_ref has no pointer: %r' % (rid, ref))
            continue
        rel, ptr = ref.split('#', 1)
        full = os.path.join(REPO, rel)
        if not os.path.isfile(full):
            problems.append('%s: file missing: %s' % (rid, rel))
            continue
        if rel not in cache:
            cache[rel] = load(full)
        try:
            val = resolve(cache[rel], ptr)
        except Exception as e:  # noqa: BLE001
            problems.append('%s: pointer unresolved %s (%s: %s)'
                            % (rid, ref, type(e).__name__, e))
            continue
        if val.get('row_id') != rid:
            problems.append('%s: pointer resolves to row_id %r'
                            % (rid, val.get('row_id')))
            continue
        checked += 1
        for key, v in (val.get('observed') or {}).items():
            if not isinstance(v, str) or '#' not in v or v.startswith('http'):
                continue
            sub, sptr = v.split('#', 1)
            srel = 'certification/results/' + sub
            sfull = os.path.join(REPO, srel)
            if not os.path.isfile(sfull):
                problems.append('%s.%s: nested file missing: %s'
                                % (rid, key, srel))
                continue
            if srel not in cache:
                cache[srel] = load(sfull)
            try:
                resolve(cache[srel], sptr)
            except Exception as e:  # noqa: BLE001
                problems.append('%s.%s: nested pointer unresolved %s (%s: %s)'
                                % (rid, key, v, type(e).__name__, e))
    for rid, v in art['verdicts'].items():
        if v not in LEGAL:
            problems.append('%s: illegal verdict %r' % (rid, v))
    if sorted(art['verdicts']) != sorted(art['rows']):
        problems.append('verdicts and rows disagree on row ids')
    for row in art['rows'].values():
        if not row.get('serving_commit') or not row.get('serving_ssot_sha256'):
            problems.append('%s: missing per-row build binding'
                            % row.get('row_id'))
    print('rows', len(art['rows']), 'refs resolved', checked,
          'problems', len(problems))
    for p in problems:
        print(' PROBLEM', p)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
