#!/usr/bin/env python3
# UIFA3 v7 retest of UI-FP-115 and UI-FP-133.
# Ordering bug in v3..v6: the CSV was frozen BEFORE the browser ran, and the engine writes
# ~7 order intents/second, so every rendered row postdated the snapshot (tested=0).
# v7 captures the DOM first, then reads the CSV, and scores ONLY rows whose attempts were
# already >= SETTLE_S old at DOM-capture time - those records cannot change any more, so a
# later read is still a valid oracle for them.
import csv, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8031'
RES = Path(__file__).resolve().parent
OUT = RES / 'UIFA3_v7_retest_b142cf88d3.json'
SETTLE_S = 60
WINDOW = 100


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
aud = sd / 'append_only'

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

CAPTURE_T = datetime.now(timezone.utc)
sa = read_csv(str(aud / 'send_attempts.csv'))
oi = read_csv(str(aud / 'order_intents.csv'))
print('DOM captured %s; oracle read after: sa=%d oi=%d' % (CAPTURE_T.isoformat(), len(sa), len(oi)))

sa_by_oid, att_by_intent = {}, {}
for r in sa:
    o = norm(r.get('exchange_order_id'))
    if o:
        sa_by_oid[o] = r
    i = norm(r.get('intent_id'))
    if i:
        att_by_intent.setdefault(i, []).append(r)
sa_last = {i: v[-1] for i, v in att_by_intent.items()}
win = set(norm(r.get('intent_id')) for r in sa[-WINDOW:] if norm(r.get('intent_id')))
oi_by_key = {}
for r in oi:
    oi_by_key[(norm(r.get('coin')), norm(r.get('created_at')))] = r


def settled(iid):
    rows = att_by_intent.get(iid) or []
    return True if not rows else (CAPTURE_T - max(pt(r['created_at']) for r in rows)).total_seconds() >= SETTLE_S


res = {}
shift = bool(eq_rows) and len(eq_rows[0]) != len(eq_h)
print('execqual th=%d td=%s shift=%s | audit th=%d rows=%d' % (len(eq_h), len(eq_rows[0]) if eq_rows else None, shift, len(au_h), len(au_rows)))

hi, ci, oi_h = hix(eq_h, 'Leader->send ms'), hix(eq_h, 'Coin'), hix(eq_h, 'OID')
body = lambda i: (i + 1) if (shift and i >= 4) else i
tested = under_hdr = at_body = 0
mism, skipped = [], []
for row in eq_rows:
    if len(row) <= max(hi, body(hi), body(oi_h)):
        continue
    oid = norm(row[body(oi_h)])
    rec = sa_by_oid.get(oid)
    if not rec or not settled(norm(rec.get('intent_id'))):
        skipped.append({'coin': norm(row[ci]), 'oid': oid or '\u2014',
                        'why': 'unsettled or no matching attempt'})
        continue
    tested += 1
    want = rec.get('leader_to_send_attempt_ms')
    if eq(row[hi], want):
        under_hdr += 1
    if eq(row[body(hi)], want):
        at_body += 1
    else:
        mism.append({'coin': norm(row[ci]), 'under_header': row[hi],
                     'body_shifted': row[body(hi)], 'oracle': want})

ok115 = (not shift) and tested >= 3 and under_hdr == tested
res['UI-FP-115'] = {
    'row_id': 'UI-FP-115', 'result': 'PASS' if ok115 else 'FAIL',
    'checks': [
        {'name': 'COLUMN_PRESENT', 'pass': hi >= 0, 'detail': 'header index %d (U+2192 arrow normalised)' % hi},
        {'name': 'HEADER_CELL_ALIGNMENT', 'pass': not shift,
         'detail': 'thead=%d th, tbody=%d td. renderExecQuality (SSOT 7624-7632) writes an unlabelled truth_state pill at body index 4, so every header from Status onward labels the wrong cell.' % (len(eq_h), len(eq_rows[0]) if eq_rows else 0)},
        {'name': 'FIELD_VALUE_MATCH_UNDER_HEADER', 'pass': tested >= 3 and under_hdr == tested,
         'detail': 'tested=%d matched_under_header=%d' % (tested, under_hdr)},
        {'name': 'DATA_PRESENT_AT_SHIFTED_POSITION', 'pass': tested >= 3 and at_body == tested,
         'detail': 'tested=%d matched_at_body_index_%d=%d' % (tested, body(hi), at_body)}],
    'evidence': {'header_index': hi, 'shifted_body_index': body(hi), 'tested': tested,
                 'matched_under_header': under_hdr, 'matched_at_shifted_body_index': at_body,
                 'mismatches_at_shifted_position': mism[:4], 'skipped': skipped[:6],
                 'thead_th': len(eq_h), 'row_td': len(eq_rows[0]) if eq_rows else 0}}

