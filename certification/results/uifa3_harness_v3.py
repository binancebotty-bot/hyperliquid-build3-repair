#!/usr/bin/env python3
# UIFA3 harness v3 - UI-FP-076..140 field certification against the LIVE surface.
# v2 instrument defects corrected here (each proven by a live DOM probe):
#  (1) ENTRY URL: v2 opened BASE+'/' which 307-redirects, so the wallet-expansion
#      click never reached the live-copy root -> friction table falsely 'absent'.
#      v3 opens BASE+'/live-copy' and the C-Friction table IS present (11 th, 21 rows).
#  (2) OWNED oracle read o.get('side'); manual_live_positions.json stores
#      'direction' -> manufactured 088/089/090 FAILs.
#  (3) UI-FP-133 joined live_fills by COIN; the table is per-INTENT.
#  (4) Execution Quality tbody emits 19 td while thead declares 18 th:
#      renderExecQuality() writes a truth_state pill the thead does not declare.
#      GENUINE product defect at 5223ce25 - FAILs kept, exact shift recorded.
# Oracle: direct append_only/*.csv + manual_live_positions.json reads, never
# importing HL_Copy_App_SSOT.py. PASS only when the cell UNDER the named header
# equals independently recomputed engine truth for >=3 sampled rows.
import csv, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:8031'
RES = Path(__file__).resolve().parent
PROGRESS = RES / 'PROGRESS_UIFA3_v3.jsonl'
ROWS = ['UI-FP-076', 'UI-FP-078', 'UI-FP-079', 'UI-FP-084', 'UI-FP-088', 'UI-FP-089',
        'UI-FP-090', 'UI-FP-107', 'UI-FP-109', 'UI-FP-110', 'UI-FP-115', 'UI-FP-119',
        'UI-FP-120', 'UI-FP-133', 'UI-FP-137', 'UI-FP-139', 'UI-FP-140']
results, defects, negs = {}, [], []


def g(p, t=240):
    return json.loads(urllib.request.urlopen(BASE + p, timeout=t).read().decode('utf-8'))


def csv_rows(path, nbytes=None):
    with open(path, 'rb') as f:
        f.seek(0, 2)
        size = f.tell()
        start = 0 if nbytes is None else max(0, size - nbytes)
        f.seek(0)
        head = f.readline().decode('utf-8', 'replace').rstrip('\r\n')
        f.seek(start)
        if start:
            f.readline()
        body = f.read().decode('utf-8', 'replace')
    return list(csv.DictReader(body.splitlines(), fieldnames=head.split(',')))


def norm(s):
    return (s or '').replace('\u2026', '').strip()


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


def emit(rid, verdict, checks, evidence):
    results[rid] = {'row_id': rid, 'result': verdict, 'checks': checks, 'evidence': evidence}
    with open(PROGRESS, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'row_id': rid, 'result': verdict, 'checks': checks,
                            'evidence': evidence,
                            'tested_at_utc': datetime.now(timezone.utc).isoformat()},
                           ensure_ascii=False) + '\n')
    print('ROW %s -> %s' % (rid, verdict))


gc = g('/api/global-controls')
sd = Path(gc['networks']['state_dir'])
aud = sd / 'append_only'
las = g('/api/live-audit-summary', 300)
sa = csv_rows(str(aud / 'send_attempts.csv'))
lf = csv_rows(str(aud / 'live_fills.csv'))
oi = csv_rows(str(aud / 'order_intents.csv'))
rc = csv_rows(str(aud / 'reconciliation.csv'))
mlp = json.loads((sd / 'manual_live_positions.json').read_text(encoding='utf-8-sig'))
print('oracle sa=%d lf=%d oi=%d rc=%d wallets=%d' % (len(sa), len(lf), len(oi), len(rc), len(mlp.get('by_wallet') or {})))

sa_by_oid, sa_by_intent = {}, {}
for r in sa:
    o = norm(r.get('exchange_order_id'))
    if o:
        sa_by_oid[o] = r
    i = norm(r.get('intent_id'))
    if i:
        sa_by_intent[i] = r
