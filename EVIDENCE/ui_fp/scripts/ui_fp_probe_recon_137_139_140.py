#!/usr/bin/env python3
'''Focused DOM capture of the Reconciliation tab Actionable Critical Items + Warnings tables.
READ-ONLY. playwright.chromium headless py3.11.'''
import json, io, sys, datetime
from playwright.sync_api import sync_playwright
BASE = 'http://127.0.0.1:8031'
URL = BASE + '/live-copy'

out = {'surface': URL, 'tested_at_utc': datetime.datetime.utcnow().isoformat() + 'Z'}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    try:
        pg = b.new_page()
        pg.goto(URL, wait_until='networkidle', timeout=30000)
        pg.click('button[data-lc-tab="recon"]', timeout=8000)
        pg.wait_for_timeout(2500)
        panel = pg.query_selector('div[data-lc-panel="recon"]')
        out['panel_present'] = bool(panel)
        tables = {}
        for tbody_id in ('lcReconCriticalRows', 'lcReconWarningRows', 'lcReconRows'):
            tb = pg.query_selector('#' + tbody_id)
            rec = {'present': bool(tb)}
            if tb:
                rec['row_count'] = len(tb.query_selector_all('tr'))
                rec['text_head'] = tb.inner_text()[:1200]
                # header of the owning table
                hdr = pg.evaluate('''(id)=>{const tb=document.getElementById(id);if(!tb)return null;const t=tb.closest('table');return t?Array.from(t.querySelectorAll('thead th')).map(x=>x.innerText.trim()):null;}''', tbody_id)
                rec['owning_table_headers'] = hdr
            tables[tbody_id] = rec
        out['tables'] = tables
    finally:
        b.close()
op = sys.argv[1] if len(sys.argv) > 1 else 'ui_fp_probe_recon_137_139_140.json'
with io.open(op, 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print(json.dumps(out, indent=1, ensure_ascii=False)[:4000])
