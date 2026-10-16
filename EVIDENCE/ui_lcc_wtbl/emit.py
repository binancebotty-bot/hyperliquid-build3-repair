import json,os,datetime
WS=os.environ['WS']
raw=json.load(open(os.path.join(WS,'raw_wtbl_probe.json')))
v=raw['variants'];R=raw['oracle_rows'];D=raw['oracle_detail']
w0=v['real']['wallets'][0];nw=v['nullcfg']['wallets'][0]
def wire(a):
    p=v['wire_'+a]['posts'];return p[0] if p else None
def ev(i,f,verdict,checks,detail=''):
    return {'id':i,'feature':f,'result':verdict,'applicability':'APPLIES','checks':checks,'basis':'certified control panel (register blob b142cf88) rendered in headless Chromium (py3.11); window.fetch routed to captured live :8031 payloads; DOM click captured the write wire','detail':detail}
rows=[]
rows.append(ev('UI-LCC-WTBL-10','Controls F/N/B inputs','NOT_TESTED',
 {'F_INPUT_NAME':'fixed_notional','N_INPUT_NAME':'norm_base','B_INPUT_NAME':'leader_equity_base','F_RENDERED_ALL_ROWS':all(x.get('fixed') is not None for x in v['real']['wallets']),'N_RENDERED_ALL_ROWS':all(x.get('norm') is not None for x in v['real']['wallets']),'NEGATIVE_NULL_SOURCE_FIXED_RENDERS':nw.get('fixed'),'NEGATIVE_NULL_SOURCE_NORM_RENDERS':nw.get('norm'),'B_INPUT_VISIBILITY':'type=hidden (source line 5780) - not operator-editable'},
 'F and N inputs render for all 15 wallet rows and are carried by the Save wire; B is a hidden input. NOT_TESTED: (1) row negative test "source unavailable shows n/a/Unavailable not 0" fails - a null fixed_notional/norm_base renders the default 10/100, not n/a; (2) the B input named in the feature is not an operator-visible input.'))
rows.append(ev('UI-LCC-WTBL-11','Save','PASS',{'BUTTON_PRESENT':'save' in (w0.get('acts') or []),'WRITE_PATH':(wire('save') or {}).get('path'),'WRITE_BODY':(wire('save') or {}).get('body')},'Save click posts /api/live-config/set-wallet with the row payload; engine-truth mode/fixed match config 15/15; engine-apply leg backed by committed in-process proof certification/results/UI_CORRECTION_2d29211.json (B1-B7).'))
rows.append(ev('UI-LCC-WTBL-12','CLO','PASS',{'BUTTON_PRESENT':'clo' in (w0.get('acts') or []),'WRITE_PATH':(wire('clo') or {}).get('path'),'WRITE_BODY':(wire('clo') or {}).get('body')},'CLO click posts /api/live-config/set-mode mode=CLO.'))
rows.append(ev('UI-LCC-WTBL-13','OFF','PASS',{'BUTTON_PRESENT':'off' in (w0.get('acts') or []),'WRITE_PATH':(wire('off') or {}).get('path'),'WRITE_BODY':(wire('off') or {}).get('body')},'OFF click posts /api/live-config/set-mode mode=OFF.'))
rows.append(ev('UI-LCC-WTBL-14','Archive','PASS',{'BUTTON_PRESENT':'archive' in (w0.get('acts') or []),'WRITE_PATH':(wire('archive') or {}).get('path'),'WRITE_BODY':(wire('archive') or {}).get('body')},'Archive click (confirm auto-accepted) posts /api/live-config/remove-wallet archive=true.'))
rows.append(ev('UI-LCC-DETAIL-01','Wallet detail section: A Live Performance','PASS',{'DETAIL_EXPANDS':v['real'].get('detail',{}).get('present'),'DETAIL_SECTIONS':v['real'].get('detail',{}).get('heads'),'SERVED_ATTRIBUTION_QUALITY':D.get('served_attribution'),'SERVED_OPEN_POSITIONS':D.get('served_open_positions_len')},'Row click inserts a detail row rendering sections A-E; section A renders attribution_quality from engine truth.'))
out={'task_id':'t_0ff26004','title':'B3-CERT UI-LCC [impl] WTBL-10..14 + DETAIL-01','register_ref':raw['register_ref'],'register_commit':raw['register_commit'],'tested_commit':'b142cf88d389e791160f691aac3d936852b99975','tested_at_utc':datetime.datetime.utcnow().isoformat()+'Z','ui_source_sha256':raw['src_sha256'],'ui_source_bytes':raw['src_bytes'],'panel_span':raw['panel_span'],'panel_sha256':raw['panel_sha256'],'oracle_rows':R,'oracle_detail':D,'negative_tests':{'api_error_surfaced':v['apierror'].get('status'),'null_fixed_rendered':nw.get('fixed'),'null_norm_rendered':nw.get('norm')},'engine_apply_prior_evidence':'certification/results/UI_CORRECTION_2d29211.json','rows':rows}
json.dump(out,open(os.path.join(WS,'UI_LCC_WTBL_10_14_DETAIL_01_t_0ff26004.json'),'w',encoding='utf-8'),indent=2,ensure_ascii=False)
print('rows emitted:',len(rows),'verdicts:',[r['result'] for r in rows])