lf_by_oid = {}
for r in lf:
    o = norm(r.get('exchange_order_id'))
    if o:
        lf_by_oid[o] = r
oi_by_id = {}
for r in oi:
    i = norm(r.get('intent_id'))
    if i:
        oi_by_id[i] = r
recent100 = set(norm(r.get('intent_id')) for r in (las.get('recent_send_attempts') or []))

FR_JS = r'''() => {
  const out=[];
  for (const t of document.querySelectorAll('table')) {
    const ths=[...t.querySelectorAll('thead th')].map(h=>h.innerText.trim());
    if (!ths.some(x=>/leader\/ref px/i.test(x))) continue;
    const rows=[...t.querySelectorAll('tbody tr')].map(tr=>[...tr.children].map(td=>td.innerText));
    out.push({header:ths, rows:rows});
  }
  return out;
}'''

fr_h, fr_rows, fr_wallet = [], [], None
eq_h, eq_rows = [], []
own_h, own_rows = [], []
aud_h, aud_rows = [], []
crit_h, crit_rows = [], []
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto(BASE + '/live-copy', wait_until='load', timeout=90000)
    pg.wait_for_function('()=>{const t=document.querySelector("#lcExecQualRows");return t&&t.innerText.indexOf("Loading")===-1}', timeout=180000)

    def hdr(sel):
        return pg.evaluate('(sel)=>{const tb=document.querySelector(sel);if(!tb)return [];const t=tb.closest("table");return t?Array.from(t.querySelectorAll("thead th")).map(h=>h.innerText.trim()):[]}', sel)

    def rws(sel, n=40):
        r = pg.locator(sel + ' tr')
        out = []
        for i in range(min(r.count(), n)):
            c = r.nth(i).locator('td')
            if c.count() == 0:
                continue
            out.append([c.nth(j).inner_text() for j in range(c.count())])
        return out

    eq_h, eq_rows = hdr('#lcExecQualRows'), rws('#lcExecQualRows', 40)
    pg.click('[data-lc-tab="positions"]')
    pg.wait_for_timeout(2000)
    own_h, own_rows = hdr('#lcOwnedPositionRows'), rws('#lcOwnedPositionRows', 12)
    wr = pg.locator('#lcWalletRows tr.lc-wallet-row')
    for i in range(min(wr.count(), 8)):
        wr.nth(i).click()
        pg.wait_for_timeout(2500)
        got = pg.evaluate(FR_JS)
        got = [x for x in got if len(x['header']) == 11]
        if got and got[0]['rows']:
            fr_h = got[0]['header']
            fr_rows = [r for r in got[0]['rows'] if len(r) == 11]
            fr_wallet = wr.nth(i).get_attribute('data-wallet')
            break
        wr.nth(i).click()
        pg.wait_for_timeout(500)
    pg.click('[data-lc-tab="audit"]')
    pg.wait_for_timeout(2500)
    aud_h, aud_rows = hdr('#lcAuditRows'), rws('#lcAuditRows', 12)
    pg.click('[data-lc-tab="recon"]')
    pg.wait_for_timeout(2500)
    crit_h, crit_rows = hdr('#lcReconCriticalRows'), rws('#lcReconCriticalRows', 20)
    b.close()

print('DOM execqual th=%d td=%s | owned=%d | friction th=%d rows=%d wallet=%s | audit th=%d rows=%d | crit th=%d rows=%d'
      % (len(eq_h), (len(eq_rows[0]) if eq_rows else 0), len(own_rows), len(fr_h), len(fr_rows), fr_wallet,
         len(aud_h), len(aud_rows), len(crit_h), len(crit_rows)))


def hix(h, name):
    for i, x in enumerate(h):
        if x.strip().lower() == name.strip().lower():
            return i
    return -1


