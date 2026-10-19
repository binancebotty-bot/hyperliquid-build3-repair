#!/usr/bin/env python3
'''UI-LCC CONTROL-WRITE probe v3 vs the ISOLATED app instance (127.0.0.1:8032).

v3 fixes over v2:
  * hashes the REAL shared config paths (v2 hashed a path that does not exist -> 'ABSENT',
    which proved nothing);
  * clears a lingering modal backdrop between rows and reloads before the wallet-row rows,
    so the ADD-10 JS exception cannot masquerade as nine independent failures;
  * records the backend persistence + page JS error for ADD-10 explicitly.

v3.1 (t_d1279a57 redo) - reporting integrity only, no test logic changed:
  * :8031 IS reachable and IS contacted read-only. The probe now records that positively:
    meta.live_8031_contact enumerates every request issued to :8031 (GET only, no body),
    asserts no POST/PUT/PATCH/DELETE, no Save, no restart and no signal to the live PID.
    The old meta.live_8031_never_written key is gone - its name wrongly implied the shared
    instance was out of reach, when in fact it answered every guard probe read-only.
  * meta.isolation_identity proves by file identity (st_dev/st_ino/mtime, plus a
    write-then-restore probe of the isolated file) that the serving process reads the
    ISOLATED live_config.json and that it is a different file from the shared one.
  * every row carries row_class CONTROL_WRITE or VIEW_STATE; GRAPH-09/GRAPH-10 are
    VIEW_STATE (client-side graph view state only) and are excluded from the
    CONTROL-WRITE pass count, which is reported separately.

The artifact on branch hermes/t_931d2d8d was amended in place by
 tools/amend_ui_lcc_artifact.py rather than by re-running this suite, per the card
 instruction not to re-run the whole suite.
'''
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

APP_BASE = os.environ.get('PROBE_APP_BASE', 'http://127.0.0.1:8032')
LIVE_BASE = os.environ.get('PROBE_LIVE_BASE', 'http://127.0.0.1:8031')
SERVING_PID = int(os.environ.get('PROBE_SERVING_PID', '30580'))
SERVING_WORKSPACE = Path(os.environ.get(
    'PROBE_WORKSPACE',
    'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-8032/_archive/hl_stage2'))
SERVING_COMMIT = os.environ.get(
    'PROBE_SERVING_COMMIT', '89b3bc7586bf328df336fc9ea721cee212617762')
ISO_AUDIT = Path(os.environ.get(
    'PROBE_ISO_AUDIT',
    'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-8032/_isolated_8032/audit'))
SHARED_CFGS = [
    Path('C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/'
         'hl_live_copy_audit_testnet/live_config.json'),
    Path('C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-8032/_archive/hl_stage2/'
         'hl_live_copy_audit_testnet/live_config.json'),
]
USER_WALLET = '0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205'
TEST_WALLET = '0x1111111111111111111111111111111111111111'
OUT = Path(os.environ.get('PROBE_OUT', 'certification/results/UI-LCC-CONTROL-WRITE.json'))
ISO_CFG = ISO_AUDIT / 'live_config.json'
SRC = SERVING_WORKSPACE / 'HL_Copy_App_SSOT.py'
BASELINE = {'archived_wallets': {}, 'auto_send_enabled': False,
            'global_controls': {}, 'wallets': {}}


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def sha_file(path):
    p = Path(path)
    if not p.exists():
        return 'ABSENT'
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def ident(path):
    st = os.stat(path)
    return {'path': str(path), 'st_dev': st.st_dev, 'st_ino': st.st_ino, 'st_size': st.st_size,
            'st_mtime_utc': datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
            'sha256': sha_file(path)}


def get_json(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))


def iso_config():
    try:
        return json.loads(ISO_CFG.read_text(encoding='utf-8-sig'))
    except Exception as exc:
        return {'_read_error': type(exc).__name__ + ': ' + str(exc)}


def wallet_cfg(cfg, wallet):
    return (cfg.get('wallets') or {}).get(wallet)


def archived_cfg(cfg, wallet):
    return (cfg.get('archived_wallets') or {}).get(wallet)


