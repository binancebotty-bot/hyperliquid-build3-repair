#!/usr/bin/env python3
'''Final oracle binding: DOM cell text per wallet vs served /api/live-audit-summary live_leader_performance.'''
import json, urllib.request, datetime, re
BASE='http://127.0.0.1:8031'
def jget(p):
    with urllib.request.urlopen(BASE+p,timeout=12) as r: return json.loads(r.read().decode('utf-8','replace'))

r={'tested_at_utc':datetime.datetime.utcnow().isoformat()+'Z'}
aud=jget('/api/live-audit-summary')
lp=aud.get('live_leader_performance') or {}
uc=jget('/api/ui-state')
lc=jget('/api/live-config')
r['audit_avg_bps']={w:(v.get('avg_diff_bps'),v.get('open_position_count')) for w,v in lp.items() if isinstance(v,dict)}

JS=r"""() => {
  const out=[];
  document.querySelectorAll('tr').forEach(tr=>{
    const t=(tr.innerText||'');
    if(!/0x[0-9a-fA-F]{6,}/.test(t)) return;
    const w=(t.match(/0x[0-9a-fA-F]{6,}/)||[''])[0];
    const cells=Array.from(tr.querySelectorAll('td')).map(td=>(td.innerText||'').replace(/\n+/g,' | ').trim());
    const lead=cells.find(c=>/Avg bps/i.test(c))||'';
    const risk=cells.find(c=>/Open pos/i.test(c))||'';
    const bps=(lead.match(/Avg bps:\s*([^ |]+)/)||[])[1];
    const op=(risk.match(/Open pos:\s*([^ |]+)/)||[])[1];
    const sels=Array.from(tr.querySelectorAll('select')).map(s=>({name:s.name||'',val:s.value||''}));
    const ins=Array.from(tr.querySelectorAll('input')).map(i=>({name:i.name||'',val:i.value||''}));
    out.push({wallet:w,bps,op,lead,risk,sels,ins});
  });
  return out;
}"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(headless=True)
    try:
        pg=b.new_page(); pg.goto(BASE+'/live-copy',wait_until='networkidle',timeout=30000)
        r['dom_rows']=pg.evaluate(JS)
        r['html_has_lcGraphScale']=pg.evaluate("document.documentElement.outerHTML.indexOf('lcGraphScale')>=0")
    finally:
        b.close()

cmp=[]
for row in r['dom_rows']:
    w=row['wallet'].lower()
    ap=r['audit_avg_bps'].get(w)
    cmp.append({'wallet':w[:12],'dom_bps':row['bps'],'dom_op':row['op'],'api':ap,
                'bps_match': (row['bps'] is not None and ap is not None and abs(float(row['bps'])-float(ap[0]))<0.05) if (row['bps'] and ap and ap[0] is not None) else None,
                'op_match': (str(row['op'])==str(ap[1])) if (row['op'] is not None and ap is not None) else None})
r['compare']=cmp
json.dump(r,open('C:/Users/wigmore/.hermes/kanban/workspaces/t_ab0d0f07/probe6_raw.json','w',encoding='utf-8'),indent=1,ensure_ascii=False)
print('live_leader_performance n',len(r['audit_avg_bps']))
for c in cmp[:8]:
    print(c)
print('total dom rows with wallet', len(r['dom_rows']))
m=[c for c in cmp if c['bps_match'] is True]; n=[c for c in cmp if c['bps_match'] is False]
mo=[c for c in cmp if c['op_match'] is True]; no=[c for c in cmp if c['op_match'] is False]
print('bps matches',len(m),'mismatch',len(n),'| op matches',len(mo),'mismatch',len(no))
print('lcGraphScale in HTML', r['html_has_lcGraphScale'])
