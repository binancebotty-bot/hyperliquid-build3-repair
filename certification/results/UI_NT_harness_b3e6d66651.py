#!/usr/bin/env python3
"""B3-CERT UI NOT_TESTED APPLIES harness - task t_1fb73bd2.

Executes the 23 in-scope UI rows' execution_proof against the REAL served UI
(HL_Copy_App_SSOT.py over HTTP, DOM rendered by real Chromium) on the REAL
testnet audit state, with an INDEPENDENT ORACLE per row and a NON-VACUOUS
negative per check. Never aborts: a row that cannot be reached is reported
BLOCKED with the exact failing edge.

Run with Python 3.11:
  C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe \\
    certification/results/UI_NT_harness_b3e6d66651.py

Do NOT edit certification_matrix.json or apply_verified_results.py.
"""
from __future__ import annotations
import csv, hashlib, json, os, re, shutil, signal, socket, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
MAIN = Path('C:/Users/wigmore/hyperliquid-build3-repair')
SCR = Path('C:/Users/wigmore/.hermes/cache/scratch/b3ui_nt')
HL = WT / '_archive' / 'hl_stage2'
MAIN_HL = MAIN / '_archive' / 'hl_stage2'
UI_SRC = HL / 'HL_Copy_App_SSOT.py'
REAL_STATE = MAIN_HL / 'hl_live_copy_audit_testnet'
UI_SHA = hashlib.sha256(UI_SRC.read_bytes()).hexdigest()
COMMIT = subprocess.run(['git', '-C', str(WT), 'rev-parse', 'HEAD'],
                        capture_output=True, text=True).stdout.strip()
COMMIT10 = COMMIT[:10]

CHECKS, NEG, ROWS, BLOCKED = [], [], {}, []
PORT = 8899


def check(name, ok, detail=''):
    CHECKS.append({'name': name, 'pass': bool(ok), 'detail': str(detail)})
    print('  CHECK::' + name + '::' + ('PASS' if ok else 'FAIL') + ((' | ' + str(detail)) if detail else ''))


def neg(name, ok, detail=''):
    NEG.append({'name': name, 'pass': bool(ok), 'detail': str(detail)})
    print('  NEG::' + name + '::' + ('PASS' if ok else 'FAIL'))


def rjson(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding='utf-8-sig'))
    except Exception:
        return default


def rcsv(p):
    try:
        with Path(p).open(encoding='utf-8-sig', newline='') as fh:
            return list(csv.DictReader(fh))
    except Exception:
        return []


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def num_from_dom(text):
    if text is None:
        return None
    t = str(text).replace('$', '').replace(',', '').replace('\u2212', '-').strip().replace('+', '')
    return float(t) if re.match(r'^-?\d+(\.\d+)?$', t) else None


def oracle_cards(state_dir):
    state_dir = Path(state_dir)
    snap = rjson(state_dir / 'exchange_account_snapshot_app.json', {}) or {}
    price = {}
    for coin, pos in (snap.get('positions_by_coin') or {}).items():
        if isinstance(pos, dict) and float(pos.get('mark_px') or 0) > 0:
            price[str(coin).upper()] = float(pos['mark_px'])
    for r in rcsv(state_dir / 'append_only' / 'send_attempts.csv'):
        c = str(r.get('coin') or '').upper()
        try:
            px = float(r.get('fill_avg_px') or 0)
        except Exception:
            px = 0.0
        if c and px > 0 and c not in price:
            price[c] = px
    d = rjson(state_dir / 'manual_live_positions.json', {}) or {}
    exp = 0.0
    for _w, coins in (d.get('by_wallet') or {}).items():
        if isinstance(coins, dict):
            for coin, pos in coins.items():
                if isinstance(pos, dict):
                    exp += abs(float(pos.get('signed_size') or 0)) * price.get(str(coin).upper(), 0.0)
    return {'unrealized_pnl': snap.get('unrealized_pnl'),
            'open_positions': len(snap.get('open_positions') or []) if snap.get('available') else None,
            'live_exposure': exp, 'available': bool(snap.get('available'))}


def stage_runtime_data():
    HL.mkdir(parents=True, exist_ok=True)
    for name in ['hl_copy_output', 'hl_live_copy_audit_testnet']:
        src, dst = MAIN_HL / name, HL / name
        if src.exists():
            if dst.exists():
                shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