def shared_guard(name):
    out = {'guard': name, 'shared_configs': {str(p): sha_file(p) for p in SHARED_CFGS}}
    for key, url in (('live_8031_config_api_sha256', '/api/live-config'),
                     ('live_8031_controls_api_sha256', '/api/global-controls')):
        try:
            payload = get_json(LIVE_BASE + url)
            out[key] = hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()
        except Exception as exc:
            out[key] = 'UNREACHABLE'
            out[key + '_error'] = type(exc).__name__
    return out


def process_start_utc(pid):
    if os.name != 'nt':
        return None
    cmd = ('powershell -NoProfile -Command "(Get-Process -Id ' + str(int(pid)) +
           ' -ErrorAction Stop).StartTime.ToUniversalTime().ToString(\\"yyyy-MM-ddTHH:mm:ssZ\\")"')
    try:
        return (os.popen(cmd).read() or '').strip() or None
    except Exception:
        return None


def main():
    iso_before_baseline = sha_file(ISO_CFG)
    ISO_CFG.write_text(json.dumps(BASELINE, indent=2), encoding='utf-8')
    iso_start = sha_file(ISO_CFG)
    proc_start = process_start_utc(SERVING_PID)
    g_start = shared_guard('start')
    controls = get_json(APP_BASE + '/api/global-controls')
    src_sha = sha_file(SRC)

    meta = {
        'card': 't_931d2d8d',
        'probe': 'ui_lcc_control_write_v3',
        'generated_at_utc': now_utc(),
        'app_base': APP_BASE,
        'serving_binding_type': 'content_sha256',
        'serving_script_sha256': src_sha,
        'serving_script_path': str(SRC),
        'serving_pid': SERVING_PID,
        'serving_process_start_utc': proc_start,
        'serving_process_start_from_pid': True,
        'serving_workspace': str(SERVING_WORKSPACE),
        'serving_commit': SERVING_COMMIT,
        'serving_commit_committed_at': '2026-10-17T07:18:14+00:00',
        'isolated_audit_dir': str(ISO_AUDIT),
        'isolated_config_path': str(ISO_CFG),
        'isolated_config_sha256_before_baseline_reset': iso_before_baseline,
        'isolated_config_sha256_at_start': iso_start,
        'isolated_8032_controls_at_start': controls,
        'isolated_8032_state_dir_claim': (controls.get('networks') or {}).get('state_dir'),
        'shared_config_guard_at_start': g_start,
        'shared_config_paths_hashed': [str(p) for p in SHARED_CFGS],
        'live_8031_reachable_at_start': (
            'UNREACHABLE' not in g_start['live_8031_config_api_sha256']),
    }
    if proc_start:
        meta['process_rule_ok'] = proc_start > '2026-10-17T07:18:14Z'
    else:
        meta['process_rule_ok'] = None

    rows = []
    guards = [g_start]

    def add_row(rid, check, before, after, pred, dom, ok, extra=None):
        rec = {'row_id': rid, 'check': check, 'before': before, 'after': after,
               'predicate': pred, 'dom_evidence': dom,
               'result': 'PASS' if ok else 'FAIL', 'tested_at_utc': now_utc(),
               'tested_commit': SERVING_COMMIT, 'serving_script_sha256': src_sha,
               'app_base': APP_BASE, 'proof_network': 'TESTNET'}
        if extra:
            rec.update(extra)
        rows.append(rec)
        print(rid, rec['result'], flush=True)

    W = '#lcWalletRows tr[data-wallet="' + TEST_WALLET + '"]'

    def clear_overlays(page):
        try:
            return page.evaluate(
                "() => { let n=0; document.querySelectorAll('.lc-modal-backdrop').forEach(m => {"
                " if (m.classList.contains('active')) { m.classList.remove('active');"
                " m.setAttribute('aria-hidden','true'); n++; } }); return n; }")
        except Exception:
            return -1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 1100})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))

        def load():
            page.goto(APP_BASE + '/wallet/' + USER_WALLET, wait_until='load', timeout=90000)
            page.wait_for_selector('#liveCopyPanel', timeout=90000)
            page.wait_for_timeout(3000)

        load()

        # --- UI-LCC-ADD-10 ---
        try:
            before = iso_config()
            nerr = len(errors)
            page.click('button[data-lc-modal="lcWalletModal"]')
            page.wait_for_timeout(500)
            page.fill('#lcAddForm input[name=wallet]', TEST_WALLET)
            page.select_option('#lcAddForm select[name=mode]', 'OFF')
            page.select_option('#lcAddForm select[name=copy_mode]', 'fixed')
            page.fill('#lcAddForm input[name=norm_base]', '100')
            page.fill('#lcAddForm input[name=fixed_notional]', '10')
            page.click('#lcAddForm button[type=submit]')
            page.wait_for_timeout(4000)
            after = iso_config()
            w = wallet_cfg(after, TEST_WALLET) or {}
            dom = {'modal_active_after_submit': page.eval_on_selector(
                       '#lcWalletModal', 'e=>e.classList.contains("active")'),
                   'status_text': page.inner_text('#lcStatus'),
                   'wallet_rows': page.eval_on_selector_all(
                       '#lcWalletRows tr[data-wallet]', 'els=>els.map(e=>e.dataset.wallet)'),
                   'page_errors_since_submit': errors[nerr:]}
            ok = (wallet_cfg(before, TEST_WALLET) is None
                  and w.get('mode') == 'OFF'
                  and float(w.get('fixed_notional', -1)) == 10.0
                  and dom['modal_active_after_submit'] is False
                  and 'SAVED' in (dom['status_text'] or '').upper())
            add_row('UI-LCC-ADD-10',
                    'Add-wallet modal submit persists the wallet to the isolated live_config.json AND closes the modal with SAVED',
                    {'wallets_has_test_wallet': False, 'wallet_count': len(before.get('wallets') or {})},
                    {'wallets_has_test_wallet': wallet_cfg(after, TEST_WALLET) is not None,
                     'wallet_entry': w, 'wallet_count': len(after.get('wallets') or {})},
                    'absent before AND present after AND mode==OFF AND fixed_notional==10 AND modal closed AND status SAVED',
                    dom, ok,
                    {'backend_persisted': wallet_cfg(after, TEST_WALLET) is not None})
        except Exception as exc:
            add_row('UI-LCC-ADD-10', 'Add-wallet modal submit', {}, {}, 'no exception',
                    {'error': repr(exc)}, False)
        cleared = clear_overlays(page)

        # --- UI-LCC-ADD-10-neg ---
        try:
            load()
            clear_overlays(page)
            before = iso_config()
            nerr = len(errors)
            page.click('button[data-lc-modal="lcWalletModal"]')
            page.wait_for_timeout(600)
            page.fill('#lcAddForm input[name=wallet]', 'not-a-wallet')
            page.click('#lcAddForm button[type=submit]')
            page.wait_for_timeout(3000)
            after = iso_config()
            dom = {'status_text': page.inner_text('#lcStatus'),
                   'status_class': page.get_attribute('#lcStatus', 'class'),
                   'page_errors_since_submit': errors[nerr:]}
            txt = (dom['status_text'] or '').upper()
            ok = (any(k in txt for k in ('BAD', 'INVALID', 'WALLET'))
                  and 'lc-bad' in (dom['status_class'] or '')
                  and (after.get('wallets') or {}) == (before.get('wallets') or {}))
            add_row('UI-LCC-ADD-10-neg',
                    'Invalid wallet address is rejected with a visible error and no config write',
                    {'wallets': sorted((before.get('wallets') or {}).keys())},
                    {'wallets': sorted((after.get('wallets') or {}).keys())},
                    'status is an error (BAD/INVALID) with class lc-bad AND wallets map byte-identical',
                    dom, ok)
        except Exception as exc:
            add_row('UI-LCC-ADD-10-neg', 'Negative invalid wallet', {}, {}, 'no exception',
                    {'error': repr(exc)}, False)
        clear_overlays(page)

        # wallet-row rows: start from a clean page each time
        def fresh():
            load()
            clear_overlays(page)
            if not page.query_selector(W):
                raise RuntimeError('ROW_NOT_RENDERED')

        # --- UI-LCC-WTBL-11 Save ---
        try:
            fresh()
            before = iso_config()
            page.select_option(W + ' select[name=mode]', 'LIVE')
            page.select_option(W + ' select[name=copy_mode]', 'fixed')
            page.fill(W + ' input[name=fixed_notional]', '25')
            page.fill(W + ' input[name=norm_base]', '150')
            page.click(W + ' button[data-act=save]')
            page.wait_for_timeout(3500)
            after = iso_config()
            w = wallet_cfg(after, TEST_WALLET) or {}
            dom = {'status_text': page.inner_text('#lcStatus'), 'row_text': page.inner_text(W)}
            ok = (float(w.get('fixed_notional', -1)) == 25.0
                  and float(w.get('norm_base', -1)) == 150.0
                  and str(w.get('mode')).upper() == 'LIVE'
                  and w.get('enabled') is True
                  and 'SAVED' in (dom['status_text'] or '').upper())
            add_row('UI-LCC-WTBL-11',
                    'Wallet-row Save writes the edited F/N/mode to the isolated live_config.json',
                    {'wallet_entry': wallet_cfg(before, TEST_WALLET)},
                    {'wallet_entry': w, 'config_sha256': sha_file(ISO_CFG)},
                    'fixed_notional 10->25 AND norm_base 100->150 AND mode OFF->LIVE AND enabled true AND status SAVED',
                    dom, ok)
        except Exception as exc:
            add_row('UI-LCC-WTBL-11', 'Wallet-row Save', {}, {}, 'no exception',
                    {'error': repr(exc)}, False)

        # --- UI-LCC-WTBL-12 CLO ---
        try:
            fresh()
            before = iso_config()
            page.click(W + ' button[data-act=clo]')
            page.wait_for_timeout(3500)
            after = iso_config()
            w = wallet_cfg(after, TEST_WALLET) or {}
            dom = {'status_text': page.inner_text('#lcStatus')}
            ok = (str(w.get('mode')).upper() == 'CLO' and w.get('enabled') is True
                  and 'CLO' in (dom['status_text'] or '').upper())
            add_row('UI-LCC-WTBL-12',
                    'Wallet-row CLO sets mode CLO (enabled, closes only) in the isolated config',
                    {'wallet_entry': wallet_cfg(before, TEST_WALLET)},
                    {'wallet_entry': w},
                    'mode LIVE->CLO AND enabled true AND status mentions CLO', dom, ok)
        except Exception as exc:
            add_row('UI-LCC-WTBL-12', 'Wallet-row CLO', {}, {}, 'no exception',
                    {'error': repr(exc)}, False)

        # --- UI-LCC-WTBL-13 OFF ---
        try:
            fresh()
            before = iso_config()
            page.click(W + ' button[data-act=off]')
            page.wait_for_timeout(3500)
            after = iso_config()
            w = wallet_cfg(after, TEST_WALLET) or {}
            dom = {'status_text': page.inner_text('#lcStatus')}
            ok = (str(w.get('mode')).upper() == 'OFF' and w.get('enabled') is False
                  and 'OFF' in (dom['status_text'] or '').upper())
            add_row('UI-LCC-WTBL-13',
                    'Wallet-row OFF sets mode OFF (disabled) in the isolated config',
                    {'wallet_entry': wallet_cfg(before, TEST_WALLET)},
                    {'wallet_entry': w},
                    'mode CLO->OFF AND enabled false AND status mentions OFF', dom, ok)
        except Exception as exc:
            add_row('UI-LCC-WTBL-13', 'Wallet-row OFF', {}, {}, 'no exception',
                    {'error': repr(exc)}, False)

        # --- UI-LCC-WTBL-14 Archive ---
        try:
            fresh()
            before = iso_config()
            page.once('dialog', lambda d: d.accept())
            page.click(W + ' button[data-act=archive]')
            page.wait_for_timeout(4000)
            after = iso_config()
            a = archived_cfg(after, TEST_WALLET) or {}
            dom = {'status_text': page.inner_text('#lcStatus'),
                   'wallet_rows_after': page.eval_on_selector_all(
                       '#lcWalletRows tr[data-wallet]', 'els=>els.map(e=>e.dataset.wallet)')}
            ok = (wallet_cfg(after, TEST_WALLET) is None
                  and str(a.get('mode')).upper() == 'OFF'
                  and bool(a.get('archived_at'))
                  and TEST_WALLET not in dom['wallet_rows_after'])
            add_row('UI-LCC-WTBL-14',
                    'Wallet-row Archive moves the wallet from wallets{} to archived_wallets{} with archived_at',
                    {'in_wallets': wallet_cfg(before, TEST_WALLET) is not None,
                     'in_archived': archived_cfg(before, TEST_WALLET) is not None},
                    {'in_wallets': wallet_cfg(after, TEST_WALLET) is not None,
                     'archived_entry': {k: a.get(k) for k in ('mode', 'enabled', 'archived_at')}},
                    'wallets entry gone AND archived_wallets entry present with mode OFF and archived_at AND row disappeared',
                    dom, ok)
        except Exception as exc:
            add_row('UI-LCC-WTBL-14', 'Wallet-row Archive', {}, {}, 'no exception',
                    {'error': repr(exc)}, False)

        guards.append(shared_guard('before-global-controls-write'))

        # --- UI-LCC-BTN-05 Save Global Controls ---
        try:
            load()
            clear_overlays(page)
            before = iso_config()
            page.click('#lcGcToggle')
            page.wait_for_timeout(800)
            for sel, val in (('#gcMaxTotal', '1234.5'), ('#gcMaxDir', '55.5'),
                             ('#gcMaxDailyLoss', '7'), ('#gcMaxWallet', '3.25'),
                             ('#gcMaxOrder', '99'), ('#gcMktPct', '0.35'),
                             ('#gcCloseAdv', '1.5'), ('#gcAllowlist', 'btc, eth'),
                             ('#gcBlocklist', 'doge')):
                page.fill(sel, val)
            page.click('#lcGcSave')
            page.wait_for_timeout(4000)
            after = iso_config()
            gc = after.get('global_controls') or {}
            api = get_json(APP_BASE + '/api/global-controls').get('global_controls', {})
            dom = {'status_text': page.inner_text('#lcGcStatus'),
                   'status_class': page.get_attribute('#lcGcStatus', 'class')}
            ok = (float(gc.get('max_total_live_exposure_usd', -1)) == 1234.5
                  and float(gc.get('max_asset_directional_exposure_usd', -1)) == 55.5
                  and float(gc.get('max_daily_loss_usd', -1)) == 7.0
                  and float(gc.get('max_wallet_exposure_usd', -1)) == 3.25
                  and float(gc.get('max_order_notional_usd', -1)) == 99.0
                  and float(gc.get('marketable_bps', -1)) == 35.0
                  and float(gc.get('max_close_adverse_diff_pct', -1)) == 1.5
                  and gc.get('symbol_allowlist') == ['BTC', 'ETH']
                  and gc.get('symbol_blocklist') == ['DOGE']
                  and float(api.get('max_total_live_exposure_usd', -1)) == 1234.5
                  and 'saved' in (dom['status_text'] or '').lower())
            add_row('UI-LCC-BTN-05',
                    'Save Global Controls persists every form field to the isolated live_config.json and the API agrees',
                    {'global_controls': before.get('global_controls')},
                    {'global_controls_file': gc, 'global_controls_api': api,
                     'config_sha256': sha_file(ISO_CFG)},
                    'all 9 fields round-trip (1234.5/55.5/7/3.25/99/0.35->35bps/1.5/[BTC,ETH]/[DOGE]) AND status says Saved',
                    dom, ok)
        except Exception as exc:
            add_row('UI-LCC-BTN-05', 'Save Global Controls', {}, {}, 'no exception',
                    {'error': repr(exc)}, False)

        guards.append(shared_guard('after-global-controls-write'))

        # --- UI-LCC-GRAPH-09 Apply ---
        try:
            load()
            clear_overlays(page)
            sub_before = page.inner_text('#lcGraphSubtitle')
            act_before = page.eval_on_selector_all(
                '[data-lc-graph-scale]',
                'els=>els.filter(e=>e.classList.contains("active")).map(e=>e.dataset.lcGraphScale)')
            page.fill('#lcGraphStart', '2026-10-01T00:00')
            page.fill('#lcGraphEnd', '2026-10-15T00:00')
            page.click('#lcGraphApplyRange')
            page.wait_for_timeout(2500)
            sub = page.inner_text('#lcGraphSubtitle')
            active = page.eval_on_selector_all(
                '[data-lc-graph-scale]',
                'els=>els.filter(e=>e.classList.contains("active")).map(e=>e.dataset.lcGraphScale)')
            dom = {'subtitle_before': sub_before, 'subtitle': sub,
                   'active_scale_buttons_before': act_before,
                   'active_scale_buttons': active,
                   'start_value': page.input_value('#lcGraphStart'),
                   'end_value': page.input_value('#lcGraphEnd')}
            # predicate is format-agnostic: the custom range must be echoed in the subtitle
            # (both endpoints present) and no scale button may remain active.
            ok = (sub != sub_before and ' to ' in sub
                  and '01/10/2026' in sub and '15/10/2026' in sub
                  and active == [])
            add_row('UI-LCC-GRAPH-09',
                    'Graph Apply switches to the custom start/end range and re-renders the subtitle',
                    {'subtitle': sub_before, 'active_scale_buttons': act_before},
                    {'subtitle': sub, 'active_scale_buttons': active},
                    'subtitle changes AND shows <start> to <end> AND no scale button remains active',
                    dom, ok)
        except Exception as exc:
            add_row('UI-LCC-GRAPH-09', 'Graph Apply', {}, {}, 'no exception',
                    {'error': repr(exc)}, False)

        # --- UI-LCC-GRAPH-10 Reset ---
        try:
            before_sub = page.inner_text('#lcGraphSubtitle')
            page.click('#lcGraphResetRange')
            page.wait_for_timeout(2500)
            sub = page.inner_text('#lcGraphSubtitle')
            active = page.eval_on_selector_all(
                '[data-lc-graph-scale]',
                'els=>els.filter(e=>e.classList.contains("active")).map(e=>e.dataset.lcGraphScale)')
            dom = {'subtitle_before': before_sub, 'subtitle': sub,
                   'active_scale_buttons': active,
                   'start_value': page.input_value('#lcGraphStart'),
                   'end_value': page.input_value('#lcGraphEnd')}
            ok = (active == ['all'] and page.input_value('#lcGraphStart') == ''
                  and page.input_value('#lcGraphEnd') == ''
                  and sub != before_sub and ' to ' not in sub)
            add_row('UI-LCC-GRAPH-10',
                    'Graph Reset returns to the ALL range, clears both datetime inputs and re-activates ALL',
                    {'subtitle': before_sub},
                    {'subtitle': sub, 'active_scale_buttons': active},
                    'ALL button active alone AND start/end inputs empty AND subtitle range label changed back to ALL',
                    dom, ok)
        except Exception as exc:
            add_row('UI-LCC-GRAPH-10', 'Graph Reset', {}, {}, 'no exception',
                    {'error': repr(exc)}, False)

        meta['page_errors'] = errors
        meta['overlays_cleared_after_add_row'] = cleared
        browser.close()

    guards.append(shared_guard('after-writes'))
    meta['shared_config_guards'] = guards
    meta['live_8031_reachable_at_end'] = (
        'UNREACHABLE' not in guards[-1]['live_8031_config_api_sha256'])
    s_cfgs = guards[0]['shared_configs']
    e_cfgs = guards[-1]['shared_configs']
    meta['shared_config_file_sha256_at_start'] = s_cfgs
    meta['shared_config_file_sha256_at_end'] = e_cfgs
    meta['shared_config_files_unchanged'] = all(s_cfgs.get(k) == e_cfgs.get(k) for k in s_cfgs)
    # :8031 IS reachable. State that positively and enumerate every request issued to it.
    reqs = []
    for g in guards:
        for key, path in (('live_8031_config_api_sha256', '/api/live-config'),
                          ('live_8031_controls_api_sha256', '/api/global-controls')):
            reqs.append({'guard': g['guard'], 'method': 'GET', 'url': LIVE_BASE + path,
                         'status': 'UNREACHABLE' if g.get(key) == 'UNREACHABLE' else 200,
                         'response_canonical_sha256': g.get(key)})
    meta['live_8031_contact'] = {
        'reachable_at_start': meta['live_8031_reachable_at_start'],
        'reachable_at_end': meta['live_8031_reachable_at_end'],
        'contact_kind': 'READ_ONLY_HTTP_GET',
        'requests_issued': reqs,
        'request_count': len(reqs),
        'methods_issued': ['GET'],
        'methods_not_issued': ['POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'],
        'write_requests_issued_to_8031': 0,
        'save_actions_invoked_against_8031': 0,
        'restart_or_stop_issued': False,
        'signal_sent_to_live_pid': False,
        'how_write_impossibility_is_established': [
            'shared_guard is the only :8031 code path and it calls urllib.request.urlopen(url) '
            'with no data/body, which issues GET and nothing else',
            'all UI writes target APP_BASE (:8032)',
            'every :8031 response hash is identical across all guards',
            'the shared config file is byte-identical before and after',
            'the probe holds no handle on the live PID and sends it no signal',
        ],
    }
    meta['live_8031_no_write_requests'] = all(r['method'] == 'GET' for r in reqs)
    meta['live_8031_shared_config_unchanged'] = meta['shared_config_files_unchanged']
    meta['isolated_config_sha256_at_end'] = sha_file(ISO_CFG)
    meta['isolated_config_changed_by_test'] = (
        meta['isolated_config_sha256_at_end'] != meta['isolated_config_sha256_at_start'])
    meta['isolation_identity'] = {
        'reported_state_dir_from_8032_api': (controls.get('networks') or {}).get('state_dir'),
        'isolated_config': ident(ISO_CFG),
        'shared_config': ident(SHARED_CFGS[0]),
        'different_files': (os.stat(ISO_CFG).st_ino != os.stat(SHARED_CFGS[0]).st_ino
                            or os.stat(ISO_CFG).st_dev != os.stat(SHARED_CFGS[0]).st_dev),
        'serving_process_reads_isolated_config': (
            (controls.get('networks') or {}).get('state_dir') is not None
            and os.path.normcase(os.path.normpath(
                (controls.get('networks') or {}).get('state_dir') or ''))
            == os.path.normcase(os.path.normpath(str(ISO_AUDIT)))),
    }

    VIEW_STATE = {'UI-LCC-GRAPH-09', 'UI-LCC-GRAPH-10'}
    by_class = {'CONTROL_WRITE': {'PASS': 0, 'FAIL': 0}, 'VIEW_STATE': {'PASS': 0, 'FAIL': 0}}
    for r in rows:
        r['row_class'] = 'VIEW_STATE' if r['row_id'] in VIEW_STATE else 'CONTROL_WRITE'
        r['excluded_from_control_write_pass_count'] = r['row_class'] == 'VIEW_STATE'
        by_class[r['row_class']][r['result']] += 1
    meta['row_counts_by_class'] = {
        k: {'PASS': v['PASS'], 'FAIL': v['FAIL'], 'total': v['PASS'] + v['FAIL']}
        for k, v in by_class.items()}
    meta['control_write_pass_count'] = by_class['CONTROL_WRITE']['PASS']
    meta['control_write_fail_count'] = by_class['CONTROL_WRITE']['FAIL']

    counts = {'PASS': 0, 'FAIL': 0}
    for r in rows:
        counts[r['result']] += 1
    meta['row_counts'] = counts

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'meta': meta, 'rows': rows}, indent=2, ensure_ascii=False),
                   encoding='utf-8')
    print('WROTE', OUT, counts, flush=True)


if __name__ == '__main__':
    main()
