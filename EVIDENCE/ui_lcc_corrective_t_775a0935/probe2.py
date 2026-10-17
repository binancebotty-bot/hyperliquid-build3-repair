import json,time,hashlib,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
WS=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935')
OUT=WS/'evidence';OUT.mkdir(parents=True,exist_ok=True)
SD=Path(r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet')
FRZ=WS/'frozen';FRZ.mkdir(parents=True,exist_ok=True)
URL='http://127.0.0.1:8031/live-copy'
res={'url':URL,'captured_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
with sync_playwright() as p:
    b=p.chromium.launch(headless=True);ctx=b.new_context();pg=ctx.new_page()
    pg.on('dialog',lambda d:d.accept())
    pg.goto(URL,wait_until='domcontentloaded',timeout=60000)
    rows=0;dl=time.time()+70
    while time.time()<dl:
        rows=pg.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row','e=>e.length')
        if rows>0:break
        time.sleep(1.5)
    res['rows_rendered']=rows
    rd=pg.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row',"els=>els.map(tr=>{const v=s=>{const e=tr.querySelector(s);return e?e.value:null};const b=a=>{const e=tr.querySelector('button[data-act=\"'+a+'\"]');return e?{t:e.textContent.trim(),ty:e.getAttribute('type'),act:e.dataset.act}:null};return {w:tr.dataset.wallet,mode:v('select[name=mode]'),cm:v('select[name=copy_mode]'),F:v('input[name=fixed_notional]'),N:v('input[name=norm_base]'),B:v('input[name=leader_equity_base]'),inp:Array.from(tr.querySelectorAll('input')).map(i=>i.name),save:b('save'),clo:b('clo'),off:b('off'),arc:b('archive'),cells:Array.from(tr.querySelectorAll('td')).map(t=>t.innerText.replace(/\\s+/g,' ').trim())}})")
    res['rows']=rd
    # detail expand for ALL LIVE wallets (first 3)
    dets={}
    live=[r['w'] for r in rd if (r.get('mode') or '').upper()=='LIVE'][:3]
    for w in live:
        try:
            pg.click('#lcWalletRows tr.lc-wallet-row[data-wallet=\"%s\"] td:first-child'%w,timeout=10000);time.sleep(2)
            dets[w]=pg.evaluate("(w)=>{const id='lcdet-'+w.replace(/[^a-z0-9]/gi,'');const el=document.getElementById(id);return el?el.innerText:null}",w)
            pg.click('#lcWalletRows tr.lc-wallet-row[data-wallet=\"%s\"] td:first-child'%w,timeout=10000);time.sleep(1)
        except Exception as e: dets[w]='ERR '+str(e)
    res['details']={k:(v or '') for k,v in dets.items()}
    res['detail_wallets']=live
    html=pg.content();res['dom_sha']=hashlib.sha256(html.encode()).hexdigest()
    ctx.close();b.close()
# FREEZE source files AFTER dom settle (point-in-time copy)
snap={}
for name in ['live_config.json','append_only/live_fills.csv','append_only/send_attempts.csv']:
    src=SD/name; dst=FRZ/Path(name).name
    shutil.copy2(src,dst)
    snap[name]={'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'bytes':dst.stat().st_size,'mtime':dst.stat().st_mtime}
res['frozen']=snap
res['frozen_at_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
(OUT/'probe2_result.json').write_text(json.dumps(res,indent=1,default=str),encoding='utf-8')
print('rows',res['rows_rendered'],'dom_sha',res['dom_sha'][:16])
print('details',list(res['details']))
print('frozen',json.dumps(snap,indent=1)[:600])
