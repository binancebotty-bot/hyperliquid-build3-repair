import json
from pathlib import Path
R = Path(r'C:/Users/wigmore/.hermes/cache/scratch/b3_clean')
EV = R/'certification/results/UI_LCC_WS_02_16_8031.json'
OUT = R/'certification/results/UI_LCC_WS_02_16_verdicts.json'
REF = 'certification/results/UI_LCC_WS_02_16_8031.json'
C = '89b3bc7586bf328df336fc9ea721cee212617762'
d = json.loads(EV.read_text(encoding='utf-8'))
rows = d['health_rows']; W = d['api_wallets']; s = d['api_ws_summary']
keys = sorted(W); U = d['api_wallet_field_union']; n = len(rows)
H = d['health_headers']
col = lambda i: [r[i] for r in rows]
sm_r = col(13); sm_a = [str(W[k]['stale_ms']) for k in keys]
EM = '\u2014'
V = {}
V['UI-LCC-WS-02'] = ('FAIL', "Current renders 'OFFLINE' on %d/%d rows while the same payload reports ws_status=%r, worst_health_grade=%r, stale=False for all %d wallets. Served per-wallet object carries only %s (no current_status/effective_status/status), so renderHealth's fallback paints a healthy feed OFFLINE." % (sum(x == 'OFFLINE' for x in col(1)), n, s.get('ws_status'), s.get('worst_health_grade'), n, U))
V['UI-LCC-WS-03'] = ('FAIL', "Grade renders the em-dash default on %d/%d rows; current_health_grade/health_grade absent from served wallet object (%s). ws_summary only has an aggregate worst_health_grade=%r, never per row." % (sum(x == EM for x in col(2)), n, U, s.get('worst_health_grade')))
V['UI-LCC-WS-04'] = ('FAIL', "Thread renders 'down' on %d/%d rows while ws_summary.thread_alive=%r and every wallet's last_message_ms advances (stale_ms %s..%s). Per-wallet thread_alive/worker_thread_alive is absent, so the boolean default reads as a dead worker." % (sum(x == 'down' for x in col(3)), n, s.get('thread_alive'), min(int(x) for x in sm_r), max(int(x) for x in sm_r)))
V['UI-LCC-WS-05'] = ('FAIL', "Reconnect/min renders the constant default %r on all %d rows; reconnects_per_min is absent from the served object. ws_summary has total_reconnect_count=%r only, and the panel never divides it per wallet, so the cell cannot change when reconnects do." % (sorted(set(col(4))), n, s.get('total_reconnect_count')))
for rid, i, f in [('UI-LCC-WS-06', 5, 'processed_count'), ('UI-LCC-WS-07', 6, 'raw_message_count'), ('UI-LCC-WS-08', 7, 'parsed_fill_message_count'), ('UI-LCC-WS-09', 8, 'snapshot_fill_seen_count'), ('UI-LCC-WS-10', 9, 'snapshot_fill_recovered_count'), ('UI-LCC-WS-11', 10, 'ignored_snapshot_count'), ('UI-LCC-WS-12', 11, 'recent_error_count'), ('UI-LCC-WS-13', 12, 'lifetime_error_count')]:
    V[rid] = ('FAIL', "%r renders the constant default on all %d rows (%r). The serving per-wallet object (%s) never carries %r, so this cell cannot track the counter it names; the counters exist only in the engine snapshot builder, not in the file the UI and API actually serve." % (H[i], n, sorted(set(col(i))), U, f))
m = sum(a == b for a, b in zip(sm_r, sm_a))
V['UI-LCC-WS-14'] = ('PASS', "Stale ms cell equals the API's per-wallet stale_ms on %d/%d rows, value-for-value after sorting by wallet (%r vs %r; e.g. %s/%s and %s/%s). Row-bound: the ten values are mutually distinct, so any wrong-wallet binding fails. Caveat, not a pass claim: per-wallet 'stale' was False for all %d wallets at capture, so the stale-flag branch was not exercised." % (m, n, sm_r, sm_a, sm_r[0], sm_a[0], sm_r[1], sm_a[1], n))
V['UI-LCC-WS-15'] = ('FAIL', "Data status renders the em-dash on %d/%d rows; data_status is absent from the served wallet object (%s), so WAITING_FOR_DATA/LIVE/degraded can never appear even though ws_summary.ws_status=%r is available." % (sum(x == EM for x in col(14)), n, U, s.get('ws_status')))
V['UI-LCC-WS-16'] = ('FAIL', "Last close/error renders an empty string on %d/%d rows. Renderer reads last_error_repr/last_error/last_close_msg; the served object carries last_error only (%s) and the serving health writer never emits last_close_msg, so no close/error can surface. Empty on every row is also not row-bound." % (sum(x == '' for x in col(15)), n, U))
out = [{'row_id': 'UI-LCC-WS-%02d' % i, 'verdict': V['UI-LCC-WS-%02d' % i][0], 'evidence_ref': REF, 'tested_commit': C, 'why': V['UI-LCC-WS-%02d' % i][1]} for i in range(2, 17)]
assert len(out) == 15 and all(o['why'] for o in out)
OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'out': str(OUT), 'n': len(out), 'counts': {k: sum(o['verdict'] == k for o in out) for k in ('PASS', 'FAIL', 'NOT_TESTED')}}, indent=2))
