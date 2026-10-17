#!/usr/bin/env python3
'''B3-CERT t_e2602f28 -- UI-LCC DETAIL-02..04 + ADD-06/07/10 read-only re-probe.

Adapted FROM the proven route `EVIDENCE/ui_fp/scripts/ui_fp_probe.py` @ 36d1c52
(F-UI rows), applied to the LCC DETAIL/ADD rows against register main@b142cf88.

READ-ONLY contract (identical to 36d1c52 proven route):
  * playwright.chromium headless (Python 3.11) renders http://127.0.0.1:8031/live-copy.
  * Independent oracle = urllib served JSON API + on-disk app snapshot
    exchange_account_snapshot_app.json; NO import of HL_Copy_App_SSOT.py.
  * Fully READ-ONLY: no engine imports, no UI control interaction (no clicks),
    no API writes (no POST), no :8031 start/stop. Never touches the operator
    Edge/Chrome, CDP 9223, or the :8031 process.

Scope note: the proven route renders the LIVE-COPY LANDING panel only. The
per-wallet DETAIL modal (sections B Open Positions / C Lead vs Copy+Friction /
D Execution Audit) is opened by clicking a wallet row; the add-wallet modal
fields (Leader equity base / Max diff / Submit) and the add-wallet submit write
are behind that click + a POST /api/live-config/add-wallet. Those are control
interaction / mutation and are therefore OUT of this read-only route's scope; the
rows remain NOT_TESTED with the exact missing route named (see README).
'''
import hashlib, json, os, re, time, datetime, urllib.request, subprocess, sys

BASE = 'http://127.0.0.1:8031'
URL = BASE + '/live-copy'
ROOT = r'C:/Users/wigmore/hyperliquid-build3-repair'
AUDIT_DIR = os.path.join(ROOT, '_archive', 'hl_stage2', 'hl_live_copy_audit_testnet')
REGISTER_REF = 'git show b142cf88:certification/certification_matrix.json'
REGISTER_COMMIT = 'b142cf88d389e791160f691aac3d936852b99975'
HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(HERE, '..', 'raw')

TARGETS = [
    'UI-LCC-DETAIL-02', 'UI-LCC-DETAIL-03', 'UI-LCC-DETAIL-04',
    'UI-LCC-ADD-06', 'UI-LCC-ADD-07', 'UI-LCC-ADD-10',
]

KW = ['Open Positions', 'Lead vs Copy', 'Friction', 'Execution Audit',
      'Add wallet', 'Leader equity', 'Max diff', 'Submit',
      'Detail', 'Coin', 'Side', 'Size', 'Entry', 'Mark', 'uPnL',
      'Exposure', 'Unrealized', 'PnL', 'Stale', 'Unavailable', 'Error',
      'Live', 'Action needed', 'Reconciliation', 'WALLET', 'LIVE',
      'CLOSE', 'OFF', 'LEAD', 'Execution', 'Last Fill', 'Rejection',
      'Latency', 'Technical detail']


