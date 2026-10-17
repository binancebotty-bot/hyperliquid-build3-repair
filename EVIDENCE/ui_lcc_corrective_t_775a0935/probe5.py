import json,time,hashlib,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
WS=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935')
OUT=WS/'evidence';OUT.mkdir(parents=True,exist_ok=True)
SD=Path(r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet')
FRZ=WS/'frozen5';FRZ.mkdir(parents=True,exist_ok=True)
SSOT=Path(r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/HL_Copy_App_SSOT.py')
W='0x010461c14e146ac35fe42271bdc1134ee31c703a'
URL='http://127.0.0.1:8031/live-copy'
Q=chr(34)
res={'probe':'probe5','url':URL,'t0_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
res['ssot_path']=str(SSOT)
res['ssot_sha256']=hashlib.sha256(SSOT.read_bytes()).hexdigest()
audit={'v':None}
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
            try: audit['v']=r.json()
            except Exception as e: audit['err']=str(e)
            audit['frozen']=freeze()
    pg.on('response',on_resp)
    pg.goto(URL,wait_until='domcontentloaded',timeout=60000)
    dl=time.time()+70
    while time.time()<dl:
        if pg.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row','e=>e.length')>0:break
        time.sleep(1.0)
    res['rows_rendered']=pg.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row','e=>e.length')
    sel='#lcWalletRows tr.lc-wallet-row[data-wallet='+Q+W+Q+'] td:first-child'
    try:
        pg.click(sel,timeout=15000);time.sleep(2)
        js='()=>{const els=[...document.querySelectorAll('+Q+'[id^=lcdet-]'+Q+')];return els.length?els[els.length-1].innerText:null}'
        res['detail_W1']=pg.evaluate(js)
    except Exception as e: res['detail_W1']='ERR '+str(e)
    html=pg.content()
    (OUT/'live_dom_capture.html').write_text(html,encoding='utf-8')
    res['dom_sha256']=hashlib.sha256(html.encode('utf-8')).hexdigest()
    ctx.close();b.close()
res['freeze_snapshot']=audit.get('frozen')
res['audit_ok']=audit.get('v') is not None
if audit.get('v'):
    a=audit['v']
    perf=(a.get('live_leader_performance') or {}).get(W) or {}
    row=[x for x in (a.get('live_wallet_rows') or []) if x['wallet'].lower()==W]
    res['api_W1']={'open_position_count':perf.get('open_position_count'),'fees':perf.get('fees'),'filled_count':perf.get('filled_count'),'n_open_list':len(perf.get('current_open_positions') or []),'row_fees':(row[0].get('fees') if row else None),'row_open':(row[0].get('open_position_count') if row else None)}
    res['api_open_positions_W1']=[{'coin':p.get('coin'),'signed_size':p.get('signed_size')} for p in (perf.get('current_open_positions') or [])]
(OUT/'probe5_result.json').write_text(json.dumps(res,indent=1,default=str),encoding='utf-8')
print('rows',res['rows_rendered'],'audit_ok',res['audit_ok'])
print('dom_sha256',res['dom_sha256'])
print('ssot',res['ssot_sha256'])
print('api_W1',json.dumps(res.get('api_W1')))
