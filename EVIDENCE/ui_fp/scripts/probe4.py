#!/usr/bin/env python3
'''Oracle compare (served API) + graph-scale interaction test.'''
import json, urllib.request, datetime
BASE='http://127.0.0.1:8031'
def jget(p):
    with urllib.request.urlopen(BASE+p,timeout=8) as r: return json.loads(r.read().decode('utf-8','replace'))

r={'tested_at_utc':datetime.datetime.utcnow().isoformat()+'Z'}
us=jget('/api/ui-state'); lc=jget('/api/live-config')
r['ui_state_norm_base']=us.get('norm_base')
r['ui_state_fixed_notional']=us.get('fixed_notional')
r['ui_state_copy_mode']=us.get('copy_mode')
r['ui_state_normalisation_mode']=us.get('normalisation_mode')
r['wallet_meta']=us.get('wallet_meta')
ws=lc.get('config',{}).get('wallets',{})
first=sorted(ws.keys())[0]
r['first_wallet']=first
r['first_wallet_cfg']=ws[first]
r['n_wallets']=len(ws)

from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    try:
        pg=b.new_page(); pg.goto(BASE+'/live-copy',wait_until='networkidle',timeout=30000)
        def graph_txt():
            return pg.evaluate("() => {const t=document.querySelector('#liveCopyPanel');const m=(t?t.innerText:'').match(/Exchange account graph[^\\n]*/);return m?m[0]:null;}")
        r['graph_before']=graph_txt()
        # click 7D
        try:
            pg.click("button[data-lc-graph-scale='7d']", timeout=5000)
            pg.wait_for_timeout(800)
            r['graph_after_7d']=graph_txt()
        except Exception as e:
            r['graph_after_7d_err']='%s: %r'%(type(e).__name__,e)
        # click 1D
        try:
            pg.click("button[data-lc-graph-scale='1d']", timeout=5000)
            pg.wait_for_timeout(800)
            r['graph_after_1d']=graph_txt()
        except Exception as e:
            r['graph_after_1d_err']='%s: %r'%(type(e).__name__,e)
        # which scale button is active now
        r['active_scale']=pg.evaluate("() => {const b=document.querySelector('button[data-lc-graph-scale].active');return b?b.getAttribute('data-lc-graph-scale'):null;}")
        # mode select: read the onchange/endpoint hint from source-in-DOM
        r['mode_sel_attrs']=pg.evaluate("() => {const s=document.querySelector('select[name=\"mode\"]');return s? {oc:(s.getAttribute('onchange')||''),data:Array.from(s.attributes).map(a=>[a.name,a.value])} : null;}")
        # find fetch('...live-config' references in inline script text
        r['script_endpoints']=pg.evaluate("() => {const t=document.documentElement.innerHTML;const re=/['\"]([^'\"]*live-config[^'\"]*)['\"]/g;const o=[];let m;while((m=re.exec(t))){o.push(m[1]);}return Array.from(new Set(o)).slice(0,20);}")
    finally:
        b.close()
json.dump(r,open('C:/Users/wigmore/.hermes/kanban/workspaces/t_ab0d0f07/probe4_raw.json','w',encoding='utf-8'),indent=1,ensure_ascii=False)
print('ui_state norm_base',r['ui_state_norm_base'],'fixed_notional',r['ui_state_fixed_notional'],'copy_mode',r['ui_state_copy_mode'],'norm_mode',r['ui_state_normalisation_mode'])
print('first_wallet',r['first_wallet'],r['first_wallet_cfg'],'n',r['n_wallets'])
print('graph_before',repr(r.get('graph_before')))
print('graph_after_7d',repr(r.get('graph_after_7d')))
print('graph_after_1d',repr(r.get('graph_after_1d')))
print('active_scale',r.get('active_scale'))
print('mode_sel_attrs',r.get('mode_sel_attrs'))
print('script_endpoints',r.get('script_endpoints'))
