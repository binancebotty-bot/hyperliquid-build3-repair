from playwright.sync_api import sync_playwright
import json, urllib.request
BASE='http://127.0.0.1:8031'
def get(path):
 with urllib.request.urlopen(BASE+path,timeout=8) as r: return json.loads(r.read().decode('utf-8','replace'))
with sync_playwright() as p:
 b=p.chromium.launch(headless=True); page=b.new_page(); page.goto(BASE+'/live-copy',wait_until='networkidle',timeout=25000)
 data={}
 data['table_texts']=page.eval_on_selector_all('#liveCopyPanel table','ts=>ts.map((t,i)=>({i,rows:t.rows.length,head:t.rows[0]?.innerText,text:t.innerText.slice(0,1500)}))')
 data['api']=get('/api/live-copy-summary')
 page.get_by_role('button',name='Execution Quality').click()
 page.wait_for_timeout(500)
 data['execution_quality_tables']=page.eval_on_selector_all('#liveCopyPanel table','ts=>ts.map((t,i)=>({i,rows:t.rows.length,head:t.rows[0]?.innerText,text:t.innerText.slice(0,2500)}))')
 data['execution_quality_text']=page.locator('#liveCopyPanel').inner_text()[-5000:]
 print(json.dumps(data,ensure_ascii=False))
 b.close()
