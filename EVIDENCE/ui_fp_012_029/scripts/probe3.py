import json, sys, time, datetime, urllib.request
BASE='http://127.0.0.1:8031'; URL=BASE+'/live-copy'
def gj(p,t=10):
    try:
        with urllib.request.urlopen(BASE+p,timeout=t) as r: return json.load(r)
    except Exception as e: return {'__err__':repr(e)}
from playwright.sync_api import sync_playwright
out={}
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    try:
        pg=b.new_page(); pg.goto(URL,wait_until='networkidle',timeout=25000)
        out['all_svgs_before']=pg.evaluate("()=>Array.from(document.querySelectorAll('svg')).map(s=>({id:s.id||null}))")
        out['all_ids']=pg.evaluate("()=>Array.from(document.querySelectorAll('[id]')).map(e=>e.id)")
        out['any_master_text']=pg.evaluate("()=>{const re=/MASTER REAL/i;return Array.from(document.querySelectorAll('*')).filter(e=>e.children.length===0&&re.test(e.innerText||'')).map(e=>(e.innerText||'').trim().slice(0,80)).slice(0,10);}")
        out['any_exposure_text']=pg.evaluate("()=>{const re=/exposure/i;return Array.from(document.querySelectorAll('*')).filter(e=>e.children.length===0&&re.test(e.innerText||'')).map(e=>(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,100)).slice(0,20);}")
        # read-only: click first wallet row to reveal detail
        rows=pg.query_selector_all('tr.lc-wallet-row')
        out['wallet_rows']=len(rows)
        clicked=False
        if rows:
            try:
                rows[0].click(timeout=4000); pg.wait_for_timeout(1500); clicked=True
            except Exception as e:
                out['click_err']=repr(e)
        out['clicked']=clicked
        out['all_svgs_after']=pg.evaluate("()=>Array.from(document.querySelectorAll('svg')).map(s=>({id:s.id||null,len:s.outerHTML.length}))")
        out['graph_ids_after']=pg.evaluate("()=>{const re=/(graph|chart|exposure|pnl|equity|detail)/i;return Array.from(document.querySelectorAll('[id]')).filter(e=>re.test(e.id)).map(e=>({id:e.id,vis:!!(e.offsetParent!==null||e.getClientRects().length),text:((e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,200))}));}")
        out['panel_ids_after']=pg.evaluate("()=>Array.from(document.querySelectorAll('#liveCopyPanel [id]')).map(e=>e.id)")
        out['equity_chart_subtitle']=pg.evaluate("()=>{const e=document.querySelector('#lcGraphSubtitle');return e?e.innerText:null;}")
        out['equity_first_last']=pg.evaluate("()=>{const s=document.querySelector('#lcEquityChart');if(!s)return null;const t=s.querySelectorAll('text');return Array.from(t).map(x=>x.textContent).slice(0,12);}")
        out['route']='ROUTE_AVAILABLE'
    finally: b.close()
# same-instant API
s=gj('/api/live-copy-summary')
lts=(s or {}).get('live_top_status',{}) if isinstance(s,dict) else {}
out['api_last_send']={k:lts.get('last_send',{}).get(k) for k in ['coin','side','status','created_at']} if isinstance(lts.get('last_send'),dict) else lts.get('last_send')
out['api_last_fill']={k:lts.get('last_fill',{}).get(k) for k in ['coin','side','fill_size','created_at']} if isinstance(lts.get('last_fill'),dict) else None
out['api_last_reject']={k:lts.get('last_reject',{}).get(k) for k in ['coin','status','created_at']} if isinstance(lts.get('last_reject'),dict) else None
out['api_last_lat']=lts.get('last_latency_warning')
out['api_master']=lts.get('master_real_orders'); out['api_active']=lts.get('active_wallets'); out['api_sub']=lts.get('subscribed_wallets')
out['tested_at_utc']=datetime.datetime.utcnow().isoformat()+'Z'
print(json.dumps(out,indent=1,ensure_ascii=False))
