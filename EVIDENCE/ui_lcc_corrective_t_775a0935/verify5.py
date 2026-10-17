import json,re,csv,hashlib
from pathlib import Path
WS=Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_775a0935')
OUT=WS/'evidence'
FRZ=WS/'frozen5'
W='0x010461c14e146ac35fe42271bdc1134ee31c703a'
pr=json.loads((OUT/'probe5_result.json').read_text(encoding='utf-8'))
det=pr['detail_W1'] or ''
# header count from DOM section B
m=re.search(r'B \u2014 Open Positions \((\d+)\)(.*?)(?:C \u2014|$)',det,re.S)
dom_header=int(m.group(1)) if m else None
secB=m.group(0) if m else ''
dom={}
for line in secB.split('\n'):
    p=line.split('\t')
    if len(p)>=3 and p[1] in ('LONG','SHORT'):
        try: dom[p[0].upper()]=float(p[2])
        except: pass
# truth: frozen manual_live_positions.json at the same API instant
mp=json.loads((FRZ/'manual_live_positions.json').read_text(encoding='utf-8'))
byw=mp.get('by_wallet',{})
manw=byw.get(W) or byw.get(W.lower()) or {}
truth={}
for coin,v in manw.items():
    s=v.get('signed_size') if isinstance(v,dict) else v
    try: s=float(s)
    except: s=None
    if s is not None and abs(s)>1e-12: truth[coin.upper()]=s
# api list from probe5
api={p['coin'].upper():p['signed_size'] for p in pr['api_open_positions_W1']}
# fees: independent sum from frozen fills
fee=0.0;nf=0
for r in csv.DictReader(open(FRZ/'live_fills.csv',newline='',encoding='utf-8',errors='replace')):
    if (r.get('leader_wallet') or '').lower()==W.lower():
        nf+=1
        try: fee+=float(r.get('fee') or 0)
        except: pass
fee=round(fee,4)
dom_fees=(re.search(r'Fees: \$([0-9.,-]+)',det) or [None,None])[1]
res={'probe5_dom_sha256':pr['dom_sha256'],'ssot_sha256':pr['ssot_sha256'],'ssot_path':pr['ssot_path'],
 'wallet':W,'frozen_snapshot':pr['freeze_snapshot'],
 'truth_n':len(truth),'api_n':len(api),'dom_n':len(dom),'dom_header_n':dom_header,
 'counts_agree_dom_api_truth':(len(dom)==len(api)==len(truth)),
 'api_vs_truth':{'only_truth':sorted(set(truth)-set(api)),'only_api':sorted(set(api)-set(truth))},
 'dom_vs_truth':{'only_truth':sorted(set(truth)-set(dom)),'only_dom':sorted(set(dom)-set(truth))},
 'api_vs_truth_size_mismatch':[],'dom_vs_truth_size_mismatch':[],
 'fees':{'dom':dom_fees,'api':pr['api_W1']['fees'],'frozen_disk_sum':fee,'fill_rows':nf}}
for c in sorted(set(truth)&set(api)):
    if abs(truth[c]-api[c])>max(1e-6,abs(truth[c])*1e-6): res['api_vs_truth_size_mismatch'].append({'c':c,'t':truth[c],'a':api[c]})
for c in sorted(set(truth)&set(dom)):
    if abs(truth[c]-dom[c])>max(1e-6,abs(truth[c])*1e-6): res['dom_vs_truth_size_mismatch'].append({'c':c,'t':truth[c],'d':dom[c]})
(OUT/'verify5_out.json').write_text(json.dumps(res,indent=1),encoding='utf-8')
print(json.dumps(res,indent=1))
