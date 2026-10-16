#!/usr/bin/env python3
'''t_674c5537: build the 6-row evidence artifact + verdicts. READ-ONLY.'''
import json, os, hashlib

W = r'C:/Users/wigmore/.hermes/kanban/workspaces/t_674c5537'
probe = json.load(open(os.path.join(W, 'ui_fp_probe_t674.json')))
cross = json.load(open(os.path.join(W, 'crosscheck_t674.json')))
disk = json.load(open(os.path.join(W, 'disk_oracle_t674.json')))
diag = json.load(open(os.path.join(W, 'diag_t674.json')))

dom = probe['dom']
api_ws = probe['api_live_ws_health']['body']['health']
wallets = api_ws['wallets']
ws_sum = api_ws['ws_summary']
not_stale = [k for k, v in wallets.items() if v.get('stale') is False]
stale_true = [k for k, v in wallets.items() if v.get('stale') is True]
dc = sorted({r['dom_current'] for r in cross['ws_rows_compared']})
dt = sorted({r['dom_thread'] for r in cross['ws_rows_compared']})
dr = sorted({r['dom_reconnect_per_min'] for r in cross['ws_rows_compared']})
ui_keys = cross['ui_lookup_key_presence_in_api']
key_absent = sorted({k for _, d in ui_keys.items() for k, p in d.items() if not p})

