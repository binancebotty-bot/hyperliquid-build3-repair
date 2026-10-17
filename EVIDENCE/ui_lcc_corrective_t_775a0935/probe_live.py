import json,time,hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright
OUT=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935/evidence');OUT.mkdir(parents=True,exist_ok=True)
URL='http://127.0.0.1:8031/live-copy'
cap=[];res={'url':URL,'started':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
with sync_playwright() as p:
    b=p.chromium.launch(headless=True);ctx=b.new_context();pg=ctx.new_page()
    pg.on('dialog',lambda d:d.accept())
    pg.on('response',lambda r:cap.append({'url':r.url,'status':r.status}) if '/api/' in r.url else None)
    pg.goto(URL,wait_until='domcontentloaded',timeout=60000)
    rows=0;dl=time.time()+70
    while time.time()<dl:
        rows=pg.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row','e=>e.length')
        if rows>0:break
        time.sleep(1.5)
    res['rows_rendered']=rows
    res['rows_head']=pg.inner_text('#lcWalletRows')[:500]
    rd=pg.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row',"els=>els.map(tr=>{const v=s=>{const e=tr.querySelector(s);return e?e.value:null};const b=a=>{const e=tr.querySelector('button[data-act=\"'+a+'\"]');return e?e.textContent.trim():null};return {w:tr.dataset.wallet,mode:v('select[name=mode]'),cm:v('select[name=copy_mode]'),F:v('input[name=fixed_notional]'),N:v('input[name=norm_base]'),B:v('input[name=leader_equity_base]'),inp:Array.from(tr.querySelectorAll('input')).map(i=>i.name),save:b('save'),clo:b('clo'),off:b('off'),arc:b('archive'),cells:Array.from(tr.querySelectorAll('td')).map(t=>t.innerText.replace(/\\s+/g,' ').trim()).slice(0,9)}})")
    res['rows']=rd
    tgt=None
    for r in rd:
        if (r.get('mode') or '').upper()=='LIVE':tgt=r['w'];break
    tgt=tgt or (rd[0]['w'] if rd else None)
    res['detail_target']=tgt
    det={'text':None}
    if tgt:
        try:
            pg.click('#lcWalletRows tr.lc-wallet-row[data-wallet=\"%s\"] td:first-child'%tgt,timeout=15000);time.sleep(3)
            det=pg.evaluate("(w)=>{const id='lcdet-'+w.replace(/[^a-z0-9]/gi,'');const el=document.getElementById(id);return el?{id:id,text:el.innerText}:{id:id,text:null}}",tgt)
        except Exception as e:det={'error':str(e)}
    res['detail']=det
    html=pg.content();(OUT/'live_dom_capture.html').write_text(html,encoding='utf-8')
    res['dom_sha']=hashlib.sha256(html.encode()).hexdigest();res['dom_len']=len(html)
    ctx.close();b.close()
res['api_calls']=cap
(OUT/'live_probe_result.json').write_text(json.dumps(res,indent=1,default=str),encoding='utf-8')
print(json.dumps({k:res[k] for k in ['rows_rendered','detail_target','dom_len','api_calls']},indent=1,default=str))
print('DETLEN',len((res.get('detail') or {}).get('text') or ''))
