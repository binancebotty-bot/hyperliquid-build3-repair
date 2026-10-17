import json,time,hashlib,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
WS=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935')
OUT=WS/'evidence';OUT.mkdir(parents=True,exist_ok=True)
SD=Path(r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet')
FRZ=WS/'frozen3';FRZ.mkdir(parents=True,exist_ok=True)
URL='http://127.0.0.1:8031/live-copy'
res={}
with sync_playwright() as p:
    b=p.chromium.launch(headless=True);ctx=b.new_context();pg=ctx.new_page()
    pg.on('dialog',lambda d:d.accept())
    pg.goto(URL,wait_until='domcontentloaded',timeout=60000)
    dl=time.time()+70
    while time.time()<dl:
        if pg.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row','e=>e.length')>0:break
        time.sleep(1.5)
    # freeze oracle files IMMEDIATELY
    for name in ['live_config.json','manual_live_positions.json','append_only/live_fills.csv']:
        dst=FRZ/Path(name).name; shutil.copy2(SD/name,dst)
    res['freeze_t']=time.time()
    rd=pg.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row',"els=>els.map(tr=>{const v=s=>{const e=tr.querySelector(s);return e?e.value:null};return {w:tr.dataset.wallet,mode:v('select[name=mode]'),cm:v('select[name=copy_mode]'),F:v('input[name=fixed_notional]'),N:v('input[name=norm_base]'),B:v('input[name=leader_equity_base]'),inp:Array.from(tr.querySelectorAll('input')).map(i=>i.name),btn:Array.from(tr.querySelectorAll('button[data-act]')).map(x=>x.dataset.act),cells:Array.from(tr.querySelectorAll('td')).map(t=>t.innerText.replace(/\\s+/g,' ').trim())}})")
    res['rows']=rd
    W='0x010461c14e146ac35fe42271bdc1134ee31c703a'
    try:
        pg.click('#lcWalletRows tr.lc-wallet-row[data-wallet=\"%s\"] td:first-child'%W,timeout=15000);time.sleep(2)
        res['detail_W1']=pg.evaluate("(w)=>{const id='lcdet-'+w.replace(/[^a-z0-9]/gi,'');const el=document.getElementById(id);return el?el.innerText:null}",W)
    except Exception as e:res['detail_W1']='ERR '+str(e)
    html=pg.content();res['dom_sha']=hashlib.sha256(html.encode()).hexdigest()
    ctx.close();b.close()
for f in ['live_config.json','manual_live_positions.json','live_fills.csv']:
    res.setdefault('frozen_sha',{})[f]=hashlib.sha256((FRZ/f).read_bytes()).hexdigest()
(OUT/'probe3_result.json').write_text(json.dumps(res,indent=1,default=str),encoding='utf-8')
print('rows',len(res['rows']),'dom',res['dom_sha'][:12])
print('frozen',json.dumps(res['frozen_sha'],indent=1))
