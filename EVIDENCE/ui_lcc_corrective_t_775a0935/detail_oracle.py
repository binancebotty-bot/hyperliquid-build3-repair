import csv,json
from pathlib import Path
from collections import defaultdict
WS=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935')
FRZ=WS/'frozen'

def fnum(x):
    try: return float(x)
    except: return 0.0

def replay(fills,eps=1e-9):
    state={};realized=fees=0.0;complete=True;notes=[]
    rows=sorted(fills,key=lambda r:(fnum(r.get('created_at_ms')),str(r.get('copy_fill_id') or '')))
    for row in rows:
        coin=str(row.get('coin') or '').upper();side=str(row.get('side') or '').upper()
        price=fnum(row.get('fill_price'));size=abs(fnum(row.get('fill_size')))
        pos,avg=state.get(coin,[0.0,0.0]);fees+=fnum(row.get('fee'))
        if side not in {'BUY','SELL'} or price<=0:
            if abs(pos)>eps: complete=False;notes.append(coin+': closed w/o price')
            state[coin]=[0.0,0.0];continue
        br=row.get('wallet_position_before')
        if br not in (None,'') and abs(fnum(br)-pos)>max(eps,abs(pos)*1e-6):
            complete=False;notes.append(coin+': earlier fills missing');pos=fnum(br);avg=avg if avg>0 else price
        delta=size if side=='BUY' else -size
        if abs(pos)<=eps or pos*delta>0:
            new=pos+delta;avg=(avg*abs(pos)+price*abs(delta))/abs(new) if abs(new)>eps else 0.0;pos=new
        else:
            closed=min(abs(delta),abs(pos))
            pnl=(price-avg)*closed*(1 if pos>0 else -1);realized+=pnl
            pos=pos+delta
            if abs(pos)<=eps:pos=0.0;avg=0.0
            elif pos*delta>0:avg=price
        state[coin]=[pos,avg]
    return {'realized':round(realized,4),'fees':round(fees,4),'complete':complete,'notes':notes,'open':{k:v for k,v in state.items() if abs(v[0])>eps}}

cfg=json.loads((FRZ/'live_config.json').read_text(encoding='utf-8'))
fills_by=defaultdict(list)
for row in csv.DictReader(open(FRZ/'live_fills.csv',newline='',encoding='utf-8',errors='replace')):
    lw=(row.get('leader_wallet') or '').lower()
    if lw: fills_by[lw].append(row)

# manual positions for this wallet
mp=json.loads((Path(r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet')/'manual_live_positions.json').read_text(encoding='utf-8'))
byw=mp.get('by_wallet',{})

out={'frozen_hashes':{},'per_wallet':{}}
import hashlib
for f in ['live_config.json','live_fills.csv','send_attempts.csv']:
    out['frozen_hashes'][f]=hashlib.sha256((FRZ/f).read_bytes()).hexdigest()
for w in cfg['wallets']:
    wl=w.lower()
    r=replay(fills_by.get(wl,[]))
    man=byw.get(w,{}) or byw.get(wl,{}) or {}
    out['per_wallet'][wl]={'replay_realized':r['realized'],'replay_fees':r['replay_fees'] if 'replay_fees' in r else r['fees'],'complete':r['complete'],'n_notes':len(r['notes']),'open_count':len(r['open']),'manual_open_count':(len(man.get('positions',[])) if isinstance(man,dict) and 'positions' in man else None),'fill_rows':len(fills_by.get(wl,[]))}
(WS/'detail_oracle_out.json').write_text(json.dumps(out,indent=1),encoding='utf-8')
w1='0x010461c14e146ac35fe42271bdc1134ee31c703a'
print('W1',json.dumps(out['per_wallet'][w1]))
print('TOTAL_ROWS',sum(len(v) for v in fills_by.values()))
print('KEYS_BYW',list(byw)[:3] if isinstance(byw,dict) else type(byw))
