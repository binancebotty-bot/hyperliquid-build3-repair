#!/usr/bin/env python3
'''B3-CERT t_7fc73e22 -- UI-WALLET-002/006/008/014/015 + UI-LCC-CARD-02 probe.

READ-ONLY. Renders http://127.0.0.1:8031/live-copy in a NEW headless Chromium
(playwright, Python 3.11) and captures the RENDERED DOM of the Real Account card
strip + wallet table. Independent oracle: urllib read of the served JSON API
(/api/state, /api/ui-state, /api/live-config, /api/live-audit-summary) plus the
on-disk app snapshot, WITHOUT importing HL_Copy_App_SSOT.py (independence rule).

Never touches the operator Edge/Chrome, CDP 9223, or the :8031 process. No
start/stop/order action, no mocks, no writes to any served config.
'''
import datetime
import hashlib
import json
import os
import sys
import time
import urllib.request

BASE = 'http://127.0.0.1:8031'
URL = BASE + '/live-copy'
AUDIT_DIR = r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/hl_live_copy_audit_testnet'
SRC = os.environ.get('SSOT_REGISTER_BLOB') or r'C:/Users/wigmore/hyperliquid-build3-repair/_archive/hl_stage2/HL_Copy_App_SSOT.py'


def http_json(path, timeout=90):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return {'http': r.status, 'body': json.loads(r.read().decode('utf-8', 'replace'))}
    except Exception as e:
        return {'http': None, 'error': '%s: %r' % (type(e).__name__, e)}


def http_text(path, timeout=60):
    try:
        with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
            return {'http': r.status, 'len': len(r.read()), 'error': None}
    except Exception as e:
        return {'http': None, 'len': None, 'error': '%s: %r' % (type(e).__name__, e)}