def http_json(path, timeout=12):
    try:
        req = urllib.request.Request(BASE + path, headers={'Connection': 'close'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                body = json.loads(raw.decode('utf-8', 'replace'))
            except Exception:
                body = raw.decode('utf-8', 'replace')[:5000]
            return {'http': r.status, 'bytes': len(raw), 'body': body}
    except Exception as e:
        return {'http': None, 'error': '%s: %r' % (type(e).__name__, e)}


def _slice(d, keys):
    out = {}
    for k in keys:
        v = d.get(k)
        s = json.dumps(v, ensure_ascii=False)
        out[k] = {'len': len(s), 'preview': s[:1200]}
    return out


def served_summary_trim(body):
    if not isinstance(body, dict):
        return {'raw_type': type(body).__name__}
    out = {'ok': body.get('ok')}
    out['tracked_wallet_count'] = body.get('tracked_wallet_count')
    out['auto_live_wallet_count'] = body.get('auto_live_wallet_count')
    out['auto_live_eligible_wallets'] = body.get('auto_live_eligible_wallets')
    lwr = body.get('live_wallet_rows') or []
    out['live_wallet_rows_count'] = len(lwr)
    ocp = body.get('owned_copy_positions') or []
    out['owned_copy_positions_count'] = len(ocp)
    out['owned_copy_positions_sample'] = ocp[:5]
    ocp_real = body.get('real_copy_positions') or []
    out['real_copy_positions_count'] = len(ocp_real)
    mls = body.get('manual_live_summary') or {}
    out['manual_live_summary'] = {
        'open_manual_position_count': mls.get('open_manual_position_count'),
        'manual_positions_total': mls.get('manual_positions_total'),
    }
    ss = body.get('exchange_account_snapshot') or {}
    now_ms = int(time.time() * 1000)
    fa = ss.get('fetched_at_ms')
    out['exchange_account_snapshot'] = {
        'ok': ss.get('ok'), 'status': ss.get('status'),
        'updated_at': ss.get('updated_at'), 'fetched_at_ms': fa,
        'account_value': ss.get('account_value'),
        'account_value_source': ss.get('account_value_source'),
        'raw_total_usd': ss.get('raw_total_usd'),
        'age_ms': (now_ms - int(fa)) if isinstance(fa, (int, float)) else None,
    }
    out['execution_quality_summary'] = body.get('execution_quality_summary')
    sb = body.get('status_banner') or {}
    out['status_banner'] = {
        'account_value': sb.get('account_value'),
        'follower_network': sb.get('follower_network'),
        'sending': sb.get('sending'),
        'live_wallets': sb.get('live_wallets'),
        'health_level': (sb.get('health') or {}).get('level'),
        'health_text': (sb.get('health') or {}).get('text'),
    }
    out['tracked_counts'] = _slice(body, ['reason_counts', 'status_counts', 'source_counts'])
    return out


def oracle_snapshot_file():
    p = os.path.join(AUDIT_DIR, 'exchange_account_snapshot_app.json')
    res = {'path': p}
    try:
        raw = open(p, 'rb').read()
        d = json.loads(raw.decode('utf-8-sig', 'replace'))
        now_ms = int(time.time() * 1000)
        fa = d.get('fetched_at_ms')
        res.update(ok=bool(d.get('ok')), status=d.get('status'),
                   account_value_source=d.get('account_value_source'),
                   updated_at=d.get('updated_at'), fetched_at_ms=fa,
                   age_ms=(now_ms - int(fa)) if isinstance(fa, (int, float)) else None,
                   sha256=hashlib.sha256(raw).hexdigest(), size=len(raw))
    except Exception as e:
        res.update(ok=False, error='%s: %r' % (type(e).__name__, e))
    return res


def oracle_live_config_file():
    p = os.path.join(AUDIT_DIR, 'live_config.json')
    res = {'path': p}
    try:
        raw = open(p, 'rb').read()
        res.update(sha256=hashlib.sha256(raw).hexdigest(),
                   mtime=datetime.datetime.utcfromtimestamp(os.path.getmtime(p)).isoformat() + 'Z',
                   size=len(raw), body=json.loads(raw.decode('utf-8-sig', 'replace')))
    except Exception as e:
        res.update(error='%s: %r' % (type(e).__name__, e))
    return res


def live_config_api_trim(body):
    if not isinstance(body, dict):
        return {'raw_type': type(body).__name__}
    cfg = body.get('config') or {}
    wallets = cfg.get('wallets') or {}
    return {
        'ok': body.get('ok'),
        'auto_send_enabled': cfg.get('auto_send_enabled'),
        'wallets_count': len(wallets),
        'wallet_addrs': list(wallets.keys()),
        'global_controls': cfg.get('global_controls'),
        'archived_wallets_count': len(cfg.get('archived_wallets') or {}),
    }


def dom_capture():
    out = {'url': URL, 'ts': datetime.datetime.now().isoformat(), 'route': 'ATTEMPT'}
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
                pt = panel.inner_text() if panel else ''
                out['panel_text_len'] = len(pt)
                out['panel_text'] = ' '.join(pt.split())[:20000]
                out['dom_element_count'] = pg.evaluate('document.querySelectorAll("*").length')
                bt = ' '.join((pg.evaluate('document.body.innerText || ""')).split())
                out['page_body_len'] = len(bt)
                body = out['panel_text'] + '\n' + bt
                out['keyword_hits'] = {k: bool(re.search(re.escape(k), body, re.I)) for k in KW}
                out['pills'] = pg.evaluate(
                    'Array.from(document.querySelectorAll("#liveCopyPanel .lc-pill,#liveCopyPanel .lc-badge,#liveCopyPanel .badge,#liveCopyPanel .status-pill")).map(e=>e.innerText.trim())'
                )[:60]
                out['greenred'] = pg.evaluate(
                    "() => Array.from(document.querySelectorAll('#liveCopyPanel .lc-green,#liveCopyPanel .lc-red,#liveCopyPanel .lc-amber,#liveCopyPanel .text-red,#liveCopyPanel .text-green,#liveCopyPanel .text-warning')).map(e=>({cls:e.className, txt:(e.innerText||'').trim().slice(0,60)})).slice(0,80)"
                )
                out['route'] = 'ROUTE_AVAILABLE'
            finally:
                b.close()
    except Exception as e:
        out['route'] = 'NO_ROUTE'
        out['first_failure'] = '%s: %r' % (type(e).__name__, e)
    return out


def engine_blob_sha():
    try:
        blob = subprocess.check_output(
            ['git', 'show', '%s:_archive/hl_stage2/HL_Copy_App_SSOT.py' % REGISTER_COMMIT], cwd=ROOT)
        return hashlib.sha256(blob).hexdigest()
    except Exception as e:
        return 'ERR: %r' % (e,)


def load_register():
    try:
        raw = subprocess.check_output(['git', 'show', 'b142cf88:certification/certification_matrix.json'], cwd=ROOT)
        d = json.loads(raw.decode('utf-8-sig', 'replace'))
        recs = d.get('records') or d.get('rows') or []
        full_sha = hashlib.sha256(raw).hexdigest()
        rows = {r['id']: r for r in recs}
        return {tid: rows.get(tid) for tid in TARGETS}, full_sha
    except Exception as e:
        return {}, 'ERR: %r' % (e,)


def main():
    register_rows, register_sha = load_register()
    r = {}
    r['task_id'] = 't_e2602f28'
    r['title'] = 'B3-CERT UI-LCC DETAIL-02..04 + ADD-06/07/10 (6 rows) — re-probe with proven DOM route'
    r['register_ref'] = REGISTER_REF
    r['register_commit'] = REGISTER_COMMIT
    r['register_blob_sha256'] = register_sha
    r['engine_sha256'] = engine_blob_sha()
    r['tested_at_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    r['targets'] = TARGETS
    r['runtime'] = {'python': sys.version.split()[0], 'exe': sys.executable}
    r['dom'] = dom_capture()
    s = http_json('/api/live-copy-summary')
    r['api_live_copy_summary'] = {'http': s.get('http'), 'bytes': s.get('bytes')}
    r['api_live_copy_summary_trim'] = served_summary_trim(s.get('body'))
    lc = http_json('/api/live-config')
    r['api_live_config'] = {'http': lc.get('http')}
    r['api_live_config_trim'] = live_config_api_trim(lc.get('body'))
    ws = http_json('/api/live-ws-health')
    r['api_ws_health'] = {'http': ws.get('http'), 'body': ws.get('body')}
    r['oracle_exchange_snapshot_file'] = oracle_snapshot_file()
    r['oracle_live_config_file'] = oracle_live_config_file()
    r['register_rows'] = register_rows
    os.makedirs(RAW_DIR, exist_ok=True)
    out_path = os.path.join(RAW_DIR, 'ui_lcc_detail_add_probe.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(r, f, indent=2, ensure_ascii=False, default=str)
    print('WROTE', out_path)
    print('route:', r['dom'].get('route'), 'http:', r['dom'].get('http_status'),
          'panel:', r['dom'].get('panel_present'), 'els:', r['dom'].get('dom_element_count'))
    print('kw_true:', [k for k, v in r['dom'].get('keyword_hits', {}).items() if v])
    print('summary:', r['api_live_copy_summary'].get('http'), r['api_live_copy_summary'].get('bytes'),
          'B:', r['api_live_copy_summary_trim'].get('tracked_wallet_count'),
          'OCPP:', r['api_live_copy_summary_trim'].get('owned_copy_positions_count'),
          'snap_age_ms:', r['api_live_copy_summary_trim'].get('exchange_account_snapshot', {}).get('age_ms'))
    print('ondisk_snapshot_age_ms:', r['oracle_exchange_snapshot_file'].get('age_ms'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
