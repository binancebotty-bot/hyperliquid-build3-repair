#!/usr/bin/env python3
"""Read-only rendered UI and served API capture for UI-FP corrective rows."""
import datetime, json, urllib.request
from pathlib import Path
BASE = 'http://127.0.0.1:8031'
OUT = Path(__file__).with_name('dom_capture.json')
def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return {'status': r.status, 'body': json.loads(r.read().decode('utf-8', 'replace'))}
def main():
    from playwright.sync_api import sync_playwright
    capture = {'captured_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'url': BASE + '/live-copy'}
    for path in ['/api/live-config', '/api/ui-state', '/api/state', '/api/global-controls']:
        try: capture['api' + path.replace('/', '_')] = get(path)
        except Exception as e: capture['api' + path.replace('/', '_')] = {'error': repr(e)}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            response = page.goto(BASE + '/live-copy', wait_until='networkidle', timeout=30000)
            capture['dom'] = page.evaluate('''() => ({
              status: document.readyState, title: document.title, body_text: document.body.innerText,
              input_select_values: Array.from(document.querySelectorAll('input,select,textarea')).map(e=>({tag:e.tagName,type:e.type||'',name:e.name||'',id:e.id||'',value:e.value||'',selected:Array.from(e.selectedOptions||[]).map(o=>o.textContent.trim())})),
              elements: Array.from(document.querySelectorAll('[class*=block],[id*=block],[class*=allow],[id*=allow],[data-symbol],tr')).map(e=>({tag:e.tagName,id:e.id||'',class:String(e.className||''),data_symbol:e.getAttribute('data-symbol'),text:(e.innerText||'').trim().slice(0,1000)})).filter(e=>e.text||e.data_symbol).slice(0,500),
              wallet_rows: Array.from(document.querySelectorAll('tr[data-wallet]')).map(tr=>({wallet:tr.getAttribute('data-wallet'),copy_mode:tr.querySelector('select[name=copy_mode]')?.value||null,fixed_notional:tr.querySelector('input[name=fixed_notional]')?.value||null})),
              html: document.documentElement.outerHTML
            })''')
            capture['http_status'] = response.status if response else None
        finally: browser.close()
    OUT.write_text(json.dumps(capture, indent=2, ensure_ascii=False), encoding='utf-8')
    print('capture_file=', OUT)
    print('http_status=', capture.get('http_status'), 'title=', capture.get('dom', {}).get('title'))
    for key in ('api_api_live-config','api_api_ui-state','api_api_state','api_api_global-controls'):
        obj=capture.get(key,{}); body=obj.get('body',{})
        print(key, 'status=',obj.get('status'),'error=',obj.get('error'),'keys=',list(body)[:35] if isinstance(body,dict) else type(body).__name__)
    d=capture.get('dom',{})
    print('DOM inputs=',len(d.get('input_select_values',[])),'body chars=',len(d.get('body_text','')))
    for line in d.get('body_text','').splitlines():
        if any(k in line.lower() for k in ('block','allow','symbol','marketable','adverse','copy mode','notional')): print('UI:',line[:300])
if __name__=='__main__': main()
