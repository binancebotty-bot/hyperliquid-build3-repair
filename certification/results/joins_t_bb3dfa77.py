import json
P='C:/Users/wigmore/.hermes/cache/scratch/b3_cert13/certification/results/UI_LCC_AUD_REC_WS_capture_t_bb3dfa77.json'
d=json.load(open(P,encoding='utf-8'))
src=d['manual_reconciliation_rows']; dom=d['rendered_recon_rows']
D='\u2014'
def js(v):
    if v is None: return ''
    if isinstance(v,bool): return 'true' if v else 'false'
    if isinstance(v,float): return str(int(v)) if v==int(v) else repr(v)
    return str(v)
def sw(w):
    s=js(w); return s[:10]+'...'+s[-6:] if len(s)>18 else (s or 'ACCOUNT_LEVEL_ONLY')
def man(r): return (js(r.get('side') or '')+' '+js(D if r.get('manual_signed_size') is None else r['manual_signed_size'])).strip()
def exc(r): return js(D if r.get('exchange_signed_size') is None else r['exchange_signed_size'])
def iss(r): return js(r.get('issue') or 'n/a')
out={}
for name,fn,i in (('issue',iss,3),('manual',man,4),('exchange',exc,5)):
    out['pos_'+name]=sum(1 for s,r in zip(src,dom) if len(r)>i and r[i]==fn(s))
def key(s): return (js(s.get('coin') or D), sw(s.get('wallet')))
m={}
for s in src: m.setdefault(key(s),[]).append(s)
for name,fn,i in (('issue',iss,3),('manual',man,4),('exchange',exc,5)):
    n=0; bad=[]
    for r in dom:
        k=(r[1],r[2]); hit=[s for s in m.get(k,[]) if fn(s)==r[i]]
        if hit: n+=1
        else: bad.append({'dom':r[:6],'src':[[iss(s),man(s),exc(s)] for s in m.get(k,[])]})
    out['keyed_'+name]=n; out['bad_'+name]=bad[:12]; out['nbad_'+name]=len(bad)
out['src_rows']=len(src); out['dom_rows']=len(dom); out['dupe_keys']=sum(1 for v in m.values() if len(v)>1)
print(json.dumps(out,indent=1)[:6000])
