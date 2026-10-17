#!/usr/bin/env python3
'''Emit the structured 6-row results JSON from the raw probe capture.

Reads EVIDENCE/ui_lcc_detail_add/raw/ui_lcc_detail_add_probe.json (produced by
ui_lcc_detail_add_probe.py) and writes results/ui_lcc_detail_add_results.json.
Programmatic so the committed verdicts cite the EXACT captured values (engine
sha256, register blob sha256, dom facts, served-oracle freshness, on-disk
oracle staleness) rather than hand-transcription.
'''
import hashlib, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, '..', 'raw', 'ui_lcc_detail_add_probe.json')
OUT = os.path.join(HERE, '..', 'results', 'ui_lcc_detail_add_results.json')

DETAIL_ROUTE_MISSING = (
    "Read-only UI-control-interaction capture of the per-wallet DETAIL modal "
    "(click a wallet row -> open DETAIL sections B/C/D) and read its cells; "
    "the 36d1c52 landing-render route does not click. The certified read-only "
    "detail-capture harness proven for sibling DETAIL-01 (t_0ff26004: wallet-row "
    "click + served-API field match) is the concrete route to convert these rows "
    "to PASS/PARTIAL. Plus a fresh independent per-wallet exchange position/fill/"
    "attribution oracle (on-disk exchange_account_snapshot_app.json is ~12.4h stale)."
)
ADD_ROUTE_MISSING = (
    "Sanctioned non-mutating write-wire capture of POST /api/live-config/add-wallet "
    "(page.route intercept) to verify (a) field -> live_config.json persistence and "
    "(b) invalid-input -> visible error. Forbidden by the fully-READ-ONLY route, the "
    "CERT_ENVIRONMENT (no served-config write), OD-07/OD-10, and wallets disabled "
    "(auto_send_enabled=false; WALLES_ENABLED=0). The add-wallet modal fields "
    "(Leader equity base is type=hidden per register source line 5780; Max diff %; "
    "Submit) are not rendered on the landing. The on-disk live_config.json is a stale "
    "13-day fixture (0xdddddd placeholder), not the live engine config."
)


