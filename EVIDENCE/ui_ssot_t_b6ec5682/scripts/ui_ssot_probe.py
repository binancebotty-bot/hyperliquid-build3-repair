#!/usr/bin/env python3
'''B3-CERT t_b6ec5682 -- UI-SSOT TOP-06/07/09 + TBL-25 + PAGE-01/11 rendered-DOM probe.

READ-ONLY. Renders http://127.0.0.1:8031 in a NEW headless Chromium (playwright,
Python 3.11), captures RENDERED DOM of the SSOT pages, and cross-reads the same
truth from the served JSON API + on-disk app-owned state WITHOUT importing
HL_Copy_App_SSOT.py (independence rule). Never touches the operator Edge/Chrome,
CDP 9223, or the :8031 process.
'''
import json, os, sys, time, datetime, urllib.request, hashlib

BASE = 'http://127.0.0.1:8031'
REGISTER = 'b142cf88d389e791160f691aac3d936852b99975'
AUDIT_DIR = r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet'
STAGE = r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2'


def http(path, timeout=8):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            raw = r.read()
            try:
                return {'http': r.status, 'url': r.geturl(), 'json': json.loads(raw.decode('utf-8', 'replace'))}
            except Exception:
                return {'http': r.status, 'url': r.geturl(), 'text_head': raw[:200].decode('utf-8', 'replace')}
    except Exception as e:
        return {'http': None, 'error': '%s: %r' % (type(e).__name__, e)}


def read_json_file(p):
    try:
        with open(p, 'rb') as f:
            return json.loads(f.read().decode('utf-8-sig', 'replace'))
    except Exception as e:
        return {'error': '%s: %r' % (type(e).__name__, e)}


def capture(pw_pages):
    out = {}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {'route': 'NO_ROUTE', 'first_failure': 'import playwright: %r' % (e,)}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            for name, url, selector in pw_pages:
                rec = {'url': url}
                try:
                    pg = b.new_page()
                    resp = pg.goto(url, wait_until='networkidle', timeout=25000)
                    rec['http_status'] = resp.status if resp else None
                    rec['final_url'] = pg.url
                    rec['title'] = pg.title()
                    if selector:
                        el = pg.query_selector(selector)
                        rec['selector'] = selector
                        rec['selector_present'] = bool(el)
                        rec['selector_text'] = ' '.join((el.inner_text() if el else '').split())[:1500]
                    rec['body_text'] = ' '.join(pg.inner_text('body').split())[:4000]
                except Exception as e:
                    rec['error'] = '%s: %r' % (type(e).__name__, e)
                out[name] = rec
                try:
                    pg.close()
                except Exception:
                    pass
        finally:
            b.close()
    out['route'] = 'ROUTE_AVAILABLE'
    return out


def dom_queries():
    '''Extra structured DOM reads from the SORT page (which serves the analytics top bar).'''
    res = {}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return {'error': '%r' % (e,)}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page()
            pg.goto(BASE + '/sort/wallet?direction=asc', wait_until='networkidle', timeout=25000)
            res['topbar_present'] = bool(pg.query_selector('div.top'))
            res['topbar_text'] = ' '.join((pg.query_selector('div.top').inner_text() if pg.query_selector('div.top') else '').split())
            res['poll_badge'] = pg.evaluate("() => {const e=document.querySelector('div.top span.live');return e?e.innerText.trim():null;}")
            res['has_set_button'] = pg.evaluate("() => Array.from(document.querySelectorAll('div.top button')).some(b=>b.innerText.trim()==='Set')")
            res['set_forms'] = pg.evaluate("() => Array.from(document.querySelectorAll('div.top form')).map(f=>f.getAttribute('action'))")
            res['mode_select_names'] = pg.evaluate("() => Array.from(document.querySelectorAll('div.top select')).map(s=>s.getAttribute('name'))")
            res['current_label'] = pg.evaluate("() => {const re=/Current:|Engine sizing:/;const e=Array.from(document.querySelectorAll('div.top span,div.top b')).find(x=>re.test(x.innerText||''));return e?e.innerText.trim():null;}")
            res['th_sort_links'] = pg.evaluate("() => Array.from(document.querySelectorAll('th a[href^=\"/sort/\"]')).map(a=>a.getAttribute('href')).slice(0,40)")
            res['th_sort_active'] = pg.evaluate("() => Array.from(document.querySelectorAll('th.sort-active')).map(h=>h.innerText.trim())")
            res['data_sort_cells'] = pg.evaluate("() => document.querySelectorAll('td[data-sort]').length")
            res['table_rows'] = pg.evaluate("() => document.querySelectorAll('table tbody tr').length")
            res['diff_flags'] = pg.evaluate("() => document.querySelectorAll('td.diff,span.diff,.diff-flag').length")
        finally:
            b.close()
    return res


def main():
    r = {}
    r['register_ref'] = 'main:certification/certification_matrix.json'
    r['register_commit'] = REGISTER
    r['tested_at_utc'] = datetime.datetime.utcnow().isoformat() + 'Z'

    pages = [
        ('root', BASE + '/', None),
        ('live_copy', BASE + '/live-copy', '#liveCopyPanel'),
        ('sort_wallet', BASE + '/sort/wallet?direction=asc', 'div.top'),
        ('wallet_user', BASE + '/wallet/' + (read_json_file(os.path.join(STAGE, 'ui_state.json')).get('user_wallet') or '0x010461c14e146ac35fe42271bdc1134ee31c703a'), '#liveCopyPanel'),
    ]
    r['dom'] = capture(pages)
    r['dom_queries'] = dom_queries()

    r['api_root_redirect'] = http('/')
    r['api_state'] = http('/api/state')
    r['api_ui_state'] = http('/api/ui-state')
    r['api_live_config'] = http('/api/live-config')
    r['api_live_ws_health'] = http('/api/live-ws-health')
    r['api_live_audit_summary'] = http('/api/live-audit-summary')

    r['oracle_exchange_snapshot_app'] = read_json_file(os.path.join(AUDIT_DIR, 'exchange_account_snapshot_app.json'))
    if isinstance(r['oracle_exchange_snapshot_app'], dict) and 'fetched_at_ms' in r['oracle_exchange_snapshot_app']:
        r['oracle_exchange_snapshot_app']['age_ms'] = int(time.time() * 1000) - int(r['oracle_exchange_snapshot_app']['fetched_at_ms'])
    r['oracle_ui_state_disk'] = read_json_file(os.path.join(STAGE, 'ui_state.json'))
    r['oracle_live_config_disk'] = read_json_file(os.path.join(AUDIT_DIR, 'live_config.json'))
    r['oracle_live_ws_health_disk'] = read_json_file(os.path.join(AUDIT_DIR, 'live_ws_health.json'))

    print(json.dumps(r, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