ev = {
 'card': 't_674c5537',
 'register_ref': 'main:certification/certification_matrix.json',
 'register_commit': 'b142cf88d389e791160f691aac3d936852b99975',
 'live_ui': 'http://127.0.0.1:8031/live-copy (HTTP 200, UI PID 8668 uvicorn HL_Copy_App_SSOT:app)',
 'live_state_dir': disk['live_state_dir'],
 'captured_at_utc': probe['tested_at_utc'],
 'dom_route': dom['route'],
 'method': 'playwright.chromium headless py3.11 rendered DOM (tabs: Reconciliation, WS Health); oracles = served JSON API + on-disk state files; no HL_Copy_App_SSOT import; READ-ONLY',
 'UI-FP-145': {'feature': 'Reconciliation / Warnings: Action', 'required': 'Action cell text from reconciliation records', 'rendered_header': 'ACTION present in Warnings thead', 'positive_result': 'PASS', 'basis': 'Action cell captured for 100/100 rendered rows (7 critical + 93 warnings); distinct values all real reconciliation action tokens; 100/100 bind to reconciliation.csv SEND_TERMINAL rows (6857 in live CSV) and to served send_terminal_rows (100)', 'negative_tests': 'NOT_EXERCISED (read-only run)', 'prior': 'FAIL (interval element not found)'},
 'UI-FP-149': {'feature': 'Reconciliation / Warnings: Wallet', 'required': 'Wallet cell text from reconciliation records', 'rendered_header': 'WALLET present in Warnings thead', 'positive_result': 'PASS', 'basis': 'Wallet cell captured for 100/100 rows; 93/93 warnings wallet cells are exact shortWallet() of a leader_wallet in served send_terminal_rows; 0 unbound; no placeholder', 'negative_tests': 'NOT_EXERCISED', 'prior': 'FAIL (tags element not found)'},
 'UI-FP-150': {'feature': 'Reconciliation / Warnings: Intent', 'required': 'Intent cell text from reconciliation records', 'rendered_header': 'INTENT present in Warnings thead', 'positive_result': 'PASS', 'basis': 'Intent cell captured for 100/100 rows; 78 bind to served send_terminal_rows intent_id, remaining 22 bind to intent_id values in reconciliation.csv (22/22) -> 100/100 provenance-bound', 'negative_tests': 'NOT_EXERCISED', 'prior': 'FAIL (links element not found)'},
 'UI-FP-165': {'feature': 'WS Health Detail: Current', 'required': 'Current cell shows live_ws_health.json state at T', 'rendered_header': 'CURRENT present in WS thead', 'positive_result': 'FAIL', 'basis': 'Rendered Current = OFFLINE for all 10 wallets while same-capture /api/live-ws-health reports stale=false for %d/10 (summary thread_alive=%s ws_status=%s wallet_count=%s). Source @register reads wh.current_status||wh.effective_status||wh.status||"OFFLINE" but neither payload nor disk per-wallet keys contain any of them (keys = last_error,last_message_ms,stale,stale_ms) -> hardcoded OFFLINE fallback. Chain API->cell BROKEN.' % (len(not_stale), ws_sum.get('thread_alive'), ws_sum.get('ws_status'), ws_sum.get('wallet_count')), 'negative_tests': 'N/A (positive chain fails)', 'prior': 'FAIL (search element not found)'},
 'UI-FP-167': {'feature': 'WS Health Detail: Thread', 'required': 'Thread cell shows live_ws_health.json thread state at T', 'rendered_header': 'THREAD present in WS thead', 'positive_result': 'FAIL', 'basis': 'Rendered Thread = "down" for all 10 wallets; same-capture API thread_alive=%s. UI reads wh.thread_alive||wh.worker_thread_alive, neither key exists in payload or disk -> hardcoded "down" fallback contradicting live thread state. Chain BROKEN.' % (ws_sum.get('thread_alive'),), 'negative_tests': 'N/A', 'prior': 'FAIL (export element not found)'},
 'UI-FP-168': {'feature': 'WS Health Detail: Reconnect/min', 'required': 'Reconnect/min cell shows live_ws_health.json reconnect rate at T', 'rendered_header': 'RECONNECT/MIN present in WS thead', 'positive_result': 'FAIL', 'basis': 'Rendered Reconnect/min = 0.00 for all 10 wallets because UI reads wh.reconnects_per_min (absent); the summary counter that does exist is ws_summary.total_reconnect_count=%s which the per-wallet path never reads -> Number(undefined||0).toFixed(2) fallback. Chain BROKEN.' % (ws_sum.get('total_reconnect_count'),), 'negative_tests': 'N/A', 'prior': 'FAIL (import element not found)'},
 'hard_facts': {'ws_tab_rendered': dom.get('ws_tab_visible'), 'ws_rows_rendered': dom.get('ws_row_count'), 'ws_headers': dom.get('ws_headers'), 'ws_dom_current_distinct': dc, 'ws_dom_thread_distinct': dt, 'ws_dom_reconnect_distinct': dr, 'api_per_wallet_keys': cross['api_per_wallet_keys'], 'disk_per_wallet_keys': cross['disk_per_wallet_keys'], 'api_wallets_stale_false': len(not_stale), 'api_wallets_stale_true': len(stale_true), 'api_ws_summary': {k: ws_sum.get(k) for k in ['thread_alive', 'ws_status', 'wallet_count', 'total_reconnect_count', 'worst_health_grade', 'stale_count']}, 'ui_lookup_keys_absent_everywhere': key_absent, 'register_src_token_counts': diag['src_token_counts'], 'ws_stale_ms_dom_matches_api_all_rows': cross['ws_all_stale_ms_match_api'], 'recon_warnings_rows': cross['warnings_row_count'], 'recon_critical_rows': cross['critical_row_count'], 'recon_warnings_headers': 'EVENT, STATUS, ACTION, REJECT CATEGORY, TERMINAL STATE, COIN, WALLET, INTENT, NOTES', 'recon_legacy_rows': (dom.get('recon_legacy') or {}).get('rows'), 'unbound_intent_cells_vs_api': diag['unbound_intent_cells']['count'], 'unbound_intent_cells_bound_to_csv': diag['unbound_intent_cells']['csv_rebind'], 'live_csv': {k: disk['live_csv'][k] for k in ['bytes', 'lines', 'data_rows', 'send_terminal_rows', 'mtime']}, 'live_csv_distinct_actions_count': len(disk['live_csv']['distinct_actions']), 'live_csv_distinct_terminal_states_count': len(disk['live_csv']['distinct_terminal_states'])},
 'instrument_notes': ['The disk oracle first read the ARCHIVED repo dir _archive/hl_stage2/hl_live_copy_audit_testnet (live_ws_health.json dated 2026-10-14, 1 wallet). The RUNNING app (/api/global-controls) uses state_dir C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet (10 wallets, created_at %s). All disk facts above come from the running state_dir.' % disk['disk_created_at'], 'stale_ms: DOM == same-capture API for all 10 rows (%s); DOM vs DISK stale_ms differs 10/10 - expected lag between two writers of the rolling file, NOT a UI defect.' % cross['ws_all_stale_ms_match_api'], 'Prior notes (interval/tags/links/search/export/import element not found) came from a matcher searching the WRONG tokens; the real headers are ACTION/WALLET/INTENT and CURRENT/THREAD/RECONNECT/MIN.'],
 'verdicts': {'UI-FP-145': 'PASS', 'UI-FP-149': 'PASS', 'UI-FP-150': 'PASS', 'UI-FP-165': 'FAIL', 'UI-FP-167': 'FAIL', 'UI-FP-168': 'FAIL'},
 'negative_tests_note': 'The three negative tests on 145/149/150 were NOT exercised (inducing them needs mutating the read-only live surface); reported NOT_EXERCISED, not PASS.',
}
raw = json.dumps(ev, sort_keys=True, ensure_ascii=False).encode('utf-8')
ev['artifact_sha256'] = hashlib.sha256(raw).hexdigest()
out = os.path.join(W, 'UI_FP_145_149_150_165_167_168_t_674c5537.json')
json.dump(ev, open(out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
print('WROTE', out)
print(json.dumps(ev['verdicts'], indent=1))
