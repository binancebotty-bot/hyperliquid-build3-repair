# Replay probe: UI-LCC-TAB-01..05 visible-table-set discriminator.
# Requires: py3.11 + playwright;  PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright
# Run from repo root: C:/Users/wigmore/.hermes/cache/scratch/b3_clean
import json, os
from playwright.sync_api import sync_playwright

URL = 'http://127.0.0.1:8031/live-copy'
OUT = os.path.dirname(os.path.abspath(__file__))

VIS = ('() => Array.from(document.querySelectorAll("table")).map((t,i)=>{'
       'const r=t.getBoundingClientRect();const s=getComputedStyle(t);'
       'return {i:i,w:Math.round(r.width),h:Math.round(r.height),'
       'display:s.display,visibility:s.visibility};})')

TABS = ['Real Copy Positions', 'Execution Quality', 'Order Intents / Audit',
        'Reconciliation', 'WS Health']

out = {}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1800, 'height': 1200})
    pg.goto(URL, wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_function('document.readyState==="complete"', timeout=60000)
    pg.wait_for_timeout(2000)
    out['url'] = pg.url
    for name in TABS:
        pg.get_by_role('button', name=name, exact=True).first.click(timeout=15000)
        pg.wait_for_timeout(2000)
        boxes = pg.evaluate(VIS)
        vis = [x['i'] for x in boxes
               if x['h'] > 0 and x['w'] > 0
               and x['display'] != 'none' and x['visibility'] != 'hidden']
        out[name] = {'visible_tables': vis, 'all': boxes}
        print(name, '->', vis)
    b.close()

with open(os.path.join(OUT, 'dom_tabs.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=1)

sets = [tuple(out[t]['visible_tables']) for t in TABS]
assert len(set(sets)) == 5, 'tab visible-sets not pairwise distinct: %s' % (sets,)
print('OK: 5 pairwise-distinct visible-table sets -> probe is non-vacuous')
