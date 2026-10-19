import hashlib, json, os, socket, subprocess, sys, time, urllib.request
from pathlib import Path
ROOT = Path(r'C:/Users/wigmore/.hermes/kanban/workspaces/t_1c4509ec/iso')
TAG, APP, PORT = sys.argv[1], ROOT/sys.argv[2], int(sys.argv[3])
AUDIT = ROOT/'run'/('audit_'+TAG); EV = ROOT/'ev'; BASE = f'http://127.0.0.1:{PORT}'
ENV_FILE = ROOT/'run'/('env_'+TAG+'.env')
W1 = '0x1111111111111111111111111111111111111730'; W2 = '0x2222222222222222222222222222222222221740'
F1 = {'snapshot_fill_seen_count': 710170, 'snapshot_fill_recovered_count': 710173, 'ignored_snapshot_count': 710174, 'recent_error_count': 710175, 'lifetime_error_count': 710176, 'stale_ms': 710177, 'data_status': 'DS178_LIVE_OK', 'last_close_msg': 'LC179 close sentinel'}
F2 = {'snapshot_fill_seen_count': 3, 'snapshot_fill_recovered_count': 1, 'ignored_snapshot_count': 2, 'recent_error_count': 4, 'lifetime_error_count': 5, 'stale_ms': 6, 'data_status': 'DS178_OTHER', 'last_close_msg': 'LC179 other wallet'}
HROWS = [('UI-FP-173', 'Snap recovered', 'snapshot_fill_recovered_count'), ('UI-FP-174', 'Ignored', 'ignored_snapshot_count'), ('UI-FP-175', 'Recent errors', 'recent_error_count'), ('UI-FP-176', 'Lifetime errors', 'lifetime_error_count'), ('UI-FP-177', 'Stale ms', 'stale_ms'), ('UI-FP-178', 'Data status', 'data_status'), ('UI-FP-179', 'Last close/error', 'last_close_msg')]
CROWS = [('UI-FP-180', 'gcMaxTotal', 'max_total_live_exposure_usd', 12500.5, 12500.5), ('UI-FP-181', 'gcMaxDir', 'max_asset_directional_exposure_usd', 2500, 2500.0), ('UI-FP-182', 'gcMaxWallet', 'max_wallet_exposure_usd', 750.25, 750.25), ('UI-FP-183', 'gcMaxOrder', 'max_order_notional_usd', '50.5', 50.5), ('UI-FP-184', 'gcMktPct', 'marketable_slippage_pct', 0.35, 0.35), ('UI-FP-185', 'gcCloseAdv', 'max_close_adverse_diff_pct', '0.1200', 0.12), ('UI-FP-186', 'gcAllowlist', 'symbol_allowlist', ['btc', ' eth ', 'Sol'], ['BTC', 'ETH', 'SOL']), ('UI-FP-187', 'gcBlocklist', 'symbol_blocklist', ['doge', ' xrp'], ['DOGE', 'XRP'])]
UNOWNED = {'send_mode': 'CLOSE', 'follower_leverage': 7, 'liq_parity': True}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def hj(path, method='GET', body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE+path, data=data, method=method, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r: return json.loads(r.read().decode())
def wait_port(d=120):
    end = time.time()+d
    while time.time() < end:
        try:
            with socket.create_connection(('127.0.0.1', PORT), timeout=1): return True
        except OSError: time.sleep(0.5)
    return False
def write_health(path, wallets, status='LIVE'):
    p = {'created_at': '2026-10-19T00:00:00+00:00', 'created_at_ms': 1792400000000, 'ws_summary': {'ws_status': status}, 'wallets': wallets}
    path.write_text(json.dumps(p, indent=2), encoding='utf-8'); return p

def main():
    EV.mkdir(parents=True, exist_ok=True); (AUDIT/'append_only').mkdir(parents=True, exist_ok=True); (AUDIT/'app_cache').mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text('HL_LEADER_NETWORK=mainnet\nHL_FOLLOWER_NETWORK=testnet\nHL_APP_PORT=%d\nHL_LIVE_AUDIT_DIR=%s\n' % (PORT, str(AUDIT).replace(chr(92), '/')), encoding='utf-8')
    cfg = {'wallets': {}, 'archived_wallets': {}, 'global_controls': {'max_total_live_exposure_usd': 0.0, 'max_asset_directional_exposure_usd': 0.0, 'max_daily_loss_usd': 0.0, 'max_wallet_exposure_usd': 0.0, 'max_order_notional_usd': 0.0, 'marketable_bps': 20.0, 'max_close_adverse_diff_pct': 0.0, 'symbol_allowlist': [], 'symbol_blocklist': [], 'send_mode': 'CLOSE', 'follower_leverage': 7, 'liq_parity': True}}
    cf = AUDIT/'live_config.json'; cf.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
    env = dict(os.environ); env['HL_LIVE_ENV_FILE'] = str(ENV_FILE); env['PYTHONPATH'] = str(APP)
    log = open(EV/('uvicorn_%s.log' % TAG), 'w', encoding='utf-8')
    proc = subprocess.Popen([sys.executable, '-c', "import uvicorn;uvicorn.run('HL_Copy_App_SSOT:app',host='127.0.0.1',port=%d,log_level='info')" % PORT], cwd=str(APP), env=env, stdout=log, stderr=subprocess.STDOUT)
    ev = {'tag': TAG, 'app_dir': str(APP), 'port': PORT, 'state_dir': str(AUDIT), 'app_file_sha256': sha(APP/'HL_Copy_App_SSOT.py'), 'rows': {}}
    try:
        if not wait_port(): raise SystemExit('server did not start')
        hj('/api/global-controls', 'POST', {'max_order_notional_usd': -5, 'unknown_key': 123})
        neg = json.loads(cf.read_text())['global_controls']
        ev['controls_negative'] = {'minus5_clamped_to_zero': neg.get('max_order_notional_usd') == 0.0, 'unknown_key_not_persisted': 'unknown_key' not in neg}
        payload = {'max_daily_loss_usd': 900, 'marketable_slippage_pct': 0.35}
        for _r, _e, field, sent, _x in CROWS: payload[field] = sent
        post = hj('/api/global-controls', 'POST', payload)['global_controls']
        get = hj('/api/global-controls')['global_controls']
        disk = json.loads(cf.read_text())['global_controls']
        ev['controls_post_response'] = post; ev['controls_get'] = get; ev['controls_disk'] = disk; ev['config_sha_after_post'] = sha(cf)
        ev['unowned_keys_after_ui_save'] = {k: disk.get(k, '<DROPPED>') for k in UNOWNED}
        ev['passthrough'] = {'seeded': UNOWNED, 'after': {k: disk.get(k, '<DROPPED>') for k in UNOWNED}, 'all_preserved': all(disk.get(k) == v for k, v in UNOWNED.items())}
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True); page = b.new_page(viewport={'width': 2200, 'height': 1800})
            page.goto(BASE+'/live-copy', wait_until='domcontentloaded', timeout=120000)
            for _ in range(60):
                if page.evaluate('document.readyState') == 'complete': break
                page.wait_for_timeout(500)
            page.wait_for_timeout(4000)
            page.screenshot(path=str(EV/('dom_controls_%s.png' % TAG)), full_page=True)
            (EV/('dom_controls_%s.html' % TAG)).write_text(page.content(), encoding='utf-8')
            gv = {e: page.eval_on_selector('#'+e, 'el => el.value') for _r, e, *_ in CROWS}
            ev['gc_input_values'] = gv
            for rid, eid, field, sent, exp in CROWS:
                is184 = rid == 'UI-FP-184'
                av = get.get('marketable_bps') if is184 else get.get(field)
                pv = post.get('marketable_bps') if is184 else post.get(field)
                dv = disk.get('marketable_bps') if is184 else disk.get(field)
                tgt = 35.0 if is184 else exp
                want = (','.join(exp) if isinstance(exp, list) else (str(int(exp)) if float(exp) == int(exp) else str(exp)))
                ck = {'post_normalised': pv == tgt, 'get_roundtrip': av == tgt, 'disk_persisted': dv == tgt, 'dom_input_shows_value': gv.get(eid) == want}
                ev['rows'][rid] = {'kind': 'control', 'expected': exp, 'posted_raw': sent, 'api_value': av, 'dom_input_id': eid, 'dom_input_value': gv.get(eid), 'want_dom': want, 'checks': ck, 'pass': all(ck.values()), 'provenance': 'POST /api/global-controls -> live_config.json -> GET /api/global-controls -> #%s.value' % eid}
            hp = AUDIT/'live_ws_health.json'
            write_health(hp, {W1: dict(F1, last_message_ms=1792400000000, stale=False), W2: dict(F2, last_message_ms=1792390000000, stale=False)})
            ev['health_fixture_sha256'] = sha(hp); ev['health_fixture_wallets'] = {W1: F1, W2: F2}
            ah = hj('/api/live-ws-health')['health']['wallets']; ev['health_api_wallets'] = ah
            def cap(tag):
                page.click('#lcRefresh'); page.wait_for_timeout(3500)
                (EV/('dom_health_%s_%s.html' % (TAG, tag))).write_text(page.content(), encoding='utf-8')
                page.screenshot(path=str(EV/('dom_health_%s_%s.png' % (TAG, tag))), full_page=True)
                return page.evaluate("""() => {const tb=document.querySelector('#lcHealthRows');const t=tb.closest('table');const hd=Array.from(t.querySelectorAll('thead th')).map(x=>x.textContent.trim());const rows=Array.from(tb.querySelectorAll('tr')).map(tr=>{const td=Array.from(tr.querySelectorAll('td'));const o={};hd.forEach((h,i)=>o[h]=td[i]?td[i].textContent.trim():null);return o;});return {heads:hd,rows:rows};}""")
            dom = cap('fixture'); ev['health_table_headers'] = dom['heads']; ev['health_table_rows'] = dom['rows']
            def fr(w):
                for r in dom['rows']:
                    c = (r.get('Wallet') or '').lower()
                    if c and (w[2:8].lower() in c or w[-4:].lower() in c): return r
                return None
            r1, r2 = fr(W1), fr(W2)
            for rid, hdr, field in HROWS:
                src = F1[field]; got = (r1 or {}).get(hdr); av = (ah.get(W1) or {}).get(field); oth = (r2 or {}).get(hdr)
                ck = {'api_matches_source_file': av == src, 'dom_cell_matches_source_value': got == str(src), 'row_bound_not_neighbour_value': oth is not None and oth != got}
                ev['rows'][rid] = {'kind': 'health', 'source_field': field, 'source_value': src, 'header': hdr, 'api_value': av, 'dom_cell': got, 'neighbour_cell': oth, 'checks': ck, 'pass': all(ck.values()), 'dom_capture': 'iso/ev/dom_health_%s_fixture.html' % TAG, 'provenance': 'live_ws_health.json wallets[%s].%s -> GET /api/live-ws-health -> %s cell in #lcHealthRows' % (W1, field, hdr)}
            hp.unlink()
            dm = cap('missing'); ev['negative_source_unavailable'] = {'rows': dm['rows'], 'shows_unavailable_not_zero': ('WS service not running or no wallet health file found.' in json.dumps(dm['rows'])) or ('Unavailable' in json.dumps(dm['rows'])) or ('n/a' in json.dumps(dm['rows']))}
            hp.write_text('{not json', encoding='utf-8')
            bad = cap('badjson')
            ev['negative_malformed_source'] = {'rows': bad['rows'], 'no_traceback_or_zero': ('WS service not running or no wallet health file found.' in json.dumps(bad['rows'])) or ('0' not in json.dumps(bad['rows']))}
            write_health(hp, {W1: dict(F1, last_message_ms=1792300000000, stale=True, current_status='STALE', thread_alive=True, fatal_error_count=0)}, status='STALE')
            ds = cap('stale'); sr = None
            for r in ds['rows']:
                c = (r.get('Wallet') or '').lower()
                if c and (W1[2:8].lower() in c or W1[-4:].lower() in c): sr = r
            ev['negative_stale_flagged'] = {'row': sr, 'stale_ms_cell': (sr or {}).get('Stale ms'), 'flagged': bool(sr) and (sr.get('Stale ms') or '') == str(F1['stale_ms']) and 'STALE' in ((sr.get('Current') or '').upper())}
            b.close()
        ev['pass_count'] = sum(1 for r in ev['rows'].values() if r['pass']); ev['row_count'] = len(ev['rows'])
        (EV/('ui_fp_173_187_evidence_%s.json' % TAG)).write_text(json.dumps(ev, indent=2), encoding='utf-8')
        print(json.dumps({'tag': TAG, 'sha': ev['app_file_sha256'][:12], 'rows': ev['row_count'], 'pass': ev['pass_count'], 'passthrough_preserved': ev['passthrough']['all_preserved'], 'unowned_after': ev['unowned_keys_after_ui_save'], 'neg_clamp': ev['controls_negative'], 'neg_unavail': ev['negative_source_unavailable']['shows_unavailable_not_zero'], 'neg_stale': ev['negative_stale_flagged']['flagged'], 'neg_badjson': ev['negative_malformed_source']['no_traceback_or_zero']}))
        for rid in sorted(ev['rows']): print(rid, 'PASS' if ev['rows'][rid]['pass'] else 'FAIL', json.dumps(ev['rows'][rid]['checks']))
    finally:
        proc.terminate()
        try: proc.wait(20)
        except Exception: proc.kill()
        log.close()

main()
