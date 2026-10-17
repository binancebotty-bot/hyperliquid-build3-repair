import json, os, sys, time, datetime, urllib.request
BASE = 'http://127.0.0.1:8031'
URL = BASE + '/live-copy'

def dom_capture():
    out = {'url': URL}
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page()
            pg.goto(URL, wait_until='networkidle', timeout=25000)
            out['truth_status_html'] = pg.evaluate("()=>{const e=document.querySelector('#lcTruthStatus');return e?e.outerHTML.slice(0,14000):null;}")
            out['stat_cards'] = pg.evaluate("()=>{const t=document.querySelector('#lcTruthStatus');if(!t)return [];return Array.from(t.querySelectorAll('.lc-stat')).map(s=>({label:((s.querySelector('.label')||{}).innerText||'').trim(), value:((s.querySelector('.value')||s).innerText||'').trim().replace(/\\s+/g,' ').slice(0,250), cls:String(s.className)}));}")
            out['top_status_full_text'] = pg.evaluate("()=>{const s=document.querySelector('section.lc-panel.lc-top-status');return s?s.innerText.split(/\\s+/).join(' ').slice(0,8000):null;}")
            out['svgs'] = pg.evaluate("()=>Array.from(document.querySelectorAll('svg')).map(s=>({outer_len:s.outerHTML.length,id:s.id||null,cls:String(s.getAttribute('class')||''),ptext:((s.parentElement&&s.parentElement.innerText)||'').trim().replace(/\\s+/g,' ').slice(0,400)}))")
            out['graph_ids'] = pg.evaluate("()=>{const re=/(graph|chart|exposure|pnl|equity)/i;return Array.from(document.querySelectorAll('#liveCopyPanel *')).filter(e=>e.id&&re.test(e.id)).map(e=>({id:e.id,cls:String(e.className||''),text:(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,500)}));}")
            out['canvas'] = pg.evaluate("()=>document.querySelectorAll('canvas').length")
            out['panel_ids'] = pg.evaluate("()=>Array.from(document.querySelectorAll('#liveCopyPanel [id]')).map(e=>e.id)")
            out['route']='ROUTE_AVAILABLE'
        finally:
            b.close()
    return out

r={}
r['tested_at_utc']=datetime.datetime.utcnow().isoformat()+'Z'
r['tested_at_ms']=int(time.time()*1000)
r['dom']=dom_capture()
print(json.dumps(r,indent=1,ensure_ascii=False))