ri, ti, coini = hix(au_h, 'Real order result'), hix(au_h, 'Time'), hix(au_h, 'Coin')
matched, mism133, skipped133 = 0, [], []
for row in au_rows:
    if ri < 0 or len(row) <= max(ri, ti, coini):
        continue
    intent = oi_by_key.get((norm(row[coini]), norm(row[ti])))
    if not intent:
        skipped133.append({'coin': norm(row[coini]), 'why': 'no intent with that exact created_at'})
        continue
    iid = norm(intent.get('intent_id'))
    a = sa_last.get(iid)
    if a and not settled(iid):
        skipped133.append({'coin': norm(row[coini]), 'why': 'attempt younger than %ds at capture' % SETTLE_S})
        continue
    if a and iid in win:
        st = norm(a.get('status'))
        want = {'ORDER_FILLED': 'REAL_ORDER_FILLED', 'ORDER_REJECTED': 'EXCHANGE_REJECTED'}.get(st, st)
    elif a:
        skipped133.append({'coin': norm(row[coini]), 'why': 'attempt outside last-%d window (UI join rule)' % WINDOW})
        continue
    else:
        want = 'WOULD_SEND_ONLY' if norm(intent.get('decision')) == 'WOULD_PLACE_IOC_LIMIT' else 'NO_SEND_ATTEMPT'
    if eq(row[ri], want):
        matched += 1
    else:
        mism133.append({'coin': norm(row[coini]), 'dom': row[ri], 'oracle': want, 'intent_id': iid,
                        'attempt_status': (a or {}).get('status')})

ok133 = ri >= 0 and matched >= 3 and not mism133
res['UI-FP-133'] = {
    'row_id': 'UI-FP-133', 'result': 'PASS' if ok133 else 'FAIL',
    'checks': [
        {'name': 'COLUMN_PRESENT', 'pass': ri >= 0, 'detail': 'Real order result'},
        {'name': 'FIELD_VALUE_MATCH', 'pass': bool(matched >= 3 and not mism133),
         'detail': 'matched=%d mism=%d skipped=%d' % (matched, len(mism133), len(skipped133))}],
    'evidence': {'matched': matched, 'mismatches': mism133[:4], 'skip_detail': skipped133[:8],
                 'join_rule': 'order_intents.csv row with the identical created_at string for that coin',
                 'settle_rule': 'newest attempt >= %ds old at DOM capture' % SETTLE_S,
                 'window_rule': 'last %d send_attempts.csv rows (mirrors the UI join)' % WINDOW}}

out = {'task_id': 't_770ce423', 'harness': 'certification/results/uifa3_harness_v7_retest.py',
       'ssot_commit': '5223ce257fe504636967a50f7064630bdc8e0ab0', 'register_commit': 'b142cf8',
       'captured_at_utc': CAPTURE_T.isoformat(),
       'scope': 're-test of UI-FP-115 and UI-FP-133; the other 15 rows keep their v3 verdicts',
       'summary': {'pass': sum(1 for r in res.values() if r['result'] == 'PASS'),
                   'fail': sum(1 for r in res.values() if r['result'] == 'FAIL')},
       'rows': list(res.values())}
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
for r in res.values():
    print('ROW', r['row_id'], '->', r['result'], json.dumps(r['evidence'])[:700])
print('WROTE', OUT)
