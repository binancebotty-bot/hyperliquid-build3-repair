#!/usr/bin/env python3
'''t_674c5537: bind truncated DOM cell prefixes to API/CSV exact values. READ-ONLY.'''
import json, os, csv, io

W = r'C:/Users/wigmore/.hermes/kanban/workspaces/t_674c5537'
d = json.load(open(os.path.join(W, 'ui_fp_probe_t674.json')))
dom = d['dom']
api = d['api_live_audit_summary']['body']
term = api.get('send_terminal_rows') or []

short = lambda w: (w[:10] + '...' + w[-6:]) if len(w) > 18 else w
api_wal_short = {short(str(x.get('leader_wallet') or x.get('wallet'))): str(x.get('leader_wallet') or x.get('wallet')) for x in term if (x.get('leader_wallet') or x.get('wallet'))}
api_intents = [str(x.get('intent_id')) for x in term if x.get('intent_id')]

wrows = (dom.get('recon_warnings') or {}).get('rows') or []
crows = (dom.get('recon_critical') or {}).get('rows') or []
print('DOM warnings rows', len(wrows), 'DOM critical rows', len(crows), 'sum', len(wrows) + len(crows))
print('API send_terminal_rows', len(term))

def bind(rows):
    w_ok = w_bad = i_ok = i_bad = 0
    samples = []
    for r in rows:
        if len(r) < 9:
            continue
        wcell, icell = r[6], r[7]
        if wcell in api_wal_short:
            w_ok += 1
        else:
            w_bad += 1
            if len(samples) < 3:
                samples.append({'wallet_cell': wcell})
        pref = icell.rstrip('\u2026')
        if any(x.startswith(pref) for x in api_intents):
            i_ok += 1
        else:
            i_bad += 1
    return {'wallet_bound': w_ok, 'wallet_unbound': w_bad, 'intent_prefix_bound': i_ok, 'intent_prefix_unbound': i_bad, 'unbound_samples': samples}

out = {'warnings_binding': bind(wrows), 'critical_binding': bind(crows),
       'api_distinct_actions_in_terminal': sorted({str(x.get('action') or x.get('operator_action')) for x in term}),
       'dom_warnings_distinct_actions': sorted({r[2] for r in wrows if len(r) >= 9}),
       'dom_critical_distinct_actions': sorted({r[2] for r in crows if len(r) >= 9})}

p = d['oracle_disk']['reconciliation.csv']['path']
try:
    with open(p, 'rb') as f:
        txt = f.read().decode('utf-8', 'replace')
    rdr = list(csv.DictReader(io.StringIO(txt)))
    st = [r for r in rdr if (r.get('event') or '').strip() == 'SEND_TERMINAL']
    out['csv_total_rows'] = len(rdr)
    out['csv_send_terminal_rows'] = len(st)
    out['csv_distinct_actions'] = sorted({(r.get('action') or '').strip() for r in st})
    out['csv_distinct_terminal_states'] = sorted({(r.get('terminal_state') or '').strip() for r in st})
    out['csv_distinct_intent_prefix_ok'] = sum(1 for r in st if any(x.startswith((r.get('intent_id') or '')[:28]) for x in api_intents)) if api_intents else None
except Exception as e:
    out['csv_error'] = repr(e)

print(json.dumps(out, indent=1, ensure_ascii=False))
