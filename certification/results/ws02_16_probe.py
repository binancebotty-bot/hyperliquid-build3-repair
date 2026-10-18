import json, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(r'C:/Users/wigmore/.hermes/cache/scratch/b3_clean')
OUT = ROOT / 'certification/results/UI_LCC_WS_02_16_8031.json'
URL = 'http://127.0.0.1:8031/live-copy'
COMMIT = '89b3bc7586bf328df336fc9ea721cee212617762'


def api(path):
    with urllib.request.urlopen('http://127.0.0.1:8031' + path, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


live = api('/api/live-ws-health')
observed = {}

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_page()

    def on_resp(resp):
        if resp.url.endswith('/api/live-ws-health'):
            try:
                observed['live-ws-health'] = resp.json()
            except Exception:
                pass

    page.on('response', on_resp)
    resp = page.goto(URL, wait_until='domcontentloaded', timeout=30000)
    deadline = time.time() + 45
    while time.time() < deadline:
        st = page.evaluate("() => ({ready:document.readyState,h:document.querySelectorAll('#lcHealthRows tr').length})")
        if st['ready'] == 'complete' and st['h'] > 1:
            break
        page.wait_for_timeout(500)
    snap = page.evaluate("""() => {const b=document.querySelector('#lcHealthRows');const t=b&&b.closest('table');
      return {at:new Date().toISOString(),
              headers: t?Array.from(t.querySelectorAll('thead th')).map(x=>x.innerText.trim()):[],
              rows: b?Array.from(b.querySelectorAll('tr')).map(tr=>Array.from(tr.querySelectorAll('td')).map(td=>td.innerText.trim())):[],
              rowtitles: b?Array.from(b.querySelectorAll('tr')).map(tr=>Array.from(tr.querySelectorAll('td')).map(td=>td.getAttribute('title')||'')):[]};}""")
    b.close()

hb = (observed.get('live-ws-health') or live).get('health', {})
wallets = hb.get('wallets', {})
result = {
    'tested_commit': COMMIT,
    'tested_at_utc': datetime.now(timezone.utc).isoformat(),
    'page': {'url': URL, 'http_status': resp.status if resp else None, 'dom_captured_at': snap['at']},
    'serving_process': {'pid': 33368, 'started_at_utc': '2026-10-17T10:54:09.552605+00:00', 'serving_commit': COMMIT},
    'health_headers': snap['headers'],
    'health_rows': snap['rows'],
    'health_row_titles': snap['rowtitles'],
    'api_health_keys': sorted(hb.keys()),
    'api_ws_summary': hb.get('ws_summary'),
    'api_wallets': wallets,
    'api_wallet_field_union': sorted({k for v in wallets.values() if isinstance(v, dict) for k in v}),
}
OUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({'out': str(OUT), 'headers': snap['headers'], 'nrows': len(snap['rows']),
                  'first_row': snap['rows'][0] if snap['rows'] else None,
                  'wallet_field_union': result['api_wallet_field_union'],
                  'status': resp.status if resp else None}, indent=2))
