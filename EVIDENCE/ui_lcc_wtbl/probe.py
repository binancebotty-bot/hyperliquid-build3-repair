import datetime,hashlib,json,os,sys,copy
WS=os.path.dirname(os.path.abspath(__file__))
SRC=os.path.join(WS,'UI_b142cf88.py');OUT=os.path.join(WS,'raw_wtbl_probe.json')
REG='b142cf88d389e791160f691aac3d936852b99975';ORIGIN='http://ui-cert.local'
def panel(p):
    L=open(p,encoding='utf-8').read().split('\n')
    s=next(i for i,l in enumerate(L) if l.startswith('def render_live_copy_control_panel'))
    r=next(j for j in range(s,len(L)) if L[j].strip()=='return """')
    e=next(k for k in range(r+1,len(L)) if L[k].strip()=='"""')
    return '\n'.join(L[r+1:e]),(r+1,e)
def lj(n): return json.loads(open(os.path.join(WS,n),'rb').read().decode('utf-8-sig','replace'))
JS_W="()=>Array.from(document.querySelectorAll('#lcWalletRows tr.lc-wallet-row')).map(tr=>({wallet:tr.getAttribute('data-wallet'),cells:Array.from(tr.children).map(td=>td.innerText),modeVal:(tr.querySelector('select[name=mode]')||{}).value||null,copyVal:(tr.querySelector('select[name=copy_mode]')||{}).value||null,fixed:(tr.querySelector('input[name=fixed_notional]')||{}).value??null,norm:(tr.querySelector('input[name=norm_base]')||{}).value??null,acts:Array.from(tr.querySelectorAll('button[data-act]')).map(b=>b.getAttribute('data-act'))}))"
JS_D="()=>{const R=Array.from(document.querySelectorAll('tr[id^=\"lcdet-\"]'));if(!R.length)return{present:false};const r=R[0];return{present:true,heads:Array.from(r.querySelectorAll('b')).map(b=>(b.innerText||'').trim()).filter(t=>/^[A-E] /.test(t)),text:(r.innerText||'').replace(/\\s+/g,' ').slice(0,3500)}}"
def run():
    P,span=panel(SRC);raw=open(SRC,'rb').read()
    html='<!doctype html><html><head><meta charset="utf-8"></head><body>'+P+'</body></html>'
    lc=lj('live_config.json');wh=lj('ws_health.json');au=lj('audit_summary.json')
    gc={'global_controls':(lc.get('config') or {}).get('global_controls') or {},'networks':{'leader':'mainnet','follower':'testnet','state_dir':'x'}}
    base={'/api/live-config':lc,'/api/live-ws-health':wh,'/api/live-audit-summary':au,'/api/global-controls':gc}
    na=copy.deepcopy(au);wr=na.get('live_wallet_rows') or [];nw=wr[0].get('wallet') if wr else None
    if wr: wr[0]['fixed_notional']=None;wr[0]['norm_base']=None
    nul=dict(base);nul['/api/live-audit-summary']=na
    from playwright.sync_api import sync_playwright
    res={'register_ref':'main:certification/certification_matrix.json','register_commit':REG,'panel_span':span,'panel_sha256':hashlib.sha256(P.encode()).hexdigest(),'src_sha256':hashlib.sha256(raw).hexdigest(),'src_bytes':len(raw),'tested_at_utc':datetime.datetime.utcnow().isoformat()+'Z','variants':{}}
    def mkpage(b,pl,failpath=None):
        pg=b.new_page();posts=[]
        pg.on('dialog',lambda d:d.accept())
        def route(r):
            u=r.request.url;path='/'+u.split(ORIGIN+'/',1)[-1] if ORIGIN+'/' in u else u
            if r.request.method=='POST':
                posts.append({'path':path,'body':r.request.post_data});r.fulfill(status=200,content_type='application/json',body='{"ok":true}');return
            if path=='/live-copy': r.fulfill(status=200,content_type='text/html',body=html);return
            if failpath and path==failpath: r.fulfill(status=500,content_type='text/html',body='<html>Internal Server Error</html>');return
            d=pl.get(path)
            if d is None: r.fulfill(status=404,content_type='application/json',body='{"ok":false}');return
            r.fulfill(status=200,content_type='application/json',body=json.dumps(d))
        pg.route('**/*',route);pg.goto(ORIGIN+'/live-copy',wait_until='domcontentloaded',timeout=60000)
        return pg,posts
    def st(pg): return pg.evaluate("()=>{var s=document.getElementById('lcStatus');return s?(s.innerText||'').slice(0,300):null;}")
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        try:
            pg,po=mkpage(b,base);pg.wait_for_selector('#lcWalletRows tr.lc-wallet-row',timeout=40000)
            o={'rows':pg.evaluate("()=>document.querySelectorAll('#lcWalletRows tr.lc-wallet-row').length"),'wallets':pg.evaluate(JS_W),'status':st(pg),'posts_on_load':po}
            try:
                pg.evaluate("()=>{var td=document.querySelector('#lcWalletRows tr.lc-wallet-row td');if(td)td.click();}")
                pg.wait_for_selector('tr[id^="lcdet-"]',timeout=20000);o['detail']=pg.evaluate(JS_D)
            except Exception as e: o['detail']={'error':type(e).__name__}
            res['variants']['real']=o;pg.close()
            pg2,_=mkpage(b,nul);pg2.wait_for_selector('#lcWalletRows tr.lc-wallet-row',timeout=40000)
            res['variants']['nullcfg']={'null_wallet':nw,'wallets':pg2.evaluate(JS_W)};pg2.close()
            pg3,_=mkpage(b,base,failpath='/api/live-config');pg3.wait_for_timeout(5000)
            res['variants']['apierror']={'status':st(pg3),'rows':pg3.evaluate("()=>document.querySelectorAll('#lcWalletRows tr.lc-wallet-row').length")};pg3.close()
            for act in ['save','clo','off','archive']:
                pg4,po=mkpage(b,base);pg4.wait_for_selector('#lcWalletRows tr.lc-wallet-row',timeout=40000)
                pg4.evaluate("a=>{var t=document.querySelector('#lcWalletRows tr.lc-wallet-row button[data-act=\"'+a+'\"]');if(t)t.click();}",act)
                pg4.wait_for_timeout(1500);res['variants']['wire_'+act]={'posts':po};pg4.close()
        finally: b.close()
    cw=(lc.get('config') or {}).get('wallets') or {}
    er={str(r.get('wallet')).lower():r for r in (au.get('live_wallet_rows') or [])}
    rows=res['variants']['real']['wallets'];cmp_rows=[];mn=0;md=0
    for w in rows:
        e=er.get(str(w['wallet']).lower(),{})
        em=str(e.get('mode') or '').upper();dm=str(w['modeVal'] or '').upper()
        ec=e.get('copy_mode');dc=w['copyVal']
        cmp_rows.append({'wallet':w['wallet'],'eng_mode':em,'dom_mode':dm,'mode_match':em==dm,'eng_copy':ec,'dom_copy':dc,'copy_match':str(ec)==str(dc),'eng_fixed':e.get('fixed_notional'),'dom_fixed':w['fixed']})
        if em==dm: mn+=1
        if str(ec)==str(dc): md+=1
    res['oracle_rows']={'n':len(cmp_rows),'mode_match':mn,'copy_match':md,'rows':cmp_rows}
    ag=[];dis=[]
    for w,c in cw.items():
        e=er.get(str(w).lower())
        if not e: continue
        rec={'wallet':w,'cfg_mode':c.get('mode'),'eng_mode':e.get('mode'),'cfg_fixed':c.get('fixed_notional'),'eng_fixed':e.get('fixed_notional')}
        (ag if str(rec['cfg_mode']).upper()==str(rec['eng_mode']).upper() else dis).append(rec)
    res['oracle_cfg_vs_eng']={'n_cfg':len(cw),'n_eng':len(er),'agree':len(ag),'disagree':len(dis),'disagreements':dis[:10]}
    w0=(res['variants']['real']['wallets'][0]['wallet'] if res['variants']['real'].get('wallets') else '').lower()
    perf=(au.get('live_leader_performance') or {}).get(w0,{})
    res['oracle_detail']={'w0':w0,'served_open_positions_len':len(perf.get('current_open_positions') or []),'served_attribution':perf.get('attribution_quality'),'dom_heads':(res['variants']['real'].get('detail') or {}).get('heads')}
    json.dump(res,open(OUT,'w',encoding='utf-8'),indent=2,ensure_ascii=False)
    print('WROTE',OUT);print('vars',list(res['variants'].keys()))
    return 0
sys.exit(run())
