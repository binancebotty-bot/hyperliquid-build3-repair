"""Assemble the UI-ROUTE + UI-TRUTH verdict artifact for card t_cfcad924."""
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUTE_JSON = os.path.join(HERE, 'UI_ROUTE_TRUTH_t_cfcad924.json')

SERVED = {
    'path': 'C:/Users/wigmore/trading_stack/build3-live-screen-0513-view/hl_stage2/HL_Copy_App_SSOT.py',
    'sha256': 'fad19d220d7af13d48a3eec664c56a32b31624d671b00e2f80ec2dc9062a29b0',
    'mtime': '2026-05-13T08:18:03+01:00',
    'pid': 15760,
    'pid_started': '2026-10-19T08:40:25+01:00',
    'cmdline': 'python.exe -m uvicorn HL_Copy_App_SSOT:app --host 127.0.0.1 --port 8023',
    'pyc_mtime': '2026-10-19T08:38:20+01:00',
    'repo_archive_copy_sha256': 'f7a3e9f1e9fe18f8cb46400991f384e32d0cca1a31b4229f4c92943bbb9804f3',
    'repo_archive_copy_note': 'repo _archive copy is NOT byte-identical to the served file; certify by served path+sha256, never by repo path',
}

TRUTH_ROWS = [
    {
        'id': 'UI-TRUTH-001',
        'feature': 'Truth tier and freshness on every value',
        'evidence': [
            'Grep of served module fad19d22 for AUTHORITATIVE_EXCHANGE|LOCAL_LEDGER|LEADER_SIGNAL|DISPLAY_ONLY|SKIPPED: 0 matches - tier vocabulary absent from the served UI source.',
            'Rendered HTML of / and /live-copy contains none of those tokens.',
            'No per-cell age/freshness rendered; only an in-process cache max_age_sec, invisible to the user.',
            'Counter-example: /api/live-ws-health serves live_ws_health.json verbatim (_load_live_ws_health only normalises ws_summary -> overall; it never recomputes age). That file was last written 2026-10-09T15:04Z and its newest message is 860,709 s old, yet it reports stale=false and stale_ms=593,963 - i.e. the served freshness field is ~1450x understated and the UI has no independent clock to catch it.',
        ],
        'verdict': 'FAIL',
        'statement': 'FAIL - no truth tier carried or displayed on any value; staleness understated ~1450x (593963 ms reported vs 860709000 ms real age), stale=false.',
    },
    {
        'id': 'UI-TRUTH-002',
        'feature': 'No cosmetic green',
        'evidence': [
            'No GREEN-ONLY-001 gate and no master-gate function in served source (0 matches).',
            'Green assigned by JS string matching: pill() -> lc-green for OPEN/LIVE/OK/GOOD/ACTIVE; integCls GREEN; wsCls WS_OK.',
            'Counter-example: live-audit-summary reports hard_copy_active_red=1012 and audit_proof_missing=2 while /live-copy renders green header/status elements.',
        ],
        'verdict': 'FAIL',
        'statement': 'FAIL - green is a cosmetic token match, not a derived gate; 1012 ACTIVE_RED rows coexist with green UI elements.',
    },
    {
        'id': 'UI-TRUTH-003',
        'feature': 'UI is read-only observer',
        'evidence': [
            'Module docstring lines 4-10: reads engine SSOT only; never mutates engine truth.',
            'Grep for hyperliquid import, place_order, market_open, usd_class_transfer, submit_order, /exchange: 0 matches - no order path exists.',
            'Writes confined to app-derived files (app_model_state.json, copy_trades.csv, portfolio_history.json, equity_history.json, live_config.json, ui_state.json) plus admin purge/snapshot.',
            'No route gates the engine; engine reads hl_copy_output/engine_truth.json + raw_live_fills.csv, which this app never writes.',
        ],
        'verdict': 'PASS',
        'statement': 'PASS - source-level read-only observer; no exchange write path in the served module.',
    },
    {
        'id': 'UI-TRUTH-004',
        'feature': 'At-a-glance wallet, portfolio and system health',
        'evidence': [
            'At-a-glance surface exists only on /live-copy (74,062 bytes server HTML; it contains the JS that builds the status cards, and / and /model at 21,730 bytes do not). Correction to my first draft: the cards are built CLIENT-SIDE by renderTopStatus()/renderRealCards() from four JSON calls (live-config, live-ws-health, live-audit-summary, global-controls), so counting lc-stat divs in server HTML is meaningless (2 found). No DOM capture was performed for this row.',
            'Wallet truth disjoint: /api/metrics reports 1 wallet (0x7ae3b0... funding master); /api/live-config and /api/live-ws-health report 4 different leader wallets. config_wallets == metrics_wallets is False.',
            'Portfolio curve for the only metrics wallet is a placeholder: ts=1970-01-01T00:00:00Z, all 0.0, equity=100.0, while source default DEFAULT_LEADER_EQUITY=10000.0. 100.0 is neither default nor measured.',
            'WS health stale: file written 2026-10-09T15:04Z, age 860709 s, still served with stale=false.',
            'Matrix row is OPEN_DECISION (OD-20): the required screen is not contractually defined.',
        ],
        'verdict': 'FAIL',
        'statement': 'FAIL - no single screen shows wallet + portfolio + system health from one truth source: wallet sets disagree (1 vs 4), equity curve is a 1970 placeholder, WS health is ~9.9 days stale but reported healthy.',
    },
    {
        'id': 'UI-TRUTH-005',
        'feature': 'Historical Build 3 UI restored, not rebuilt',
        'evidence': [
            'PID 15760 runs uvicorn HL_Copy_App_SSOT:app on 127.0.0.1:8023, started 2026-10-19T08:40:25+01:00.',
            'Served module mtime 2026-05-13T08:18:03+01:00, sha256 fad19d22... = matrix-declared hash.',
            'Process start postdates pyc compile (08:38:20) and source mtime by 5 months: the historical file was loaded, not rebuilt.',
            'Caveat: repo _archive copy is f7a3e9f1, a different object; served provenance established, repo provenance is not the same artifact.',
        ],
        'verdict': 'PASS',
        'statement': 'PASS for the served artifact (historical 13 May file, sha256 fad19d22, loaded by PID 15760). Flag: repo copy differs (f7a3e9f1).',
    },
]

