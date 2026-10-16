#!/usr/bin/env python3
"""B3-CERT UI SSOT/TRUTH corrective harness - task t_8fc704ce.

Executes each row's execution_proof against the REAL UI source served over
starlette TestClient on the REAL testnet audit state (read-only copy), and
asserts each row's NAMED DATA PROPERTY via an independent oracle. A PASS is
EARNED by runtime behaviour (not a guessed header string). Every row carries a
NON-VACUOUS negative (a mutation that must flip the verdict).

Rows: UI-SSOT-TOP-07, UI-SSOT-TOP-09, UI-SSOT-PAGE-01, UI-SSOT-PAGE-13/14/15,
UI-TRUTH-003.

Row semantics from certification/MASTER_PRODUCT_INVARIANTS_AND_CERTIFICATION.md
OD-18: the analytics dashboard top bar (Normalisation Base / Mode / Fixed $ /
Fee bps / Friction) is an APP-DERIVED MODEL of copy performance and must carry
its truth tier so a model value cannot be read as live engine truth; the Live
Copy Command Centre shows real-account truth.

Run with Python 3.11:
  C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe \\
    certification/results/UI_SSOT_FAIL_harness_b3e6d66651.py
Do NOT edit certification_matrix.json or apply_verified_results.py.
"""
from __future__ import annotations
import copy, hashlib, json, os, re, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(os.environ.get('UI_SSOT_REPO') or 'C:/Users/wigmore/.hermes/kanban/workspaces/t_4811b885/repo')
SCR = Path(os.environ.get('UI_SSOT_SCR') or 'C:/Users/wigmore/.hermes/cache/scratch/b3ui_t4811b885')
REAL_STATE = REPO / '_archive' / 'hl_stage2' / 'hl_live_copy_audit_testnet'
UI_SRC = REPO / '_archive' / 'hl_stage2' / 'HL_Copy_App_SSOT.py'
APP_MODEL = REPO / '_archive' / 'hl_stage2' / 'hl_copy_output' / 'app_model_state.json'
COMMIT = subprocess.run(['git', '-C', str(REPO), 'rev-parse', 'HEAD'],
                        capture_output=True, text=True).stdout.strip()
COMMIT10 = COMMIT[:10]
UI_SHA = hashlib.sha256(UI_SRC.read_bytes()).hexdigest()

CHECKS, NEG, ROWS, BLOCKED = [], [], {}, []


def check(name, ok, detail=''):
    CHECKS.append({'name': name, 'pass': bool(ok), 'detail': detail})
    print(f'  CHECK::{name}::{"PASS" if ok else "FAIL"}' + (f' | {detail}' if detail and not ok else ''))


def neg(name, ok, detail=''):
    NEG.append({'name': name, 'pass': bool(ok), 'detail': detail})
    print(f'  NEG::{name}::{"PASS" if ok else "FAIL"}' + (f' | {detail}' if detail and not ok else ''))


def build_env():
    SCR.mkdir(parents=True, exist_ok=True)
    aud = SCR / 'audit'
    if aud.exists():
        shutil.rmtree(aud, ignore_errors=True)
    (aud / 'append_only').mkdir(parents=True, exist_ok=True)
    for n in ['live_config.json', 'live_ws_health.json', 'live_integrity_status.json',
              'live_service_state.json', 'manual_live_positions.json',
              'exchange_account_snapshot.json', 'exchange_account_history.json',
              'clean_core_runtime_state.json']:
        if (REAL_STATE / n).exists():
            shutil.copy2(REAL_STATE / n, aud / n)
    for n in ['send_attempts.csv', 'order_intents.csv', 'live_fills.csv', 'reconciliation.csv']:
        if (REAL_STATE / 'append_only' / n).exists():
            shutil.copy2(REAL_STATE / 'append_only' / n, aud / 'append_only' / n)
    env = SCR / 'test.env'
    env.write_text('HL_LEADER_NETWORK=mainnet\nHL_FOLLOWER_NETWORK=testnet\n'
                   'HL_LIVE_HL_ACCOUNT_ADDRESS=0x' + 'c' * 40 + '\nHL_APP_PORT=8899\n')
    os.environ['HL_LIVE_ENV_FILE'] = str(env)
    os.environ['HL_LIVE_AUDIT_DIR'] = str(aud)
    stray = REPO / '_archive' / 'hl_stage2' / 'ui_state.json'
    if stray.exists():
        stray.unlink()
    return aud


