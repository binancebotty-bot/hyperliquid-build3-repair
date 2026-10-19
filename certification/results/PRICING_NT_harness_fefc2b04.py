import hashlib,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
R=Path('C:/Users/wigmore/hyperliquid-build3-repair')
C='certification/results/PRICING_CORRECTION_fefc2b04.json'
H='certification/results/PRICING_CORRECTION_harness_fefc2b04.py'
ES='2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405'
CC='346d9128da507ab64fd09ccce099f97b30e8c293'
O='certification/results/PRICING_NT_fefc2b04.json'
ROWS=['PRICE-001','PRICE-002','PRICE-005','PRICE-006','PRICE-007']
CH=[]
def ck(n,p,d=''):
    CH.append({'name':n,'pass':bool(p),'detail':d}); print('CHECK',('PASS' if p else 'FAIL'),n,d)
def g(*a): return subprocess.check_output(['git','-C',str(R)]+list(a),text=True).strip()
head=g('rev-parse','HEAD')
p=R/C
ck('CITED_ARTIFACT_EXISTS',p.is_file(),str(p))
if not p.is_file(): sys.exit(2)
tr=g('ls-files',C,H).splitlines()
ck('CITED_ARTIFACT_TRACKED',C in tr,repr(tr))
ck('CITED_HARNESS_TRACKED',H in tr,repr(tr))
b=subprocess.check_output(['git','-C',str(R),'show','fefc2b04:_archive/hl_stage2/HL_Live_Copy_Service_Core.py'])
ac=hashlib.sha256(b).hexdigest()
ck('ENGINE_SHA256_MATCHES_COMMITTED_BLOB',ac==ES,'actual='+ac)
a=json.loads(p.read_text(encoding='utf-8'))
rows=a.get('rows',{})
ck('ALL_ROWS_PRESENT',[r for r in ROWS if r in rows]==ROWS,repr(list(rows)))
gm={r:rows.get(r,{}).get('gate_logic_checks_pass') for r in ROWS}
ck('PER_ROW_GATE_LOGIC_PASS',all(gm.get(r) is True for r in ROWS),repr(gm))
allc=a.get('checks',[]); cp=sum(1 for x in allc if x.get('pass'))
ck('CITED_ALL_GATE_CHECKS_PASS',bool(allc) and cp==len(allc),'n=%d p=%d'%(len(allc),cp))
ng=a.get('negative_tests',[]); np=sum(1 for x in ng if x.get('pass'))
ck('CITED_NEGATIVES_NON_VACUOUS',len(ng)>=1 and np==len(ng),'n=%d p=%d'%(len(ng),np))
bad=[x.get('name') for x in list(allc)+list(ng) if 'ORDER_FILLED' in str(x.get('detail','')) and 'NOT exchange truth' not in str(x.get('detail',''))]
ck('NO_UNLABELLED_ORDER_FILLED',not bad,repr(bad))
ost=str(a.get('oracle_statement',''))
ck('ORACLE_NOT_ACHIEVABLE',('NOT achievable' in ost and 'exchange truth' in ost),'len=%d'%len(ost))
per={r:{'verdict':rows.get(r,{}).get('verdict'),'oracle_named_in_matrix':rows.get(r,{}).get('oracle_named_in_matrix'),'oracle_actually_used':rows.get(r,{}).get('oracle_actually_used'),'exchange_truth_aspect':rows.get(r,{}).get('exchange_truth_aspect'),'gate_logic_checks_pass':rows.get(r,{}).get('gate_logic_checks_pass'),'checks_pass':rows.get(r,{}).get('checks_pass'),'checks_total':rows.get(r,{}).get('checks_total'),'cited_from':C} for r in ROWS}
ok=all(x['pass'] for x in CH)
res={'task_id':'t_5e812878','title':'B3-CERT PRICING residual NOT_TESTED (5 rows) - CONFIRMATION','mode':'CONFIRM_AND_CITE (no engine re-run)','repo_head_at_run':head,'engine_commit_reference':'fefc2b04','engine_sha256':ES,'tested_at_utc':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'cited_artifact':C,'cited_harness':H,'cited_task_id':'t_0246c47f','citation_commit':CC,'rows':per,'confirmation_checks':CH,'summary':{'overall':'CONFIRMED' if ok else 'FAIL','checks_total':len(CH),'checks_pass':sum(1 for x in CH if x['pass']),'rows_total':len(ROWS),'rows_confirmed':sum(1 for r in ROWS if gm.get(r) is True)},'note':'All 5 rows already earned by committed PRICING_CORRECTION_fefc2b04.json (t_0246c47f): gate semantics ESTABLISHED, exchange-truth NOT_ESTABLISHED (follower wallet absent on testnet; t_5cf2e6cf). certification_matrix.json NOT edited.','output':O}
(R/O).write_text(json.dumps(res,indent=2),encoding='utf-8')
print('OVERALL',res['summary']['overall'],res['summary']['checks_pass'],'/',res['summary']['checks_total'])
print('OUT',str(R/O))
sys.exit(0 if ok else 1)
