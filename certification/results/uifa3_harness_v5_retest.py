#!/usr/bin/env python3
# UIFA3 v5 retest of UI-FP-115 and UI-FP-133.
# v3 defects (mine): 115 compared literal 'Leader->send ms' to rendered 'Leader\u2192send ms';
#                    133 refused any intent inside the API last-100 window, skipping 10/10.
# v4 defects (mine): 115 looked up the payload through a shifted OID cell (tested=0);
#                    133 raced a pending_send row against a later terminal write.
# v5: snapshot the CSV BEFORE the DOM read; only score settled attempts (>=60s old);
#     match headers arrow-insensitively; report both the header and the shifted body index.
import csv, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8031'
RES = Path(__file__).resolve().parent
OUT = RES / 'UIFA3_v5_retest_b142cf88d3.json'
SETTLE_S = 60


def g(p, t=240):
    return json.loads(urllib.request.urlopen(BASE + p, timeout=t).read().decode('utf-8'))


def csv_head_rows(path, n):
    with open(path, encoding='utf-8', errors='replace', newline='') as f:
        r = csv.reader(f)
        head = next(r)
        out = []
        for row in r:
            if len(out) >= n:
                break
            out.append(dict(zip(head, row)))
        return out


def count_lines(path):
    with open(path, 'rb') as f:
        return sum(1 for _ in f)


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
sa_p, oi_p = str(aud / 'send_attempts.csv'), str(aud / 'order_intents.csv')

sa_n, oi_n = count_lines(sa_p) - 1, count_lines(oi_p) - 1
CAPTURE_T = datetime.now(timezone.utc)
sa = csv_head_rows(sa_p, sa_n)
oi = csv_head_rows(oi_p, oi_n)
las = g('/api/live-audit-summary', 300)
print('frozen oracle: sa=%d oi=%d captured_at=%s' % (len(sa), len(oi), CAPTURE_T.isoformat()))

attempts_by_intent = {}
for r in sa:
    i = norm(r.get('intent_id'))
    if i:
        attempts_by_intent.setdefault(i, []).append(r)
sa_last = {i: v[-1] for i, v in attempts_by_intent.items()}


def settled(iid):
    rows = attempts_by_intent.get(iid) or []
    if not rows:
        return True
    return (CAPTURE_T - max(pt(r.get('created_at')) for r in rows)).total_seconds() >= SETTLE_S


WINDOW = 100
win = set(norm(r.get('intent_id')) for r in sa[-WINDOW:] if norm(r.get('intent_id')))
oi_by_ts = {}
for r in oi:
    oi_by_ts[(norm(r.get('coin')), norm(r.get('created_at'))[:26])] = r

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

res = {}
shift = bool(eq_rows) and len(eq_rows[0]) != len(eq_h)
print('execqual th=%d td=%s shift=%s | audit th=%d rows=%d' % (len(eq_h), len(eq_rows[0]) if eq_rows else None, shift, len(au_h), len(au_rows)))

hi = hix(eq_h, 'Leader->send ms')
payload = {}
for r in (las.get('execution_quality_rows') or []):
    o = norm(r.get('oid'))
    if o:
        payload[o] = r

body_i = (hi + 1) if (shift and hi >= 4) else hi
at_hdr, at_body, tested = 0, 0, 0
mism = []
body_ci = hix(eq_h, 'Coin') + (1 if shift and hix(eq_h, 'Coin') >= 4 else 0)
body_oi = hix(eq_h, 'OID') + (1 if shift and hix(eq_h, 'OID') >= 4 else 0)
for row in eq_rows:
    if len(row) <= max(hi, body_i):
        continue
    pr = payload.get(norm(row[body_oi])) if 0 <= body_oi < len(row) else None
    if not pr:
        continue
    tested += 1
    if eq(row[hi], pr.get('leader_to_send_attempt_ms')):
        at_hdr += 1
    if eq(row[body_i], pr.get('leader_to_send_attempt_ms')):
        at_body += 1
    else:
        mism.append({'oid': norm(row[body_oi]), 'under_header': row[hi], 'body_pos': row[body_i],
                     'oracle': pr.get('leader_to_send_attempt_ms')})