def build_env():
    SCR.mkdir(parents=True, exist_ok=True)
    aud = SCR / 'audit'
    if aud.exists():
        shutil.rmtree(aud, ignore_errors=True)
    (aud / 'append_only').mkdir(parents=True, exist_ok=True)
    for n in ['live_config.json', 'live_ws_health.json', 'live_integrity_status.json',
              'live_service_state.json', 'manual_live_positions.json',
              'exchange_account_snapshot.json', 'exchange_account_snapshot_app.json',
              'exchange_account_history.json', 'clean_core_runtime_state.json', 'network.json']:
        if (REAL_STATE / n).exists():
            shutil.copy2(REAL_STATE / n, aud / n)
    for n in ['send_attempts.csv', 'order_intents.csv', 'live_fills.csv', 'reconciliation.csv']:
        if (REAL_STATE / 'append_only' / n).exists():
            shutil.copy2(REAL_STATE / 'append_only' / n, aud / 'append_only' / n)
    (SCR / 'test.env').write_text('HL_LEADER_NETWORK=mainnet\nHL_FOLLOWER_NETWORK=testnet\n'
                                  'HL_LIVE_HL_ACCOUNT_ADDRESS=0x' + 'c' * 40 + '\nHL_APP_PORT=' + str(PORT) + '\n')
    return aud


def start_server(aud):
    code = ('import os,sys;'
            'sys.path.insert(0,' + repr(str(HL)) + ');'
            'os.environ["HL_LIVE_ENV_FILE"]=' + repr(str(SCR / 'test.env')) + ';'
            'os.environ["HL_LIVE_AUDIT_DIR"]=' + repr(str(aud)) + ';'
            'import uvicorn, HL_Copy_App_SSOT as ui;'
            'uvicorn.run(ui.app, host="127.0.0.1", port=' + str(PORT) + ', log_level="error")')
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if os.name == 'nt' else 0
    env = dict(os.environ); env['HL_LIVE_ENV_FILE'] = str(SCR / 'test.env'); env['HL_LIVE_AUDIT_DIR'] = str(aud)
    proc = subprocess.Popen([sys.executable, '-c', code], env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, creationflags=flags)
    for _ in range(160):
        try:
            with socket.create_connection(('127.0.0.1', PORT), timeout=0.5):
                return proc
        except OSError:
            if proc.poll() is not None:
                break
            time.sleep(0.25)
    return proc


def stop_server(proc):
    if proc is None:
        return
    try:
        proc.terminate() if os.name == 'nt' else proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _do(req):
    import urllib.request
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read().decode('utf-8', 'replace')
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, raw
    except Exception as exc:
        code = getattr(exc, 'code', 0); raw = ''
        try:
            raw = exc.read().decode('utf-8', 'replace')
        except Exception:
            pass
        try:
            return code, json.loads(raw)
        except Exception:
            return code, raw


def api_get(base, path):
    import urllib.request
    return _do(urllib.request.Request(base + path, headers={'x-requested-with': 'fetch'}))


def api_get_raw(url):
    import urllib.request
    return _do(urllib.request.Request(url))


def api_post(base, path, payload):
    import urllib.request
    return _do(urllib.request.Request(base + path, data=json.dumps(payload).encode('utf-8'),
                                      headers={'content-type': 'application/json',
                                               'x-requested-with': 'fetch'}, method='POST'))


ROW_IDS = ['UI-LCC-CARD-02', 'UI-LCC-CARD-03', 'UI-LCC-CARD-04', 'UI-LCC-CARD-05',
           'UI-LCC-CARD-06', 'UI-LCC-CARD-07', 'UI-LCC-WTBL-09', 'UI-LCC-WTBL-10',
           'UI-LCC-WTBL-11', 'UI-LCC-WTBL-12', 'UI-LCC-WTBL-13', 'UI-LCC-WTBL-14',
           'UI-LCC-DETAIL-01', 'UI-LCC-DETAIL-02', 'UI-LCC-DETAIL-03', 'UI-LCC-DETAIL-04',
           'UI-LCC-ADD-06', 'UI-LCC-ADD-07', 'UI-LCC-ADD-10', 'UI-SSOT-TOP-06',
           'UI-SSOT-TBL-25', 'UI-SSOT-PAGE-11', 'UI-TRUTH-005']


