# Replay probe: UI-LCC-WS-01..16, the 16 WS Health columns.
# Requires: py3.11 + playwright;  PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright
# Run from repo root: C:/Users/wigmore/.hermes/cache/scratch/b3_clean
import json, os
from playwright.sync_api import sync_playwright

URL = 'http://127.0.0.1:8031/live-copy'
OUT = os.path.dirname(os.path.abspath(__file__))

JS = '''() => {
  const t = Array.from(document.querySelectorAll("table"))
                 .find(x => x.querySelectorAll("thead th").length === 16);
  if (!t) return null;
  const hdr = Array.from(t.querySelectorAll("thead th")).map(h => h.innerText.trim());
  const rows = Array.from(t.querySelectorAll("tbody tr")).map((r, ri) => {
    const tds = Array.from(r.querySelectorAll("td"));
    return {ri: ri, ncell: tds.length, cells: tds.map(c => c.innerText.trim())};
  });
  return {nheaders: hdr.length, hdr: hdr, nrows: rows.length, rows: rows};
}'''

d = None
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={'width': 1800, 'height': 1200})
    pg.goto(URL, wait_until='domcontentloaded', timeout=60000)
    pg.wait_for_function('document.readyState==="complete"', timeout=60000)
    pg.wait_for_timeout(2000)
    pg.get_by_role('button', name='WS Health', exact=True).first.click(timeout=15000)
    for attempt in range(20):
        pg.wait_for_timeout(1500)
        d = pg.evaluate(JS)
        print('poll', attempt, 'rows', (d['nrows'] if d else None))
        if d and d['nrows'] > 0:
            break
    html = pg.content()
    open(os.path.join(OUT, 'page_ws_health.html'), 'w', encoding='utf-8').write(html)
    b.close()

if not d or d['nrows'] == 0:
    raise SystemExit('FAIL: WS Health tbody never populated within 30s')

with open(os.path.join(OUT, 'dom_ws_cells.json'), 'w', encoding='utf-8') as f:
    json.dump(d, f, indent=1)

assert d['nheaders'] == 16, d['nheaders']
for r in d['rows']:
    assert r['ncell'] == 16, 'row %d has %d cells' % (r['ri'], r['ncell'])

print('HEADERS 16, ROWS', d['nrows'], 'every row has 16 cells')
for i, h in enumerate(d['hdr']):
    vals = [r['cells'][i] for r in d['rows']]
    print('%2d %-18s distinct=%-3d %s' % (i, h, len(set(vals)), json.dumps(vals)))
