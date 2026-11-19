#!/usr/bin/env python3
"""Batch 04: derived UI route behavior. Isolated temporary data; no network/orders."""
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"RESULT::{name}_{'PASS' if ok else 'FAIL'}" + (f" | {detail}" if not ok else ""))
def main():
    tmp = Path(tempfile.mkdtemp(prefix="uiroutes_batch04_", dir=os.environ.get("TMPDIR") or None))
    os.environ.update(HL_LIVE_AUDIT_DIR=str(tmp/'audit'), HL_LEADER_NETWORK='mainnet', HL_FOLLOWER_NETWORK='testnet')
    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient
    ui.DATA_DIR=tmp/'data'; ui.LIVE_COPY_AUDIT_DIR=tmp/'audit'; ui.LIVE_COPY_CONFIG_FILE=tmp/'audit'/'live_config.json'; ui.LIVE_CONFIG_FILE=ui.LIVE_COPY_CONFIG_FILE
    ui.WALLET_GATE_FILE=tmp/'wallet_gate.json'; ui.MODEL_DASHBOARD_LAST_GOOD_HTML_FILE=tmp/'absent.html'
    ui._model_dashboard_last_good_html_disk_get = lambda: '<html><title>Model dashboard sentinel</title></html>'
    ui._model_dashboard_html_cache_latest_get = lambda: None
    ui._model_cache_snapshot_nonblocking = lambda: ({}, 1e30)
    ui._kick_model_cache_refresh_background = lambda: False
    ui._load_live_copy_config=lambda: {"global_controls":{"send_mode":"CLOSE"},"auto_send_enabled":False}
    check('UI_ROUTE_05_GATE_ZERO', b'"wallet_gate_on_count":0' in ui.api_state().body)
    ui.WALLET_GATE_FILE.write_text(json.dumps({'0x'+'a'*40: {'mode':'ON'}}), encoding='utf-8')
    check('UI_ROUTE_05_GATE_NONZERO', b'"wallet_gate_on_count":1' in ui.api_state().body)
    ui._MODEL_CACHE.clear(); ui._MODEL_REFRESH_STATUS.clear(); ui._MODEL_DASHBOARD_HTML_CACHE.clear()
    check('UI_ROUTE_04_MODEL_STATE_ABSENT', b'"model_state_present":false' in ui.api_model_cache_status().body)
    ui._MODEL_CACHE['state']={'sentinel': 73}
    check('UI_ROUTE_04_MODEL_STATE_PRESENT', b'"model_state_present":true' in ui.api_model_cache_status().body)
    check('UI_ROUTE_04_DISK_HTML_ABSENT', b'"disk_html_present":false' in ui.api_model_cache_status().body)
    ui.MODEL_DASHBOARD_LAST_GOOD_HTML_FILE.write_text('<html>derived disk html</html>', encoding='utf-8')
    check('UI_ROUTE_04_DISK_HTML_PRESENT', b'"disk_html_present":true' in ui.api_model_cache_status().body)
    # Exercise the real implementation; global_controls must override auto_send_enabled.
    cases=[({'global_controls':{'send_mode':'OFF'},'auto_send_enabled':True},'OFF'),({'global_controls':{'send_mode':'CLOSE'},'auto_send_enabled':True},'CLOSE'),({'global_controls':{'send_mode':'ON'},'auto_send_enabled':False},'ON')]
    for i,(cfg,want) in enumerate(cases): check(f'UI_ROUTE_SEND_MODE_{want}', ui._send_mode(cfg)==want, f"got={ui._send_mode(cfg)}")
    # Root redirect and real page responses.
    client=TestClient(ui.app)
    r=client.get('/', follow_redirects=False)
    check('UI_ROUTE_ROOT_REDIRECT_307', r.status_code==307 and r.headers.get('location')=='/live-copy', f'{r.status_code} {r.headers.get("location")}')
    for route, marker in [('/model','Model dashboard sentinel'),('/legacy-model','Model dashboard sentinel')]:
        r=client.get(route); check('UI_ROUTE_PAGE_'+route.strip('/').replace('-','_').upper(), r.status_code==200 and marker.lower() in r.text.lower(), f'status={r.status_code}')
    # /live-copy: its static shell is only doctype/head/title, so the marker must prove the control panel itself rendered.
    panel=ui.render_live_copy_control_panel(); r=client.get('/live-copy')
    check('UI_ROUTE_PAGE_LIVE_COPY', r.status_code==200 and 'Live Copy Command Centre' in panel and 'id="liveCopyPanel"' in panel and panel in r.text, f'status={r.status_code} panel_len={len(panel)}')
    # Real handler, real clock: the miss must MEASURE a genuinely slow build and the hit must re-use that same figure.
    ui._AUDIT_SUMMARY_CACHE.clear()
    def slow_build():
        time.sleep(0.2)
        return {'exchange_snapshot_status':'derived'}
    ui._live_audit_summary=slow_build
    a=client.get('/api/live-audit-summary').json(); b=client.get('/api/live-audit-summary').json()
    check('UI_ROUTE_AUDIT_SUMMARY_CACHE_MISS', a.get('cache_hit') is False and float(a.get('build_seconds') or -1)>=0.15, str(a)[:250])
    check('UI_ROUTE_AUDIT_SUMMARY_CACHE_HIT', b.get('cache_hit') is True and b.get('build_seconds')==a.get('build_seconds'), str(b)[:250])
    r=client.get('/api/symbol-not-listed')
    check('UI_ROUTE_SYMBOL_NOT_LISTED_JSON', 'application/json' in r.headers.get('content-type','') and r.status_code==200, f'{r.status_code} {r.headers.get("content-type")}')
    # GET /api/ui-state: load_ui_state() repairs what the raw file holds, so assert the derived values, not the raw bytes.
    ui.UI_STATE_FILE=tmp/'ui_state.json'
    ui.UI_STATE_FILE.write_text(json.dumps({'norm_base':'42','copy_mode':'FIXED','ranking':{'column':'pnl','direction':'sideways'}}), encoding='utf-8')
    st=json.loads(ui.api_get_ui_state().body)
    check('UI_ROUTE_UI_STATE_DERIVED', st.get('copy_mode')=='fixed' and st.get('norm_base')==42.0 and st.get('ranking',{}).get('direction')=='desc', json.dumps(st)[:220])
    print('SKIP::GET /api/model-cache-status — covered by api_model_cache_status direct handler checks')
    print('SKIP::GET /api/state — covered by api_state direct handler checks')
    print('SKIP::GET /api/metrics — covered by batch02 api_metrics direct handler check')
    print('SKIP::GET /api/trades — covered by batch02 api_trades direct handler check')
    print('SKIP::GET /api/equity — covered by batch02 api_equity direct handler check')
    print('SKIP::GET /api/live-copy-summary — covered by batch02 get_live_copy_summary direct handler check')
    print('SKIP::GET /live-copy.json — covered by batch02 live_copy_dashboard_json direct handler check')
    print('SKIP::GET /api/global-controls — covered by batch02 get_global_controls direct handler check')
    print('SKIP::GET /api/live-ws-health — covered by batch02 get_live_ws_health direct handler check')
    print('SKIP::GET /api/live-config — covered by batch02 get_live_config direct handler check (UI_ROUTE_23_LIVE_CONFIG_ENABLED)')
    print('NOTE::GET /api/symbol-not-listed is not part of the live audit summary; it is checked separately above, so this is not a skip')
    failed=[n for n,ok in RESULTS if not ok]
    print('TOTAL=%d FAILED=%d'%(len(RESULTS),len(failed)))
    if failed: print('FAILED: '+', '.join(failed))
    return 1 if failed else 0
if __name__=='__main__': raise SystemExit(main())
