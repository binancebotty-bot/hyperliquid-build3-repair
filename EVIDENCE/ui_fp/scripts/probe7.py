#!/usr/bin/env python3
'''Final binding probe: full wallet from tr.dataset.wallet; bind DOM cells to served APIs + disk config.'''
import json, urllib.request, datetime
BASE='http://127.0.0.1:8031'
AUD='C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet'
def jget(p):
    with urllib.request.urlopen(BASE+p,timeout=12) as r: return json.loads(r.read().decode('utf-8','replace'))

r={'tested_at_utc':datetime.datetime.utcnow().isoformat()+'Z'}
aud=jget('/api/live-audit-summary')
lp=aud.get('live_leader_performance') or {}
r['api_leader_perf']={w:{'avg_diff_bps':v.get('avg_diff_bps'),'open_position_count':v.get('open_position_count')} for w,v in lp.items() if isinstance(v,dict)}
lc=jget('/api/live-config'); cfg=lc.get('config',{}); r['api_live_config_wallets']=cfg.get('wallets',{})
uc=jget('/api/ui-state'); r['api_ui_state']={'norm_base':uc.get('norm_base'),'copy_mode':uc.get('copy_mode'),'fixed_notional':uc.get('fixed_notional'),'normalisation_mode':uc.get('normalisation_mode'),'user_norm_base':uc.get('user_norm_base')}

JS=r"""() => {
  const out=[];
  document.querySelectorAll('tr').forEach(tr=>{
    const w=tr.dataset.wallet; if(!w) return;
    const cells=Array.from(tr.querySelectorAll('td')).map(td=>(td.innerText||'').replace(/\n+/g,' | ').trim());
    const lead=cells.find(c=>/Avg bps/i.test(c))||'';
    const risk=cells.find(c=>/Open pos/i.test(c))||'';
    out.push({wallet:w,
      dom_bps:(lead.match(/Avg bps:\s*([^ |]+)/)||[])[1]||null,
      dom_op:(risk.match(/Open pos:\s*([^ |]+)/)||[])[1]||null,
      sels:Array.from(tr.querySelectorAll('select')).map(s=>({name:s.name||'',val:s.value||''})),
      ins:Array.from(tr.querySelectorAll('input')).map(i=>({name:i.name||'',val:i.value||''}))});
  });
  return out;
}"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    try:
        pg=b.new_page(); pg.goto(BASE+'/live-copy',wait_until='networkidle',timeout=30000)
        r['dom']=pg.evaluate(JS)
        r['html_lcGraphScale']=pg.evaluate("document.documentElement.outerHTML.indexOf('lcGraphScale')>=0")
    finally:
        b.close()
try: r['disk_live_config']=json.load(open(AUD+'/live_config.json',encoding='utf-8'))
except Exception as e: r['disk_live_config_err']=repr(e)
try: r['disk_ui_state']=json.load(open(AUD+'/ui_state.json',encoding='utf-8'))
except Exception as e: r['disk_ui_state_err']=repr(e)
json.dump(r,open('C:/Users/wigmore/.hermes/kanban/workspaces/t_ab0d0f07/probe7_raw.json','w',encoding='utf-8'),indent=1,ensure_ascii=False)

api={k.lower():v for k,v in r['api_leader_perf'].items()}
res={'rows':[],'bps_match':0,'bps_mismatch':0,'op_match':0,'op_mismatch':0,'ctrl_match':0,'ctrl_mismatch':0,'fn_match':0,'fn_mismatch':0,'nb_match':0,'nb_mismatch':0,'n':0}
for d in r['dom']:
    w=d['wallet'].lower(); ap=api.get(w)
    cfgw=r['api_live_config_wallets'].get(d['wallet']) or r['api_live_config_wallets'].get(w) or {}
    e={'wallet':d['wallet'][:12],'dom_bps':d['dom_bps'],'dom_op':d['dom_op'],'api':ap,'dom_ctrl':d['sels'],'dom_fn':d['ins']}
    res['n']+=1
    if ap and d['dom_bps'] and d['dom_bps']!='n/a' and ap['avg_diff_bps'] is not None:
        if abs(float(d['dom_bps'])-float(ap['avg_diff_bps']))<0.06: res['bps_match']+=1
        else: res['bps_mismatch']+=1; e['bps_diff']=(d['dom_bps'],ap['avg_diff_bps'])
    if ap and d['dom_op'] and d['dom_op']!='n/a' and ap['open_position_count'] is not None:
        if str(d['dom_op'])==str(ap['open_position_count']): res['op_match']+=1
        else: res['op_mismatch']+=1; e['op_diff']=(d['dom_op'],ap['open_position_count'])
    mode=[s['val'] for s in d['sels'] if s['name']=='mode']
    if mode and cfgw.get('mode'):
        if mode[0]==cfgw['mode']: res['ctrl_match']+=1
        else: res['ctrl_mismatch']+=1; e['mode_diff']=(mode[0],cfgw.get('mode'))
    fn=[i['val'] for i in d['ins'] if i['name']=='fixed_notional']
    if fn and cfgw.get('fixed_notional') is not None:
        if abs(float(fn[0])-float(cfgw['fixed_notional']))<0.01: res['fn_match']+=1
        else: res['fn_mismatch']+=1; e['fn_diff']=(fn[0],cfgw.get('fixed_notional'))
    nb=[i['val'] for i in d['ins'] if i['name']=='norm_base']
    if nb and r['api_ui_state']['norm_base'] is not None:
        if abs(float(nb[0])-float(r['api_ui_state']['norm_base']))<0.01: res['nb_match']+=1
        else: res['nb_mismatch']+=1; e['nb_diff']=(nb[0],r['api_ui_state']['norm_base'])
    res['rows'].append(e)
r['summary']=res
json.dump(r,open('C:/Users/wigmore/.hermes/kanban/workspaces/t_ab0d0f07/probe7_raw.json','w',encoding='utf-8'),indent=1,ensure_ascii=False)
s=res
print('dom rows',s['n'])
print('bps match/mismatch',s['bps_match'],s['bps_mismatch'])
print('op  match/mismatch',s['op_match'],s['op_mismatch'])
print('mode ctrl match/mismatch',s['ctrl_match'],s['ctrl_mismatch'])
print('fixed_notional match/mismatch',s['fn_match'],s['fn_mismatch'])
print('norm_base match/mismatch',s['nb_match'],s['nb_mismatch'])
print('ui_state',r['api_ui_state'])
print('disk_ui_state_keys',list((r.get('disk_ui_state') or {}).keys())[:20])
print('html_lcGraphScale',r['html_lcGraphScale'])
for e in res['rows'][:4]: print(e)
