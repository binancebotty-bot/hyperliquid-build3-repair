#!/usr/bin/env python3
# UIFA3 v8: retest UI-FP-115 (Leader->send ms) plus a column-map proof of the Execution
# Quality misalignment that drives UI-FP-107/109/110/115/119/120.
# Engine writes ~7 intents/second, so the table holds ~45s of rows and a 60s settle window
# leaves nothing (v7: tested=0). v8 scores rows whose attempt is already terminal in the CSV
# and >=2s older than the DOM capture, and reports BOTH the labelled header index and the
# body index the renderer actually writes to.
import csv, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8031'
RES = Path(__file__).resolve().parent
OUT = RES / 'UIFA3_v8_retest_b142cf88d3.json'
MIN_AGE_S = 2.0
TERMINAL = {'ORDER_FILLED', 'ORDER_REJECTED'}


def g(p, t=240):
    return json.loads(urllib.request.urlopen(BASE + p, timeout=t).read().decode('utf-8'))


def read_csv(path):
    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        return list(csv.DictReader(f))


def norm(s):
    return (s or '').replace('\u2026', '').strip()


def hkey(s):
    return norm(s).replace('\u2192', '->').replace('\u2013', '-').replace('\u2014', '-').lower()


def num(v):
    try:
        return float(str(v).replace(',', '').replace('$', '').strip())
    except Exception:
        return None


def eq(a, b, tol=1e-6):
    na, nb = num(a), num(b)
    if na is not None and nb is not None:
        return abs(na - nb) <= max(tol, abs(nb) * 1e-9)
    return norm(str(a)) == norm(str(b))


def hix(h, name):
    k = hkey(name)
    for i, x in enumerate(h):
        if hkey(x) == k:
            return i
    return -1


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
print('DOM captured %s; csv read after: sa=%d rows; th=%d td=%s' % (CAPTURE_T.isoformat(), len(sa), len(h), len(rows[0]) if rows else None))

by_oid = {}
for r in sa:
    o = norm(r.get('exchange_order_id'))
    if o:
        by_oid[o] = r

shift = bool(rows) and len(rows[0]) != len(h)
body = lambda i: (i + 1) if (shift and i >= 4) else i

hi, ci, oi_h, st_h = hix(h, 'Leader->send ms'), hix(h, 'Coin'), hix(h, 'OID'), hix(h, 'Status')
tested = under = at_body = 0
mism, skipped = [], []
for row in rows:
    if len(row) <= max(hi, body(hi), body(oi_h)):
        continue
    oid = norm(row[body(oi_h)])
    rec = by_oid.get(oid)
    if not rec:
        skipped.append({'coin': norm(row[ci]), 'oid': oid or '\u2014', 'why': 'no attempt with that exchange_order_id'})
        continue
    age = (CAPTURE_T - pt(rec['created_at'])).total_seconds()
    if age < MIN_AGE_S or norm(rec.get('status')) not in TERMINAL:
        skipped.append({'coin': norm(row[ci]), 'oid': oid, 'age_s': round(age, 2),
                        'status': norm(rec.get('status')), 'why': 'not yet terminal/old enough'})
        continue
    tested += 1
    want = rec.get('leader_to_send_attempt_ms')
    if eq(row[hi], want):
        under += 1
    if eq(row[body(hi)], want):
        at_body += 1
    else:
        mism.append({'coin': norm(row[ci]), 'under_header': row[hi],
                     'body_shifted': row[body(hi)], 'oracle': want})

map_proof = None
for row in rows:
    if len(row) <= body(oi_h):
        continue
    rec = by_oid.get(norm(row[body(oi_h)]))
    if rec and norm(rec.get('status')) in TERMINAL and (CAPTURE_T - pt(rec['created_at'])).total_seconds() >= MIN_AGE_S:
        map_proof = {'coin': norm(row[ci]),
                     'as_labelled_by_header': {'Status': row[st_h], 'OID': row[oi_h], 'Leader->send ms': row[hi]},
                     'at_shifted_body_index': {'Status': row[body(st_h)], 'OID': row[body(oi_h)], 'Leader->send ms': row[body(hi)]},
                     'oracle': {'status': rec.get('status'), 'oid': norm(rec.get('exchange_order_id')),
                                'leader_to_send_attempt_ms': rec.get('leader_to_send_attempt_ms')}}
        break

ok = (not shift) and tested >= 3 and under == tested
out = {'task_id': 't_770ce423',
       'harness': 'certification/results/uifa3_harness_v8_retest.py',
       'ssot_commit': '5223ce257fe504636967a50f7064630bdc8e0ab0', 'register_commit': 'b142cf8',
       'captured_at_utc': CAPTURE_T.isoformat(),
       'scope': 'UI-FP-115 plus a column-map proof of the Execution Quality misalignment',
       'rows': [{
           'row_id': 'UI-FP-115', 'result': 'PASS' if ok else 'FAIL',
           'checks': [
               {'name': 'COLUMN_PRESENT', 'pass': hi >= 0, 'detail': 'header index %d (U+2192 arrow normalised)' % hi},
               {'name': 'HEADER_CELL_ALIGNMENT', 'pass': not shift,
                'detail': 'thead=%d th vs tbody=%d td; renderExecQuality writes an unlabelled truth_state pill at body index 4' % (len(h), len(rows[0]) if rows else 0)},
               {'name': 'FIELD_VALUE_MATCH_UNDER_HEADER', 'pass': tested >= 3 and under == tested,
                'detail': 'tested=%d matched_under_header=%d' % (tested, under)},
               {'name': 'DATA_PRESENT_AT_SHIFTED_POSITION', 'pass': tested >= 3 and at_body == tested,
                'detail': 'tested=%d matched_at_body_index_%d=%d' % (tested, body(hi), at_body)}],
           'evidence': {'header_index': hi, 'shifted_body_index': body(hi), 'tested': tested,
                        'matched_under_header': under, 'matched_at_shifted_body_index': at_body,
                        'mismatches': mism[:4], 'skipped': skipped[:6],
                        'thead_th': len(h), 'row_td': len(rows[0]) if rows else 0,
                        'column_map_proof': map_proof}}]}
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
r = out['rows'][0]
print('UI-FP-115 ->', r['result'], json.dumps(r['evidence'], ensure_ascii=False)[:900])
print('WROTE', OUT)
