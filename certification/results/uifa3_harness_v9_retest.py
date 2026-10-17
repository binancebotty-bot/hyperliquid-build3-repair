#!/usr/bin/env python3
# UIFA3 v9: final row-bound retest of UI-FP-115 (Leader->send ms) and UI-FP-119 (Exchange ms).
# Both sit downstream of the same render defect: the thead at SSOT 7144 declares 18 columns, but
# the renderExecQuality row template writes 19 cells (an unlabelled truth_state pill at body
# index 4), so every header from 'Status' onward labels the cell to its LEFT's neighbour.
# v9 therefore scores BOTH candidate positions per row and reports which one holds the oracle
# value, so a PASS/FAIL can never come from a vacuous or mis-indexed comparison.
import csv, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8031'
RES = Path(__file__).resolve().parent
OUT = RES / 'UIFA3_v9_retest_b142cf88d3.json'
MIN_AGE_S = 2.0
TERMINAL = {'ORDER_FILLED', 'ORDER_REJECTED'}
ROWS = {'UI-FP-115': ('Leader\u2192send ms', 'leader_to_send_attempt_ms'),
        'UI-FP-119': ('Exchange ms', 'exchange_call_ms')}


def g(p, t=240):
    return json.loads(urllib.request.urlopen(BASE + p, timeout=t).read().decode('utf-8'))


def read_csv(path):
    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        return list(csv.DictReader(f))


def norm(s):
    return (s or '').replace('\u2026', '').strip()


def hkey(s):
    return norm(s).replace('\u2192', '->').replace('\u2013', '-').replace('\u2014', '-').lower()


def eq(a, b, tol=1e-6):
    def n(v):
        try:
            return float(str(v).replace(',', '').replace('$', '').strip())
        except Exception:
            return None
    na, nb = n(a), n(b)
    if na is not None and nb is not None:
        return abs(na - nb) <= max(tol, abs(nb) * 1e-9)
    return norm(str(a)) == norm(str(b))


def pt(s):
    return datetime.fromisoformat(norm(s).replace('Z', '+00:00'))


gc = g('/api/global-controls')
sd = Path(gc['networks']['state_dir'])

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto(BASE + '/live-copy', wait_until='load', timeout=90000)
    pg.wait_for_function('()=>{const t=document.querySelector("#lcExecQualRows");return t&&t.innerText.indexOf("Loading")===-1}', timeout=180000)
    h = pg.evaluate('()=>{const t=document.querySelector("#lcExecQualRows").closest("table");return [...t.querySelectorAll("thead th")].map(x=>x.innerText.trim())}')
    loc = pg.locator('#lcExecQualRows tr')
    rows = []
    for i in range(loc.count()):
        c = loc.nth(i).locator('td')
        if c.count():
            rows.append([c.nth(j).inner_text() for j in range(c.count())])
    b.close()

CAPTURE_T = datetime.now(timezone.utc)
sa = read_csv(str(sd / 'append_only' / 'send_attempts.csv'))
by_oid = {}
for r in sa:
    o = norm(r.get('exchange_order_id'))
    if o:
        by_oid[o] = r

shift = bool(rows) and len(rows[0]) != len(h)
body = lambda i: (i + 1) if (shift and i >= 4) else i
ci = next((i for i, x in enumerate(h) if hkey(x) == 'coin'), -1)
oi_h = next((i for i, x in enumerate(h) if hkey(x) == 'oid'), -1)
print('DOM %s th=%d td=%s shift=%s sa=%d' % (CAPTURE_T.isoformat(), len(h), len(rows[0]) if rows else None, shift, len(sa)))

samples = []
for row in rows:
    if len(row) <= body(oi_h):
        continue
    oid = norm(row[body(oi_h)])
    rec = by_oid.get(oid)
    if not rec or norm(rec.get('status')) not in TERMINAL:
        continue
    if (CAPTURE_T - pt(rec['created_at'])).total_seconds() < MIN_AGE_S:
        continue
    samples.append({'coin': norm(row[ci]), 'oid': oid, 'cells': row, 'rec': rec})

out_rows = []
for rid, (hdr, col) in ROWS.items():
    hi = next((i for i, x in enumerate(h) if hkey(x) == hkey(hdr)), -1)
    under = at_body = 0
    mism = []
    for s in samples:
        want = s['rec'].get(col)
        if hi >= 0 and eq(s['cells'][hi], want):
            under += 1
        if len(s['cells']) > body(hi) and eq(s['cells'][body(hi)], want):
            at_body += 1
        elif hi >= 0 and len(s['cells']) > body(hi):
            mism.append({'coin': s['coin'], 'oid': s['oid'], 'under_header': s['cells'][hi],
                         'body_shifted': s['cells'][body(hi)], 'oracle': want})
    proven = len(samples) >= 3
    out_rows.append({
        'row_id': rid, 'result': 'PASS' if (proven and not shift and under == len(samples)) else 'FAIL',
        'checks': [
            {'name': 'COLUMN_PRESENT', 'pass': hi >= 0,
             'detail': 'header %r at index %d (U+2192 normalised)' % (hdr, hi)},
            {'name': 'HEADER_CELL_ALIGNMENT', 'pass': not shift,
             'detail': 'thead=%d th vs tbody=%d td; renderExecQuality emits an unlabelled truth_state pill at body index 4' % (len(h), len(rows[0]) if rows else 0)},
            {'name': 'FIELD_VALUE_MATCH_UNDER_HEADER', 'pass': proven and under == len(samples),
             'detail': 'tested=%d matched_under_header=%d' % (len(samples), under)},
            {'name': 'FIELD_VALUE_MATCH_AT_RENDERED_INDEX', 'pass': proven and at_body == len(samples),
             'detail': 'tested=%d matched_at_body_index_%d=%d' % (len(samples), body(hi), at_body)}],
        'evidence': {'header_index': hi, 'shifted_body_index': body(hi), 'tested': len(samples),
                     'matched_under_header': under, 'matched_at_shifted_body_index': at_body,
                     'mismatches': mism[:4], 'oracle_column': 'send_attempts.csv:' + col,
                     'scope': 'rows whose exchange_order_id is already terminal in the CSV and >= %.0fs old at DOM capture' % MIN_AGE_S}})

out = {'task_id': 't_770ce423', 'harness': 'certification/results/uifa3_harness_v9_retest.py',
       'ssot_commit': '5223ce257fe504636967a50f7064630bdc8e0ab0', 'register_commit': 'b142cf8',
       'captured_at_utc': CAPTURE_T.isoformat(),
       'scope': 'UI-FP-115 and UI-FP-119 non-vacuous retest of the Execution Quality column shift',
       'rows': out_rows}
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
for r in out_rows:
    print(r['row_id'], '->', r['result'], json.dumps(r['evidence'], ensure_ascii=False)[:400])
print('WROTE', OUT)
