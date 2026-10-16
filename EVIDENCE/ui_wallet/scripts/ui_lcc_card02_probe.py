#!/usr/bin/env python3
'''B3-CERT t_7fc73e22 -- UI-LCC-CARD-02 probe.

Renders the CERTIFIED card renderer (function renderCards + its helpers, taken
verbatim from the register-commit blob of HL_Copy_App_SSOT.py) inside a NEW
headless Chromium, fed by the LIVE served audit payload (/api/live-audit-summary).

Why this shape: the :8031 service is NOT running the register-commit build (its
DOM labels differ), so rendering the live page would test the wrong artifact.
This probe executes the certified source's JS in a real browser and captures the
DOM it produces. Independent oracle = urllib read of the served JSON API + the
engine's on-disk snapshot/history files; HL_Copy_App_SSOT.py is never imported.

READ-ONLY. Never touches the operator Edge/Chrome, CDP 9223, or the :8031
process. No start/stop/order action, no writes to served config, no exchange calls.
'''
import datetime
import hashlib
import json
import os
import re
import sys
import urllib.request

BASE = 'http://127.0.0.1:8031'
AUDIT_DIR = r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet'
SRC = os.environ.get('SSOT_REGISTER_BLOB') or r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/HL_Copy_App_SSOT.py'
MASTER = '0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205'

HELPER_NAMES = ['function h(', 'function moneyFmt(', 'function signCls(', 'function tiny(']
TARGET_FNS = ['function renderCards(']


def http_json(path, timeout=180):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return {'http': r.status, 'body': json.loads(r.read().decode('utf-8', 'replace'))}
    except Exception as e:
        return {'http': None, 'error': '%s: %r' % (type(e).__name__, e)}


def read_json_file(p):
    try:
        with open(p, 'rb') as f:
            return json.loads(f.read().decode('utf-8-sig', 'replace'))
    except Exception as e:
        return {'__error__': '%s: %r' % (type(e).__name__, e)}


def extract_fn(text, needle):
    '''Brace-balanced extraction of a JS function beginning at `needle`.'''
    i = text.find(needle)
    if i < 0:
        return None
    j = text.find('{', i)
    depth = 0
    k = j
    while k < len(text):
        c = text[k]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return text[i:k + 1]
        k += 1
    return None


def src_census():
    out = {}
    raw = open(SRC, 'rb').read()
    out['path'] = SRC
    out['source'] = 'register-commit blob (git show b142cf88:_archive/hl_stage2/HL_Copy_App_SSOT.py)'
    out['sha256'] = hashlib.sha256(raw).hexdigest()
    out['bytes'] = len(raw)
    t = raw.decode('utf-8', 'replace')
    out['labels_in_source'] = {
        'Unrealized PnL': t.count('Unrealized PnL'),
        'OPEN POSITIONS P&L': t.count('OPEN POSITIONS P&L'),
        'PORTFOLIO VALUE (TESTNET)': t.count('PORTFOLIO VALUE (TESTNET)'),
        'Live Exposure': t.count('Live Exposure'),
        'Live exposure label present': t.count('estimated') + t.count('estimate'),
        'manual_live_exposure_estimate': t.count('manual_live_exposure_estimate'),
    }
    fns = {}
    for n in HELPER_NAMES + TARGET_FNS:
        fns[n] = extract_fn(t, n)
    out['extracted'] = {k: (len(v) if v else None) for k, v in fns.items()}
    out['renderCards_src'] = fns['function renderCards(']
    return out, fns


