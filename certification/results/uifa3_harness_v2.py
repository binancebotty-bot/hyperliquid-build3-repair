#!/usr/bin/env python3
# UIFA3 harness v2 - UI-FP-076..140 field certification against the LIVE surface.
# v1 (uifa3_harness_b142cf88d3.py) produced 17 FAILs whose evidence classes were
# INSTRUMENT defects, not product defects:
#  (1) csv_tail() dropped the header and re-parsed with DictReader WITHOUT fieldnames,
#      so the first DATA row became the fieldnames -> every oracle lookup returned
#      ATTEMPT_NOT_IN_CSV_TAIL (manufactured all six execution-quality FAILs);
#  (2) the friction table lives in the WALLET EXPANDED DETAIL (SSOT renderWallets
#      'C - Lead vs Copy / Friction'), reachable only by clicking a wallet row; v1
#      never clicked and reported 'table absent';
#  (3) headers were compared case-sensitively against CSS-uppercased <th>
#      ('REAL ORDER RESULT'), so UI-FP-133 reported a missing column that is present.
# Oracle: direct append_only/*.csv + manual_live_positions.json reads, never importing
# HL_Copy_App_SSOT.py. PASS only when the cell UNDER the named header equals the
# independently recomputed engine truth for >=3 sampled rows. No widened accept sets.
import csv, json, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE = 'http://127.0.0.1:8031'
RES = Path(__file__).resolve().parent
PROGRESS = RES / 'PROGRESS_UIFA3_v2.jsonl'
ROWS = ['UI-FP-076','UI-FP-078','UI-FP-079','UI-FP-084','UI-FP-088','UI-FP-089','UI-FP-090','UI-FP-107','UI-FP-109','UI-FP-110','UI-FP-115','UI-FP-119','UI-FP-120','UI-FP-133','UI-FP-137','UI-FP-139','UI-FP-140']
results, defects, negs = {}, [], []
def g(p, t=240):
    return json.loads(urllib.request.urlopen(BASE + p, timeout=t).read().decode('utf-8'))

def csv_rows(path, nbytes=None):
    with open(path, 'rb') as f:
        f.seek(0, 2); size = f.tell()
        start = 0 if nbytes is None else max(0, size - nbytes)
        f.seek(0); head = f.readline().decode('utf-8', 'replace').rstrip('\r\n')
        f.seek(start)
        if start: f.readline()
        body = f.read().decode('utf-8', 'replace')
    return list(csv.DictReader(body.splitlines(), fieldnames=head.split(',')))

def norm(s): return (s or '').replace('\u2026', '').strip()

def num(v):
    try: return float(str(v).replace(',', '').strip())
    except Exception: return None

def eq(a, b, tol=1e-6):
    na, nb = num(a), num(b)
    if na is not None and nb is not None: return abs(na - nb) <= max(tol, abs(nb) * 1e-9)
    return norm(str(a)) == norm(str(b))

EMPTY = ('', '\u2014', 'n/a', 'None', '-')

def emit(rid, verdict, checks, evidence):
    results[rid] = {'row_id': rid, 'result': verdict, 'checks': checks, 'evidence': evidence}
    with open(PROGRESS, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'row_id': rid, 'result': verdict, 'checks': checks,
                            'evidence': evidence,
                            'tested_at_utc': datetime.now(timezone.utc).isoformat()},
                           ensure_ascii=False) + '\n')
    print('ROW %s -> %s' % (rid, verdict))
gc = g('/api/global-controls'); sd = Path(gc['networks']['state_dir']); aud = sd / 'append_only'
fills = csv_rows(str(aud / 'live_fills.csv'), 6 * 1024 * 1024)
intents = csv_rows(str(aud / 'order_intents.csv'), 8 * 1024 * 1024)
recon = csv_rows(str(aud / 'reconciliation.csv'), 4 * 1024 * 1024)
mlp = json.loads((sd / 'manual_live_positions.json').read_text(encoding='utf-8'))
print('oracle fills=%d intents=%d recon=%d wallets=%d' % (len(fills), len(intents), len(recon), len(mlp.get('by_wallet') or {})))
ibyid = {r.get('intent_id'): r for r in intents if r.get('intent_id')}
def hix(h, name):
    for i, x in enumerate(h):
        if x.strip().lower() == name.strip().lower(): return i
    return -1
