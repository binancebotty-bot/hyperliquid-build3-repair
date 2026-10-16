#!/usr/bin/env python3
'''t_674c5537 cross-check: DOM cell text vs served API vs on-disk source. READ-ONLY.'''
import json, os, subprocess

W = r'C:/Users/wigmore/.hermes/kanban/workspaces/t_674c5537'
REPO = r'C:/Users/wigmore/hyperliquid-build3-repair'
REG = 'b142cf88d389e791160f691aac3d936852b99975'
SRC = '_archive/hl_stage2/HL_Copy_App_SSOT.py'

d = json.load(open(os.path.join(W, 'ui_fp_probe_t674.json')))
dom = d['dom']
api_h = d['api_live_ws_health']['body']['health']
api_wallets = api_h['wallets']
ws_sum = api_h['ws_summary']
disk_h = d['oracle_disk']['live_ws_health.json']

short = lambda w: (w[:10] + '...' + w[-6:]) if len(w) > 18 else w
stale_by_short = {short(k): v.get('stale_ms') for k, v in api_wallets.items()}
dom_ws = dom.get('ws_rows') or []
H = dom.get('ws_headers') or []
ci = {h: i for i, h in enumerate(H)}
rows = []
for r in dom_ws:
    w = r[ci.get('WALLET', 0)]
    rows.append({'wallet': w, 'dom_current': r[ci.get('CURRENT', 1)], 'dom_grade': r[ci.get('GRADE', 2)],
                 'dom_thread': r[ci.get('THREAD', 3)], 'dom_reconnect_per_min': r[ci.get('RECONNECT/MIN', 4)],
                 'dom_stale_ms': r[ci.get('STALE MS', 13)], 'api_stale_ms': stale_by_short.get(w),
                 'stale_match': str(stale_by_short.get(w)) == str(r[ci.get('STALE MS', 13)])})

sample = (list(api_wallets.values())[0] if api_wallets else {})
lookup = {'Current': ['current_status', 'effective_status', 'status'], 'Thread': ['thread_alive', 'worker_thread_alive'],
          'Reconnect/min': ['reconnects_per_min'], 'Grade': ['current_health_grade', 'health_grade'], 'Data status': ['data_status']}
present = {col: {k: (k in sample) for k in keys} for col, keys in lookup.items()}

disk_keys, api_keys = set(), set()
for v in (disk_h.get('wallets') or {}).values():
    if isinstance(v, dict):
        disk_keys |= set(v.keys())
for v in api_wallets.values():
    if isinstance(v, dict):
        api_keys |= set(v.keys())

pats = ["current_status||wh.effective_status||wh.status||'OFFLINE'", "alive?'alive':'down'", "reconnects_per_min||0", "wh.transport_stale_ms??wh.stale_ms"]
grep = []
for pat in pats:
    rr = subprocess.run(['git', '-C', REPO, 'grep', '-n', pat, REG, '--', SRC], capture_output=True, text=True, timeout=60)
    grep.append({'pattern': pat, 'hits': [l for l in rr.stdout.splitlines()]})

rr = subprocess.run(['git', '-C', REPO, 'show', REG + ':' + SRC], capture_output=True, timeout=180)
src = rr.stdout.decode('utf-8', 'replace')
tokens = ['current_status', 'effective_status', 'thread_alive', 'worker_thread_alive', 'reconnects_per_min',
          'current_health_grade', 'health_grade', 'processed_count', 'raw_message_count', 'data_status',
          'total_reconnect_count', 'stale_ms']
tok_counts = {t: src.count(t) for t in tokens}

api_audit = d['api_live_audit_summary']['body']
term = api_audit.get('send_terminal_rows') or []
term_intents = {str(x.get('intent_id')) for x in term if x.get('intent_id')}
term_actions = {str(x.get('action') or x.get('operator_action')) for x in term}
term_wallets = {str(x.get('leader_wallet') or x.get('wallet')) for x in term}
wrows = (dom.get('recon_warnings') or {}).get('rows') or []
w_actions, w_wallets, w_intents, w_events = set(), set(), set(), set()
for r2 in wrows:
    if len(r2) >= 9:
        w_events.add(r2[0]); w_actions.add(r2[2]); w_wallets.add(r2[6]); w_intents.add(r2[7])

out = {'register_commit': REG, 'dom_route': dom.get('route'), 'ws_row_count': len(dom_ws), 'ws_rows_compared': rows,
       'ws_all_stale_ms_match_api': all(x['stale_match'] for x in rows) if rows else None,
       'api_per_wallet_keys': sorted(api_keys), 'disk_per_wallet_keys': sorted(disk_keys),
       'ui_lookup_key_presence_in_api': present, 'register_src_fallback_exprs': grep,
       'register_src_token_counts': tok_counts, 'api_ws_summary_total_reconnect_count': ws_sum.get('total_reconnect_count'),
       'api_ws_summary_thread_alive': ws_sum.get('thread_alive'), 'api_ws_summary_worst_health_grade': ws_sum.get('worst_health_grade'),
       'warnings_row_count': len(wrows), 'warnings_dom_distinct_events': sorted(w_events),
       'warnings_dom_distinct_actions': sorted(w_actions), 'warnings_dom_distinct_wallets': sorted(w_wallets),
       'warnings_dom_distinct_intents': sorted(w_intents)[:5],
       'warnings_intents_intersect_api_send_terminal': len(w_intents & term_intents),
       'api_send_terminal_count': len(term), 'api_send_terminal_distinct_actions_sample': sorted(term_actions)[:8],
       'api_send_terminal_distinct_wallets_sample': sorted(term_wallets)[:5], 'legacy_rows': dom.get('recon_legacy'),
       'critical_row_count': len((dom.get('recon_critical') or {}).get('rows') or []),
       'orphan_row_count': len((dom.get('recon_orphan') or {}).get('rows') or []),
       'recon_csv': {k: v for k, v in (d['oracle_disk'].get('reconciliation.csv') or {}).items() if k != 'last2'},
       'recon_csv_header': (d['oracle_disk'].get('reconciliation.csv') or {}).get('header'),
       'recon_csv_last2': (d['oracle_disk'].get('reconciliation.csv') or {}).get('last2'),
       'live_ws_health_created_at': disk_h.get('created_at'), 'dom_capture_ts': dom.get('ts'),
       'greenred_count': len(dom.get('greenred') or [])}
print(json.dumps(out, indent=1, ensure_ascii=False))
