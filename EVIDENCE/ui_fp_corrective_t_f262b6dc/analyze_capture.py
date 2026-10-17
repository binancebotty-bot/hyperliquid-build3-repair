#!/usr/bin/env python3
"""Deterministic comparisons over the committed runtime capture; no service writes."""
import json
from pathlib import Path
ROOT = Path(__file__).parent
CAPTURE = ROOT / 'dom_capture.json'
OUT = ROOT / 'UI_FP_CORRECTIVE_t_f262b6dc.json'
SERVING_COMMIT = '6cf5dcf671b791e8f833060458f00cb7bb7bcdb5'
SERVING_SSOT_SHA256 = '658ec8e31eb96d70acc15dc30860334c23612d2e3e9d19fb63ed9ec4e6fa86c2'
def main():
    c=json.loads(CAPTURE.read_text(encoding='utf-8'))
    dom=c.get('dom',{})
    ui={x.get('id'):x.get('value') for x in dom.get('input_select_values',[]) if x.get('id')}
    api=c.get('api_api_live-config',{}).get('body',{}).get('config',{})
    gc=api.get('global_controls',{})
    ui_state=c.get('api_api_ui-state',{}).get('body',{})
    wallets=api.get('wallets',{})
    wallet_rows=dom.get('wallet_rows',[])
    dom_modes=[x.get('copy_mode') for x in wallet_rows]
    api_modes=[v.get('copy_mode') for v in wallets.values()]
    allow_ui=[s.strip() for s in (ui.get('gcAllowlist') or '').split(',') if s.strip()]
    block_ui=[s.strip() for s in (ui.get('gcBlocklist') or '').split(',') if s.strip()]
    dom_mode_map={str(x.get('wallet','')).lower():x.get('copy_mode') for x in wallet_rows}
    api_mode_map={str(k).lower():v.get('copy_mode') for k,v in wallets.items()}
    mode_match=(len(dom_mode_map)==len(api_mode_map)==15 and dom_mode_map==api_mode_map and all(v is not None for v in dom_mode_map.values()))
    checks={
      'UI-FP-184': (float(ui['gcMktPct'])*100 == float(gc['marketable_bps']), f"UI gcMktPct={ui['gcMktPct']}%; API marketable_bps={gc['marketable_bps']} bps; 100*bps conversion checked"),
      'UI-FP-185': (float(ui['gcCloseAdv']) == float(gc['max_close_adverse_diff_pct']), f"UI gcCloseAdv={ui['gcCloseAdv']}%; API max_close_adverse_diff_pct={gc['max_close_adverse_diff_pct']}%"),
      'UI-FP-186': (allow_ui == gc['symbol_allowlist'], f"UI gcAllowlist={allow_ui}; API symbol_allowlist={gc['symbol_allowlist']}"),
      'UI-FP-187': (block_ui == gc['symbol_blocklist'], f"OBSERVED UI gcBlocklist={block_ui}; API symbol_blocklist={gc['symbol_blocklist']}"),
      'UI-FP-190': (mode_match, f"15 DOM wallet rows copy_mode values={sorted(set(dom_modes))}; API wallet copy_mode values={sorted(set(api_modes))}; DOM/API wallet-key maps equal={dom_mode_map==api_mode_map}; count DOM={len(dom_mode_map)} API={len(api_mode_map)}"),
    }
    records=[]
    for row,(match,obs) in checks.items():
        records.append({'row_id':row,'verdict':'PARTIAL' if match else 'FAIL','serving_commit':SERVING_COMMIT,'serving_ssot_sha256':SERVING_SSOT_SHA256,'executed_probe':'python EVIDENCE/ui_fp_corrective_t_f262b6dc/probe.py; python EVIDENCE/ui_fp_corrective_t_f262b6dc/analyze_capture.py','independent_oracle':'Read-only GET of /api/live-config and /api/ui-state, compared in analyze_capture.py to live rendered Chromium DOM; no HL_Copy_App_SSOT.py import. Values can falsify the predicate.','observed':obs+'; DOM/raw API capture: EVIDENCE/ui_fp_corrective_t_f262b6dc/dom_capture.json','reproduces':'Set PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright; run C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe EVIDENCE/ui_fp_corrective_t_f262b6dc/probe.py && C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe EVIDENCE/ui_fp_corrective_t_f262b6dc/analyze_capture.py','predicate_result':'UI/API equality '+('observed' if match else 'mismatch')+'; persistence/execution-truth POST leg deliberately not tested under READ-ONLY mandate.'})
    # min_notional is not the wallet fixed_notional field; do not conflate them.
    min_api=gc.get('min_notional',None)
    min_ui=[x for x in dom.get('input_select_values',[]) if x.get('name')=='min_notional' or x.get('id')=='min_notional']
    records.append({'row_id':'UI-FP-192','verdict':'NOT_TESTED','serving_commit':SERVING_COMMIT,'serving_ssot_sha256':SERVING_SSOT_SHA256,'executed_probe':'python EVIDENCE/ui_fp_corrective_t_f262b6dc/probe.py; python EVIDENCE/ui_fp_corrective_t_f262b6dc/analyze_capture.py','independent_oracle':'Read-only rendered DOM plus GET /api/live-config and /api/ui-state; neither includes a min_notional field.','observed':f"min_notional UI control(s)={min_ui}; API global_controls.min_notional={min_api}. Distinct field fixed_notional is observed as 12 per wallet in UI and API; it is not treated as min_notional. Missing: a defined/directly served min_notional UI/API field or explicit mapping oracle. Raw capture: EVIDENCE/ui_fp_corrective_t_f262b6dc/dom_capture.json",'reproduces':'Set PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright; run C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe EVIDENCE/ui_fp_corrective_t_f262b6dc/probe.py && C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe EVIDENCE/ui_fp_corrective_t_f262b6dc/analyze_capture.py','predicate_result':'NOT_TESTED: no directly observed min_notional UI/API value; do not infer from fixed_notional.'})
    artifact={'card_id':'t_f262b6dc','serving_commit':SERVING_COMMIT,'serving_ssot_sha256':SERVING_SSOT_SHA256,'how_serving_build_was_established':'Measured in serving checkout C:/Users/wigmore/trading_stack/hl-build3-testnet-cert: git rev-parse HEAD => 6cf5dcf671b791e8f833060458f00cb7bb7bcdb5; sha256sum _archive/hl_stage2/HL_Copy_App_SSOT.py => 658ec8e31eb96d70acc15dc30860334c23612d2e3e9d19fb63ed9ec4e6fa86c2. This was measured independently of the register branch.', 'oracle':'Independent read-only live endpoints /api/live-config and /api/ui-state, compared against headless Chromium rendered DOM at http://127.0.0.1:8031/live-copy; probe does not import the engine module.', 'files':['EVIDENCE/ui_fp_corrective_t_f262b6dc/probe.py','EVIDENCE/ui_fp_corrective_t_f262b6dc/dom_capture.json','EVIDENCE/ui_fp_corrective_t_f262b6dc/analyze_capture.py'],'rows':records}
    OUT.write_text(json.dumps(artifact,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'artifact':str(OUT),'row_count':len(records),'verdicts':{r['row_id']:r['verdict'] for r in records}},indent=2))
if __name__=='__main__': main()
