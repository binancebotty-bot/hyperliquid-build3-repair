#!/usr/bin/env python3
'''UI-LCC CONTROL-WRITE probe against an ISOLATED app instance.

Safety: every write goes to APP_BASE (the isolated port). The live instance is only ever
READ (GET /api/live-config) and its on-disk config is only ever hashed - never written.
'''
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

APP_BASE = os.environ.get('PROBE_APP_BASE', 'http://127.0.0.1:8032')
LIVE_BASE = os.environ.get('PROBE_LIVE_BASE', 'http://127.0.0.1:8031')
SERVING_PID = int(os.environ.get('PROBE_SERVING_PID', '30580'))
SERVING_WORKSPACE = Path(os.environ.get('PROBE_WORKSPACE', 'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-8032/_archive/hl_stage2'))
SERVING_COMMIT = os.environ.get('PROBE_SERVING_COMMIT', '89b3bc7586bf328df336fc9ea721cee212617762')
ISO_AUDIT = Path(os.environ.get('PROBE_ISO_AUDIT', 'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert-8032/_isolated_8032/audit'))
LIVE_CFG = Path(os.environ.get('PROBE_LIVE_CFG', 'C:/Users/wigmore/.hermes/kanban/workspaces/t_bae1ce13/build/_archive/hl_stage2/hl_live_copy_audit_testnet/live_config.json'))
USER_WALLET = '0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205'
TEST_WALLET = '0x1111111111111111111111111111111111111111'
OUT = Path(os.environ.get('PROBE_OUT', 'certification/results/UI-LCC-CONTROL-WRITE.json'))

ISO_CFG = ISO_AUDIT / 'live_config.json'
SRC = SERVING_WORKSPACE / 'HL_Copy_App_SSOT.py'


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def sha_file(path):
    p = Path(path)
    if not p.exists():
        return 'ABSENT'
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def get_json(url, timeout=30):
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


def guard(name):
    out = {'guard': name, 'live_config_file': str(LIVE_CFG),
           'live_config_file_sha256': sha_file(LIVE_CFG)}
    for key, url in (('live_config_api_sha256', '/api/live-config'),
                     ('live_8031_global_controls_sha256', '/api/global-controls')):
        try:
            payload = get_json(LIVE_BASE + url)
            out[key] = hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()
        except Exception as exc:
            out[key] = 'UNREACHABLE'
            out[key + '_error'] = type(exc).__name__
    return out


def write_result(rows, meta):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'meta': meta, 'rows': rows}, indent=2, ensure_ascii=False), encoding='utf-8')
    print('WROTE', OUT)


BASELINE = {'archived_wallets': {}, 'auto_send_enabled': False,
            'global_controls': {}, 'wallets': {}}


def process_start_utc(pid):
    if os.name != 'nt':
        return None
    cmd = ('powershell -NoProfile -Command "(Get-Process -Id ' + str(int(pid)) +
           ' -ErrorAction Stop).StartTime.ToUniversalTime().ToString(\\"yyyy-MM-ddTHH:mm:ssZ\\")"')
    try:
        out = (os.popen(cmd).read() or '').strip()
        return out or None
    except Exception:
        return None


