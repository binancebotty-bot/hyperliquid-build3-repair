import json, urllib.request, hashlib, pathlib
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:8031'
def get(path):
    with urllib.request.urlopen(BASE+path, timeout=10) as r: return {'status':r.status,'body':r.read().decode('utf-8')}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    page=browser.new_page()
    page.goto(BASE+'/live-copy', wait_until='networkidle', timeout=30000)
    dom=page.evaluate('''() => ({url:location.href,title:document.title,body:document.body.innerText,controls:[...document.querySelectorAll('input,textarea,select')].map(e=>({tag:e.tagName,type:e.type,id:e.id,name:e.name,value:e.value,aria:e.getAttribute('aria-label'),placeholder:e.placeholder,outer:e.outerHTML.slice(0,500)}))})''')
    browser.close()
root=pathlib.Path(__file__).parent
out={'captured_at_utc':datetime.now(timezone.utc).isoformat(),'url':BASE+'/live-copy','dom':dom,'api':{path:get(path) for path in ['/api/state','/api/live-config','/api/ui-state']}}
(root/'dom_capture.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({'captured_at_utc':out['captured_at_utc'],'dom_title':dom['title'],'control_count':len(dom['controls']),'body_chars':len(dom['body']),'api_statuses':{k:v['status'] for k,v in out['api'].items()}},indent=2))
