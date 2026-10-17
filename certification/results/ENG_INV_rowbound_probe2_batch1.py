import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exchange_truth as X
out={}
M='0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205'
# --- INV-08: scope enumeration + fail-closed
ok_enum=X.list_perp_dexes(fetcher=lambda p: [{'name':''},{'name':'XYZ'}])
out['dex_enum_ok']=ok_enum.get('ok'); out['dex_enum_list']=ok_enum.get('dexes')
def fetcher_fail(p): raise RuntimeError('scope down')
out['dex_enum_failclosed']=X.list_perp_dexes(fetcher=fetcher_fail).get('status')
# per-scope: default ok, builder dex raises -> must fail closed
calls={'n':0}
def fetcher_partial(p):
    calls['n']+=1
    if p.get('dex'): raise RuntimeError('hip3 scope down')
    return {'marginSummary':{'accountValue':'100'},'assetPositions':[{'position':{'coin':'BTC','szi':'0.5','positionValue':'50'}}]}
r=X.master_account_net(M,'BTC',fetcher=fetcher_partial,dexes=['','XYZ'])
out['partial_scope_ok']=r.get('ok'); out['partial_scope_status']=r.get('status')
r2=X.master_account_net(M,'BTC',fetcher=fetcher_partial,dexes=[''])
out['default_only_net']=r2.get('net')
# --- INV-10: ack is not settlement
intent={'coin':'BTC','side':'BUY','size':1.0,'oid':'123'}
ack_only=X.resolve_settlement(intent, [], {'ok':False,'status':'TRUTH_UNAVAILABLE'}, reject_evidence={'ack':True})
out['ack_only_verdict']=ack_only.get('status')
settled=X.resolve_settlement(intent,[{'coin':'BTC','side':'B','sz':'1.0','oid':'123'}],{'ok':True,'net':1.0})
out['with_fill_verdict']=settled.get('status')
# --- INV-12: convergence moves toward desired, no flatten-all
import convergence_shadow as CS
out['has_compute_convergence_order']=hasattr(CS,'compute_convergence_order')
src=open('HL_Live_Copy_Service.py',encoding='utf-8',errors='replace').read().lower()
out['flatten_all_patterns']=sum(src.count(t) for t in ('flatten_all','close_all','flatten-all'))
print(json.dumps(out,indent=1))