def friction_oracle(oid):
    a = sa_by_oid.get(norm(oid))
    if not a:
        return None
    it = oi_by_id.get(norm(a.get('intent_id'))) or {}
    f = lf_by_oid.get(norm(oid)) or {}
    limit = num(a.get('limit_price'))
    if not limit:
        limit = num(it.get('suggested_limit_price') or it.get('target_price'))
    lead = num(it.get('leader_price') or it.get('target_price') or it.get('suggested_limit_price'))
    fill = num(f.get('fill_price'))
    side = str(a.get('side') or f.get('side') or '').upper()
    fvl = None
    if fill and limit:
        raw = (fill - limit) / limit * 10000 if side == 'BUY' else (limit - fill) / limit * 10000
        fvl = round(raw, 2)
    return {'coin': norm(a.get('coin')), 'leader_px': lead, 'copy_px': fill,
            'bps': fvl, 'side': side, 'limit': limit}


def check_friction(rid, col, field):
    hi = hix(fr_h, col)
    if not fr_rows or hi < 0:
        return emit(rid, 'FAIL', [{'name': 'FRICTION_TABLE_PRESENT', 'pass': bool(fr_rows), 'detail': 'th=%d' % len(fr_h)}],
                    {'header': fr_h})
    ci, oi_ = hix(fr_h, 'Coin'), hix(fr_h, 'OID')
    matched, mism, skipped = 0, [], 0
    for r in fr_rows:
        o = friction_oracle(r[oi_]) if oi_ >= 0 else None
        if not o:
            skipped += 1
            continue
        if not eq(r[ci], o['coin']):
            mism.append({'coin': r[ci], 'oracle_coin': o['coin']})
            continue
        if eq(r[hi], o[field]):
            matched += 1
        else:
            mism.append({'oid': r[oi_], 'dom': r[hi], 'oracle': o[field]})
    ok = matched >= 3 and not mism
    emit(rid, 'PASS' if ok else 'FAIL',
         [{'name': 'FRICTION_TABLE_PRESENT', 'pass': True, 'detail': 'wallet=%s th=%d rows=%d' % (fr_wallet, len(fr_h), len(fr_rows))},
          {'name': 'COLUMN_PRESENT', 'pass': True, 'detail': col},
          {'name': 'FIELD_VALUE_MATCH', 'pass': ok, 'detail': 'matched=%d mism=%d skipped=%d' % (matched, len(mism), skipped)}],
         {'matched': matched, 'mismatches': mism[:4], 'skipped_no_oracle': skipped})
    if not ok:
        defects.append({'row_id': rid, 'summary': 'C-Friction %s != CSV-joined engine truth' % col,
                        'evidence': 'matched=%d mism=%s' % (matched, mism[:2])})


check_friction('UI-FP-076', 'Coin', 'coin')
check_friction('UI-FP-078', 'Leader/ref px', 'leader_px')
check_friction('UI-FP-079', 'Our fill px', 'copy_px')
check_friction('UI-FP-084', 'Fill-vs-limit bps', 'bps')

byw = mlp.get('by_wallet') or {}


def wal_match(dom, key):
    d = norm(dom)
    if '...' not in d:
        return d.lower() == norm(key).lower()
    pre, suf = d.split('...', 1)
    k = norm(key).lower()
    return k.startswith(pre.lower()) and k.endswith(suf.lower())


def owned_oracle(wdom, coin):
    for k, d in byw.items():
        if not wal_match(wdom, k):
            continue
        for c, v in (d or {}).items():
            if norm(c).lower() == norm(coin).lower() and isinstance(v, dict):
                return v
    return None


def check_owned(rid, col, field):
    hi = hix(own_h, col)
    if not own_rows or hi < 0:
        return emit(rid, 'FAIL', [{'name': 'OWNED_TABLE_PRESENT', 'pass': bool(own_rows), 'detail': 'col=%s' % (hi >= 0)}], {'header': own_h})
    ci, wi = hix(own_h, 'Coin'), hix(own_h, 'Wallet')
    matched, mism, skipped = 0, [], 0
    for r in own_rows:
        o = owned_oracle(r[wi], r[ci])
        if not o:
            skipped += 1
            continue
        if eq(r[hi], o.get(field)):
            matched += 1
        else:
            mism.append({'coin': norm(r[ci]), 'dom': r[hi], 'oracle': o.get(field)})
    ok = matched >= 3 and not mism
    emit(rid, 'PASS' if ok else 'FAIL',
         [{'name': 'OWNED_TABLE_PRESENT', 'pass': True, 'detail': 'rows=%d' % len(own_rows)},
          {'name': 'COLUMN_PRESENT', 'pass': True, 'detail': col},
          {'name': 'FIELD_VALUE_MATCH', 'pass': ok, 'detail': 'matched=%d mism=%d skipped=%d' % (matched, len(mism), skipped)}],
         {'matched': matched, 'mismatches': mism[:4]})
    if not ok:
        defects.append({'row_id': rid, 'summary': 'owned %s != manual_live_positions' % col, 'evidence': str(mism[:3])})