def oracle_snapshot_file():
    p = os.path.join(AUDIT_DIR, 'exchange_account_snapshot_app.json')
    try:
        with open(p, 'rb') as f:
            d = json.loads(f.read().decode('utf-8-sig', 'replace'))
        fetched = d.get('fetched_at_ms')
        return {
            'path': p, 'ok': d.get('ok'), 'available': d.get('available'),
            'account_address': d.get('account_address'), 'updated_at': d.get('updated_at'),
            'fetched_at_ms': fetched,
            'unrealized_pnl': d.get('unrealized_pnl'),
            'unrealized_pnl_source': d.get('unrealized_pnl_source'),
            'account_value': d.get('account_value'),
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
                resp = pg.goto(URL, wait_until='domcontentloaded', timeout=45000)
                out['http_status'] = resp.status if resp else None
                out['title'] = pg.title()
                try:
                    pg.wait_for_selector('#lcRealCards .lc-stat', timeout=40000)
                except Exception as e:
                    out['realcards_wait'] = '%s' % (type(e).__name__,)
                panel = pg.query_selector('#liveCopyPanel')
                out['panel_present'] = bool(panel)
                out['real_account_heading_present'] = bool(pg.query_selector('#liveCopyPanel section.lc-panel h3'))
                out['real_cards'] = pg.evaluate(
                    "() => Array.from(document.querySelectorAll('#lcRealCards .lc-stat')).map(e=>({"
                    "label:(e.querySelector('.label')||{}).innerText||'',"
                    "value:(e.querySelector('.value')||{}).innerText||'',"
                    "cls:((e.querySelector('.value')||{}).className||'')}))")
                out['card_labels'] = [c['label'] for c in out['real_cards']]
                out['unrealized_card'] = next((c for c in out['real_cards'] if c['label'].strip().lower() == 'unrealized pnl'), None)
                out['live_exposure_card'] = next((c for c in out['real_cards'] if c['label'].strip().lower() == 'live exposure'), None)
                out['portfolio_card'] = next((c for c in out['real_cards'] if c['label'].strip().lower() == 'portfolio value'), None)
                out['panel_text'] = ' '.join((panel.inner_text() if panel else '').split())[:3000]
                out['stale_tokens'] = pg.evaluate(
                    "() => {const t=document.querySelector('#liveCopyPanel');if(!t)return [];const re=/(stale|age|ago|as of|updated)/i;"
                    "return Array.from(t.querySelectorAll('*')).filter(e=>e.children.length===0&&re.test(e.innerText||''))"
                    ".map(e=>e.innerText.trim().slice(0,90)).slice(0,40);}")
                out['unavailable_tokens'] = pg.evaluate(
                    "() => {const t=document.querySelector('#liveCopyPanel');if(!t)return [];const re=/(unavailable|n\/a|not available)/i;"
                    "return Array.from(t.querySelectorAll('*')).filter(e=>e.children.length===0&&re.test(e.innerText||''))"
                    ".map(e=>e.innerText.trim().slice(0,90)).slice(0,40);}")
                out['wallet_row_count'] = pg.evaluate("() => document.querySelectorAll('#liveCopyPanel tr.lc-wallet-row').length")
                out['wallet_controls'] = pg.evaluate(
                    "() => Array.from(document.querySelectorAll('#liveCopyPanel tr.lc-wallet-row')).slice(0,3)"
                    ".map(tr=>Array.from(tr.querySelectorAll('button')).map(b=>({t:(b.innerText||'').trim(),"
                    "act:b.dataset.act||'', title:(b.title||'').slice(0,60)})))")
                out['mode_buttons_present'] = pg.evaluate(
                    "() => {const bs=Array.from(document.querySelectorAll('#liveCopyPanel tr.lc-wallet-row button'));"
                    "const t=bs.map(b=>(b.innerText||'').trim());"
                    "return {LIVE:t.filter(x=>x==='LIVE').length, CLO:t.filter(x=>x==='CLO').length,"
                    "OFF:t.filter(x=>x==='OFF').length, ARCHIVE:t.filter(x=>x==='Archive').length, PURGE:t.filter(x=>x==='PURGE').length};}")
                out['effective_mode_shown'] = pg.evaluate(
                    "() => {const re=/effective|current mode|effective mode/i;"
                    "return Array.from(document.querySelectorAll('#liveCopyPanel *')).filter(e=>e.children.length===0&&re.test(e.innerText||''))"
                    ".map(e=>e.innerText.trim().slice(0,80)).slice(0,20);}")
                out['route'] = 'ROUTE_AVAILABLE'
            finally:
                b.close()
    except Exception as e:
        out['route'] = 'NO_ROUTE'
        out['first_failure'] = '%s: %r' % (type(e).__name__, e)
    return out


def src_census():
    '''READ-ONLY static census of the UI source AT THE REGISTER COMMIT (blob on disk
    is the register-commit copy; sha256 cited). No import.'''
    out = {}
    try:
        raw = open(SRC, 'rb').read()
        out['path'] = SRC
        out['source'] = 'register-commit blob (git show b142cf88:_archive/hl_stage2/HL_Copy_App_SSOT.py)'
        out['sha256'] = hashlib.sha256(raw).hexdigest()
        out['bytes'] = len(raw)
        t = raw.decode('utf-8', 'replace')
        toks = {
            'endpoint_set_mode_live_config': "/api/live-config/set-mode",
            'endpoint_remove_wallet': "/api/live-config/remove-wallet",
            'endpoint_purge_wallet': "/api/admin/purge-wallet",
            'endpoint_set_wallet_mode': "/api/set-wallet-mode",
            'endpoint_set_all_modes': "/api/set-all-modes",
            'endpoint_wallet_config': "/api/wallet-config",
            'normalise_payload_def': "def _normalise_live_wallet_payload",
            'purge_everywhere_def': "def purge_wallet_everywhere",
            'wallet_gate_file': "WALLET_GATE_FILE",
            'archived_wallets_key': "archived_wallets",
            'archived_at_key': "archived_at",
            'tombstone_token': "tombstone",
            'close_only_token': "CLOSE_ONLY",
            'effective_mode_token': "effective_mode",
            'two_writer_guard_token': "contradict",
            'exposure_guard_token': "owns exposure",
            'purge_exposure_refusal_token': "EXPOSURE",
            'fixed_hold_token': "FIXED-MODE HOLD",
            'od02_token': "OD-02",
            'od05_token': "OD-05",
            'od13_token': "OD-13",
            'restore_token': "restore",
        }
        out['token_counts'] = {k: t.count(v) for k, v in toks.items()}
        lines = t.splitlines()
        out['purge_wallet_everywhere_body'] = src_block(lines, 'def purge_wallet_everywhere')
        out['normalise_body'] = src_block(lines, 'def _normalise_live_wallet_payload')
        out['remove_wallet_body'] = src_block(lines, 'async def remove_live_config_wallet')
        out['set_mode_body'] = src_block(lines, 'async def set_live_config_mode')
        out['set_wallet_mode_body'] = src_block(lines, 'async def set_wallet_mode')
        out['set_all_modes_body'] = src_block(lines, 'async def set_all_modes')
    except Exception as e:
        out['error'] = '%s: %r' % (type(e).__name__, e)
    return out


def src_block(lines, needle, limit=60):
    for i, ln in enumerate(lines):
        if needle in ln:
            return '\n'.join(lines[i:i + limit])
    return None


def main():
    r = {}
    r['register_ref'] = 'main:certification/certification_matrix.json'
    r['register_commit'] = 'b142cf88d389e791160f691aac3d936852b99975'
    r['tested_at_utc'] = datetime.datetime.utcnow().isoformat() + 'Z'
    r['dom'] = dom_capture()
    r['api_state'] = http_json('/api/state')
    r['api_ui_state'] = http_json('/api/ui-state')
    r['api_live_config'] = http_json('/api/live-config')
    r['api_live_audit_summary'] = http_json('/api/live-audit-summary', timeout=180)
    r['oracle_snapshot_file'] = oracle_snapshot_file()
    r['src_census'] = src_census()
    # oracle recompute for UI-LCC-CARD-02
    sn = (r['api_live_audit_summary'].get('body') or {}).get('exchange_account_snapshot') or {}
    f = sn.get('fetched_at_ms')
    r['oracle_recompute'] = {
        'served_unrealized_pnl': sn.get('unrealized_pnl'),
        'served_unrealized_pnl_source': sn.get('unrealized_pnl_source'),
        'served_unified_portfolio_value': sn.get('unified_portfolio_value'),
        'served_available': sn.get('available'),
        'served_updated_at': sn.get('updated_at'),
        'age_ms_at_capture': (int(time.time() * 1000) - int(f)) if isinstance(f, (int, float)) else None,
        'file_unrealized_pnl': r['oracle_snapshot_file'].get('unrealized_pnl'),
        'file_fetched_at_ms': r['oracle_snapshot_file'].get('fetched_at_ms'),
    }
    man = (r['api_live_audit_summary'].get('body') or {}).get('manual_live_summary') or {}
    r['oracle_recompute']['manual_live_exposure_estimate'] = man.get('manual_live_exposure_estimate')
    r['oracle_recompute']['manual_signed_size_total_abs'] = None
    ssz = man.get('signed_size_by_coin')
    if isinstance(ssz, dict):
        try:
            r['oracle_recompute']['manual_signed_size_total_abs'] = round(sum(abs(float(v)) for v in ssz.values() if v), 4)
        except Exception as e:
            r['oracle_recompute']['manual_signed_size_total_abs'] = 'ERR %r' % (e,)
    out = json.dumps(r, indent=2, ensure_ascii=False)
    outp = os.environ.get('PROBE_OUT')
    if outp:
        with open(outp, 'w', encoding='utf-8') as fh:
            fh.write(out)
    print(out[:12000])
    return 0


if __name__ == '__main__':
    sys.exit(main())
