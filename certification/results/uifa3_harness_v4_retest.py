#!/usr/bin/env python3
# UIFA3 v4 retest: re-tests ONLY the two rows whose v3 verdict was harness-limited.
#  UI-FP-115  v3 compared literal 'Leader->send ms' with rendered 'Leader\u2192send ms' (U+2192)
#             -> reported COLUMN_PRESENT False. That was a harness defect, corrected here.
#  UI-FP-133  v3 skipped all rows because its oracle refused any intent inside the API
#             last-100 window. v4 recomputes that window from send_attempts.csv directly and
#             only skips attempts younger than 30s (race) or older than the window (UI rule).
import csv, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8031'
RES = Path(__file__).resolve().parent
OUT = RES / 'UIFA3_v4_retest_b142cf88d3.json'


def g(p, t=240):
    return json.loads(urllib.request.urlopen(BASE + p, timeout=t).read().decode('utf-8'))


def rows_of(path):
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
aud = sd / 'append_only'
sa = rows_of(str(aud / 'send_attempts.csv'))
oi = rows_of(str(aud / 'order_intents.csv'))
las = g('/api/live-audit-summary', 300)

WINDOW = 100
win = set(norm(r.get('intent_id')) for r in sa[-WINDOW:] if norm(r.get('intent_id')))
sa_by_intent = {}
for r in sa:
    i = norm(r.get('intent_id'))
    if i:
        sa_by_intent[i] = r

oi_by_ts = {}
for r in oi:
    oi_by_ts[(norm(r.get('coin')), norm(r.get('created_at'))[:26])] = r

print('csv sa=%d oi=%d window_ids=%d' % (len(sa), len(oi), len(win)))
now = datetime.now(timezone.utc)

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto(BASE + '/live-copy', wait_until='load', timeout=90000)
    pg.wait_for_function('()=>{const t=document.querySelector("#lcExecQualRows");return t&&t.innerText.indexOf("Loading")===-1}', timeout=180000)

    def hdr(sel):
        return pg.evaluate('(s)=>{const t=document.querySelector(s);if(!t)return [];const tb=t.closest("table");return tb?Array.from(tb.querySelectorAll("thead th")).map(x=>x.innerText.trim()):[]}', sel)

    def rws(sel, n=40):
        loc = pg.locator(sel + ' tr')
        out = []
        for i in range(min(loc.count(), n)):
            c = loc.nth(i).locator('td')
            if c.count():
                out.append([c.nth(j).inner_text() for j in range(c.count())])
        return out

    eq_h, eq_rows = hdr('#lcExecQualRows'), rws('#lcExecQualRows', 40)
    pg.click('[data-lc-tab="audit"]')
    pg.wait_for_timeout(2500)
    au_h, au_rows = hdr('#lcAuditRows'), rws('#lcAuditRows', 12)
    b.close()

print('execqual th=%d td=%s | audit th=%d rows=%d' % (len(eq_h), len(eq_rows[0]) if eq_rows else None, len(au_h), len(au_rows)))
res = {}

hi = hix(eq_h, 'Leader->send ms')
payload = {}
for r in (las.get('execution_quality_rows') or []):
    o = norm(r.get('oid'))
    if o:
        payload[o] = r
oi_col, ci = hix(eq_h, 'OID'), hix(eq_h, 'Coin')
matched, mism, tested = 0, [], 0
if hi >= 0 and eq_rows:
    for row in eq_rows:
        if len(row) <= max(hi, oi_col, ci):
            continue
        pr = payload.get(norm(row[oi_col])) if oi_col >= 0 else None
        if not pr:
            continue
        tested += 1
        if eq(row[hi], pr.get('leader_to_send_attempt_ms')):
            matched += 1
        else:
            mism.append({'coin': norm(row[ci]), 'dom': row[hi], 'oracle': pr.get('leader_to_send_attempt_ms')})