ok115 = (not shift) and tested >= 3 and at_hdr == tested
res['UI-FP-115'] = {
    'row_id': 'UI-FP-115', 'result': 'PASS' if ok115 else 'FAIL',
    'checks': [
        {'name': 'COLUMN_PRESENT', 'pass': hi >= 0, 'detail': 'header index %d (arrow-normalised match)' % hi},
        {'name': 'HEADER_CELL_ALIGNMENT', 'pass': not shift,
         'detail': 'thead=%d th vs tbody=%d td; renderExecQuality (SSOT 7624-7632) emits an unlabelled truth_state pill at body index 4, shifting every cell from Status onward by one' % (len(eq_h), len(eq_rows[0]) if eq_rows else 0)},
        {'name': 'FIELD_VALUE_MATCH_UNDER_HEADER', 'pass': tested >= 3 and at_hdr == tested,
         'detail': 'tested=%d matched_under_header=%d' % (tested, at_hdr)},
        {'name': 'DATA_PRESENT_AT_SHIFTED_POSITION', 'pass': tested >= 3 and at_body == tested,
         'detail': 'tested=%d matched_at_body_index_%d=%d' % (tested, body_i, at_body)}],
    'evidence': {'header_index': hi, 'body_index_with_shift': body_i, 'tested': tested,
                 'matched_under_header': at_hdr, 'matched_at_shifted_body_index': at_body,
                 'mismatches_at_shifted_position': mism[:4], 'thead_th': len(eq_h),
                 'row_td': len(eq_rows[0]) if eq_rows else 0,
                 'harness_note': 'v3 missed the header (U+2192 arrow) and v4 looked up the payload through a shifted OID cell; v5 snapshots the CSV before the DOM read, matches headers arrow-insensitively, and reports both the labelled and the shifted body position.'}}

ri, ti, coini = hix(au_h, 'Real order result'), hix(au_h, 'Time'), hix(au_h, 'Coin')
matched, mism133, skipped = 0, [], 0
detail = []
for row in au_rows:
    if ri < 0 or len(row) <= max(ri, ti, coini):
        continue
    key = (norm(row[coini]), norm(row[ti])[:26])
    intent = oi_by_ts.get(key)
    if not intent:
        skipped += 1
        detail.append({'coin': key[0], 'skip': 'no intent at exact created_at in the frozen snapshot'})
        continue
    iid = norm(intent.get('intent_id'))
    a = sa_last.get(iid)
    if not settled(iid):
        skipped += 1
        detail.append({'coin': key[0], 'skip': 'attempt written < %ds before capture' % SETTLE_S})
        continue
    if a and iid in win:
        st = norm(a.get('status'))
        want = {'ORDER_FILLED': 'REAL_ORDER_FILLED', 'ORDER_REJECTED': 'EXCHANGE_REJECTED'}.get(st, st)
    elif a:
        skipped += 1
        detail.append({'coin': key[0], 'skip': 'attempt outside last-%d window' % WINDOW})
        continue
    else:
        dec = norm(intent.get('decision'))
        want = 'WOULD_SEND_ONLY' if dec == 'WOULD_PLACE_IOC_LIMIT' else 'NO_SEND_ATTEMPT'
    if eq(row[ri], want):
        matched += 1
    else:
        mism133.append({'coin': key[0], 'dom': row[ri], 'oracle': want, 'intent_id': iid,
                        'attempt_status': (a or {}).get('status')})

ok133 = ri >= 0 and matched >= 3 and not mism133
res['UI-FP-133'] = {
    'row_id': 'UI-FP-133', 'result': 'PASS' if ok133 else 'FAIL',
    'checks': [
        {'name': 'COLUMN_PRESENT', 'pass': ri >= 0, 'detail': 'Real order result'},
        {'name': 'FIELD_VALUE_MATCH', 'pass': bool(matched >= 3 and not mism133),
         'detail': 'matched=%d mism=%d skipped=%d' % (matched, len(mism133), skipped)}],
    'evidence': {'matched': matched, 'mismatches': mism133[:4], 'skipped': skipped, 'skip_detail': detail[:8],
                 'window_rule': 'last %d send_attempts.csv rows from the frozen snapshot' % WINDOW,
                 'settle_rule': 'only intents whose newest attempt is >= %ds old at capture' % SETTLE_S,
                 'harness_note': 'v3 skipped everything (window rule); v4 raced a pending_send row against the later terminal write; v5 freezes the CSV before the DOM read and refuses in-flight attempts.'}}

out = {'task_id': 't_770ce423', 'harness': 'certification/results/uifa3_harness_v5_retest.py',
       'ssot_commit': '5223ce257fe504636967a50f7064630bdc8e0ab0', 'register_commit': 'b142cf8',
       'captured_at_utc': CAPTURE_T.isoformat(),
       'scope': 're-test of UI-FP-115 and UI-FP-133 only; the other 15 rows keep their v3 verdicts',
       'summary': {'pass': sum(1 for r in res.values() if r['result'] == 'PASS'),
                   'fail': sum(1 for r in res.values() if r['result'] == 'FAIL')},
       'rows': list(res.values())}
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
for r in res.values():
    print('ROW', r['row_id'], '->', r['result'], json.dumps(r['evidence'])[:600])
print('WROTE', OUT)
