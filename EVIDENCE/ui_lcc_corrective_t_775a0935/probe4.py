import json,time,hashlib,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
WS=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935')
OUT=WS/'evidence';OUT.mkdir(parents=True,exist_ok=True)
SD=Path(r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet')
FRZ=WS/'frozen4';FRZ.mkdir(parents=True,exist_ok=True)
W='0x010461c14e146ac35fe42271bdc1134ee31c703a'
URL='http://127.0.0.1:8031/live-copy'
res={'url':URL,'t0_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
audit_body={'v':None}
def freeze():
    snap={}
    for name in ['live_config.json','manual_live_positions.json','append_only/live_fills.csv']:
        dst=FRZ/Path(name).name; shutil.copy2(SD/name,dst)
        snap[name]={'sha256':hashlib.sha256(dst.read_bytes()).hexdigest(),'bytes':dst.stat().st_size}
    snap['_at']=time.time()
    return snap
with sync_playwright() as p:
    b=p.chromium.launch(headless=True);ctx=b.new_context();pg=ctx.new_page()
    pg.on('dialog',lambda d:d.accept())
    def on_resp(r):
        if '/api/live-audit-summary' in r.url:
            try: audit_body['v']=r.json()
            except Exception as e: audit_body['err']=str(e)
            audit_body['frozen']=freeze()
    pg.on('response',on_resp)
    pg.goto(URL,wait_until='domcontentloaded',timeout=60000)
    dl=time.time()+70
    while time.time()<dl:
        if pg.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row','e=>e.length')>0:break
        time.sleep(1.0)
    res['rows_rendered']=pg.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row','e=>e.length')
    try:
        pg.click('#lcWalletRows tr.lc-wallet-row[data-wallet=\"%s\"] td:first-child'%W,timeout=15000);time.sleep(2)
        res['detail_W1']=pg.evaluate("(w)=>{const id='lcdet-'+w.replace(/[^a-z0-9]/gi,'');const el=document.getElementById(id);return el?el.innerText:null}",W)
    except Exception as e: res['detail_W1']='ERR '+str(e)
    html=pg.content();res['dom_sha']=hashlib.sha256(html.encode()).hexdigest()
    ctx.close();b.close()
res['freeze_snapshot']=audit_body.get('frozen')
res['audit_ok']=audit_body.get('v') is not None
if audit_body.get('v'):
    a=audit_body['v']
    perf=(a.get('live_leader_performance') or {}).get(W) or {}
    row=[x for x in (a.get('live_wallet_rows') or []) if x['wallet'].lower()==W]
    res['api_W1']={'open_position_count':perf.get('open_position_count'),'fees':perf.get('fees'),'realized':perf.get('live_realized_pnl'),'filled_count':perf.get('filled_count'),'n_open_list':len(perf.get('current_open_positions') or []),'row_fees':(row[0].get('fees') if row else None),'row_open':(row[0].get('open_position_count') if row else None)}
    res['api_open_positions_W1']=[{'coin':p.get('coin'),'signed_size':p.get('signed_size')} for p in (perf.get('current_open_positions') or [])]
(OUT/'probe4_result.json').write_text(json.dumps(res,indent=1,default=str),encoding='utf-8')
print('rows',res['rows_rendered'],'audit_ok',res['audit_ok'])
print('api_W1',json.dumps(res.get('api_W1')))
print('freeze',json.dumps(res.get('freeze_snapshot'),indent=1)[:500])