shift = bool(eq_rows) and len(eq_rows[0]) != len(eq_h)
ok115 = hi >= 0 and tested >= 3 and not mism and not shift
res['UI-FP-115'] = {
    'row_id': 'UI-FP-115', 'result': 'PASS' if ok115 else 'FAIL',
    'checks': [
        {'name': 'COLUMN_PRESENT', 'pass': hi >= 0, 'detail': 'header index %d (arrow-normalised match)' % hi},
        {'name': 'HEADER_CELL_ALIGNMENT', 'pass': not shift, 'detail': 'thead=%d th vs tbody=%d td' % (len(eq_h), len(eq_rows[0]) if eq_rows else 0)},
        {'name': 'FIELD_VALUE_MATCH_UNDER_HEADER', 'pass': bool(tested >= 3 and not mism), 'detail': 'tested=%d matched=%d mism=%d' % (tested, matched, len(mism))}],
    'evidence': {'header_index': hi, 'tested': tested, 'mismatches': mism[:4], 'thead_th': len(eq_h),
                 'row_td': len(eq_rows[0]) if eq_rows else 0,
                 'v3_note': 'v3 compared literal Leader->send ms with rendered Leader\u2192send ms (U+2192) and reported COLUMN_PRESENT False; harness defect, corrected in v4.'}}

ri, ti, coini = hix(au_h, 'Real order result'), hix(au_h, 'Time'), hix(au_h, 'Coin')
matched, mism, skipped = 0, [], 0
detail = []
for row in au_rows:
    if ri < 0 or len(row) <= max(ri, ti, coini):
        continue
    key = (norm(row[coini]), norm(row[ti])[:26])
    intent = oi_by_ts.get(key)
    if not intent:
        skipped += 1
        detail.append({'coin': key[0], 'skip': 'no intent at exact created_at'})
        continue
    iid = norm(intent.get('intent_id'))
    a = sa_by_intent.get(iid)
    if a and (now - pt(a.get('created_at'))).total_seconds() < 30:
        skipped += 1
        detail.append({'coin': key[0], 'skip': 'attempt too fresh to be race-free'})
        continue
    if a and iid in win:
        st = norm(a.get('status'))
        want = {'ORDER_FILLED': 'REAL_ORDER_FILLED', 'ORDER_REJECTED': 'EXCHANGE_REJECTED'}.get(st, st)
    elif a:
        skipped += 1
        detail.append({'coin': key[0], 'skip': 'attempt outside last-100 window (UI rule)'})
        continue
    else:
        dec = norm(intent.get('decision'))
        want = 'WOULD_SEND_ONLY' if dec == 'WOULD_PLACE_IOC_LIMIT' else 'NO_SEND_ATTEMPT'
    if eq(row[ri], want):
        matched += 1
    else:
        mism.append({'coin': key[0], 'dom': row[ri], 'oracle': want, 'intent_id': iid,
                     'attempt_status': (a or {}).get('status')})
ok133 = ri >= 0 and matched >= 3 and not mism
res['UI-FP-133'] = {
    'row_id': 'UI-FP-133', 'result': 'PASS' if ok133 else 'FAIL',
    'checks': [
        {'name': 'COLUMN_PRESENT', 'pass': ri >= 0, 'detail': 'Real order result'},
        {'name': 'FIELD_VALUE_MATCH', 'pass': bool(matched >= 3 and not mism),
         'detail': 'matched=%d mism=%d skipped=%d' % (matched, len(mism), skipped)}],
    'evidence': {'matched': matched, 'mismatches': mism[:4], 'skipped': skipped,
                 'skip_detail': detail[:6], 'window_rule': 'last %d send_attempts.csv rows' % WINDOW,
                 'v3_note': 'v3 skipped all 10 rows because its oracle rejected any intent present in the API last-100 window; v4 recomputes that window from the CSV and only skips attempts younger than 30s or outside the window.'}}

out = {'task_id': 't_770ce423', 'harness': 'certification/results/uifa3_harness_v4_retest.py',
       'ssot_commit': '5223ce257fe504636967a50f7064630bdc8e0ab0', 'register_commit': 'b142cf8',
       'tested_at_utc': datetime.now(timezone.utc).isoformat(),
       'scope': 're-test of UI-FP-115 and UI-FP-133 only; all other rows carry their v3 verdict unchanged',
       'summary': {'pass': sum(1 for r in res.values() if r['result'] == 'PASS'),
                   'fail': sum(1 for r in res.values() if r['result'] == 'FAIL')},
       'rows': list(res.values())}
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
for r in res.values():
    print('ROW', r['row_id'], '->', r['result'], json.dumps(r['evidence'])[:400])
print('WROTE', OUT)
