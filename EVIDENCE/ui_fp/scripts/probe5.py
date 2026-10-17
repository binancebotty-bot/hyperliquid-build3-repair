#!/usr/bin/env python3
'''Bind rendered Avg bps / Open pos cells to the served audit API payload.'''
import json, urllib.request, datetime
BASE='http://127.0.0.1:8031'
def jget(p):
    with urllib.request.urlopen(BASE+p,timeout=10) as r: return json.loads(r.read().decode('utf-8','replace'))

r={'tested_at_utc':datetime.datetime.utcnow().isoformat()+'Z'}
aud=jget('/api/live-audit-summary')
r['audit_topkeys']=list(aud.keys()) if isinstance(aud,dict) else type(aud)
# find per-wallet rows
cand=[]
if isinstance(aud,dict):
    for k,v in aud.items():
        if isinstance(v,dict) and ('avg_diff_bps' in v or 'open_position_count' in v):
            cand.append((k,'dict',v))
        if isinstance(v,list) and v and isinstance(v[0],dict):
            cand.append((k,'list',v))
        if isinstance(v,dict) and any(isinstance(x,dict) for x in v.values()):
            for k2,v2 in v.items():
                if isinstance(v2,dict) and ('avg_diff_bps' in v2 or 'open_position_count' in v2):
                    cand.append((k+'.'+k2,'dict',v2))
r['candidates']=[(a,b) for a,b,_ in cand]
rows=None
for k,kind,v in cand:
    if kind=='list':
        rows=v; r['rows_key']=k; break
if rows:
    r['n_rows']=len(rows)
    r['sample']=rows[0]
    ext={}
    for row in rows:
        w=row.get('wallet') or row.get('wallet_address') or ''
        if w: ext[w.lower()]={'avg_diff_bps':row.get('avg_diff_bps'),'open_position_count':row.get('open_position_count'),'total_diff_usd':row.get('total_diff_usd'),'worst_diff_bps':row.get('worst_diff_bps')}
    r['by_wallet']=ext
json.dump(r,open('C:/Users/wigmore/.hermes/kanban/workspaces/t_ab0d0f07/probe5_raw.json','w',encoding='utf-8'),indent=1,ensure_ascii=False)
print('audit_topkeys',r['audit_topkeys'])
print('candidates',r['candidates'])
print('rows_key',r.get('rows_key'),'n',r.get('n_rows'))
print('sample',json.dumps(r.get('sample'))[:600])
bw=r.get('by_wallet') or {}
for w in list(bw)[:3]:
    print(w, bw[w])
