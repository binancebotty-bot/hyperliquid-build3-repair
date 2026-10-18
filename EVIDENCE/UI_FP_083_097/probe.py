import json
from playwright.sync_api import sync_playwright

URL = 'http://127.0.0.1:8035/live-copy'
out = {'url': URL}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    pg.goto(URL, wait_until='domcontentloaded', timeout=30000)
    for _ in range(60):
        if pg.evaluate('document.readyState') == 'complete':
            break
        pg.wait_for_timeout(500)
    pg.wait_for_timeout(6000)
    out['readyState'] = pg.evaluate('document.readyState')
    out['owned_rows'] = pg.evaluate("document.querySelectorAll('#lcOwnedPositionRows tr').length")
    out['owned_html'] = pg.evaluate("document.getElementById('lcOwnedPositionRows').innerHTML")
    out['orphan_rows'] = pg.evaluate("document.querySelectorAll('#lcOrphanPositionRows tr').length")
    out['orphan_html'] = pg.evaluate("document.getElementById('lcOrphanPositionRows').innerHTML")
    out['friction_present'] = pg.evaluate("document.body.innerText.includes('Lead vs Copy / Friction')")
    out['panel_text'] = pg.evaluate("document.getElementById('liveCopyPanel').innerText")
    b.close()
open('_dom.json', 'w', encoding='utf-8').write(json.dumps(out, indent=1, ensure_ascii=False))
print('READY', out['readyState'], 'OWNED', out['owned_rows'], 'ORPHAN', out['orphan_rows'], 'FRICTION', out['friction_present'])