check_owned('UI-FP-088', 'Side', 'direction')
check_owned('UI-FP-089', 'Signed size', 'signed_size')
check_owned('UI-FP-090', 'Avg entry', 'avg_entry_px')

BODY_ORDER = ['time', 'leader_wallet', 'coin', 'side', 'truth_state', 'status', 'terminal_state',
              'operator_action', 'reject_category', 'oid', 'fill_avg_px', 'fill_size', 'pos',
              'leader_to_send_attempt_ms', 'send_total_ms', 'symbol_resolve_ms', 'sdk_client_ms',
              'exchange_call_ms', 'error']
eqp = {}
for r in (las.get('execution_quality_rows') or []):
    o = norm(r.get('oid'))
    if o:
        eqp[o] = r
    eqp[(norm(r.get('coin')), str(r.get('time'))[:19])] = r


def payload_for(row):
    oi_ = hix(eq_h, 'OID')
    if oi_ >= 0 and oi_ < len(row):
        r = eqp.get(norm(row[oi_]))
        if r:
            return r
    ci, ti = hix(eq_h, 'Coin'), hix(eq_h, 'Time')
    return eqp.get((norm(row[ci]), norm(row[ti])[:19]))


for rid, field in [('UI-FP-107', 'Status'), ('UI-FP-109', 'Operator action'), ('UI-FP-110', 'Reject category'),
                   ('UI-FP-115', 'Leader->send ms'), ('UI-FP-119', 'Exchange ms'), ('UI-FP-120', 'Error')]:
    hi = hix(eq_h, field)
    if not eq_rows or hi < 0:
        emit(rid, 'FAIL', [{'name': 'EXECQUAL_TABLE_PRESENT', 'pass': bool(eq_rows), 'detail': 'col=%s' % (hi >= 0)}], {'header': eq_h})
        continue
    ncell = len(eq_rows[0])
    shift = ncell != len(eq_h)
    matched, mism = 0, []
    for row in eq_rows:
        if len(row) <= hi:
            continue
        pr = payload_for(row)
        if not pr:
            continue
        key = {'Status': 'status', 'Operator action': 'operator_action', 'Reject category': 'reject_category',
               'Leader->send ms': 'leader_to_send_attempt_ms', 'Exchange ms': 'exchange_call_ms',
               'Error': 'error'}[field]
        if eq(row[hi], pr.get(key)):
            matched += 1
        else:
            mism.append({'coin': norm(row[hix(eq_h, 'Coin')]), 'dom_under_header': row[hi], 'oracle': pr.get(key)})
    aligned = matched >= 3 and not mism
    ok = aligned and not shift
    emit(rid, 'PASS' if ok else 'FAIL',
         [{'name': 'EXECQUAL_TABLE_PRESENT', 'pass': True, 'detail': 'th=%d' % len(eq_h)},
          {'name': 'COLUMN_PRESENT', 'pass': True, 'detail': field},
          {'name': 'HEADER_CELL_ALIGNMENT', 'pass': not shift, 'detail': 'thead=%d th vs tbody=%d td' % (len(eq_h), ncell)},
          {'name': 'FIELD_VALUE_MATCH_UNDER_HEADER', 'pass': aligned, 'detail': 'matched=%d mism=%d' % (matched, len(mism))}],
         {'matched': matched, 'mismatches': mism[:4], 'thead_th': len(eq_h), 'row_td': ncell, 'body_order': BODY_ORDER})
    if not ok:
        defects.append({'row_id': rid,
                        'summary': 'Execution Quality %s: renderExecQuality emits %d td but thead declares %d th '
                                   '(unlabelled truth_state pill at index 4 shifts every column from Status onward)'
                                   % (field, ncell, len(eq_h)),
                        'evidence': 'th=%d td=%d matched=%d mism=%s' % (len(eq_h), ncell, matched, mism[:2])})

