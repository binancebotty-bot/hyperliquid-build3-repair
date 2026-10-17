#!/usr/bin/env python3
'''B3-CERT t_9dee8e17 -- UI-FP-119/120/133/137/139/140 rendered-DOM + independent oracle.

READ-ONLY. Headless Chromium (playwright py3.11) renders http://127.0.0.1:8031/live-copy,
clicks each tab (execqual/audit/recon) and captures the RENDERED table headers + first rows.
Independent oracle: served JSON API (urllib, no engine import) + append_only CSV reads.
No engine import. No mocks. No register edit.
'''
import json, os, io, csv, sys, time, datetime, urllib.request

BASE = 'http://127.0.0.1:8031'
URL = BASE + '/live-copy'
AUDIT = r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet'


def jget(path, timeout=20):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return {'http': r.status, 'body': json.loads(r.read().decode('utf-8', 'replace'))}
    except Exception as e:
        return {'http': None, 'error': '%s: %r' % (type(e).__name__, e)}


def csv_header(name):
    p = os.path.join(AUDIT, 'append_only', name)
    try:
        with io.open(p, 'r', encoding='utf-8-sig', errors='replace') as f:
            line = f.readline().rstrip('\r\n')
        return {'path': p, 'header': line.split(',') if line else []}
    except Exception as e:
        return {'path': p, 'error': '%s: %r' % (type(e).__name__, e)}


def dom_tabs():
    out = {}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {'route': 'NO_ROUTE', 'first_failure': 'import playwright: %r' % (e,)}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page()
            resp = pg.goto(URL, wait_until='networkidle', timeout=30000)
            out['http_status'] = resp.status if resp else None
            out['title'] = pg.title()
            tabs = [('execqual', '#lcExecQualRows'), ('audit', '#lcAuditRows'), ('recon', '#lcReconRows')]
            for tab, sel in tabs:
                rec = {}
                try:
                    pg.click('button[data-lc-tab="%s"]' % tab, timeout=8000)
                    pg.wait_for_timeout(2500)
                    panel = pg.query_selector('div[data-lc-panel="%s"]' % tab)
                    rec['panel_present'] = bool(panel)
                    if panel:
                        ths = panel.query_selector_all('thead th')
                        rec['table_headers'] = [t.inner_text().strip() for t in ths]
                        tb = panel.query_selector('tbody' + sel.lstrip('#') if False else sel)
                        if tb:
                            rec['tbody_text_head'] = tb.inner_text()[:1500]
                            rec['tbody_row_count'] = len(tb.query_selector_all('tr'))
                        tbl = panel.query_selector('table')
                        rec['table_text_head'] = tbl.inner_text()[:2500] if tbl else None
                except Exception as e:
                    rec['error'] = '%s: %r' % (type(e).__name__, e)
                out[tab] = rec
        finally:
            b.close()
    return out


def main():
    r = {'register_ref': 'main:certification/certification_matrix.json',
         'register_commit': 'b142cf88d389e791160f691aac3d936852b99975',
         'tested_at_utc': datetime.datetime.utcnow().isoformat() + 'Z',
         'surface': URL}
    r['dom'] = dom_tabs()
    r['api_live_audit_summary'] = {}
    s = jget('/api/live-audit-summary')
    if isinstance(s.get('body'), dict):
        b = s['body']
        r['api_live_audit_summary'] = {
            'http': s['http'],
            'top_keys': sorted(list(b.keys()))[:60],
            'audit_rows_len': len(b.get('audit_rows') or []),
            'audit_row0_keys': sorted(list((b.get('audit_rows') or [{}])[0].keys())) if b.get('audit_rows') else [],
            'exec_qual_rows_len': len(b.get('execution_quality_rows') or []),
            'exec_qual_row0_keys': sorted(list((b.get('execution_quality_rows') or [{}])[0].keys())) if b.get('execution_quality_rows') else [],
            'manual_recon_rows_len': len(b.get('manual_reconciliation_rows') or []),
            'manual_recon_row0_keys': sorted(list((b.get('manual_reconciliation_rows') or [{}])[0].keys())) if b.get('manual_reconciliation_rows') else [],
        }
    else:
        r['api_live_audit_summary'] = s
    r['csv_headers'] = {n: csv_header(n) for n in ('send_attempts.csv', 'live_fills.csv', 'order_intents.csv', 'reconciliation.csv')}
    # negative-test surface: an API error must surface, not be swallowed
    r['api_error_probe'] = jget('/api/does-not-exist-xyz')
    out = sys.argv[1] if len(sys.argv) > 1 else 'ui_fp_probe_119_140.json'
    with io.open(out, 'w', encoding='utf-8') as f:
        json.dump(r, f, indent=1, ensure_ascii=False)
    print('WROTE', out)
    print(json.dumps({k: r[k] for k in ('dom',)}, indent=1, ensure_ascii=False)[:4000])


if __name__ == '__main__':
    main()