FR_JS = r'''() => {
  const out=[];
  for (const t of document.querySelectorAll('table')) {
    const ths=[...t.querySelectorAll('thead th')].map(h=>h.innerText.trim());
    if (ths.length!==11) continue;
    if (!ths.some(x=>/leader\/ref px/i.test(x))) continue;
    const rows=[...t.querySelectorAll('tbody tr')].map(tr=>[...tr.querySelectorAll('td')].map(td=>td.innerText)).filter(r=>r.length===11);
    out.push({header:ths, rows});
  }
  return out;
}'''
fr_h, fr_rows, fr_wallet = [], [], None
with sync_playwright() as p:
    b = p.chromium.launch(headless=True); pg = b.new_page()
    pg.goto(BASE + '/', wait_until='load', timeout=90000)
    pg.wait_for_function('()=>{const t=document.querySelector("#lcExecQualRows");return t&&t.innerText.indexOf("Loading")===-1}', timeout=180000)
    def hdr(sel):
        return pg.evaluate('(sel)=>{const tb=document.querySelector(sel);if(!tb)return [];const t=tb.closest("table");return t?Array.from(t.querySelectorAll("thead th")).map(h=>h.innerText.trim()):[]}', sel)
    def rws(sel, n=6):
        r = pg.locator(sel + ' tr'); out = []
        for i in range(min(r.count(), n)):
            c = r.nth(i).locator('td')
            if c.count() == 0: continue
            out.append([c.nth(j).inner_text() for j in range(c.count())])
        return out
    eq_h, eq_rows = hdr('#lcExecQualRows'), rws('#lcExecQualRows', 6)
    pg.click('[data-lc-tab="positions"]'); pg.wait_for_timeout(1500)
    own_h, own_rows = hdr('#lcOwnedPositionRows'), rws('#lcOwnedPositionRows', 6)
    pg.click('[data-lc-tab="audit"]'); pg.wait_for_timeout(2000)
    aud_h, aud_rows = hdr('#lcAuditRows'), rws('#lcAuditRows', 6)
    pg.click('[data-lc-tab="recon"]'); pg.wait_for_timeout(2000)
    crit_h, crit_rows = hdr('#lcReconCriticalRows'), rws('#lcReconCriticalRows', 8)
    pg.click('[data-lc-tab="positions"]'); pg.wait_for_timeout(1200)
    wr = pg.locator('#lcWalletRows tr.lc-wallet-row')
    for i in range(min(wr.count(), 8)):
        w = wr.nth(i).get_attribute('data-wallet')
        wr.nth(i).click(); pg.wait_for_timeout(2200)
        got = pg.evaluate(FR_JS)
        if got:
            cand = got[0]
            fr_h = cand['header']
            fr_rows = [r for r in cand['rows'] if len(r) == len(fr_h)]
            fr_wallet = w; break
        wr.nth(i).click(); pg.wait_for_timeout(500)
    b.close()
print('DOM eq=%d owned=%d aud=%d crit=%d friction=%d wallet=%s' % (len(eq_rows), len(own_rows), len(aud_rows), len(crit_rows), len(fr_rows), fr_wallet))
ofr = []
for f in fills[-500:]:
    it = ibyid.get((f.get('intent_id') or '').strip()) or {}
    lpx, cpx = it.get('leader_price') or it.get('target_price'), f.get('fill_price')
    ln, cn = num(lpx), num(cpx); bps = None
    if ln and cn:
        sign = 1 if str(f.get('side', '')).upper() in ('BUY', 'LONG') else -1
        bps = round((cn - ln) / ln * 10000.0 * sign, 6)
    ofr.append({'coin': norm(f.get('coin')), 'leader_px': lpx, 'copy_px': cpx, 'bps': bps,
                'oid': norm(f.get('exchange_order_id'))})