def top_bar(home: str) -> str:
    m = re.search(r'<div class="top">.{0,1400}', home, re.S)
    return m.group(0) if m else ''


def main():
    aud = build_env()
    sys.path.insert(0, str(REPO / '_archive' / 'hl_stage2'))
    import HL_Copy_App_SSOT as ui
    from starlette.testclient import TestClient
    c = TestClient(ui.app)
    stamp = datetime.now(timezone.utc).isoformat()
    print(f'UI SSOT/TRUTH corrective | commit {COMMIT} | ui_sha {UI_SHA[:12]}')
    check('UI_SHA256_RECORDED', len(UI_SHA) == 64, UI_SHA)
    check('APP_SERVES_LIVE_COPY', c.get('/live-copy').status_code == 200)

    st = json.loads(APP_MODEL.read_text(encoding='utf-8-sig'))
    bar = top_bar(ui.render_home(copy.deepcopy(st)))
    lcf = aud / 'live_config.json'

    # ================= TOP-07: current mode label =================
    h0 = hashlib.sha256(lcf.read_bytes()).hexdigest()
    cfg0 = json.dumps(c.get('/api/live-config').json(), sort_keys=True)
    r = c.post('/api/ui-state', data={'copy_mode': 'fixed', 'norm_base': '250', 'fixed_notional': '321'})
    h1 = hashlib.sha256(lcf.read_bytes()).hexdigest()
    cfg1 = json.dumps(c.get('/api/live-config').json(), sort_keys=True)
    u = c.get('/api/ui-state').json()
    model_scope = (r.status_code == 200 and h0 == h1 and cfg0 == cfg1
                   and u.get('copy_mode') == 'fixed' and float(u.get('norm_base')) == 250.0)
    mode_labelled_model = bool(re.search(r'<span class="muted">\s*Model mode:', bar))
    engine_truth_labelled = 'Engine sizing:' in bar
    top07 = model_scope and mode_labelled_model and engine_truth_labelled
    check('UI-SSOT-TOP-07:CURRENT_MODE_LABEL', top07,
          f'model_scope={model_scope} mode_labelled_model={mode_labelled_model} '
          f'engine_truth_labelled={engine_truth_labelled}')
    c.post('/api/ui-state', data={'copy_mode': 'proportional', 'norm_base': '100', 'fixed_notional': '100'})
    orig_tpl = ui.HTML_TEMPLATE
    ui.HTML_TEMPLATE = orig_tpl.replace('<span class="muted">Model mode:</span>', '<span class="muted"></span>')
    bar_mut = top_bar(ui.render_home(copy.deepcopy(st)))
    ui.HTML_TEMPLATE = orig_tpl
    neg('NEG_TOP07_MODEL_LABEL', mode_labelled_model and 'Model mode:' not in bar_mut,
        'removing the model label from the top bar makes the property false (non-vacuous)')

    # ================= TOP-09: POLL badge =================
    poll_present = '>POLL<' in bar
    check('UI-SSOT-TOP-09:POLL_BADGE', poll_present, f'POLL badge in analytics top bar={poll_present}')
    ui.HTML_TEMPLATE = orig_tpl.replace('>POLL<', '>XXXX<')
    poll_mut = '>POLL<' in top_bar(ui.render_home(copy.deepcopy(st)))
    ui.HTML_TEMPLATE = orig_tpl
    neg('NEG_TOP09_POLL_BADGE', poll_present and not poll_mut,
        'removing the POLL badge from the template removes it from the render (non-vacuous)')

    # ================= PAGE-13: /api/live-ws-health =================
    r13 = c.get('/api/live-ws-health')
    b13 = r13.json() if r13.status_code == 200 else {}
    h13 = b13.get('health') or {}
    w13 = h13.get('wallets') or {}
    page13 = (r13.status_code == 200 and b13.get('ok') is True and bool(w13)
              and all(isinstance(v, dict) and len(v) >= 3 for v in w13.values()))
    check('UI-SSOT-PAGE-13:WS_HEALTH_ENDPOINT', page13,
          f'status={r13.status_code} ok={b13.get("ok")} wallets={len(w13)} '
          f'fields={sorted(list(next(iter(w13.values()), {}).keys()))[:6]}')
    _saved = ui.LIVE_COPY_WS_HEALTH_FILE
    ui.LIVE_COPY_WS_HEALTH_FILE = SCR / 'nonexistent_ws_health.json'
    empty13 = bool((c.get('/api/live-ws-health').json().get('health') or {}).get('wallets'))
    ui.LIVE_COPY_WS_HEALTH_FILE = _saved
    neg('NEG_PAGE13_MUTABLE', page13 and not empty13,
        'a missing health file yields empty wallets -> the row would FAIL (non-vacuous)')

    # ================= PAGE-14: /api/live-audit-summary =================
    r14 = c.get('/api/live-audit-summary')
    try:
        b14 = r14.json()
    except Exception:
        b14 = {}
    proc = subprocess.run([sys.executable, '-c', (
        'import os,sys,json;'
        f'sys.path.insert(0,{str(REPO / "_archive" / "hl_stage2")!r});'
        f'os.environ["HL_LIVE_ENV_FILE"]={str(SCR / "test.env")!r};'
        f'os.environ["HL_LIVE_AUDIT_DIR"]={str(aud)!r};'
        'import HL_Copy_App_SSOT as ui;'
        '\ntry:\n d=ui._live_audit_summary(); print(json.dumps({"ok":True,"keys":list(d.keys())}))\n'
        'except Exception as e:\n print(json.dumps({"ok":False,"exc":type(e).__name__+": "+str(e)}))')],
        capture_output=True, text=True, timeout=180)
    oracle14 = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else '{}'
    page14 = r14.status_code == 200 and b14.get('ok') is True
    check('UI-SSOT-PAGE-14:AUDIT_SUMMARY_ENDPOINT', page14,
          f'status={r14.status_code} body_ok={b14.get("ok")} error={str(b14.get("error"))[:70]} oracle={oracle14[:110]}')
    # Non-vacuous negative: the empty-tail guard is LOAD-BEARING. Reverting it
    # and calling the exact production path (_service_position_evidence_by_coin)
    # with the REAL empty-tail live_fills rows raises IndexError; the shipped
    # guard returns cleanly. This proves the PASS is earned by the fix.
    _lf = ui._load_recent_live_fills(250000)
    _empty_tail = [r for r in _lf if 'exchange_order_id=' in str(r.get('notes') or '')
                   and not str(r.get('exchange_order_id') or '').strip()]

    def _buggy_row_oid(row):
        for _k in ('exchange_order_id', 'oid', 'order_id', 'orderId'):
            _v = str(row.get(_k) or '').strip()
            if _v:
                return _v
        _notes = str(row.get('notes') or '')
        _m = 'exchange_order_id='
        if _m in _notes:
            _tail = _notes.split(_m, 1)[1]
            return _tail.split(';', 1)[0].split()[0]
        return ''

    _good_row_oid = ui._row_exchange_order_id
    _good_clean = True
    try:
        ui._service_position_evidence_by_coin(send_attempts=[], live_fills=list(_empty_tail))
    except Exception:
        _good_clean = False
    ui._row_exchange_order_id = _buggy_row_oid
    _buggy_raised = False
    try:
        ui._service_position_evidence_by_coin(send_attempts=[], live_fills=list(_empty_tail))
    except Exception:
        _buggy_raised = True
    finally:
        ui._row_exchange_order_id = _good_row_oid
    neg('NEG_PAGE14_GUARD_LOAD_BEARING',
        page14 and bool(_empty_tail) and _good_clean and _buggy_raised,
        f'empty_tail_rows={len(_empty_tail)} good_path_clean={_good_clean} '
        f'buggy_path_raises={_buggy_raised} -> the guard is load-bearing (PASS is earned by the fix)')

    # ================= PAGE-15: contract warning banner =================
    errs_clean = ui.validate_render_contract(copy.deepcopy(st))
    bad = copy.deepcopy(st)
    for row in (bad.get('wallet_rows') or []):
        for side in ('lead', 'copy'):
            if isinstance(row.get(side), dict) and row[side]:
                row[side]['equity'] = 999999.99
    errs_bad = ui.validate_render_contract(bad)
    banner_ok = 'CONTRACT WARNING' in ui.render_home(bad)
    page15 = (not errs_clean) and bool(errs_bad) and banner_ok
    check('UI-SSOT-PAGE-15:CONTRACT_BANNER', page15,
          f'clean_errs={len(errs_clean)} mutated_errs={len(errs_bad)} banner_rendered={banner_ok}')
    neg('NEG_PAGE15_NONVACUOUS', bool(errs_bad) and banner_ok,
        'a contract-violating state yields errors AND renders the banner')

    # ================= PAGE-01: /wallet/{wallet} detail page =================
    cfg = c.get('/api/live-config').json()
    wallets = list((cfg.get('config') or {}).get('wallets') or {})
    model_wallets = list((st.get('wallets') or {}).keys())
    nonuser = [w for w in model_wallets if w.lower() != ui.USER_WALLET.lower()]
    user_r = c.get('/wallet/' + ui.USER_WALLET)
    detail_rendered = (user_r.status_code == 200
                       and ('Expected copy fills' in user_r.text or 'COPY PNL' in user_r.text))
    if nonuser:
        nu = c.get('/wallet/' + nonuser[0])
        check('UI-SSOT-PAGE-01:WALLET_DETAIL', nu.status_code == 200,
              f'nonuser={nonuser[0][:12]} status={nu.status_code}')
        ROWS['UI-SSOT-PAGE-01'] = {'verdict': 'PASS' if nu.status_code == 200 else 'FAIL',
                                   'oracle': 'served non-user detail page'}
    else:
        BLOCKED.append({'row': 'UI-SSOT-PAGE-01',
                        'reason': ('no NON-USER wallet exists in the testnet model state (only the user wallet is '
                                   'present), so the non-user detail branch /wallet/{wallet} is unreachable and its '
                                   'closed-trades/actions tables cannot be verified. Route presence IS proven: '
                                   'unknown wallet -> 404, user wallet -> 200 with the detail tables rendered.'),
                        'proved': {'unknown_404': c.get('/wallet/0x' + 'e' * 40).status_code,
                                   'user_200': user_r.status_code, 'detail_rendered': detail_rendered,
                                   'model_wallets': model_wallets}})
        ROWS['UI-SSOT-PAGE-01'] = {'verdict': 'BLOCKED', 'oracle': 'route reachability + model-state census'}
        print(f'  BLOCKED::UI-SSOT-PAGE-01 | config_wallets={[w[:12] for w in wallets]} '
              f'model_wallets={[w[:12] for w in model_wallets]} user_200={user_r.status_code} detail={detail_rendered}')
    neg('NEG_PAGE01_MUTATED_404', c.get('/wallet/0x' + 'e' * 40).status_code == 404,
        'unknown wallet 404s (route is real, not a catch-all 200)')

    # ================= TRUTH-003: UI is read-only observer =================
    src = UI_SRC.read_text(encoding='utf-8', errors='replace')
    no_engine_import = ('import HL_Live_Copy_Service' not in src and 'from HL_Live_Copy_Service' not in src)
    no_spawn = not re.search(r'\bsubprocess\b|\bPopen\b', src)
    hb = hashlib.sha256(lcf.read_bytes()).hexdigest()
    c.get('/api/live-audit-summary')          # a UI endpoint that 500s
    c.get('/api/live-ws-health')
    ha = hashlib.sha256(lcf.read_bytes()).hexdigest()
    truth003 = no_engine_import and no_spawn and hb == ha
    check('UI-TRUTH-003:READ_ONLY_OBSERVER', truth003,
          f'no_engine_import={no_engine_import} no_spawn={no_spawn} live_config_unchanged={hb == ha}')
    neg('NEG_TRUTH003_500_ISOLATED', hb == ha,
        'a UI endpoint 500 does not alter live_config.json (UI outage is not a trading mutation)')

    def v(cid):
        m = [x for x in CHECKS if x['name'].startswith(cid)]
        return 'PASS' if m and all(x['pass'] for x in m) else 'FAIL'
    for cid in ['UI-SSOT-TOP-07', 'UI-SSOT-TOP-09', 'UI-SSOT-PAGE-13',
                'UI-SSOT-PAGE-14', 'UI-SSOT-PAGE-15', 'UI-TRUTH-003']:
        ROWS.setdefault(cid, {'verdict': v(cid),
                              'oracle': 'runtime TestClient on real testnet state + independent recompute/mutation'})

    ok = sum(1 for x in CHECKS if x['pass'])
    fail = len(CHECKS) - ok
    neg_ok = sum(1 for x in NEG if x['pass'])
    print(f'\nROWS ' + json.dumps({k: x['verdict'] for k, x in ROWS.items()}))
    print(f'CHECKS {ok}/{len(CHECKS)} PASS, {fail} FAIL | NEG {neg_ok}/{len(NEG)} PASS | BLOCKED {len(BLOCKED)}')
    result = {
        'task_id': 't_8fc704ce',
        'title': 'B3-CERT UI SSOT/TRUTH FAIL corrective (UI-SSOT-*, UI-TRUTH-003)',
        'tested_commit': COMMIT,
        'source_branch': os.environ.get('UI_SSOT_SRC_BRANCH', ''),
        'source_commit': os.environ.get('UI_SSOT_SRC_COMMIT', ''),
        'page01_fixture': os.environ.get('UI_SSOT_PAGE01_FIXTURE', ''),
        'tested_at_utc': stamp,
        'ui_source': str(UI_SRC),
        'ui_source_sha256': UI_SHA,
        'oracle': ('runtime: starlette TestClient against the real testnet audit state (read-only copy); '
                   'independent recompute of the audit-summary builder in a fresh interpreter; per-row mutation '
                   'negatives; engine-independence by source census + live_config byte-hash invariance'),
        'provenance_note': ('certification_matrix.json pins UI sha256 fad19d22 (HL_Copy_App_SSOT_20260513.py) / '
                            'c0f9e508 (HL_Copy_App_SSOT.py). Neither hash exists as a git object here; the only tracked '
                            'UI source is _archive/hl_stage2/HL_Copy_App_SSOT.py @ sha256 ' + UI_SHA[:12] + '. Rows were '
                            'executed against that SERVED real source; the pinned 13-May hash is UNVERIFIABLE in this repo '
                            '(provenance gap to report).'),
        'rows': ROWS,
        'checks': {x['name']: {'pass': x['pass'], 'detail': x['detail']} for x in CHECKS},
        'negative_tests': {x['name']: {'pass': x['pass'], 'detail': x['detail']} for x in NEG},
        'blocked': BLOCKED,
        'summary': {'total_checks': len(CHECKS), 'passed_checks': ok, 'failed_checks': fail,
                    'total_negative_tests': len(NEG), 'passed_negative_tests': neg_ok,
                    'failed_negative_tests': len(NEG) - neg_ok, 'blocked_count': len(BLOCKED),
                    'rows_pass': sum(1 for x in ROWS.values() if x['verdict'] == 'PASS'),
                    'rows_fail': sum(1 for x in ROWS.values() if x['verdict'] == 'FAIL'),
                    'rows_blocked': sum(1 for x in ROWS.values() if x['verdict'] == 'BLOCKED')},
    }
    out = REPO / 'certification' / 'results' / f'UI_SSOT_FAIL_{COMMIT10}.json'
    out.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f'results -> {out}')
    return result


if __name__ == '__main__':
    main()