def dom_render(js_fns, audit_body, variant):
    out = {'variant': variant, 'ts': datetime.datetime.now().isoformat()}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        out['route'] = 'NO_ROUTE'
        out['first_failure'] = 'import playwright: %r' % (e,)
        return out
    page_html = '<!doctype html><html><body><div id="liveCopyPanel"><div class="lc-stat-strip" id="lcRealCards"></div></div></body></html>'
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            try:
                pg = b.new_page()
                pg.set_content(page_html)
                pg.evaluate('(a)=>{window.lcAudit=a;window.renderGraph=function(){};}', audit_body)
                script = '\n'.join(js_fns[n] for n in HELPER_NAMES if js_fns.get(n)) + '\n' + js_fns['function renderCards(']
                pg.evaluate('(s)=>{window.__src=s;}', script)
                pg.add_script_tag(content='window.root=document.getElementById("liveCopyPanel");' + script + ';window.__runRender=renderCards;')
                pg.evaluate('()=>window.__runRender()')
                out['http_status'] = 'set_content'
                out['cards'] = pg.evaluate(
                    "() => Array.from(document.querySelectorAll('#lcRealCards .lc-stat')).map(e=>({"
                    "label:((e.querySelector('.label')||{}).innerText||'').trim(),"
                    "value:((e.querySelector('.value')||{}).innerText||'').trim(),"
                    "cls:((e.querySelector('.value')||{}).className||'')}))")
                out['card_labels'] = [c['label'] for c in out['cards']]
                out['unrealized_card'] = next((c for c in out['cards'] if c['label'].lower() == 'unrealized pnl'), None)
                out['live_exposure_card'] = next((c for c in out['cards'] if c['label'].lower() == 'live exposure'), None)
                out['portfolio_card'] = next((c for c in out['cards'] if c['label'].lower() == 'portfolio value'), None)
                out['rendered_text'] = ' | '.join('%s=%s' % (c['label'], c['value']) for c in out['cards'])
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
    r['row'] = 'UI-LCC-CARD-02'
    census, fns = src_census()
    r['src_census'] = census
    r['api_live_audit_summary'] = http_json('/api/live-audit-summary')
    r['api_state'] = http_json('/api/state')
    audit = (r['api_live_audit_summary'].get('body') or {})
    snap = audit.get('exchange_account_snapshot') or {}
    man = audit.get('manual_live_summary') or {}
    r['served'] = {
        'snapshot_available': snap.get('available'),
        'snapshot_account_address': snap.get('account_address'),
        'snapshot_account_is_master': str(snap.get('account_address', '')).lower() == MASTER,
        'snapshot_unrealized_pnl': snap.get('unrealized_pnl'),
        'snapshot_unrealized_pnl_source': snap.get('unrealized_pnl_source'),
        'snapshot_updated_at': snap.get('updated_at'),
        'snapshot_open_positions': len(snap.get('open_positions') or []),
        'manual_live_exposure_estimate': man.get('manual_live_exposure_estimate'),
    }
    # independent oracle: on-disk engine/app artefacts
    disk_app = read_json_file(os.path.join(AUDIT_DIR, 'exchange_account_snapshot_app.json'))
    disk_hist = read_json_file(os.path.join(AUDIT_DIR, 'exchange_account_history.json'))
    disk_snap = read_json_file(os.path.join(AUDIT_DIR, 'exchange_account_snapshot.json'))
    r['oracle_disk'] = {
        'app_snapshot_account': disk_app.get('account_address'),
        'app_snapshot_is_master': str(disk_app.get('account_address', '')).lower() == MASTER,
        'app_snapshot_unrealized_pnl': disk_app.get('unrealized_pnl'),
        'app_snapshot_fetched_at_ms': disk_app.get('fetched_at_ms'),
        'history_type': type(disk_hist).__name__,
        'history_len': len(disk_hist) if isinstance(disk_hist, (list, dict)) else None,
        'snapshot_type': type(disk_snap).__name__,
        'snapshot_keys': list(disk_snap)[:10] if isinstance(disk_snap, dict) else None,
    }
    if isinstance(disk_hist, list) and disk_hist:
        last = disk_hist[-1]
        r['oracle_disk']['history_last'] = {k: last.get(k) for k in ('account_address', 'updated_at', 'fetched_at_ms', 'unrealized_pnl', 'available') if isinstance(last, dict)}
    elif isinstance(disk_hist, dict):
        pts = disk_hist.get('points') if isinstance(disk_hist.get('points'), list) else None
        if pts:
            last = pts[-1]
            r['oracle_disk']['history_last'] = {k: last.get(k) for k in ('account_address', 'updated_at', 'fetched_at_ms', 'unrealized_pnl', 'available') if isinstance(last, dict)}
    # rendered DOM of the certified renderer, live payload
    r['dom_live'] = dom_render(fns, audit, 'live_payload')
    # negative test: same certified renderer, source unavailable / null pnl
    neg = json.loads(json.dumps(audit))
    if isinstance(neg.get('exchange_account_snapshot'), dict):
        neg['exchange_account_snapshot']['available'] = False
        neg['exchange_account_snapshot']['unrealized_pnl'] = None
        neg['exchange_account_snapshot']['unified_portfolio_value'] = None
    r['dom_negative_unavailable'] = dom_render(fns, neg, 'negative_source_unavailable')
    out = json.dumps(r, indent=2, ensure_ascii=False)
    outp = os.environ.get('PROBE_OUT')
    if outp:
        with open(outp, 'w', encoding='utf-8') as fh:
            fh.write(out)
    print(json.dumps({k: v for k, v in r.items() if k not in ('api_live_audit_summary', 'api_state')}, indent=2, ensure_ascii=False)[:9000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