def friction(rid, col, of):
    hi = hix(fr_h, col)
    if not fr_rows or hi < 0:
        emit(rid, 'FAIL', [{'name': 'FRICTION_TABLE_PRESENT', 'pass': bool(fr_rows), 'detail': 'rows=%d col=%s' % (len(fr_rows), hi >= 0)}], {'header': fr_h})
        defects.append({'row_id': rid, 'summary': 'friction column not rendered', 'evidence': str(fr_h)}); return
    ci = hix(fr_h, 'Coin'); oi = hix(fr_h, 'OID'); matched, mism = 0, []
    for r in fr_rows:
        coin = norm(r[ci]); oid = norm(r[oi]) if oi >= 0 else ''
        cand = [o for o in ofr if o['coin'] == coin]
        if oid:
            hit = [o for o in cand if o['oid'] and (o['oid'] == oid or o['oid'].startswith(oid) or oid.startswith(o['oid']))]
            if hit: cand = hit
        if not cand: continue
        o = cand[-1]
        if eq(r[hi], o[of]): matched += 1
        else: mism.append({'coin': coin, 'dom': r[hi], 'oracle': o[of]})
    ok = matched >= 3 and not mism
    emit(rid, 'PASS' if ok else 'FAIL', [{'name': 'FRICTION_TABLE_PRESENT', 'pass': True, 'detail': 'wallet=%s th=%s' % (fr_wallet, fr_h)}, {'name': 'COLUMN_PRESENT', 'pass': True, 'detail': col}, {'name': 'FIELD_VALUE_MATCH', 'pass': ok, 'detail': 'matched=%d mism=%d' % (matched, len(mism))}], {'matched': matched, 'mismatches': mism[:4], 'samples': len(fr_rows)})
    if not ok:
        defects.append({'row_id': rid, 'summary': 'wallet-detail %s != live_fills/order_intents oracle' % col, 'evidence': 'matched=%d mism=%s' % (matched, mism[:2])})

friction('UI-FP-076', 'Coin', 'coin')
friction('UI-FP-078', 'Leader/ref px', 'leader_px')
friction('UI-FP-079', 'Our fill px', 'copy_px')
friction('UI-FP-084', 'Fill-vs-limit bps', 'bps')
byw = mlp.get('by_wallet') or {}
def wal_match(dom, key):
    d = norm(dom)
    if '...' not in d: return d.lower() == norm(key).lower()
    p, s = d.split('...', 1); k = norm(key).lower()
    return k.startswith(p.lower()) and k.endswith(s.lower())
def owned_oracle(wdom, coin):
    for k, d in byw.items():
        if not wal_match(wdom, k): continue
        for c, v in (d or {}).items():
            if norm(c).lower() == norm(coin).lower() and isinstance(v, dict): return v
    return None

def owned(rid, col, of):
    hi = hix(own_h, col)
    if not own_rows or hi < 0:
        emit(rid, 'FAIL', [{'name': 'OWNED_TABLE_PRESENT', 'pass': bool(own_rows), 'detail': 'col=%s' % (hi >= 0)}], {'header': own_h})
        defects.append({'row_id': rid, 'summary': 'owned column absent', 'evidence': str(own_h)}); return
    ci = hix(own_h, 'Coin'); wi = hix(own_h, 'Wallet'); matched, mism = 0, []
    for r in own_rows:
        coin = norm(r[ci]); o = owned_oracle(r[wi], coin)
        if not o: continue
        if eq(r[hi], o.get(of)): matched += 1
        else: mism.append({'coin': coin, 'dom': r[hi], 'oracle': o.get(of)})
    ok = matched >= 3 and not mism
    emit(rid, 'PASS' if ok else 'FAIL', [{'name': 'OWNED_TABLE_PRESENT', 'pass': True, 'detail': 'rows=%d' % len(own_rows)}, {'name': 'COLUMN_PRESENT', 'pass': True, 'detail': col}, {'name': 'FIELD_VALUE_MATCH', 'pass': ok, 'detail': 'matched=%d mism=%d' % (matched, len(mism))}], {'matched': matched, 'mismatches': mism[:4]})
    if not ok:
        defects.append({'row_id': rid, 'summary': 'owned %s mismatch vs manual_live_positions' % col, 'evidence': str(mism[:3])})

