#!/usr/bin/env python3
'''t_674c5537 disk oracle vs the app LIVE state_dir. READ-ONLY.'''
import json, os, csv, io, datetime

LIVE = r'C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2/hl_live_copy_audit_testnet'
W = r'C:/Users/wigmore/.hermes/kanban/workspaces/t_674c5537'
d = json.load(open(os.path.join(W, 'ui_fp_probe_t674.json')))
api = d['api_live_ws_health']['body']['health']
api_audit = d['api_live_audit_summary']['body']

out = {'live_state_dir': LIVE, 'exists': os.path.isdir(LIVE)}

def rd(n):
    p = os.path.join(LIVE, n)
    try:
        with open(p, 'rb') as f:
            return json.loads(f.read().decode('utf-8-sig', 'replace'))
    except Exception as e:
        return {'__error__': repr(e), '__path__': p}

h = rd('live_ws_health.json')
out['disk_created_at'] = h.get('created_at') if isinstance(h, dict) else None
out['disk_ws_summary'] = h.get('ws_summary') if isinstance(h, dict) else None
dw = (h.get('wallets') or {}) if isinstance(h, dict) else {}
out['disk_wallet_count'] = len(dw)
out['disk_per_wallet_keys'] = sorted({k for v in dw.values() if isinstance(v, dict) for k in v})
aw = api.get('wallets') or {}
out['api_wallet_count'] = len(aw)
out['api_per_wallet_keys'] = sorted({k for v in aw.values() if isinstance(v, dict) for k in v})

same = diff = 0
diffs = []
for k, v in aw.items():
    dv = dw.get(k)
    if isinstance(dv, dict) and dv.get('stale_ms') == v.get('stale_ms'):
        same += 1
    else:
        diff += 1
        if len(diffs) < 5:
            diffs.append({'wallet': k, 'api': v.get('stale_ms'), 'disk': (dv or {}).get('stale_ms')})
out['stale_ms_identical_wallets'] = same
out['stale_ms_differing_wallets'] = diff
out['stale_ms_diffs_sample'] = diffs
out['only_in_api'] = sorted(set(aw) - set(dw))
out['only_in_disk'] = sorted(set(dw) - set(aw))

rc = os.path.join(LIVE, 'append_only', 'reconciliation.csv')
try:
    with open(rc, 'rb') as f:
        data = f.read()
    lines = data.decode('utf-8', 'replace').splitlines()
    rdr = list(csv.DictReader(io.StringIO('\n'.join(lines))))
    st = [r for r in rdr if (r.get('event') or '').strip() == 'SEND_TERMINAL']
    out['live_csv'] = {'path': rc, 'bytes': len(data), 'lines': len(lines), 'header': lines[0] if lines else '',
                       'data_rows': len(rdr), 'send_terminal_rows': len(st),
                       'distinct_actions': sorted({(r.get('action') or '').strip() for r in st}),
                       'distinct_terminal_states': sorted({(r.get('terminal_state') or '').strip() for r in st}),
                       'mtime': datetime.datetime.fromtimestamp(os.path.getmtime(rc)).isoformat(),
                       'last_line': lines[-1] if lines else ''}
except Exception as e:
    out['live_csv'] = {'path': rc, 'error': repr(e)}

term = api_audit.get('send_terminal_rows') or []
api_intents = [str(x.get('intent_id')) for x in term if x.get('intent_id')]
try:
    with open(rc, 'rb') as f:
        rdr2 = list(csv.DictReader(io.StringIO(f.read().decode('utf-8', 'replace'))))
    strows = [r for r in rdr2 if (r.get('event') or '').strip() == 'SEND_TERMINAL']
    out['live_csv_intents_bound_to_api_prefix'] = sum(1 for r in strows if any(x.startswith((r.get('intent_id') or '')[:28]) for x in api_intents))
except Exception as e:
    out['live_csv_intents_bound_to_api_prefix'] = repr(e)

out['other_files'] = {}
for n in ['manual_live_positions.json', 'exchange_account_snapshot.json', 'exchange_account_snapshot_app.json']:
    p = os.path.join(LIVE, n)
    j = rd(n)
    out['other_files'][n] = {'exists': os.path.exists(p), 'keys': sorted(j)[:12] if isinstance(j, dict) else None,
                             'fetched_at_ms': j.get('fetched_at_ms') if isinstance(j, dict) else None}

print(json.dumps(out, indent=1, ensure_ascii=False))
