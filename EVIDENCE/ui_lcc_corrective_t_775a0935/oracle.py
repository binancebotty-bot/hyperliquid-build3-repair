import csv,json
from pathlib import Path
from collections import defaultdict,Counter
SD=Path(r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet')
WS=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935')
cfg=json.loads((SD/'live_config.json').read_text(encoding='utf-8'))
wallets=cfg['wallets']
fee=defaultdict(float);fills=defaultdict(int)
for row in csv.DictReader(open(SD/'append_only'/'live_fills.csv',newline='',encoding='utf-8',errors='replace')):
    w=(row.get('leader_wallet') or '').lower()
    if not w: continue
    try: fee[w]+=float(row.get('fee') or 0)
    except: pass
    fills[w]+=1
filled=defaultdict(int);rej=defaultdict(int)
for row in csv.DictReader(open(SD/'append_only'/'send_attempts.csv',newline='',encoding='utf-8',errors='replace')):
    w=(row.get('leader_wallet') or '').lower()
    if not w: continue
    s=row.get('status') or ''
    if s=='ORDER_FILLED': filled[w]+=1
    elif s=='ORDER_REJECTED': rej[w]+=1
out={'live_config_wallets':len(wallets),'modes':dict(Counter(v.get('mode') for v in wallets.values())),'per_wallet':{}}
for w,v in wallets.items():
    wl=w.lower()
    out['per_wallet'][wl]={'cfg_mode':v.get('mode'),'cfg_fixed_notional':v.get('fixed_notional'),'cfg_norm_base_present':'norm_base' in v,'cfg_norm_base':v.get('norm_base'),'cfg_leader_equity_base_present':'leader_equity_base' in v,'fills':fills.get(wl,0),'filled_attempts':filled.get(wl,0),'rejected_attempts':rej.get(wl,0),'fees_sum':round(fee.get(wl,0.0),4)}
(WS/'oracle_out.json').write_text(json.dumps(out,indent=1),encoding='utf-8')
print(json.dumps(out['modes']))
print('wallets',len(out['per_wallet']))
for w in list(out['per_wallet'])[:2]: print(w,json.dumps(out['per_wallet'][w]))
print('TOTAL_FEES',round(sum(fee.values()),2))