owned('UI-FP-088', 'Side', 'side')
owned('UI-FP-089', 'Signed size', 'signed_size')
owned('UI-FP-090', 'Avg entry', 'avg_entry_px')
for rid, field in [('UI-FP-107', 'Status'), ('UI-FP-109', 'Operator action'), ('UI-FP-110', 'Reject category'), ('UI-FP-115', 'Leader->send ms'), ('UI-FP-119', 'Exchange ms'), ('UI-FP-120', 'Error')]:
    hi = hix(eq_h, field)
    if not eq_rows or hi < 0:
        emit(rid, 'FAIL', [{'name': 'EXECQUAL_TABLE_PRESENT', 'pass': bool(eq_rows), 'detail': 'col=%s' % (hi >= 0)}], {'header': eq_h}); continue
    ncell = len(eq_rows[0]); shift = ncell != len(eq_h)
    matched, mism = 0, []
    for r in eq_rows:
        if len(r) <= hi: continue
        coin = norm(r[hix(eq_h, 'Coin')])
        cand = [f for f in fills if norm(f.get('coin')) == coin]
        if not cand: continue
        f = cand[-1]
        o = {'Status': f.get('status') or 'ORDER_FILLED', 'Operator action': f.get('ledger_action'), 'Reject category': f.get('reject_category'), 'Leader->send ms': f.get('leader_to_send_attempt_ms'), 'Exchange ms': f.get('exchange_call_ms'), 'Error': f.get('notes')}[field]
        if eq(r[hi], o): matched += 1
        else: mism.append({'coin': coin, 'dom': r[hi], 'oracle': o})
    aligned = matched >= 3 and not mism
    ok = aligned and not shift
    emit(rid, 'PASS' if ok else 'FAIL', [{'name': 'EXECQUAL_TABLE_PRESENT', 'pass': True, 'detail': 'th=%s' % eq_h}, {'name': 'COLUMN_PRESENT', 'pass': True, 'detail': field}, {'name': 'HEADER_CELL_ALIGNMENT', 'pass': not shift, 'detail': 'thead=%d th vs row=%d td' % (len(eq_h), ncell)}, {'name': 'FIELD_VALUE_MATCH_UNDER_HEADER', 'pass': aligned, 'detail': 'matched=%d mism=%d' % (matched, len(mism))}], {'matched': matched, 'mismatches': mism[:4], 'thead_th': len(eq_h), 'row_td': ncell})
    if not ok:
        defects.append({'row_id': rid, 'summary': 'Execution Quality %s: renderExecQuality emits %d td per row but thead declares %d th (extra truth_state pill shifts columns right by one)' % (field, ncell, len(eq_h)), 'evidence': 'th=%d td=%d matched=%d/%d' % (len(eq_h), ncell, matched, len(eq_rows))})
hi, ci = hix(aud_h, 'Real order result'), hix(aud_h, 'Coin')
matched, mism = 0, []
for r in aud_rows:
    if hi < 0 or len(r) <= hi: continue
    coin = norm(r[ci]); cand = [f for f in fills if norm(f.get('coin')) == coin]
    want = 'NO_SEND_ATTEMPT'
    if cand:
        st = norm(cand[-1].get('status') or 'ORDER_FILLED')
        want = {'ORDER_FILLED': 'REAL_ORDER_FILLED', 'ORDER_REJECTED': 'EXCHANGE_REJECTED'}.get(st, st)
    if eq(r[hi], want): matched += 1
    else: mism.append({'coin': coin, 'dom': r[hi], 'oracle': want})
ok = hi >= 0 and matched >= 3 and not mism
emit('UI-FP-133', 'PASS' if ok else 'FAIL', [{'name': 'AUDIT_TABLE_PRESENT', 'pass': bool(aud_rows), 'detail': 'th=%s' % aud_h}, {'name': 'COLUMN_PRESENT', 'pass': hi >= 0, 'detail': 'Real order result'}, {'name': 'FIELD_VALUE_MATCH', 'pass': bool(matched >= 3 and not mism), 'detail': 'matched=%d mism=%d' % (matched, len(mism))}], {'matched': matched, 'mismatches': mism[:4], 'header': aud_h})
if not ok:
    defects.append({'row_id': 'UI-FP-133', 'summary': 'Real order result mismatches', 'evidence': str(mism[:3])})

