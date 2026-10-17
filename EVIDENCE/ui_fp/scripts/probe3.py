#!/usr/bin/env python3
'''Focused per-cell extraction for UI-FP rows + lcGraphScale whole-HTML check.'''
import json, datetime
BASE='http://127.0.0.1:8031'
OUT='C:/Users/wigmore/.hermes/kanban/workspaces/t_ab0d0f07/probe3_raw.json'

JS = r"""() => {
  const out={rows:[]};
  const trs=document.querySelectorAll('tr');
  for (const tr of trs){
    const t=(tr.innerText||'');
    if(!/0x[0-9a-fA-F]{6,}/.test(t)) continue;
    const cells=Array.from(tr.querySelectorAll('td')).map(td=>(td.innerText||'').replace(/\n+/g,' | ').trim().slice(0,220));
    const hdr=Array.from(tr.closest('table')?.querySelectorAll('thead th')||[]).map(th=>(th.innerText||'').trim());
    // find the lead-copy diff + risk cells by scanning for Avg bps / Open pos
    const lead = cells.find(c=>/Avg bps|LEAD|Copy Diff|diff/i.test(c))||'';
    const risk = cells.find(c=>/Open pos|Exposure:/i.test(c))||'';
    const ctrl = cells.find(c=>/LIVE|Save|Archive|mode/i.test(c))||'';
    const sels=Array.from(tr.querySelectorAll('select')).map(s=>({name:s.name||'',val:s.value||'',opts:Array.from(s.options).map(o=>o.value)}));
    const ins=Array.from(tr.querySelectorAll('input')).map(i=>({name:i.name||'',id:i.id||'',type:i.type||'',val:i.value||''}));
    out.rows.push({wallet:(t.match(/0x[0-9a-fA-F]{4,}/)||[''])[0].slice(0,12), hdr, cells, lead, risk, ctrl, sels, ins});
  }
  out.html_has_lcGraphScale = document.documentElement.outerHTML.indexOf('lcGraphScale')>=0;
  out.html_has_lcGraphStart = document.documentElement.outerHTML.indexOf('lcGraphStart')>=0;
  out.html_has_lcGraphEnd = document.documentElement.outerHTML.indexOf('lcGraphEnd')>=0;
  out.graph_ctx = (()=>{const h=document.documentElement.outerHTML;const i=h.indexOf('lcGraphStart');return i<0?null:h.slice(i-400,i+400);})();
  return out;
}"""


def main():
    from playwright.sync_api import sync_playwright
    r={'tested_at_utc':datetime.datetime.utcnow().isoformat()+'Z'}
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        try:
            pg=b.new_page(); pg.goto(BASE+'/live-copy',wait_until='networkidle',timeout=30000)
            r.update(pg.evaluate(JS))
        finally:
            b.close()
    json.dump(r,open(OUT,'w',encoding='utf-8'),indent=1,ensure_ascii=False)
    print('nrows',len(r['rows']))
    print('lcGraphScale present:',r.get('html_has_lcGraphScale'),'| Start:',r.get('html_has_lcGraphStart'),'| End:',r.get('html_has_lcGraphEnd'))
    print('graph_ctx:',repr((r.get('graph_ctx') or '')[:700]))
    for row in r['rows'][:4]:
        print('---',row['wallet'])
        print('  sels',row['sels'])
        print('  ins',[(i['name'],i['val']) for i in row['ins']])
        print('  LEAD',repr(row['lead'][:200]))
        print('  RISK',repr(row['risk'][:200]))
    return 0
if __name__=='__main__': raise SystemExit(main())
