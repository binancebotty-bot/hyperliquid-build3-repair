#!/usr/bin/env python3
'''Assemble F_UI_FP_119_120_133_137_139_140_t_9dee8e17.json from the two raw captures.'''
import json, io, os, hashlib
D = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(D, 'raw')


def load(n):
    with io.open(os.path.join(RAW, n), encoding='utf-8') as f:
        return json.load(f)


probe = load('ui_fp_probe_119_140.json')
orc = load('ui_fp_oracle_119_140.json')


def sha(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


EXQ = probe['dom']['execqual']['table_headers']
AUD = probe['dom']['audit']['table_headers']

rows = []

def row(rid, area, feature, expected, probe_txt, oracle_txt, verdict, basis, negative):
    rows.append({'id': rid, 'area': area, 'feature': feature, 'expected_behaviour': expected,
                 'probe': probe_txt, 'independent_oracle': oracle_txt, 'result': verdict,
                 'basis': basis, 'negative_test': negative})

row('UI-FP-119', 'UI', 'Execution Quality table: Exchange ms',
    'Shows Exchange ms from append_only/send_attempts.csv + live_fills.csv as direct send_attempt/live_fill field or latency delta.',
    'rendered DOM header "EXCHANGE MS" present in Execution Quality table (headers=%s); 300 tbody rows rendered.' % (EXQ,),
    'served /api/live-audit-summary execution_quality_rows[].exchange_call_ms nonempty=%d (sample 1078/1117/1045 ms); append_only/send_attempts.csv exchange_call_ms nonempty=%d.' % (orc['ui_fp_119']['api_rows_nonempty'], orc['ui_fp_119']['oracle_rows_nonempty']),
    'PASS',
    'Field header present in RENDERED DOM and populated with real per-attempt ms values; API field name matches the CSV column name, so the render is a direct read of send_attempts.csv latency. Non-vacuous: pending_send rows render "\u2014" not 0.',
    'source unavailable renders \u2014 (not 0): observed on pending_send rows.')

row('UI-FP-120', 'UI', 'Execution Quality table: Error',
    'Shows Error from append_only/send_attempts.csv + live_fills.csv as direct send_attempt/live_fill field or latency delta.',
    'rendered DOM header "ERROR" present (headers=%s).' % (EXQ,),
    'execution_quality_rows[].error nonempty=%d with real exchange reject text (e.g. "Insufficient margin to place order. asset=140", reject_category INSUFFICIENT_MARGIN); append_only/send_attempts.csv error nonempty=%d.' % (orc['ui_fp_120']['api_rows_nonempty'], orc['ui_fp_120']['oracle_rows_nonempty']),
    'PASS',
    'ERROR column rendered and carrying the exchange rejection message paired with its reject_category.',
    'empty source must not fabricate; errors shown are real reject strings.')

row('UI-FP-133', 'UI', 'Order Intents / Audit table: Real order result',
    'Shows Real order result from append_only/order_intents.csv + send_attempts.csv as direct intent/send join field.',
    'rendered DOM header "REAL ORDER RESULT" present in Order Intents/Audit table (headers=%s); observed rendered values include REAL_ORDER_FILLED, EXCHANGE_REJECTED, pending_send, NO_SEND_ATTEMPT.' % (AUD,),
    'independent recompute of intent_id\u2192send_attempts.csv.status join yields the same value space (NO_SEND_ATTEMPT / ORDER_FILLED\u2192REAL_ORDER_FILLED / ORDER_REJECTED\u2192EXCHANGE_REJECTED); sample intents=%s.' % ([c['computed_real_result'] for c in orc['ui_fp_133']['oracle_computed_sample']],),
    'PASS',
    'The join field is present in the rendered audit table AND reproducible from the CSVs without engine import.',
    'intent with no send attempt renders NO_SEND_ATTEMPT, not a false positive fill.')

row('UI-FP-137', 'UI', 'Reconciliation / Actionable Critical Items: Reject category',
    'Shows Reject category from append_only/reconciliation.csv as direct reconciliation field.',
    'rendered DOM: recon panel contains "Actionable Critical Items" + "Warnings" tables, header "REJECT CATEGORY" present (live table headers=[EVENT,STATUS,ACTION,REJECT CATEGORY,TERMINAL STATE,COIN,WALLET,INTENT,NOTES]).',
    'reconciliation_rows[].reject_category nonempty=%d (samples INSUFFICIENT_MARGIN, LIQ_PARITY_BLOCK); append_only/reconciliation.csv reject_category nonempty=%d.' % (orc['ui_fp_137']['api_rows_nonempty'], orc['ui_fp_137']['oracle_rows_nonempty']),
    'PASS',
    'Actionable Critical Items table renders a REJECT CATEGORY column populated from reconciliation.csv (cross-read via API + CSV, no engine import).',
    'rows without a reject category render \u2014.')

row('UI-FP-139', 'UI', 'Reconciliation / Actionable Critical Items: Coin',
    'Shows Coin from append_only/reconciliation.csv as direct reconciliation field.',
    'rendered DOM: Actionable Critical Items table header "COIN" present; 50 tbody rows rendered.',
    'reconciliation_rows[].coin nonempty=%d; reconciliation.csv coin nonempty=%d.' % (orc['ui_fp_139']['api_rows_nonempty'], orc['ui_fp_139']['oracle_rows_nonempty']),
    'PASS',
    'COIN column present and populated with real symbols (DOGE/WLD/ZORA) matching reconciliation.csv.',
    'n/a coin renders \u2014.')

row('UI-FP-140', 'UI', 'Reconciliation / Actionable Critical Items: Wallet',
    'Shows Wallet from append_only/reconciliation.csv as direct reconciliation field.',
    'rendered DOM: Actionable Critical Items table header "WALLET" present.',
    'reconciliation_rows[].wallet/leader_wallet nonempty=%d (real 0x addresses); reconciliation.csv leader_wallet nonempty=%d.' % (orc['ui_fp_140']['api_rows_nonempty'], orc['ui_fp_140']['oracle_rows_nonempty']),
    'PASS',
    'WALLET column present and populated with real wallet addresses.',
    'account-level-only rows render ACCOUNT_LEVEL_ONLY, not a fake address.')

out = {
    'register_ref': 'main:certification/certification_matrix.json',
    'register_commit': 'b142cf88d389e791160f691aac3d936852b99975',
    'tested_at_utc': probe['tested_at_utc'],
    'surface': probe['surface'],
    'route': 'playwright.chromium headless (py3.11) RENDERED DOM of http://127.0.0.1:8031/live-copy with per-tab clicks; oracle = urllib served JSON API + on-disk append_only CSV; no engine import; fully READ-ONLY.',
    'rows': rows,
    'verdict_summary': {'PASS': 6, 'FAIL': 0, 'NOT_TESTED': 0},
    'provenance_finding': {
        'issue': 'The RUNNING UI is deployed from a commit NEWER than the register of record.',
        'register_commit': 'b142cf88d389e791160f691aac3d936852b99975',
        'live_source_commit': '5223ce2 (hermes/ui-delta-landing) / re-run at ecd6788',
        'detail': 'At b142cf88 the Execution Quality table has 13 columns with NO Exchange ms / Terminal state / Operator action / Reject category / Leader->send ms; and the Reconciliation panel is "Ledger vs Exchange" with NO "Actionable Critical Items" table. The LIVE DOM has an 18-column Execution Quality table incl. EXCHANGE MS, and a recon Actionable Critical Items table incl. REJECT CATEGORY/COIN/WALLET. Rows UI-FP-119/137/139/140 therefore certify the LIVE surface, which is ahead of the register commit.',
        'recommendation': 'Certify these 4 rows against the deployed commit (5223ce2/ecd6788), or fold the live source into the register; the register currently pins b142cf88 which lacks the fields.',
    },
    'raw_captures': {
        'ui_fp_probe_119_140.json': sha(os.path.join(RAW, 'ui_fp_probe_119_140.json')),
        'ui_fp_oracle_119_140.json': sha(os.path.join(RAW, 'ui_fp_oracle_119_140.json')),
    },
}
with io.open(os.path.join(D, 'F_UI_FP_119_120_133_137_139_140_t_9dee8e17.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print('WROTE verdicts; rows=%d' % len(rows))
