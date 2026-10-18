"""Atomic evidence capture for UI-FP-001..100.
Order: snapshot A (before) -> render DOM -> snapshot B (after).
Every volatile DOM counter must fall inside the bracket [oracle(A), oracle(B)].
READ-ONLY: no POST, no save, no engine contact.
"""
import json, os, shutil, hashlib, datetime, urllib.request
from playwright.sync_api import sync_playwright

STATE = 'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet'
OUT = 'EVIDENCE/ui_fp_001_100'
FILES = ['live_config.json', 'live_ws_health.json', 'live_integrity_status.json',
         'manual_live_positions.json', 'exchange_account_snapshot.json',
         'exchange_account_history.json', 'live_service_state.json']
CSVS = ['send_attempts.csv', 'live_fills.csv', 'order_intents.csv', 'reconciliation.csv']


def snap(tag):
    d = os.path.join(OUT, 'snap_' + tag)
    os.makedirs(os.path.join(d, 'append_only'), exist_ok=True)
    man = {}
    for f in FILES:
        s = os.path.join(STATE, f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(d, f))
            man[f] = hashlib.sha256(open(os.path.join(d, f), 'rb').read()).hexdigest()
    for f in CSVS:
        s = os.path.join(STATE, 'append_only', f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(d, 'append_only', f))
            man['append_only/' + f] = hashlib.sha256(
                open(os.path.join(d, 'append_only', f), 'rb').read()).hexdigest()
    return {'dir': os.path.abspath(d),
            'taken_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'sha256': man}


JS = r"""
() => {
  const txt = e => (e ? (e.innerText||'').replace(/\s+/g,' ').trim() : null);
  const idmap = {}; document.querySelectorAll('[id]').forEach(e => { idmap[e.id] = txt(e); });
  const wt = document.getElementById('lcWalletRows');
  const rows = [];
  if (wt) Array.from(wt.querySelectorAll('tr')).forEach((tr, idx) =>
    rows.push({idx, cells: Array.from(tr.children).map(td => txt(td))}));
  const ctrls = {}; document.querySelectorAll('select,input').forEach(e => {
    if (e.id) ctrls[e.id] = {tag:e.tagName, type:e.type, value:e.value, checked:!!e.checked}; });
  const svg = {};
  ['lcEquityChart'].forEach(i => { const e = document.getElementById(i);
    svg[i] = e ? {viewBox:e.getAttribute('viewBox'),
      paths: e.querySelectorAll('path,line,polyline').length,
      d: Array.from(e.querySelectorAll('path')).map(p => (p.getAttribute('d')||'').slice(0,200)).slice(0,3)} : null; });
  return {idmap, rows, ctrls, svg, body:(document.body.innerText||'').replace(/\s+/g,' ')};
}
"""

A = snap('A')
with urllib.request.urlopen('http://127.0.0.1:8031/live-copy', timeout=60) as r:
    raw = r.read()
res = {'url': 'http://127.0.0.1:8031/live-copy', 'snap_A': A,
       'raw_http_sha256': hashlib.sha256(raw).hexdigest(), 'raw_http_bytes': len(raw)}
open(os.path.join(OUT, 'served_live_copy.raw.html'), 'wb').write(raw)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={'width': 1900, 'height': 1400})
    pg.goto('http://127.0.0.1:8031/live-copy', wait_until='networkidle', timeout=180000)
    pg.wait_for_timeout(8000)
    res['dom'] = pg.evaluate(JS)
    res['rendered_html_sha256'] = hashlib.sha256(pg.content().encode('utf-8')).hexdigest()
    res['wallet_trs'] = pg.evaluate("""() => {const t=document.getElementById('lcWalletRows'); if(!t) return -1;
        const trs=t.querySelectorAll('tbody tr'); if(!trs.length) return 0; trs[0].click(); return trs.length;}""")
    pg.wait_for_timeout(3500)
    res['dom_expanded'] = pg.evaluate(JS)
    pg.screenshot(path=os.path.join(OUT, 'served_live_copy.png'))
    b.close()

B = snap('B')
res['snap_B'] = B
json.dump(res, open(os.path.join(OUT, 'dom_capture.json'), 'w'), ensure_ascii=False)
print('snapA', A['taken_at_utc'])
print('snapB', B['taken_at_utc'])
print('raw_http_sha256', res['raw_http_sha256'], res['raw_http_bytes'])
print('rendered_sha256', res['rendered_html_sha256'])
print('rows', len(res['dom']['rows']), 'expanded', len(res['dom_expanded']['rows']))
print('identical A/B files:', sum(1 for k in A['sha256'] if A['sha256'][k] == B['sha256'].get(k)), '/', len(A['sha256']))
