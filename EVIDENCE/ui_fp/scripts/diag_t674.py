#!/usr/bin/env python3
'''t_674c5537 diagnostics: (a) 22 unbound intent cells, (b) per-row source-field basis. READ-ONLY.'''
import json, os, csv, io, subprocess

W = r'C:/Users/wigmore/.hermes/kanban/workspaces/t_674c5537'
REPO = r'C:/Users/wigmore/hyperliquid-build3-repair'
REG = 'b142cf88d389e791160f691aac3d936852b99975'
SRC = '_archive/hl_stage2/HL_Copy_App_SSOT.py'
LIVE = r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet'

probe = json.load(open(os.path.join(W, 'ui_fp_probe_t674.json')))
dom = probe['dom']
api_audit = probe['api_live_audit_summary']['body']
term = api_audit.get('send_terminal_rows') or []

wrows = (dom.get('recon_warnings') or {}).get('rows') or []

api_all_intents = {str(x.get('intent_id')) for x in term if x.get('intent_id')}

unbound = []
for r in wrows:
    if len(r) < 9:
        continue
    pref = r[7].rstrip('\u2026')
    if not any(x.startswith(pref) for x in api_all_intents):
        unbound.append({'action': r[2], 'wallet': r[6], 'intent_cell': r[7], 'event': r[0]})

csvp = os.path.join(LIVE, 'append_only', 'reconciliation.csv')
try:
    with open(csvp, 'rb') as f:
        rdr = list(csv.DictReader(io.StringIO(f.read().decode('utf-8', 'replace'))))
    st = [r for r in rdr if (r.get('event') or '').strip() == 'SEND_TERMINAL']
    csv_intents = [(r.get('intent_id') or '') for r in st]
    hits = sum(1 for u in unbound if any(x.startswith(u['intent_cell'].rstrip('\u2026')) for x in csv_intents))
    csv_pref_hit = {'unbound_tested': len(unbound), 'bound_to_csv': hits}
except Exception as e:
    csv_pref_hit = repr(e)

rr = subprocess.run(['git', '-C', REPO, 'show', REG + ':certification/certification_matrix.json'], capture_output=True, timeout=180)
reg = json.loads(rr.stdout.decode('utf-8', 'replace'))
m = {r['id']: r for r in reg['records']}
rows_fields = {}
for i in ['UI-FP-145', 'UI-FP-149', 'UI-FP-150', 'UI-FP-165', 'UI-FP-167', 'UI-FP-168']:
    r = m[i]
    rows_fields[i] = {'feature': r.get('feature'), 'expected_behaviour': r.get('expected_behaviour'),
                      'sources': r.get('sources'), 'negative_tests': r.get('negative_tests'),
                      'independent_oracle': r.get('independent_oracle'), 'result_in_register': r.get('result'),
                      'field_keys': sorted(r.keys())}

src = subprocess.run(['git', '-C', REPO, 'show', REG + ':' + SRC], capture_output=True, timeout=180).stdout.decode('utf-8', 'replace')
out = {
    'unbound_intent_cells': {'count': len(unbound), 'sample': unbound[:6], 'csv_rebind': csv_pref_hit},
    'api_send_terminal_row_keys': sorted({k for x in term for k in x}),
    'api_terminal_intent_id_sample': [x.get('intent_id') for x in term[:3]],
    'register_rows': rows_fields,
    'src_token_counts': {t: src.count(t) for t in ['current_status', 'effective_status', 'wh.status', 'thread_alive',
                                                   'worker_thread_alive', 'reconnects_per_min', 'total_reconnect_count',
                                                   'current_health_grade', 'health_grade', 'data_status']},
}
print(json.dumps(out, indent=1, ensure_ascii=False))