def main():
    raw = json.load(open(RAW, encoding='utf-8'))
    dom = raw['dom']
    s = raw['api_live_copy_summary_trim']
    ec = s.get('exchange_account_snapshot') or {}
    odc = raw['oracle_exchange_snapshot_file']
    olc = raw['oracle_live_config_file']
    reg = raw['register_rows']

    dom_facts = {
        "route": dom.get('route'),
        "http_status": dom.get('http_status'),
        "panel_present": dom.get('panel_present'),
        "dom_element_count": dom.get('dom_element_count'),
        "page_body_len": dom.get('page_body_len'),
        "keywords_true": [k for k, v in dom.get('keyword_hits', {}).items() if v],
        "keywords_absent_from_landing": [k for k, v in dom.get('keyword_hits', {}).items() if not v
                                         and k in ('Lead vs Copy', 'Friction', 'Execution Audit',
                                                   'Leader equity', 'Max diff', 'Submit', 'uPnL',
                                                   'Stale', 'Unavailable', 'Error')],
        "pills_present": dom.get('pills', [])[:30],
        "greenred_classed_elements": len(dom.get('greenred', [])),
    }

    served_facts = {
        "http": raw['api_live_copy_summary']['http'],
        "tracked_wallet_count": s.get('tracked_wallet_count'),
        "owned_copy_positions_count": s.get('owned_copy_positions_count'),
        "exchange_account_snapshot": {
            "updated_at": ec.get('updated_at'), "account_value": ec.get('account_value'),
            "account_value_source": ec.get('account_value_source'), "age_ms": ec.get('age_ms'),
        },
        "status_banner_health": (s.get('status_banner') or {}).get('health_level'),
        "status_banner_text": (s.get('status_banner') or {}).get('health_text'),
        "sending": (s.get('status_banner') or {}).get('sending'),
        "live_wallets": (s.get('status_banner') or {}).get('live_wallets'),
        "last_fill": (s.get('execution_quality_summary') or {}).get('last_fill'),
    }

    oracle_facts = {
        "served_api_fresh": served_facts['exchange_account_snapshot'],
        "on_disk_independent_snapshot": {
            "path": odc.get('path'), "updated_at": odc.get('updated_at'),
            "age_ms": odc.get('age_ms'), "sha256": odc.get('sha256'),
        },
        "on_disk_live_config_fixture": {
            "path": olc.get('path'), "mtime": olc.get('mtime'),
            "sha256": olc.get('sha256'),
            "wallet_count": len((olc.get('body') or {}).get('wallets', {})),
        },
    }

    targets = [
        ('UI-LCC-DETAIL-02', 'Wallet detail section: B Open Positions (Coin/Side/Size/Entry/Mark/uPnL/Exposure/Exchange match)',
         "Landing renders OPEN POSITIONS 131 + per-wallet coin position list (e.g. 'shared 0G shared AAVE...') + per-wallet Exposure/Open-pos/LAST FILL. The per-wallet DETAIL modal B=Open Positions table (Coin/Side/Size/Entry/Mark/uPnL/Exposure/Exchange-match cells) is opened by clicking a wallet row; 'uPnL' keyword is ABSENT from the landing, so the full detail table is not rendered. Served owned_copy_positions (414, fresh) has coin/side/signed_size/avg_entry_px/mark_px but not uPnL/Exchange-match (unrealized_pnl=None, position_value=None) and is the engine copy-ledger, not an independent exchange oracle; on-disk independent oracle ~12.4h stale.",
         DETAIL_ROUTE_MISSING,
         "Surface renders an open-positions summary (count + coin list + exposure), not the full per-wallet detail table. No PASS claimed. No mutation."),
        ('UI-LCC-DETAIL-03', 'Wallet detail section: C Lead vs Copy / Friction',
         "Landing renders the wallet-TABLE 'LEAD<->COPY DIFF' column + 'Avg bps'/'Worst bps' + 'N filled / N recent rejects' (execution-quality summary). The detail C-section ('Lead vs Copy'/'Friction') is in the per-wallet DETAIL modal (wallet-row click). Keywords 'Lead vs Copy' and 'Friction' are ABSENT from the landing. Independent oracle stale.",
         DETAIL_ROUTE_MISSING,
         "Surface renders lead<->copy diff + friction/bps aggregates, not the per-wallet C-section detail. No PASS claimed. No mutation."),
        ('UI-LCC-DETAIL-04', 'Wallet detail section: D Execution Audit',
         "Landing renders 'EXECUTION' column + 'LAST FILL' + 'LAST REJECT ... INSUFFICIENT_MARGIN' + 'LAST LATENCY WARNING severity=CRITICAL delay_ms=6947' + 'Technical detail'. The detail D-section ('Execution Audit') is in the per-wallet DETAIL modal (wallet-row click). Keyword 'Execution Audit' is ABSENT from the landing. Independent oracle stale.",
         DETAIL_ROUTE_MISSING,
         "Surface renders last-fill/last-reject/latency/execution summary, not the per-wallet D-section Execution Audit detail. No PASS claimed. No mutation."),
        ('UI-LCC-ADD-06', 'Add-wallet modal field: Leader equity base',
         "Landing renders the 'Add wallet' button only; 'Leader equity' is ABSENT. Per register UI source @ b142cf88 (sha256 7468ab51...), the leader_equity_base input is type=hidden (source line 5780). Verifying persistence to live_config.json requires POST /api/live-config/add-wallet (mutation), forbidden. On-disk live_config.json is a 13-day stale fixture (0xdddddd placeholder), not the live config (15 wallets served via /api/live-config).",
         ADD_ROUTE_MISSING,
         "No PASS claimed. No live configuration was mutated. Constrained by OD-07/OD-10 + wallets disabled (auto_send_enabled=false)."),
        ('UI-LCC-ADD-07', 'Add-wallet modal field: Max diff %',
         "Landing renders the 'Add wallet' button only; 'Max diff' is ABSENT. Add-wallet modal field requires opening the modal (control interaction) + POST /api/live-config/add-wallet for persistence (mutation, forbidden)." ,
         ADD_ROUTE_MISSING,
         "No PASS claimed. No live configuration was mutated. Constrained by OD-07/OD-10 + wallets disabled."),
        ('UI-LCC-ADD-10', 'Add-wallet modal field: Add wallet submit',
         "Landing renders the 'Add wallet' button only; 'Submit' is ABSENT. Submit == POST /api/live-config/add-wallet (mutation), forbidden by the fully-READ-ONLY route and the CERT_ENVIRONMENT (no served-config write); OD-07/OD-10 unresolved and wallets disabled.",
         ADD_ROUTE_MISSING,
         "No PASS claimed. No live configuration was mutated. Constrained by OD-07/OD-10 + wallets disabled (auto_send_enabled=false)."),
    ]

    rows = []
    for tid, feature, basis, missing, note in targets:
        rr = reg.get(tid, {})
        rows.append({
            "id": tid,
            "feature": feature,
            "register_result_at_b142cf88": rr.get('result'),
            "applicability": rr.get('applicability'),
            "result": "NOT_TESTED",
            "execution_proof": basis,
            "independent_oracle": ("EXECUTED (mixed freshness): served /api exchange_account_snapshot is "
                                   "FRESH (" + str(ec.get('age_ms')) + " ms old, account_value=" + str(ec.get('account_value')) + "); "
                                   "on-disk exchange_account_snapshot_app.json is the independent app-owned snapshot but is STALE ("
                                   + str(odc.get('age_ms')) + " ms, updated " + str(odc.get('updated_at')) + "). "
                                   "No engine/UI import was used as an oracle."),
            "negative_tests": "NOT EXECUTED: the route is landing-render only; 'source unavailable / stale-flag / API-error' states are not triggered (would require control interaction / fault injection / mutation).",
            "exact_missing_route": missing,
            "notes": note,
        })

    artifact = {
        "task_id": "t_e2602f28",
        "title": "B3-CERT UI-LCC DETAIL-02..04 + ADD-06/07/10 (6 rows) - re-probe with proven DOM route",
        "register_of_record": "git show b142cf88:certification/certification_matrix.json",
        "register_commit": "b142cf88d389e791160f691aac3d936852b99975",
        "register_blob_sha256": raw.get('register_blob_sha256'),
        "engine_sha256": raw.get('engine_sha256'),
        "tested_at_utc": raw.get('tested_at_utc'),
        "tested_commit": "b142cf88d389e791160f691aac3d936852b99975",
        "route": raw.get('route'),
        "two_run_control": raw.get('two_run_control'),
        "dom": dom_facts,
        "served_api_fresh": served_facts,
        "oracle": oracle_facts,
        "api_live_config": {'http': raw.get('api_live_config', {}).get('http'), 'wallets_count': raw.get('api_live_config_trim', {}).get('wallets_count'), 'auto_send_enabled': raw.get('api_live_config_trim', {}).get('auto_send_enabled')},
        "rows": rows,
        "status": "NOT_TESTED_ALL_ROWS",
        "raw_capture_sha256": hashlib.sha256(open(RAW, 'rb').read()).hexdigest(),
        "raw_capture_bytes": os.path.getsize(RAW),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False, default=str)
    print('WROTE', OUT)
    print('rows:', [(r['id'], r['result']) for r in rows])
    print('dom:', dom_facts['route'], dom_facts['http_status'], 'present:', dom_facts['panel_present'])
    print('served snap age_ms:', ec.get('age_ms'), 'ondisk age_ms:', odc.get('age_ms'))
    print('raw_capture_sha256:', artifact['raw_capture_sha256'], 'bytes:', artifact['raw_capture_bytes'])
    return 0


if __name__ == '__main__':
    main()