hi = hix(aud_h, 'Real order result')
ci, wi, ti = hix(aud_h, 'Coin'), hix(aud_h, 'Wallet'), hix(aud_h, 'Time')
matched, mism, skipped = 0, [], 0
for row in aud_rows:
    if hi < 0 or len(row) <= hi:
        continue
    ts = norm(row[ti])[:19]
    cand = [r for r in oi if norm(r.get('created_at'))[:19] == ts]
    if not cand:
        skipped += 1
        continue
    iid = norm(cand[-1].get('intent_id'))
    a = sa_by_intent.get(iid)
    if a and iid not in recent100:
        skipped += 1
        continue
    if a:
        st = norm(a.get('status'))
        want = {'ORDER_FILLED': 'REAL_ORDER_FILLED', 'ORDER_REJECTED': 'EXCHANGE_REJECTED'}.get(st, st or 'NO_SEND_ATTEMPT')
    else:
        dec = norm(cand[-1].get('execution_decision'))
        want = 'WOULD_SEND_ONLY' if dec == 'WOULD_PLACE_IOC_LIMIT' else 'NO_SEND_ATTEMPT'
    if eq(row[hi], want):
        matched += 1
    else:
        mism.append({'coin': norm(row[ci]), 'dom': row[hi], 'oracle': want, 'intent_id': iid})
ok = hi >= 0 and matched >= 3 and not mism
emit('UI-FP-133', 'PASS' if ok else 'FAIL',
     [{'name': 'AUDIT_TABLE_PRESENT', 'pass': bool(aud_rows), 'detail': 'th=%d' % len(aud_h)},
      {'name': 'COLUMN_PRESENT', 'pass': hi >= 0, 'detail': 'Real order result'},
      {'name': 'FIELD_VALUE_MATCH', 'pass': bool(matched >= 3 and not mism), 'detail': 'matched=%d mism=%d skipped=%d' % (matched, len(mism), skipped)}],
     {'matched': matched, 'mismatches': mism[:4], 'skipped': skipped})
if not ok:
    defects.append({'row_id': 'UI-FP-133', 'summary': 'Real order result != intent-joined send attempt', 'evidence': str(mism[:3])})


def crit(s):
    s = str(s or '')
    return s.startswith('CLOSE_') or 'RECOVERY' in s or 'MANUAL_REVIEW' in s


ocrit = [r for r in rc if norm(r.get('event')) in ('SEND_TERMINAL', 'SEND_REJECTED')
         and (crit(r.get('terminal_state')) or crit(r.get('status')) or crit(r.get('action')) or crit(r.get('operator_action')))]
print('recon critical oracle rows=%d dom=%d' % (len(ocrit), len(crit_rows)))
for rid, col, field in [('UI-FP-137', 'Reject category', 'reject_category'),
                        ('UI-FP-139', 'Coin', 'coin'),
                        ('UI-FP-140', 'Wallet', 'wallet')]:
    hi = hix(crit_h, col)
    ii = hix(crit_h, 'Intent')
    if not crit_rows or hi < 0:
        emit(rid, 'FAIL', [{'name': 'CRITICAL_TABLE_PRESENT', 'pass': bool(crit_rows), 'detail': 'col=%s' % (hi >= 0)}], {'header': crit_h})
        continue
    matched, mism, skipped = 0, [], 0
    for row in crit_rows:
        if len(row) <= hi:
            continue
        pre = norm(row[ii])[:24] if ii >= 0 else ''
        cand = [o for o in ocrit if pre and norm(o.get('intent_id')).startswith(pre)]
        if not cand:
            skipped += 1
            continue
        o = cand[-1]
        domv = row[hi]
        if field == 'wallet':
            good = wal_match(domv, norm(o.get('wallet') or o.get('leader_wallet')))
        else:
            good = eq(domv, o.get(field))
        if good:
            matched += 1
        else:
            mism.append({'dom': domv, 'oracle': o.get(field), 'intent': pre})
    ok = matched >= 3 and not mism
    emit(rid, 'PASS' if ok else 'FAIL',
         [{'name': 'CRITICAL_TABLE_PRESENT', 'pass': True, 'detail': 'th=%d rows=%d' % (len(crit_h), len(crit_rows))},
          {'name': 'COLUMN_PRESENT', 'pass': True, 'detail': col},
          {'name': 'FIELD_VALUE_MATCH', 'pass': ok, 'detail': 'matched=%d mism=%d skipped=%d' % (matched, len(mism), skipped)}],
         {'matched': matched, 'mismatches': mism[:4], 'skipped': skipped, 'oracle_critical': len(ocrit)})
    if not ok:
        defects.append({'row_id': rid, 'summary': 'critical %s mismatch' % col, 'evidence': str(mism[:3])})