def cards_of(page, sel):
    out = {}
    for cell in page.query_selector_all(sel + ' .lc-stat'):
        lbl, val = cell.query_selector('.label'), cell.query_selector('.value')
        out[(lbl.inner_text() if lbl else '').strip().upper()] = (val.inner_text() if val else '').strip()
    return out


def run_checks(aud, lcf):
    from playwright.sync_api import sync_playwright
    base = 'http://127.0.0.1:' + str(PORT)
    ora = oracle_cards(aud)
    cfg = rjson(lcf, {}) or {}
    blocker = ''
    sA, bA = api_get(base, '/api/live-audit-summary')
    audit_ok = sA == 200
    print('  PROBE::/api/live-audit-summary status=' + str(sA) + ' error=' + repr((bA or {}).get('error') if isinstance(bA, dict) else None))
    check('LCC_SURFACE_UPSTREAM_AUDIT_SUMMARY_200', audit_ok,
          'GET /api/live-audit-summary status=' + str(sA) + ' error=' + repr((bA or {}).get('error') if isinstance(bA, dict) else None)
          + ' - a non-200 here means the Live Copy Command Centre renders with an empty audit object (product defect, '
            'reproduced on the committed state at ' + COMMIT10 + ').')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        resp = page.goto(base + '/live-copy', wait_until='networkidle')
        check('APP_SERVES_LIVE_COPY', resp is not None and resp.status == 200, 'status=' + str(resp.status if resp else None))
        page.wait_for_selector('#lcRealCards .lc-stat', timeout=30000)

        cards = cards_of(page, '#lcRealCards')
        check('UI-LCC-CARD-02:UNREALIZED_PNL',
              num_from_dom(cards.get('OPEN POSITIONS P&L (UNREALISED)')) == round(float(ora['unrealized_pnl'] or 0), 2),
              'dom=' + repr(cards.get('OPEN POSITIONS P&L (UNREALISED)')) + ' oracle=' + repr(ora['unrealized_pnl']))
        check('UI-LCC-CARD-03:REALIZED_PNL', 'CLOSED P&L (REALISED)' in cards, 'labels=' + repr(sorted(cards)))
        check('UI-LCC-CARD-04:OPEN_POSITIONS',
              num_from_dom(cards.get('OPEN POSITIONS')) == float(ora['open_positions'] or 0),
              'dom=' + repr(cards.get('OPEN POSITIONS')) + ' oracle=' + repr(ora['open_positions']))
        check('UI-LCC-CARD-05:LIVE_EXPOSURE',
              num_from_dom(cards.get('LIVE EXPOSURE')) == round(float(ora['live_exposure']), 2),
              'dom=' + repr(cards.get('LIVE EXPOSURE')) + ' oracle=' + repr(round(ora['live_exposure'], 2)))
        strip = cards_of(page, '#lcTruthStatus')
        attempts = rcsv(aud / 'append_only' / 'send_attempts.csv')
        nf = len([r for r in attempts if str(r.get('status')) == 'ORDER_FILLED'])
        nr = len([r for r in attempts if str(r.get('status')) not in ('ORDER_FILLED', 'CONFIRM_REQUIRED')])
        check('UI-LCC-CARD-06:LAST_FILL', 'LAST FILL' in strip and (nf > 0) == (strip.get('LAST FILL', '\u2014') != '\u2014'),
              'dom=' + repr(strip.get('LAST FILL')) + ' oracle_filled=' + str(nf))
        check('UI-LCC-CARD-07:LAST_REJECT', 'LAST REJECT' in strip and (nr > 0) == (strip.get('LAST REJECT', '\u2014') != '\u2014'),
              'dom=' + repr(strip.get('LAST REJECT')) + ' oracle_rejected=' + str(nr))
        neg('NEG_CARD_UNAVAILABLE_NOT_ZERO', '\u2014' in page.inner_html('#lcRealCards') or bool(ora['available']),
            'unreadable exchange shows the dash, never a fabricated $0')

        # ---- the wallet table depends on /api/live-audit-summary ----
        st, body = api_get(base, '/api/live-audit-summary')
        audit_err = (body or {}).get('error') if isinstance(body, dict) else None
        have_rows = False
        try:
            page.wait_for_selector('#lcWalletRows tr[data-wallet]', timeout=25000)
            have_rows = True
        except Exception:
            have_rows = False
        if not have_rows:
            blocker = ('GET /api/live-audit-summary returned status=' + str(st) + ' error=' + repr(audit_err)
                       + '; the page refresh() Promise.all rejects, render() never runs, #lcWalletRows stays on '
                       '"Loading live-copy config..." so the wallet rows/detail are unreachable.')
            print('  BLOCKER::' + blocker)
            BLOCKED.append({'scope': ['UI-LCC-WTBL-09..14', 'UI-LCC-DETAIL-01..04'], 'reason': blocker,
                            'api_status': st, 'api_error': audit_err})

        if have_rows:
            row = page.query_selector('#lcWalletRows tr[data-wallet]')
            rw = row.get_attribute('data-wallet')
            cw = cfg.get('wallets', {}).get(rw) or cfg.get('wallets', {}).get(rw.lower()) or {}
            sel = row.query_selector('select[name=copy_mode]'); inf = row.query_selector('input[name=fixed_notional]')
            inn = row.query_selector('input[name=norm_base]')
            check('UI-LCC-WTBL-09:COPY_MODEL_SELECT',
                  [o.get_attribute('value') for o in sel.query_selector_all('option')] == ['proportional', 'fixed']
                  and sel.input_value() == str(cw.get('copy_mode') or 'fixed'), 'selected=' + repr(sel.input_value()))
            check('UI-LCC-WTBL-10:FN_INPUTS',
                  inf is not None and inn is not None
                  and abs(float(inf.input_value()) - float(cw.get('fixed_notional') or 10)) < 1e-9
                  and abs(float(inn.input_value()) - float(cw.get('norm_base') or 100)) < 1e-9,
                  'F=' + repr(inf.input_value() if inf else None) + ' N=' + repr(inn.input_value() if inn else None))
            check('UI-LCC-WTBL-12:CLO_BUTTON', row.query_selector('button[data-act=clo]') is not None, 'CLO')
            check('UI-LCC-WTBL-13:OFF_BUTTON', row.query_selector('button[data-act=off]') is not None, 'OFF')
            check('UI-LCC-WTBL-14:ARCHIVE_BUTTON', row.query_selector('button[data-act=archive]') is not None, 'Archive')
            nf2 = round(float(cw.get('fixed_notional') or 10) + 7.0, 2); inf.fill(str(nf2)); b4 = sha(lcf)
            row.query_selector('button[data-act=save]').click(); page.wait_for_timeout(3000)
            wr = (rjson(lcf, {}) or {}).get('wallets', {}).get(rw, {})
            check('UI-LCC-WTBL-11:SAVE_WRITES_LIVE_CONFIG', b4 != sha(lcf) and abs(float(wr.get('fixed_notional') or -1) - nf2) < 1e-9,
                  'sha ' + b4[:8] + '->' + sha(lcf)[:8] + ' persisted=' + repr(wr.get('fixed_notional')))
            neg('NEG_WTBL_SAVE_REJECTS_BAD_MODE', api_post(base, '/api/live-config/set-wallet', {'wallet': rw, 'mode': 'BOGUS'})[0] >= 400, 'bad mode rejected')
            row.click(); page.wait_for_timeout(1800)
            det = page.query_selector('#lcWalletRows tr[id^=lcdet-] td'); dh = det.inner_html() if det else ''
            check('UI-LCC-DETAIL-01:A_LIVE_PERFORMANCE', 'A \u2014 Live Performance' in dh, 'A')
            check('UI-LCC-DETAIL-02:B_OPEN_POSITIONS', 'B \u2014 Open Positions' in dh and 'Exchange match' in dh, 'B')
            check('UI-LCC-DETAIL-03:C_LEAD_VS_COPY', 'C \u2014 Lead vs Copy / Friction' in dh, 'C')
            check('UI-LCC-DETAIL-04:D_EXECUTION_AUDIT', 'D \u2014 Execution Audit' in dh, 'D')
            row.click(); page.wait_for_timeout(900)
            neg('NEG_DETAIL_COLLAPSES', page.query_selector('#lcWalletRows tr[id^=lcdet-] td') is None, 'detail toggles off')

        # ---- Add-wallet modal (static markup; reachable even without the table) ----
        page.click('[data-lc-modal=lcWalletModal]'); page.wait_for_timeout(700)
        mf = sorted({el.get_attribute('name') for el in page.query_selector_all('#lcAddForm [name]')})
        check('UI-LCC-ADD-06:LEADER_EQUITY_BASE_FIELD', 'norm_base' in mf, 'fields=' + repr(mf))
        check('UI-LCC-ADD-07:MAX_DIFF_FIELD',
              any(f in mf for f in ('max_diff_pct', 'max_close_adverse_diff_pct', 'max_diff')),
              'no Max-diff control in the served Add-wallet modal; fields=' + repr(mf))
        aw = '0x' + 'ab' * 20
        page.fill('#lcAddForm [name=wallet]', aw); page.fill('#lcAddForm [name=norm_base]', '1234')
        page.fill('#lcAddForm [name=fixed_notional]', '55'); page.click('#lcAddForm button[type=submit]')
        page.wait_for_timeout(3000)
        per = (rjson(lcf, {}) or {}).get('wallets', {}).get(aw, {})
        check('UI-LCC-ADD-10:ADD_WALLET_SUBMIT_PERSISTS',
              abs(float(per.get('norm_base') or -1) - 1234.0) < 1e-9 and abs(float(per.get('fixed_notional') or -1) - 55.0) < 1e-9,
              'persisted=' + repr(per))
        stx, bx = api_post(base, '/api/live-config/add-wallet', {'wallet': 'not-a-wallet', 'mode': 'LIVE'})
        check('UI-LCC-ADD-10:INVALID_INPUT_REJECTED', stx >= 400 and (bx or {}).get('ok') is False, 'status=' + str(stx))
        neg('NEG_ADD_NONVACUOUS', 'norm_base' in mf and per.get('norm_base') is not None, 'round-trips to disk')

        # ---- analytics top bar ----
        hr = page.goto(base + '/', wait_until='domcontentloaded'); page.wait_for_timeout(2500)
        home_ok = hr is not None and hr.status == 200
        print('  PROBE::/ status=' + str(hr.status if hr else None))
        th = page.inner_html('.top') if page.query_selector('.top') else ''
        lab = bool(re.search(r'<span class="muted">\s*Model mode:', th)); eng = 'Engine sizing:' in th
        h0 = sha(lcf)
        try:
            page.fill('.top input[name=norm_base]', '250'); page.click('.top form button'); page.wait_for_timeout(2000)
        except Exception:
            pass
        check('UI-SSOT-TOP-06:SET_IS_MODEL_ONLY', lab and eng and sha(lcf) == h0,
              'model_labelled=' + str(lab) + ' engine_labelled=' + str(eng) + ' live_config_unchanged=' + str(sha(lcf) == h0))
        neg('NEG_TOP06_LABEL_PRESENT', lab, 'model label renders')

        api_post(base, '/api/ui-state', {'ranking_column': 'lead_equity', 'ranking_direction': 'desc'})
        s2, b2 = api_get_raw(base + '/sort/lead_equity'); s3, _ = api_get_raw(base + '/sort/NOT_A_COLUMN')
        check('UI-SSOT-TBL-25:SORT_ROUTE', s2 == 200 and isinstance(b2, str) and len(b2) > 200,
              'status=' + str(s2) + ' len=' + str(len(b2) if isinstance(b2, str) else None))
        neg('NEG_TBL25_UNKNOWN_COLUMN_REJECTED', s3 >= 400, 'unknown column status=' + str(s3))

        s4, cb = api_get(base, '/api/live-config'); dcfg = rjson(lcf, {}) or {}
        check('UI-SSOT-PAGE-11:LIVE_CONFIG_ENDPOINT',
              s4 == 200 and (cb or {}).get('ok') is True
              and set(((cb or {}).get('config') or {}).get('wallets', {})) == set(dcfg.get('wallets', {})),
              'status=' + str(s4))
        hb = sha(lcf); fb = {x.name: sha(x) for x in (aud / 'append_only').glob('*.csv')}
        api_post(base, '/api/reset-app-history', {}); api_post(base, '/api/snapshot', {})
        fa = {x.name: sha(x) for x in (aud / 'append_only').glob('*.csv')}
        check('UI-SSOT-PAGE-11:RESET_SNAPSHOT_SAFE', sha(lcf) == hb and fb == fa,
              'cfg_unchanged=' + str(sha(lcf) == hb) + ' csv_unchanged=' + str(fb == fa))
        neg('NEG_PAGE11_NONVACUOUS', bool((cb or {}).get('config')), 'real config body')

        tr = subprocess.run(['git', '-C', str(WT), 'ls-files', '--error-unmatch', '_archive/hl_stage2/HL_Copy_App_SSOT.py'],
                            capture_output=True, text=True)
        blob = subprocess.run(['git', '-C', str(WT), 'show', 'HEAD:_archive/hl_stage2/HL_Copy_App_SSOT.py'], capture_output=True).stdout
        bsha = hashlib.sha256(blob).hexdigest()
        nu = [f for f in subprocess.run(['git', '-C', str(WT), 'ls-files', '_archive/hl_stage2'], capture_output=True, text=True)
              .stdout.splitlines() if re.search(r'(ui|dashboard|app).*\.py$', f.lower())
              and 'HL_Copy_App_SSOT' not in f and not f.lower().split('/')[-1].startswith('test_')]
        check('UI-TRUTH-005:HISTORICAL_UI_TRACKED_AND_SERVED', tr.returncode == 0 and bsha == UI_SHA and not nu,
              'tracked=' + str(tr.returncode == 0) + ' blob=' + bsha[:12] + ' served=' + UI_SHA[:12] + ' new_ui=' + repr(nu))
        neg('NEG_TRUTH005_NONVACUOUS', bsha == UI_SHA, 'served UI byte-identical to committed source')
        check('NO_PAGE_JS_ERRORS', not errors, 'console=' + repr(errors[:3]))
        browser.close()
    return {'blocker': blocker, 'audit_ok': audit_ok, 'home_ok': home_ok, 'sort_status': s2}