def main():
    # reset ONLY the isolated config to a documented baseline
    iso_before_baseline = sha_file(ISO_CFG)
    ISO_CFG.write_text(json.dumps(BASELINE, indent=2), encoding='utf-8')
    iso_after_baseline = sha_file(ISO_CFG)
    proc_start = process_start_utc(SERVING_PID)

    live_start = guard('start')
    iso_start = get_json(APP_BASE + '/api/global-controls')
    meta = {
        'card': 't_931d2d8d',
        'probe': 'ui_lcc_control_write',
        'generated_at_utc': now_utc(),
        'app_base': APP_BASE,
        'serving_binding_type': 'content_sha256',
        'serving_script_sha256': sha_file(SRC),
        'serving_script_path': str(SRC),
        'serving_pid': SERVING_PID,
        'serving_process_start_utc': proc_start,
        'serving_workspace': str(SERVING_WORKSPACE),
        'serving_commit': SERVING_COMMIT,
        'serving_commit_committed_at': '2026-10-17T07:18:14+00:00',
        'isolated_audit_dir': str(ISO_AUDIT),
        'isolated_config_path': str(ISO_CFG),
        'isolated_config_sha256_before_baseline_reset': iso_before_baseline,
        'isolated_config_sha256_at_start': iso_after_baseline,
        'live_config_path': str(LIVE_CFG),
        'live_config_file_sha256_at_start': sha_file(LIVE_CFG),
        'live_config_api_sha256_at_start': guard('start')['live_config_api_sha256'],
        'live_8031_observation_at_start': live_start,
        'isolated_8032_controls_at_start': iso_start,
        'isolated_8032_state_dir_claim': (iso_start.get('networks') or {}).get('state_dir'),
    }

    rows = []
    guards = [{'guard': 'before-writes', **live_start}]

    def add_row(row_id, check, before, after, predicate, dom, passed, extra=None):
        rec = {
            'row_id': row_id,
            'check': check,
            'before': before,
            'after': after,
            'predicate': predicate,
            'dom_evidence': dom,
            'result': 'PASS' if passed else 'FAIL',
            'tested_at_utc': now_utc(),
            'tested_commit': SERVING_COMMIT,
            'serving_script_sha256': meta['serving_script_sha256'],
            'proof_network': 'TESTNET',
        }
        if extra:
            rec.update(extra)
        rows.append(rec)
        print(rec['row_id'], rec['result'], flush=True)

    W = '#lcWalletRows tr[data-wallet="' + TEST_WALLET + '"]'

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(APP_BASE + '/wallet/' + USER_WALLET, wait_until='load', timeout=90000)
        page.wait_for_selector('#liveCopyPanel', timeout=90000)
        page.wait_for_timeout(3000)

        try:
            before_cfg = iso_config()
            page.click('button[data-lc-modal="lcWalletModal"]')
            page.wait_for_timeout(400)
            page.fill('#lcAddForm input[name=wallet]', TEST_WALLET)
            page.select_option('#lcAddForm select[name=mode]', 'OFF')
            page.select_option('#lcAddForm select[name=copy_mode]', 'fixed')
            page.fill('#lcAddForm input[name=norm_base]', '100')
            page.fill('#lcAddForm input[name=fixed_notional]', '10')
            page.click('#lcAddForm button[type=submit]')
            page.wait_for_timeout(3000)
            after_cfg = iso_config()
            w = wallet_cfg(after_cfg, TEST_WALLET) or {}
            dom = {
                'modal_active_after_submit': page.eval_on_selector('#lcWalletModal', 'e=>e.classList.contains("active")'),
                'status_text': page.inner_text('#lcStatus'),
                'wallet_rows': page.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row', 'els=>els.map(e=>e.dataset.wallet)'),
            }
            pred = ('added key absent before AND present after AND mode==OFF AND fixed_notional==10 AND '
                    'modal closed AND status shows SAVED')
            ok = (wallet_cfg(before_cfg, TEST_WALLET) is None
                  and w.get('mode') == 'OFF'
                  and float(w.get('fixed_notional', -1)) == 10.0
                  and dom['modal_active_after_submit'] is False
                  and 'SAVED' in (dom['status_text'] or '').upper())
            add_row('UI-LCC-ADD-10', 'Add-wallet modal submit persists exactly to the isolated live_config.json and shows SAVED',
                    {'wallets_has_test_wallet': False, 'wallet_count': len(before_cfg.get('wallets') or {})},
                    {'wallets_has_test_wallet': True, 'wallet_entry': w, 'wallet_count': len(after_cfg.get('wallets') or {})},
                    pred, dom, ok)
        except Exception as exc:
            add_row('UI-LCC-ADD-10', 'Add-wallet modal submit', {}, {}, 'no exception', {'error': repr(exc)}, False)

        try:
            before_cfg = iso_config()
            page.click('button[data-lc-modal="lcWalletModal"]')
            page.wait_for_timeout(400)
            page.fill('#lcAddForm input[name=wallet]', 'not-a-wallet')
            page.click('#lcAddForm button[type=submit]')
            page.wait_for_timeout(2500)
            after_cfg = iso_config()
            dom = {'status_text': page.inner_text('#lcStatus'), 'status_class': page.get_attribute('#lcStatus', 'class')}
            ok = ('BAD_WALLET' in (dom['status_text'] or '').upper()
                  and 'lc-bad' in (dom['status_class'] or '')
                  and (after_cfg.get('wallets') or {}) == (before_cfg.get('wallets') or {}))
            add_row('UI-LCC-ADD-10-neg', 'Negative: invalid wallet address rejected with a visible error and no config write',
                    {'wallets': list((before_cfg.get('wallets') or {}).keys())},
                    {'wallets': list((after_cfg.get('wallets') or {}).keys())},
                    'status shows BAD_WALLET with lc-bad class AND wallets map unchanged', dom, ok)
            page.click('#lcWalletModal button[data-lc-close]')
            page.wait_for_timeout(400)
        except Exception as exc:
            add_row('UI-LCC-ADD-10-neg', 'Negative invalid wallet', {}, {}, 'no exception', {'error': repr(exc)}, False)

        try:
            page.wait_for_timeout(800)
            before_cfg = iso_config()
            if not page.query_selector(W):
                raise RuntimeError('ROW_NOT_RENDERED')
            page.select_option(W + ' select[name=mode]', 'LIVE')
            page.select_option(W + ' select[name=copy_mode]', 'fixed')
            page.fill(W + ' input[name=fixed_notional]', '25')
            page.fill(W + ' input[name=norm_base]', '150')
            page.click(W + ' button[data-act=save]')
            page.wait_for_timeout(3000)
            after_cfg = iso_config()
            w = wallet_cfg(after_cfg, TEST_WALLET) or {}
            dom = {'status_text': page.inner_text('#lcStatus'), 'row_text': page.inner_text(W)}
            ok = (float(w.get('fixed_notional', -1)) == 25.0
                  and float(w.get('norm_base', -1)) == 150.0
                  and str(w.get('mode')).upper() == 'LIVE'
                  and w.get('enabled') is True
                  and 'SAVED' in (dom['status_text'] or '').upper())
            add_row('UI-LCC-WTBL-11', 'Wallet-row Save writes the edited F/N/mode to the isolated live_config.json',
                    {'wallet_entry': wallet_cfg(before_cfg, TEST_WALLET)},
                    {'wallet_entry': w, 'config_sha256': sha_file(ISO_CFG)},
                    'fixed_notional 10->25 AND norm_base 100->150 AND mode OFF->LIVE AND enabled true AND status SAVED',
                    dom, ok)
        except Exception as exc:
            add_row('UI-LCC-WTBL-11', 'Wallet-row Save', {}, {}, 'no exception', {'error': repr(exc)}, False)

        try:
            before_cfg = iso_config()
            page.click(W + ' button[data-act=clo]')
            page.wait_for_timeout(3000)
            after_cfg = iso_config()
            w = wallet_cfg(after_cfg, TEST_WALLET) or {}
            dom = {'status_text': page.inner_text('#lcStatus')}
            ok = (str(w.get('mode')).upper() == 'CLO' and w.get('enabled') is True
                  and 'CLO' in (dom['status_text'] or '').upper())
            add_row('UI-LCC-WTBL-12', 'Wallet-row CLO button sets mode CLO (enabled, closes only) in the isolated config',
                    {'wallet_entry': wallet_cfg(before_cfg, TEST_WALLET)},
                    {'wallet_entry': w}, 'mode LIVE->CLO AND enabled true AND status mentions CLO', dom, ok)
        except Exception as exc:
            add_row('UI-LCC-WTBL-12', 'Wallet-row CLO', {}, {}, 'no exception', {'error': repr(exc)}, False)

        try:
            before_cfg = iso_config()
            page.click(W + ' button[data-act=off]')
            page.wait_for_timeout(3000)
            after_cfg = iso_config()
            w = wallet_cfg(after_cfg, TEST_WALLET) or {}
            dom = {'status_text': page.inner_text('#lcStatus')}
            ok = (str(w.get('mode')).upper() == 'OFF' and w.get('enabled') is False
                  and 'OFF' in (dom['status_text'] or '').upper())
            add_row('UI-LCC-WTBL-13', 'Wallet-row OFF button sets mode OFF (disabled) in the isolated config',
                    {'wallet_entry': wallet_cfg(before_cfg, TEST_WALLET)},
                    {'wallet_entry': w}, 'mode CLO->OFF AND enabled false AND status mentions OFF', dom, ok)
        except Exception as exc:
            add_row('UI-LCC-WTBL-13', 'Wallet-row OFF', {}, {}, 'no exception', {'error': repr(exc)}, False)

        try:
            before_cfg = iso_config()
            page.once('dialog', lambda d: d.accept())
            page.click(W + ' button[data-act=archive]')
            page.wait_for_timeout(3000)
            after_cfg = iso_config()
            a = archived_cfg(after_cfg, TEST_WALLET) or {}
            dom = {'status_text': page.inner_text('#lcStatus'),
                   'wallet_rows_after': page.eval_on_selector_all('#lcWalletRows tr.lc-wallet-row', 'els=>els.map(e=>e.dataset.wallet)')}
            ok = (wallet_cfg(after_cfg, TEST_WALLET) is None
                  and a.get('mode') == 'OFF'
                  and bool(a.get('archived_at'))
                  and TEST_WALLET not in dom['wallet_rows_after'])
            add_row('UI-LCC-WTBL-14', 'Wallet-row Archive moves the wallet from wallets{} to archived_wallets{} with archived_at',
                    {'in_wallets': wallet_cfg(before_cfg, TEST_WALLET) is not None,
                     'in_archived': archived_cfg(before_cfg, TEST_WALLET) is not None},
                    {'in_wallets': wallet_cfg(after_cfg, TEST_WALLET) is not None,
                     'archived_entry': {k: a.get(k) for k in ('mode', 'enabled', 'archived_at')}},
                    'wallets entry gone AND archived_wallets entry present with mode OFF and archived_at AND row disappeared',
                    dom, ok)
        except Exception as exc:
            add_row('UI-LCC-WTBL-14', 'Wallet-row Archive', {}, {}, 'no exception', {'error': repr(exc)}, False)

        guards.append(guard('before-global-controls-write'))

        try:
            before_cfg = iso_config()
            page.click('#lcGcToggle')
            page.wait_for_timeout(500)
            page.fill('#gcMaxTotal', '1234.5')
            page.fill('#gcMaxDir', '55.5')
            page.fill('#gcMaxDailyLoss', '7')
            page.fill('#gcMaxWallet', '3.25')
            page.fill('#gcMaxOrder', '99')
            page.fill('#gcMktPct', '0.35')
            page.fill('#gcCloseAdv', '1.5')
            page.fill('#gcAllowlist', 'btc, eth')
            page.fill('#gcBlocklist', 'doge')
            page.click('#lcGcSave')
            page.wait_for_timeout(3000)
            after_cfg = iso_config()
            gc = after_cfg.get('global_controls') or {}
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
                  and 'Saved' == (dom['status_text'] or '').strip())
            add_row('UI-LCC-BTN-05', 'Save Global Controls persists every form field to the isolated live_config.json and the API agrees',
                    {'global_controls': before_cfg.get('global_controls')},
                    {'global_controls_file': gc, 'global_controls_api': api, 'config_sha256': sha_file(ISO_CFG)},
                    'all 9 fields round-trip (1234.5/55.5/7/3.25/99/0.35->35bps/1.5/[BTC,ETH]/[DOGE]) AND status text == Saved',
                    dom, ok)
        except Exception as exc:
            add_row('UI-LCC-BTN-05', 'Save Global Controls', {}, {}, 'no exception', {'error': repr(exc)}, False)

        guards.append(guard('after-global-controls-write'))

        try:
            page.fill('#lcGraphStart', '2026-10-01T00:00')
            page.fill('#lcGraphEnd', '2026-10-15T00:00')
            page.click('#lcGraphApplyRange')
            page.wait_for_timeout(1500)
            sub = page.inner_text('#lcGraphSubtitle')
            active = page.eval_on_selector_all('[data-lc-graph-scale]', 'els=>els.filter(e=>e.classList.contains("active")).length')
            dom = {'subtitle': sub, 'active_scale_buttons': active,
                   'start_value': page.input_value('#lcGraphStart'), 'end_value': page.input_value('#lcGraphEnd')}
            ok = (' to ' in sub) and active == 0 and 'Oct' in sub
            add_row('UI-LCC-GRAPH-09', 'Graph Apply switches the range to the custom start/end and re-renders',
                    {'subtitle': 'ALL (initial render)', 'active_scale_buttons': 1},
                    {'subtitle': sub, 'active_scale_buttons': active},
                    'subtitle shows <custom start> to <custom end> AND no scale button remains active', dom, ok)
        except Exception as exc:
            add_row('UI-LCC-GRAPH-09', 'Graph Apply', {}, {}, 'no exception', {'error': repr(exc)}, False)

        try:
            before_sub = page.inner_text('#lcGraphSubtitle')
            page.click('#lcGraphResetRange')
            page.wait_for_timeout(1500)
            sub = page.inner_text('#lcGraphSubtitle')
            active = page.eval_on_selector_all('[data-lc-graph-scale]', 'els=>els.filter(e=>e.classList.contains("active")).map(e=>e.dataset.lcGraphScale)')
            dom = {'subtitle': sub, 'active_scale_buttons': active,
                   'start_value': page.input_value('#lcGraphStart'), 'end_value': page.input_value('#lcGraphEnd')}
            ok = (active == ['all'] and page.input_value('#lcGraphStart') == ''
                  and page.input_value('#lcGraphEnd') == '' and '(ALL)' in sub and ' to ' not in sub)
            add_row('UI-LCC-GRAPH-10', 'Graph Reset returns to the ALL range, clears both datetime inputs and re-activates ALL',
                    {'subtitle': before_sub},
                    {'subtitle': sub, 'active_scale_buttons': active},
                    'ALL button active alone AND start/end inputs empty AND subtitle range label == ALL', dom, ok)
        except Exception as exc:
            add_row('UI-LCC-GRAPH-10', 'Graph Reset', {}, {}, 'no exception', {'error': repr(exc)}, False)

        meta['page_errors'] = errors
        browser.close()

    guards.append(guard('after-writes'))
    meta['shared_config_guards'] = guards
    meta['live_config_file_sha256_at_end'] = sha_file(LIVE_CFG)
    meta['live_config_api_sha256_at_end'] = guards[-1]['live_config_api_sha256']
    meta['live_8031_controls_sha256_at_end'] = guards[-1]['live_8031_global_controls_sha256']
    def same_or_unreachable(a, b):
        return a == b or 'UNREACHABLE' in (a, b)

    meta['live_config_unchanged'] = (
        meta['live_config_file_sha256_at_start'] == meta['live_config_file_sha256_at_end']
        and same_or_unreachable(meta['live_config_api_sha256_at_start'],
                                meta['live_config_api_sha256_at_end'])
        and same_or_unreachable(guards[0]['live_8031_global_controls_sha256'],
                                guards[-1]['live_8031_global_controls_sha256'])
    )
    meta['live_8031_reachable_during_probe'] = (
        'UNREACHABLE' not in (meta['live_config_api_sha256_at_start'],
                              meta['live_config_api_sha256_at_end']))
    meta['isolated_config_sha256_at_end'] = sha_file(ISO_CFG)
    meta['isolated_config_written'] = meta['isolated_config_sha256_at_start'] != meta['isolated_config_sha256_at_end']
    meta['row_results'] = {r['row_id']: r['result'] for r in rows}
    meta['summary'] = {
        'tested': len(rows),
        'pass': sum(1 for r in rows if r['result'] == 'PASS'),
        'fail': sum(1 for r in rows if r['result'] == 'FAIL'),
    }
    write_result(rows, meta)
    print(json.dumps(meta['summary']))
    return 0 if meta['summary']['fail'] == 0 and meta['live_config_unchanged'] else 1


if __name__ == '__main__':
    sys.exit(main())
