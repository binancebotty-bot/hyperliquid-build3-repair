import os, json
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = 'C:/Users/wigmore/AppData/Local/ms-playwright'
from playwright.sync_api import sync_playwright
JS = "() => { const o={}; const t=Array.from(document.querySelectorAll('table')); for (const i of [0,2,3,4,5,9]) { const tab=t[i]; if(!tab){o['t'+i]=null;continue;} const hr=tab.tHead?tab.tHead.rows[0]:null; const hc=hr?Array.from(hr.cells):[]; const sp=hc.reduce((a,c)=>a+(c.colSpan||1),0); const tb=tab.tBodies[0]; const rows=tb?Array.from(tb.rows):[]; const hist={}; rows.forEach(r=>{const w=r.cells.length; hist[w]=(hist[w]||0)+1;}); o['t'+i]={headers:hc.map(c=>c.innerText.trim()), hcells:hc.length, span:sp, rows:rows.length, hist:hist, s0:rows[0]?Array.from(rows[0].cells).map(c=>c.innerText.trim().slice(0,24)):[]}; } o.tables=t.length; return o; }"
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width':1920,'height':1080})
    pg.goto('http://127.0.0.1:8031/live-copy', wait_until='domcontentloaded', timeout=90000)
    pg.wait_for_timeout(35000)
    r = pg.evaluate(JS)
    b.close()
open('EVIDENCE/ui_lcc_verify.json','w',encoding='utf-8').write(json.dumps(r,indent=1,ensure_ascii=False))
print('tables', r['tables'])
for k in ['t0','t2','t3','t4','t5','t9']:
    v = r[k]
    if not v:
        print(k,'MISSING'); continue
    print(k,'hcells',v['hcells'],'span',v['span'],'rows',v['rows'],'hist',v['hist'])
    print('  hdr',v['headers'])
    print('  r0 ',v['s0'])