POST_IDS = ['UI-ROUTE-09', 'UI-ROUTE-10', 'UI-ROUTE-12', 'UI-ROUTE-13', 'UI-ROUTE-16',
            'UI-ROUTE-17', 'UI-ROUTE-18', 'UI-ROUTE-19', 'UI-ROUTE-20', 'UI-ROUTE-21',
            'UI-ROUTE-28', 'UI-ROUTE-31', 'UI-ROUTE-32', 'UI-ROUTE-33', 'UI-ROUTE-34',
            'UI-ROUTE-35']

POST_NOTE = ('Declared in openapi.json and bound to a handler in the served source, but deliberately NOT '
             'exercised: each is a state-mutating write and this card forbids editing live engine state. '
             'Route existence is PASS-by-declaration; write-persistence behaviour is NOT_TESTED.')


def main():
    with open(ROUTE_JSON, 'r', encoding='utf-8') as fh:
        probe = json.load(fh)

    route_rows = []
    for r in probe['route_rows']:
        row = dict(r)
        if r['id'] in POST_IDS:
            row['verdict'] = 'NOT_TESTED'
            row['write_behaviour'] = POST_NOTE
        else:
            row['served_by'] = SERVED['pid']
            row['served_module_sha256'] = SERVED['sha256']
            if r['id'] == 'UI-ROUTE-07':
                row['content_note'] = 'body is [] (2 bytes) - route live, no copy trades yet for this wallet; existence verified, data emptiness recorded.'
        route_rows.append(row)

    out = {
        'card': 't_cfcad924',
        'title': 'UI-ROUTE + UI-TRUTH - 40 rows',
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'fixture': SERVED,
        'base_url': 'http://127.0.0.1:8023',
        'probe_method': 'Read-only HTTP GET from Python 3.11; POST routes never invoked.',
        'port_notes': {
            ':8023': 'USED - 13 May UI, populated data, 33 openapi paths',
            ':8031': 'NOT USED - serves b45ff9af, /live-copy 404',
            ':8035': 'NOT USED - one response, never verified as intended fixture',
        },
        'totals': {
            'rows': 40,
            'ui_route': 35,
            'ui_truth': 5,
            'route_pass': sum(1 for r in route_rows if r['verdict'] == 'PASS'),
            'route_fail': sum(1 for r in route_rows if r['verdict'] == 'FAIL'),
            'route_not_tested': sum(1 for r in route_rows if r['verdict'] == 'NOT_TESTED'),
            'truth_pass': sum(1 for r in TRUTH_ROWS if r['verdict'] == 'PASS'),
            'truth_fail': sum(1 for r in TRUTH_ROWS if r['verdict'] == 'FAIL'),
        },
        'route_rows': route_rows,
        'truth_rows': TRUTH_ROWS,
    }

    with open(ROUTE_JSON, 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=2)

    print(json.dumps(out['totals'], indent=2))
    for r in TRUTH_ROWS:
        print(r['id'], r['verdict'])


if __name__ == '__main__':
    main()
