import json
from pathlib import Path
WS=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935')
dom=json.loads((WS/'evidence'/'live_probe_result.json').read_text(encoding='utf-8'))
orc=json.loads((WS/'oracle_out.json').read_text(encoding='utf-8'))
rows={r['w'].lower():r for r in dom['rows']}
per=orc['per_wallet']
res={'dom_row_count':len(rows),'oracle_wallet_count':len(per),'mismatch':[],'checks':[]}
# 1) row set equality
missing=[w for w in per if w not in rows]
extra=[w for w in rows if w not in per]
res['missing_in_dom']=missing;res['extra_in_dom']=extra
# 2) per-wallet config match: mode, copy_mode, fixed_notional
bad=[]
for w,p in per.items():
    r=rows.get(w)
    if not r: continue
    d={'w':w,'dom_mode':r.get('mode'),'cfg_mode':(p.get('cfg_mode') or '').upper(),
       'dom_cm':r.get('cm'),'cfg_cm':'fixed',
       'dom_F':r.get('F'),'cfg_F':str(p.get('cfg_fixed_notional')),
       'dom_N':r.get('N'),'cfg_norm_base_present':p.get('cfg_norm_base_present'),
       'dom_B':r.get('B'),'cfg_leb_present':p.get('cfg_leader_equity_base_present')}
    d['mode_ok']=d['dom_mode']==d['cfg_mode']
    d['cm_ok']=d['dom_cm']==d['cfg_cm']
    d['F_ok']=d['dom_F']==d['cfg_F']
    res['checks'].append(d)
    if not(d['mode_ok'] and d['cm_ok'] and d['F_ok']): bad.append(w)
res['config_cell_mismatches']=bad
res['all_mode_ok']=all(c['mode_ok'] for c in res['checks'])
res['all_cm_ok']=all(c['cm_ok'] for c in res['checks'])
res['all_F_ok']=all(c['F_ok'] for c in res['checks'])
# 3) B input presence
res['dom_rows_with_B_input']=sum(1 for c in res['checks'] if c['dom_B'] is not None)
res['cfg_wallets_with_leader_equity_base']=sum(1 for p in per.values() if p.get('cfg_leader_equity_base_present'))
# 4) controls present on every row
res['rows_with_all_4_buttons']=sum(1 for r in dom['rows'] if all([r.get('save'),r.get('clo'),r.get('off'),r.get('arc')]))
res['button_sample']={k:dom['rows'][0].get(k) for k in ['save','clo','off','arc']}
(WS/'compare_out.json').write_text(json.dumps(res,indent=1),encoding='utf-8')
print(json.dumps({k:res[k] for k in ['dom_row_count','oracle_wallet_count','missing_in_dom','extra_in_dom','config_cell_mismatches','all_mode_ok','all_cm_ok','all_F_ok','dom_rows_with_B_input','cfg_wallets_with_leader_equity_base','rows_with_all_4_buttons']},indent=1))