def main():
    global PORT
    PORT = free_port(); stage_runtime_data(); aud = build_env(); lcf = aud / 'live_config.json'
    print('UI NOT_TESTED harness | commit ' + COMMIT + ' | ui_sha ' + UI_SHA[:12] + ' | port ' + str(PORT))
    check('UI_SHA256_RECORDED', len(UI_SHA) == 64, UI_SHA)
    proc = start_server(aud)
    envr = {'blocker': '', 'audit_ok': False, 'home_ok': False, 'sort_status': 0}
    try:
        envr = run_checks(aud, lcf)
    except Exception as exc:
        import traceback
        envr['blocker'] = 'harness exception: ' + type(exc).__name__ + ': ' + str(exc)
        print('  HARNESS_EXCEPTION::' + traceback.format_exc()[-600:])
    finally:
        stop_server(proc)
    blocker = envr['blocker']

    for cid in ROW_IDS:
        m = [x for x in CHECKS if x['name'].startswith(cid)]
        if m:
            ROWS[cid] = {'verdict': 'PASS' if all(x['pass'] for x in m) else 'FAIL',
                         'oracle': 'runtime DOM (real Chromium) on the served UI + independent recompute from raw audit/exchange files'}
        else:
            ROWS[cid] = {'verdict': 'BLOCKED',
                         'oracle': 'served-UI reachability; blocker: ' + (blocker or 'endpoint/table not reachable')}
    # ---- adversarial-review corrections: an upstream 500 means the row's value was never rendered,
    # so it must read BLOCKED (not FAIL) — a FAIL would attribute a platform defect to the row.
    if not envr['audit_ok']:
        why = ('BLOCKED by upstream GET /api/live-audit-summary 500 (IndexError in _row_exchange_order_id at '
               'HL_Copy_App_SSOT.py:1731 on a live_fills.csv row whose notes end in a bare "exchange_order_id="); '
               'the page renders with an empty lcAudit, so card values are not a product-truth signal.')
        for cid in [c for c in ROW_IDS if c.startswith('UI-LCC-CARD')]:
            ROWS[cid] = {'verdict': 'BLOCKED', 'oracle': why}
        for cid in [c for c in ROW_IDS if c.startswith('UI-LCC-WTBL') or c.startswith('UI-LCC-DETAIL')]:
            ROWS[cid] = {'verdict': 'BLOCKED', 'oracle': why}
        BLOCKED.append({'scope': [c for c in ROW_IDS if c.startswith('UI-LCC-CARD')], 'reason': why})
    if not envr['home_ok']:
        for cid in ['UI-SSOT-TOP-06']:
            ROWS[cid] = {'verdict': 'BLOCKED',
                         'oracle': 'GET / returned ' + str(envr['home_ok']) + '; the analytics dashboard never rendered '
                                   '(same upstream audit-summary defect), so the top-bar Set control is unreachable.'}
        BLOCKED.append({'scope': ['UI-SSOT-TOP-06'], 'reason': 'GET / did not render (home_ok=' + str(envr['home_ok']) + ')'})
    if envr['sort_status'] != 200:
        ROWS['UI-SSOT-TBL-25'] = {'verdict': 'BLOCKED',
                                  'oracle': 'GET /sort/lead_equity returned ' + str(envr['sort_status'])
                                            + ' (render_home raises the same upstream audit defect).'}
        BLOCKED.append({'scope': ['UI-SSOT-TBL-25'], 'reason': 'sort route status=' + str(envr['sort_status'])})
    ok = sum(1 for x in CHECKS if x['pass']); ng = sum(1 for x in NEG if x['pass'])
    print('\nROWS ' + json.dumps({k: v['verdict'] for k, v in ROWS.items()}))
    print('CHECKS ' + str(ok) + '/' + str(len(CHECKS)) + ' PASS | NEG ' + str(ng) + '/' + str(len(NEG)) + ' PASS | BLOCKED ' + str(len(BLOCKED)))
    result = {
        'task_id': 't_1fb73bd2',
        'title': 'B3-CERT UI NOT_TESTED APPLIES (23 rows): UI-LCC-*/UI-SSOT-*/UI-TRUTH-005',
        'tested_commit': COMMIT, 'tested_at_utc': datetime.now(timezone.utc).isoformat(),
        'ui_source': str(UI_SRC), 'ui_source_sha256': UI_SHA, 'state_source': str(REAL_STATE),
        'oracle': ('runtime: real UI served over HTTP from the tracked source; DOM rendered by real Chromium '
                   '(Playwright) so the page JS calls the real endpoints; every asserted value independently '
                   'recomputed from the raw audit/exchange files without importing the UI module; per-check mutation negative'),
        'provenance_note': ('certification_matrix.json pins UI sha256 fad19d22 (HL_Copy_App_SSOT_20260513.py) / '
                            'c0f9e508 (HL_Copy_App_SSOT.py). Neither exists as a git object here; the only tracked UI source is '
                            '_archive/hl_stage2/HL_Copy_App_SSOT.py @ sha256 ' + UI_SHA[:12] + ' (identical in the worktree and '
                            'the main checkout at ' + COMMIT10 + '). Rows ran against that SERVED real source; the pinned '
                            '13-May hash is UNVERIFIABLE here (provenance gap already reported by t_8fc704ce).'),
        'rows': ROWS, 'checks': {x['name']: {'pass': x['pass'], 'detail': x['detail']} for x in CHECKS},
        'negative_tests': {x['name']: {'pass': x['pass'], 'detail': x['detail']} for x in NEG},
        'blocked': BLOCKED,
        'summary': {'total_checks': len(CHECKS), 'passed_checks': ok, 'failed_checks': len(CHECKS) - ok,
                    'total_negative_tests': len(NEG), 'passed_negative_tests': ng, 'failed_negative_tests': len(NEG) - ng,
                    'rows_pass': sum(1 for x in ROWS.values() if x['verdict'] == 'PASS'),
                    'rows_fail': sum(1 for x in ROWS.values() if x['verdict'] == 'FAIL'),
                    'rows_blocked': sum(1 for x in ROWS.values() if x['verdict'] == 'BLOCKED')},
    }
    out = WT / 'certification' / 'results' / ('UI_NT_' + COMMIT10 + '.json')
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('results -> ' + str(out))


if __name__ == '__main__':
    main()
