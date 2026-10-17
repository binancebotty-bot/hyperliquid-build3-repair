#!/usr/bin/env python3
'''B3-CERT t_ab0d0f07 probe -- UI-FP-030/041/048/052/054/055.
READ-ONLY. Renders http://127.0.0.1:8031/live-copy via headless Chromium (py3.11).
Independent oracle = served JSON APIs + on-disk snapshot. No engine import.
'''
import json, os, sys, datetime, urllib.request

BASE = 'http://127.0.0.1:8031'
SNAP = 'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet/exchange_account_snapshot_app.json'
OUT = {}


def jget(path, timeout=8):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return {'http': r.status, 'body': json.loads(r.read().decode('utf-8','replace'))}
    except Exception as e:
        return {'http': None, 'error': '%s: %r' % (type(e).__name__, e)}


def dom():
    from playwright.sync_api import sync_playwright
    r = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        try:
            pg = b.new_page()
            resp = pg.goto(BASE + '/live-copy', wait_until='networkidle', timeout=30000)
            r['http_status'] = resp.status if resp else None
            r['title'] = pg.title()
            r['body_text'] = pg.evaluate('document.body.innerText')
            r['html_len'] = len(pg.content())
            r['inputs'] = pg.evaluate("""() => Array.from(document.querySelectorAll('input,select,textarea')).map(e=>({tag:e.tagName,type:e.type||'',name:e.name||'',id:e.id||'',cls:e.className||'',ph:e.placeholder||'',val:(e.value||'').slice(0,60),txt:(e.innerText||'').slice(0,60)}))""")
            r['data_attrs'] = pg.evaluate("""() => Array.from(document.querySelectorAll('[data-field],[data-testid],[data-metric],[data-key]')).map(e=>({tag:e.tagName,df:e.getAttribute('data-field'),dt:e.getAttribute('data-testid'),dm:e.getAttribute('data-metric'),dk:e.getAttribute('data-key'),txt:(e.innerText||'').trim().slice(0,80)})).slice(0,200)""")
            r['panel_present'] = pg.evaluate("!!document.querySelector('#liveCopyPanel')")
            r['lc_pills'] = pg.evaluate("Array.from(document.querySelectorAll('.lc-pill')).map(e=>(e.innerText||'').trim()).slice(0,80)")
        finally:
            b.close()
    return r


def main():
    r = {'register_ref': 'main:certification/certification_matrix.json',
         'register_commit': 'b142cf88d389e791160f691aac3d936852b99975',
         'tested_at_utc': datetime.datetime.utcnow().isoformat() + 'Z'}
    r['dom'] = dom()
    for pth in ['/api/ui-state', '/api/state', '/api/live-copy-summary', '/api/live-ws-health', '/api/live-config']:
        r['api' + pth.replace('/', '_')] = jget(pth)
    try:
        r['oracle_snapshot'] = json.load(open(SNAP, encoding='utf-8'))
    except Exception as e:
        r['oracle_snapshot_err'] = '%s: %r' % (type(e).__name__, e)
    json.dump(r, open('C:/Users/wigmore/.hermes/kanban/workspaces/t_ab0d0f07/probe_raw.json', 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    d = r['dom']
    print('http', d.get('http_status'), 'title', d.get('title'), 'html_len', d.get('html_len'))
    print('inputs', len(d.get('inputs') or []))
    print('data_attrs', len(d.get('data_attrs') or []))
    print('lc_pills', len(d.get('lc_pills') or []))
    for pth in ['/api/ui-state', '/api/state', '/api/live-copy-summary', '/api/live-ws-health', '/api/live-config']:
        k = 'api' + pth.replace('/', '_')
        v = r[k]
        print(k, v.get('http'), list(v.get('body', {}).keys())[:20] if isinstance(v.get('body'), dict) else v.get('error'))
    print('oracle_keys', list(r.get('oracle_snapshot', {}).keys())[:20] if isinstance(r.get('oracle_snapshot'), dict) else r.get('oracle_snapshot_err'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
