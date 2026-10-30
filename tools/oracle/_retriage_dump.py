import json, collections
base='runs/'
A=json.load(open(base+'after/m3_oracle_20261030T005055Z.json'))
B=json.load(open(base+'prefix_before/m3_oracle_20261030T004231Z.json'))
O=json.load(open(base+'m3_oracle_20261029T224357Z.json'))
bk={(r['wallet'],r['coin']) for r in B['rows'] if r['label']=='LOST_OBLIGATION'}
ok={(r['wallet'],r['coin']) for r in O['rows'] if r['label']=='LOST_OBLIGATION'}
bl={(r['wallet'],r['coin']):r for r in B['rows']}
rows=[r for r in A['rows'] if r['label']=='LOST_OBLIGATION']
def cls(r):
    act=float(r['actual']);tu=r['target_units'];tgt=float(r['target'] or 0)
    fc=r['leader_fill_count'];pbn=float(r['leader_postbaseline_net'] or 0)
    if tgt==0 and abs(act)>0:
        return ('UNDECIDED','OPERATOR_DECISION') if r['coin']=='NEAR' else ('ORPHAN_POSITION','OPERATOR_DECISION')
    if tu is None: return 'UNDECIDED','OPERATOR_DECISION'
    if act!=0 and (act>0)!=(float(tu)>0): return 'SIGN_INVERSION','OPERATOR_DECISION'
    if fc==0 and pbn==0: return 'BASELINE_ARTEFACT','NO_ACTION'
    if abs(act)>abs(float(tu)): return 'STALE_LEDGER','RECONCILE'
    return 'PARTIAL_COPY','RECONCILE'
cnt=collections.Counter();rem=collections.Counter()
for i,r in enumerate(sorted(rows,key=lambda x:(x['wallet'],x['coin'])),1):
    k=(r['wallet'],r['coin']);st='STABLE' if k in bk else 'VOLATILE'
    c,rm=cls(r);cnt[(st,c)]+=1;rem[(st,rm)]+=1
    b=bl.get(k);chg=''
    if b and b['actual']!=r['actual']: chg='pos %s->%s'%(b['actual'],r['actual'])
    if b and b['target']!=r['target']: chg+=' tgt %s->%s'%(b['target'],r['target'])
    print('| %d | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |'%(i,st,k[0][:8],r['coin'],r['target'],r['target_units'] if r['target_units'] is not None else 'null',r['actual'],r['in_flight'],r['delta_usd'] if r['delta_usd'] else 'null',c,rm,'Y' if k in ok else '-',chg))
print('##COUNTS')
for k,v in sorted(cnt.items()): print(k,v)
print('##REMEDY')
for k,v in sorted(rem.items()): print(k,v)
print('##NEW')
for k in sorted({(r['wallet'],r['coin']) for r in rows}-ok): print(k[0][:8],k[1])
print('##DROPPED')
for k in sorted(ok-{(r['wallet'],r['coin']) for r in rows}): print(k[0][:8],k[1])
