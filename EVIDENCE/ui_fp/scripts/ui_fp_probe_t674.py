#!/usr/bin/env python3
'''B3-CERT t_674c5537 UI-FP-145/149/150/165/167/168 rendered-DOM + independent-oracle probe. READ-ONLY.'''
import json, os, sys, datetime, urllib.request
BASE = 'http://127.0.0.1:8031'
URL = BASE + '/live-copy'
AUDIT = r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet'


def http_json(path, timeout=20):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return {'http': r.status, 'body': json.loads(r.read().decode('utf-8', 'replace'))}
    except Exception as e:
        return {'http': None, 'error': '%s: %r' % (type(e).__name__, e)}


def _rd(p):
    try:
        with open(p, 'rb') as f:
            return json.loads(f.read().decode('utf-8-sig', 'replace'))
    except Exception as e:
        return {'__error__': '%s: %r' % (type(e).__name__, e), '__path__': p}


def oracle_disk():
    out = {}
    for n in ['live_ws_health.json', 'manual_live_positions.json', 'exchange_account_snapshot.json', 'exchange_account_snapshot_app.json']:
        out[n] = _rd(os.path.join(AUDIT, n))
    rc = os.path.join(AUDIT, 'append_only', 'reconciliation.csv')
    try:
        with open(rc, 'rb') as f:
            data = f.read()
        lines = data.decode('utf-8', 'replace').splitlines()
        out['reconciliation.csv'] = {'path': rc, 'bytes': len(data), 'lines': len(lines), 'header': lines[0] if lines else '', 'last2': lines[-2:]}
    except Exception as e:
        out['reconciliation.csv'] = {'path': rc, 'error': '%s: %r' % (type(e).__name__, e)}
    return out


def dom_capture():
    out = {'url': URL, 'ts': datetime.datetime.now().isoformat()}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        out['route'] = 'NO_ROUTE'
        out['first_failure'] = 'import playwright: %r' % (e,)
        return out
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page()
                resp = pg.goto(URL, wait_until='networkidle', timeout=30000)
                out['http_status'] = resp.status if resp else None
                out['title'] = pg.title()
                out['panel_present'] = bool(pg.query_selector('#liveCopyPanel'))
                try:
                    pg.wait_for_function("() => {const e=document.querySelector('#lcWalletRows');return e && e.children.length && !(e.innerText||'').includes('Loading');}", timeout=25000)
                except Exception as e:
                    out['wait_warn'] = 'wallet rows: %r' % (e,)
                pg.click('button[data-lc-tab="ws"]')
                pg.wait_for_timeout(1000)
                out['ws_tab_visible'] = pg.evaluate("() => {const p=document.querySelector('.lc-tab-panel[data-lc-panel=\"ws\"]');return !!p && getComputedStyle(p).display!=='none';}")
                out['ws_headers'] = pg.evaluate("() => Array.from(document.querySelectorAll('.lc-tab-panel[data-lc-panel=\"ws\"] thead th')).map(e=>e.innerText.trim())")
                out['ws_rows'] = pg.evaluate("() => {const tb=document.querySelector('#lcHealthRows'); if(!tb) return []; return Array.from(tb.querySelectorAll('tr')).map(tr=>Array.from(tr.querySelectorAll('td')).map(td=>(td.innerText||'').trim()));}")
                out['ws_row_count'] = len(out['ws_rows'])
                out['ws_first_row_html'] = pg.evaluate("() => {const tr=document.querySelector('#lcHealthRows tr'); return tr?tr.innerHTML.slice(0,1500):null;}")
                pg.click('button[data-lc-tab="recon"]')
                pg.wait_for_timeout(1000)
                out['recon_tab_visible'] = pg.evaluate("() => {const p=document.querySelector('.lc-tab-panel[data-lc-panel=\"recon\"]');return !!p && getComputedStyle(p).display!=='none';}")
                out['recon_critical'] = pg.evaluate("() => {const tb=document.querySelector('#lcReconCriticalRows'); if(!tb) return null; return {html_len: tb.innerHTML.length, text: (tb.innerText||'').trim().slice(0,800), rows: Array.from(tb.querySelectorAll('tr')).map(tr=>Array.from(tr.querySelectorAll('td')).map(td=>(td.innerText||'').trim()))};}")
                out['recon_warnings'] = pg.evaluate("() => {const tb=document.querySelector('#lcReconWarningRows'); if(!tb) return null; return {html_len: tb.innerHTML.length, text: (tb.innerText||'').trim().slice(0,800), rows: Array.from(tb.querySelectorAll('tr')).map(tr=>Array.from(tr.querySelectorAll('td')).map(td=>(td.innerText||'').trim()))};}")
                out['recon_warnings_headers'] = pg.evaluate("() => {const tb=document.querySelector('#lcReconWarningRows'); if(!tb) return []; const t=tb.closest('table'); return t?Array.from(t.querySelectorAll('thead th')).map(e=>e.innerText.trim()):[];}")
                out['recon_legacy'] = pg.evaluate("() => {const tb=document.querySelector('#lcReconLegacyRows'); if(!tb) return null; return {rows: Array.from(tb.querySelectorAll('tr')).map(tr=>Array.from(tr.querySelectorAll('td')).map(td=>(td.innerText||'').trim()))};}")
                out['recon_orphan'] = pg.evaluate("() => {const tb=document.querySelector('#lcReconRows'); if(!tb) return null; return {text:(tb.innerText||'').trim().slice(0,500), rows: Array.from(tb.querySelectorAll('tr')).map(tr=>Array.from(tr.querySelectorAll('td')).map(td=>(td.innerText||'').trim()))};}")
                out['greenred'] = pg.evaluate("() => Array.from(document.querySelectorAll('#liveCopyPanel .lc-green,#liveCopyPanel .lc-red,#liveCopyPanel .lc-amber')).map(e=>({cls:e.className, txt:(e.innerText||'').trim().slice(0,60)})).slice(0,60)")
                out['route'] = 'ROUTE_AVAILABLE'
            finally:
                b.close()
    except Exception as e:
        out['route'] = 'NO_ROUTE'
        out['first_failure'] = '%s: %r' % (type(e).__name__, e)
    return out


def main():
    r = {'card': 't_674c5537', 'rows': ['UI-FP-145', 'UI-FP-149', 'UI-FP-150', 'UI-FP-165', 'UI-FP-167', 'UI-FP-168'], 'register_ref': 'main:certification/certification_matrix.json', 'register_commit': 'b142cf88d389e791160f691aac3d936852b99975', 'tested_at_utc': datetime.datetime.utcnow().isoformat() + 'Z'}
    r['dom'] = dom_capture()
    r['api_live_ws_health'] = http_json('/api/live-ws-health')
    r['api_live_audit_summary'] = http_json('/api/live-audit-summary')
    r['oracle_disk'] = oracle_disk()
    print(json.dumps(r, indent=1, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
