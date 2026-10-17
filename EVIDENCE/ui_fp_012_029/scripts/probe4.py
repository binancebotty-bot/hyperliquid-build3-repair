import json, time, datetime, urllib.request
BASE='http://127.0.0.1:8031'; URL=BASE+'/live-copy'
def gj(p,t=8):
    with urllib.request.urlopen(BASE+p,timeout=t) as r: return json.load(r)
from playwright.sync_api import sync_playwright
out={}
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    try:
        pg=b.new_page(); pg.goto(URL,wait_until='networkidle',timeout=25000)
        out['dom_cards']=pg.evaluate("()=>{const t=document.querySelector('#lcTruthStatus');if(!t)return [];return Array.from(t.querySelectorAll('.lc-stat')).map(s=>({label:((s.querySelector('.label')||{}).innerText||'').trim(), value:((s.querySelector('.value')||s).innerText||'').trim().replace(/\\s+/g,' ')}));}")
        out['dom_captured_ms']=int(time.time()*1000)
    finally: b.close()
s=gj('/api/live-copy-summary'); lts=s['live_top_status']
out['api_captured_ms']=int(time.time()*1000)
ls=lts.get('last_send') or {}
lf=lts.get('last_fill') or {}
lr=lts.get('last_reject') or {}
ll=lts.get('last_latency_warning') or {}
out['api']={'last_send_coin':ls.get('coin'),'last_send_status':ls.get('status'),'last_send_ms':ls.get('created_at_ms'),
 'last_fill_coin':lf.get('coin'),'last_fill_side':lf.get('side'),'last_fill_size':lf.get('fill_size'),
 'last_reject_coin':lr.get('coin'),'last_reject_status':lr.get('status'),
 'last_lat_status':ll.get('status'),'last_lat_notes':(ll.get('notes') or '')[:160],
 'master':lts.get('master_real_orders'),'active':lts.get('active_wallets'),'sub':lts.get('subscribed_wallets'),'live':lts.get('live_wallets')}
print(json.dumps(out,indent=1,ensure_ascii=False))