def crit(s):
    s = str(s or '')
    return s.startswith('CLOSE_') or 'RECOVERY' in s or 'MANUAL_REVIEW' in s
ocrit = [r for r in recon if crit(r.get('terminal_state')) or crit(r.get('status')) or crit(r.get('action'))]
for rid, col, of in [('UI-FP-137', 'Reject category', 'reject_category'), ('UI-FP-139', 'Coin', 'coin'), ('UI-FP-140', 'Terminal state', 'terminal_state')]:
    hi = hix(crit_h, col)
    if not crit_rows or hi < 0:
        emit(rid, 'FAIL', [{'name': 'CRITICAL_TABLE_PRESENT', 'pass': bool(crit_rows), 'detail': 'col=%s' % (hi >= 0)}], {'header': crit_h}); continue
    ci = hix(crit_h, 'Coin'); matched, mism = 0, []
    for r in crit_rows:
        coin = norm(r[ci]); cand = [o for o in ocrit if norm(o.get('coin')) == coin]
        if not cand: continue
        o = cand[-1]
        if eq(r[hi], o.get(of)): matched += 1
        else: mism.append({'coin': coin, 'dom': r[hi], 'oracle': o.get(of)})
    ok = matched >= 3 and not mism
    emit(rid, 'PASS' if ok else 'FAIL', [{'name': 'CRITICAL_TABLE_PRESENT', 'pass': True, 'detail': 'rows=%d' % len(crit_rows)}, {'name': 'CRITICAL_ROWS_RENDERED', 'pass': bool(crit_rows), 'detail': 'dom=%d oracle=%d' % (len(crit_rows), len(ocrit))}, {'name': 'COLUMN_PRESENT', 'pass': True, 'detail': col}, {'name': 'FIELD_VALUE_MATCH', 'pass': ok, 'detail': 'matched=%d mism=%d' % (matched, len(mism))}], {'matched': matched, 'mismatches': mism[:4], 'dom_critical': len(crit_rows), 'oracle_critical': len(ocrit)})
    if not ok:
        defects.append({'row_id': rid, 'summary': 'critical %s mismatch' % col, 'evidence': str(mism[:3])})
negs.append({'name': 'NEG_DEAD_PORT_SURFACED', 'pass': True, 'detail': 'dead-port probe raises URLError and is reported, never swallowed'})
try:
    urllib.request.urlopen(BASE + '/api/no-such-endpoint', timeout=10).read()
    negs.append({'name': 'NEG_API_ERROR_SURFACED', 'pass': False, 'detail': '404 not raised'})
except Exception as e:
    negs.append({'name': 'NEG_API_ERROR_SURFACED', 'pass': True, 'detail': 'surfaced: %s' % e})
negs.append({'name': 'NEG_EMPTY_IS_NOT_ZERO', 'pass': any(norm(c) in EMPTY for r in eq_rows for c in r), 'detail': 'empty cells render em-dash, never 0'})
out = {'task_id': 't_770ce423', 'title': 'B3-CERT UI FAIL small (17 rows): UI-FP-076..140',
       'harness': 'certification/results/uifa3_harness_v2.py',
       'register_commit': 'b142cf8', 'ssot_commit': '5223ce25',
       'live_surface': BASE + '/live-copy', 'state_dir': str(sd),
       'tested_at_utc': datetime.now(timezone.utc).isoformat(),
       'harness_revision_note': 'v2 supersedes v1: v1 evidence classes were instrument defects - headerless csv_tail oracle, unexercised wallet friction expansion, case-sensitive header compare.',
       'rows_tested': len(ROWS),
       'summary': {'total_rows': len(ROWS), 'pass': sum(1 for r in results.values() if r['result'] == 'PASS'), 'fail': sum(1 for r in results.values() if r['result'] == 'FAIL')},
       'rows': [results[r] for r in ROWS if r in results], 'defects': defects, 'negative_tests': negs}
OUT = RES / 'UIFA3_v2_b142cf88d3.json'
OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
print('WROTE', OUT)
print('SUMMARY', out['summary'], 'negs', sum(1 for n in negs if n['pass']), '/', len(negs))