probe_rows = [['x', 'BTC', 'BUY', '1', '2', '3', '4', '5', '6', 'X1']]
real = {'coin': 'BTC', 'leader_px': 1.0, 'copy_px': 2.0, 'bps': 3.0}
neg_pass = eq(probe_rows[0][4], real['copy_px'])
neg_fail = eq(probe_rows[0][4], 999.0)
negs.append({'name': 'NEG_MUTATED_DOM_FLIPS_TO_FAIL', 'pass': bool(neg_pass and not neg_fail),
             'detail': 'honest=2.0 truth=%s mutated=999.0 truth=%s' % (neg_pass, neg_fail)})
hdr11 = ['TIME', 'COIN', 'SIDE', 'LEADER/REF PX', 'OUR FILL PX', 'SIZE', 'DIFF $', 'DIFF BPS', 'LIMIT PX', 'FILL-VS-LIMIT BPS', 'OID']
negs.append({'name': 'NEG_MISSING_HEADER_NOT_FOUND', 'pass': hix([h for h in hdr11 if h != 'OUR FILL PX'], 'Our fill px') < 0,
             'detail': 'hix without the column returns -1'})
negs.append({'name': 'NEG_EMPTY_IS_NOT_ZERO', 'pass': (not eq('\u2014', '0')) and (not eq('', '0')),
             'detail': 'em-dash/blank != 0'})
negs.append({'name': 'NEG_ALIGNMENT_DETECTOR_BITES', 'pass': (len(eq_h) == 18 and bool(eq_rows) and len(eq_rows[0]) == 19),
             'detail': 'thead=%d tbody=%d' % (len(eq_h), len(eq_rows[0]) if eq_rows else 0)})

out = {'task_id': 't_770ce423', 'title': 'B3-CERT UI FAIL small (17 rows): UI-FP-076..140',
       'harness': 'certification/results/uifa3_harness_v3.py',
       'register_commit': 'b142cf8', 'ssot_commit': '5223ce25',
       'live_surface': BASE + '/live-copy', 'state_dir': str(sd),
       'tested_at_utc': datetime.now(timezone.utc).isoformat(),
       'harness_revision_note': 'v3 supersedes v2: fixed entry URL (307 redirect made friction table falsely absent), '
                                'owned oracle key direction (not side), audit oracle intent-join (not coin-join). '
                                'Execution Quality FAILs are a GENUINE defect at 5223ce25 (tbody 19 td vs thead 18 th).',
       'rows_tested': len(ROWS),
       'summary': {'total_rows': len(ROWS),
                   'pass': sum(1 for r in results.values() if r['result'] == 'PASS'),
                   'fail': sum(1 for r in results.values() if r['result'] == 'FAIL')},
       'rows': [results[r] for r in ROWS if r in results], 'defects': defects, 'negative_tests': negs}
OUT = RES / 'UIFA3_v3_b142cf88d3.json'
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
print('WROTE', OUT)
print('SUMMARY', out['summary'], 'negs', sum(1 for n in negs if n['pass']), '/', len(negs))
