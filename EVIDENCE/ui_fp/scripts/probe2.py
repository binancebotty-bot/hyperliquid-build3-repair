#!/usr/bin/env python3
'''Deep per-row DOM extraction for UI-FP-030/041/048/052/054/055 + on-disk oracle.'''
import json, os, datetime

BASE = 'http://127.0.0.1:8031'
AUD = 'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet'
OUT = 'C:/Users/wigmore/.hermes/kanban/workspaces/t_ab0d0f07/probe2_raw.json'

JS_ROWS = r"""() => {
  const rows = [];
  const trs = document.querySelectorAll('tr');
  for (const tr of trs) {
    const t = (tr.innerText||'');
    if (!/0x[0-9a-fA-F]{6,}/.test(t)) continue;
    const sels = Array.from(tr.querySelectorAll('select')).map(s=>({name:s.name||'',val:s.value||'',opts:Array.from(s.options).map(o=>o.value)}));
    const ins = Array.from(tr.querySelectorAll('input')).map(i=>({name:i.name||'',id:i.id||'',type:i.type||'',val:(i.value||'')}));
    rows.push({text:(t||'').replace(/\n+/g,' | ').slice(0,900), sels, ins});
  }
  return rows;
}"""

JS_GRAPH = r"""() => {
  const out = {controls:[]};
  ['lcGraphScale','lcGraphStart','lcGraphEnd'].forEach(id=>{
    const el=document.getElementById(id);
    out[id]= el? {tag:el.tagName,type:el.type||'',val:el.value||'',opts: el.options?Array.from(el.options).map(o=>o.value):null} : null;
  });
  // any label mentioning graph/scale
  out.graph_labels = Array.from(document.querySelectorAll('*')).filter(e=>e.children.length===0 && /graph|scale|range/i.test(e.innerText||'')).map(e=>(e.innerText||'').trim().slice(0,60)).slice(0,30);
  return out;
}"""


def main():
    from playwright.sync_api import sync_playwright
    r = {'tested_at_utc': datetime.datetime.utcnow().isoformat()+'Z'}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page()
            pg.goto(BASE + '/live-copy', wait_until='networkidle', timeout=30000)
            r['rows'] = pg.evaluate(JS_ROWS)
            r['graph'] = pg.evaluate(JS_GRAPH)
            r['page_present'] = pg.evaluate("!!document.querySelector('#liveCopyPanel')")
        finally:
            b.close()
    # on-disk oracle
    for fn in ['live_config.json','manual_live_positions.json','ui_state.json','live_service_state.json']:
        pth = os.path.join(AUD, fn)
        try:
            r['disk_'+fn] = json.load(open(pth, encoding='utf-8'))
        except Exception as e:
            r['disk_'+fn+'_err'] = '%s: %r' % (type(e).__name__, e)
    json.dump(r, open(OUT,'w',encoding='utf-8'), indent=1, ensure_ascii=False)
    print('rows', len(r['rows']))
    for row in r['rows'][:3]:
        print('TEXT:', row['text'][:400])
        print('  sels', row['sels'])
        print('  ins', [ (i['name'],i['val']) for i in row['ins'] ])
    print('GRAPH', json.dumps(r['graph'])[:1200])
    print('disk_live_config wallets', list((r.get('disk_live_config.json') or {}).get('wallets',{}).keys())[:20])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
