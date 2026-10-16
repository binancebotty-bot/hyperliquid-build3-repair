#!/usr/bin/env python3
'''B3-CERT t_d925c3dd -- F-UI-001/002/003 bounded rendered-DOM + independent-oracle probe.

READ-ONLY. Loads http://127.0.0.1:8031/live-copy in a NEW headless Chromium
(playwright, Python 3.11), captures the RENDERED DOM of the live-copy panel, and
cross-reads the same truth from the served JSON API and from the on-disk app-owned
exchange snapshot WITHOUT importing HL_Copy_App_SSOT.py (independence rule).

Never touches the operator Edge/Chrome, CDP 9223, or the :8031 process.
'''
import json, os, sys, time, datetime, urllib.request

BASE = 'http://127.0.0.1:8031'
URL = BASE + '/live-copy'
AUDIT_DIR = r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet'


def http_json(path, timeout=8):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return {'http': r.status, 'body': json.loads(r.read().decode('utf-8', 'replace'))}
    except Exception as e:
        return {'http': None, 'error': '%s: %r' % (type(e).__name__, e)}


def oracle_read_snapshot():
    p = os.path.join(AUDIT_DIR, 'exchange_account_snapshot_app.json')
    try:
        with open(p, 'rb') as f:
            d = json.loads(f.read().decode('utf-8-sig', 'replace'))
        now_ms = int(time.time() * 1000)
        fetched = d.get('fetched_at_ms')
        return {
            'path': p, 'ok': bool(d.get('ok')), 'status': d.get('status'),
            'account_value_source': d.get('account_value_source'),
            'updated_at': d.get('updated_at'), 'fetched_at_ms': fetched,
            'age_ms': (now_ms - int(fetched)) if isinstance(fetched, (int, float)) else None,
        }
    except Exception as e:
        return {'path': p, 'error': '%s: %r' % (type(e).__name__, e)}


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
                resp = pg.goto(URL, wait_until='networkidle', timeout=25000)
                out['http_status'] = resp.status if resp else None
                out['title'] = pg.title()
                panel = pg.query_selector('#liveCopyPanel')
                out['panel_present'] = bool(panel)
                out['panel_text'] = ' '.join((panel.inner_text() if panel else '').split())[:4000]
                out['dom_element_count'] = pg.evaluate('document.querySelectorAll("*").length')
                out['pills'] = pg.evaluate('Array.from(document.querySelectorAll("#liveCopyPanel .lc-pill")).map(e=>e.innerText.trim())')
                out['age_hits'] = pg.evaluate("() => {const t=document.querySelector('#liveCopyPanel');if(!t)return [];const re=/(age|ago|stale|fresh|updated|seconds)/i;return Array.from(t.querySelectorAll('*')).filter(e=>e.children.length===0&&re.test(e.innerText||'')).map(e=>e.innerText.trim().slice(0,80)).slice(0,60);}")
                out['acct_value_hits'] = pg.evaluate("() => {const re=/ACCOUNT VALUE|ACCOUNT CHANGE|OPEN POSITIONS|RESTING ORDERS/i;return Array.from(document.querySelectorAll('#liveCopyPanel *')).filter(e=>e.children.length<=2&&re.test(e.innerText||'')).map(e=>e.innerText.trim().replace(/\\s+/g,' ').slice(0,120)).slice(0,20);}")
                out['greenred'] = pg.evaluate("() => Array.from(document.querySelectorAll('#liveCopyPanel .lc-green,#liveCopyPanel .lc-red,#liveCopyPanel .lc-amber')).map(e=>({cls:e.className, txt:(e.innerText||'').trim().slice(0,60)})).slice(0,60)")
                out['route'] = 'ROUTE_AVAILABLE'
            finally:
                b.close()
    except Exception as e:
        out['route'] = 'NO_ROUTE'
        out['first_failure'] = '%s: %r' % (type(e).__name__, e)
    return out


def main():
    r = {}
    r['register_ref'] = 'main:certification/certification_matrix.json'
    r['register_commit'] = 'b142cf88d389e791160f691aac3d936852b99975'
    r['tested_at_utc'] = datetime.datetime.utcnow().isoformat() + 'Z'
    r['dom'] = dom_capture()
    r['api_live_copy_summary'] = http_json('/api/live-copy-summary')
    r['api_ws_health'] = http_json('/api/live-ws-health')
    r['oracle_exchange_snapshot_file'] = oracle_read_snapshot()
    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
