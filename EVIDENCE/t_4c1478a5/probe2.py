import json, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = sys.argv[1]
OUT = Path(sys.argv[2])

JS = """() => {
  const tech = [...document.querySelectorAll('#lcHealthTechBody li')].map(e => e.textContent.trim());
  const healthCard = [...document.querySelectorAll('#lcTruthStatus .lc-stat')].map(d => ({
    label: (d.querySelector('.label')||{}).textContent,
    value: (d.querySelector('.value')||{}).textContent,
    sub: (d.querySelector('.lc-muted')||{}).textContent || ''
  }));
  return { technical_detail: tech, cards: healthCard,
           tech_open: !!document.querySelector('#lcHealthTech'),
           body_has_integrity: document.body.innerText.includes('integrity gate') };
}"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(BASE + '/live-copy', wait_until='domcontentloaded', timeout=60000)
    for _ in range(60):
        if pg.evaluate("document.querySelectorAll('#lcTruthStatus .lc-stat').length") >= 2:
            break
        pg.wait_for_timeout(500)
    pg.wait_for_timeout(2000)
    out = pg.evaluate(JS)
    b.close()
OUT.write_text(json.dumps(out, indent=1), encoding='utf-8')
print(json.dumps(out, indent=1)[:1800])
