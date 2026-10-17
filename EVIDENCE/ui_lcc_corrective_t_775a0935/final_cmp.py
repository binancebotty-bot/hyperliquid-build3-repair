import json,re
from pathlib import Path
WS=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935')
FRZ=WS/'frozen4'
W='0x010461c14e146ac35fe42271bdc1134ee31c703a'
pr=json.loads((WS/'evidence'/'probe4_result.json').read_text(encoding='utf-8'))
# TRUTH: engine-written manual_live_positions.json frozen at the API-read instant
mp=json.loads((FRZ/'manual_live_positions.json').read_text(encoding='utf-8'))
manw=mp['by_wallet'].get(W) or mp['by_wallet'].get(W.lower()) or {}
truth={}
for coin,v in manw.items():
    s=v.get('signed_size') if isinstance(v,dict) else v
    try: s=float(s)
    except: s=None
    if s is not None and abs(s)>1e-12: truth[coin.upper()]=s
truth_n=len(truth)
# API list (app's own)
api_list={p['coin'].upper():p['signed_size'] for p in pr['api_open_positions_W1']}
# DOM detail (rendered)
det=pr['detail_W1']
m=re.search(r'B — Open Positions \((\d+)\)(.*?)(?:C —|$)',det,re.S)
secB=m.group(0) if m else ''
dom={}
for line in secB.split('\n'):
    p=line.split('\t')
    if len(p)>=3 and p[1] in ('LONG','SHORT'):
        try: dom[p[0].upper()]=float(p[2])
        except: pass
res={'wallet':W,'truth_n':truth_n,'api_n':len(api_list),'dom_n':len(dom),'dom_header_n':int(m.group(1)) if m else None,
     'api_vs_truth':{'only_truth':sorted(set(truth)-set(api_list)),'only_api':sorted(set(api_list)-set(truth)),'size_mismatch':[]},
     'dom_vs_truth':{'only_truth':sorted(set(truth)-set(dom)),'only_dom':sorted(set(dom)-set(truth)),'size_mismatch':[]}}
for c in sorted(set(truth)&set(api_list)):
    if abs(truth[c]-api_list[c])>max(1e-6,abs(truth[c])*1e-6): res['api_vs_truth']['size_mismatch'].append({'c':c,'t':truth[c],'a':api_list[c]})
for c in sorted(set(truth)&set(dom)):
    if abs(truth[c]-dom[c])>max(1e-6,abs(truth[c])*1e-6): res['dom_vs_truth']['size_mismatch'].append({'c':c,'t':truth[c],'d':dom[c]})
# fees: independent sum from frozen live_fills.csv for W1
import csv
fee=0.0;nf=0
for r in csv.DictReader(open(FRZ/'live_fills.csv',newline='',encoding='utf-8',errors='replace')):
    if (r.get('leader_wallet') or '').lower()==W.lower():
        nf+=1
        try: fee+=float(r.get('fee') or 0)
        except: pass
res['truth_fees_sum']=round(fee,4);res['truth_fill_rows']=nf
res['api_fees']=pr['api_W1']['fees'];res['dom_fees']=(re.search(r'Fees: \$([0-9.,-]+)',det) or [None,None])[1]
(WS/'final_cmp_out.json').write_text(json.dumps(res,indent=1),encoding='utf-8')
print(json.dumps(res,indent=1)[:2600])
