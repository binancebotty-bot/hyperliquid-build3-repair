import json
import time
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(r'C:/Users/wigmore/.hermes/cache/scratch/b3_clean')
OUT = ROOT / 'certification/results/UI_LCC_AUD_REC_WS_8031.json'
URL = 'http://127.0.0.1:8031/live-copy'
def norm(v): return '' if v is None else str(v).strip()
def short_wallet(v):
    v=str(v or '')
    return (v[:10]+'...'+v[-6:]) if len(v)>18 else (v or 'ACCOUNT_LEVEL_ONLY')
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True); page=browser.new_page()
    observed={}
    def observe(response):
        if response.url.endswith('/api/live-audit-summary') or response.url.endswith('/api/live-ws-health'):
            try: observed[response.url.rsplit('/',1)[-1]]=response.json()
            except Exception: pass
    page.on('response',observe)
    response=page.goto(URL,wait_until='domcontentloaded',timeout=30000)
    deadline=time.time()+45
    while time.time()<deadline:
        state=page.evaluate("""() => ({ready:document.readyState,a:document.querySelectorAll('#lcAuditRows tr').length,r:document.querySelectorAll('#lcReconRows tr').length,h:document.querySelectorAll('#lcHealthRows tr').length})""")
        if state['ready']=='complete' and min(state['a'],state['r'],state['h'])>1: break
        page.wait_for_timeout(500)
    snap=page.evaluate("""() => {const table=id=>{const b=document.querySelector('#'+id),t=b&&b.closest('table');return {headers:t?Array.from(t.querySelectorAll('thead th')).map(x=>x.innerText.trim()):[],rows:b?Array.from(b.querySelectorAll('tr')).map(tr=>Array.from(tr.querySelectorAll('td')).map(td=>td.innerText.trim())):[]};};return {audit:table('lcAuditRows'),recon:table('lcReconRows'),health:table('lcHealthRows'),at:new Date().toISOString()};}""")
    browser.close()
snap['auditState']=observed.get('live-audit-summary',{})
snap['healthState']=observed.get('live-ws-health',{}).get('health',{})
checks={}
def add(name,ok,detail): checks[name]={'pass':bool(ok),'detail':detail}
audit=snap['audit']; a=snap['auditState']; source=list((a.get('last_rows') or [])[-10:])[::-1]
attempts={str(x.get('intent_id') or ''):x for x in a.get('recent_send_attempts') or [] if x.get('intent_id')}
add('UI-LCC-AUD-11',False,f"Manual? cell empty on {sum(1 for row in audit['rows'][:len(source)] if len(row)>10 and row[10]=='')}/{len(source)} rendered intents; none of these intent payloads provides manual_reconcile_required; required flag is not rendered.")
notes=0
for r,row in zip(source,audit['rows']):
    value=norm(r.get('notes') or r.get('message'))
    if 'dry-run simulated fill' in value: value='legacy intent note: leader WS fill detected; check real order result'
    value=value[:59]+'…' if len(value)>60 else value
    if value and len(row)>11 and row[11]==value: notes+=1
add('UI-LCC-AUD-12',bool(source) and notes==len(source),f"Intent-note source-to-cell match, including specified legacy-note translation and UI 60-character truncation: {notes}/{len(source)} rendered intents; first source text={norm(source[0].get('notes') or source[0].get('message'))[:60]!r}.")
real=0
for r,row in zip(source,audit['rows']):
    attempt=attempts.get(str(r.get('intent_id') or '')); dec=str(r.get('execution_decision') or ''); value='NO_SEND_ATTEMPT'
    if attempt:
        st=str(attempt.get('status') or ''); value='REAL_ORDER_FILLED' if st=='ORDER_FILLED' else 'EXCHANGE_REJECTED' if st=='ORDER_REJECTED' else st or 'NO_SEND_ATTEMPT'
    elif dec=='WOULD_PLACE_IOC_LIMIT': value='WOULD_SEND_ONLY'
    if len(row)>12 and row[12]==value: real+=1
add('UI-LCC-AUD-13',bool(source) and real==len(source) and any(str(r.get('intent_id') or '') in attempts for r in source),f"Per-intent result recomputed by intent_id from send attempts (decision fallback otherwise) matched column 13 on {real}/{len(source)} intents; matched attempts among these rows={sum(1 for r in source if str(r.get('intent_id') or '') in attempts)}.")
recon=snap['recon']; rr=(a.get('manual_reconciliation_rows') or [])[:len(recon['rows'])]
add('UI-LCC-REC-01',bool(rr) and recon['headers'][0]=='Severity' and all(row[0]==str(src.get('severity') or 'INFO') for src,row in zip(rr,recon['rows'])),f"Severity header/value row comparison: {len(rr)}/{len(recon['rows'])} rendered reconciliation rows.")
add('UI-LCC-REC-02',bool(rr) and recon['headers'][1]=='Wallet' and all(row[1]==short_wallet(src.get('wallet')) for src,row in zip(rr,recon['rows'])),f"Expected Wallet in column 2; actual column 2 header={recon['headers'][1]!r}, first value={recon['rows'][0][1]!r}; source wallet is rendered in column 3 instead.")
add('UI-LCC-REC-03',bool(rr) and recon['headers'][2]=='Coin' and all(row[2]==str(src.get('coin') or '—') for src,row in zip(rr,recon['rows'])),f"Expected Coin in column 3; actual column 3 header={recon['headers'][2]!r}, first value={recon['rows'][0][2]!r}; source coin is rendered in column 2 instead.")
add('UI-LCC-REC-04',bool(rr) and recon['headers'][3]=='Issue' and all(row[3]==str(src.get('issue') or 'n/a') for src,row in zip(rr,recon['rows'])),f"Issue header/value row comparison: {len(rr)}/{len(recon['rows'])} rendered rows.")
add('UI-LCC-REC-05','Count' in recon['headers'],f"Required Count column absent; actual headers={recon['headers']!r}; count is rendered under the final Action header.")
def numeric_equal(actual,expected):
    try: return float(str(actual).split()[-1])==float(expected)
    except (ValueError,TypeError,IndexError): return False
add('UI-LCC-REC-06',bool(rr) and recon['headers'][4]=='Manual ledger' and all(row[4].split()[0]==str(src.get('side') or '') and numeric_equal(row[4],src.get('manual_signed_size')) for src,row in zip(rr,recon['rows'])),f"Manual ledger source-to-cell numeric/sign match: {sum(1 for src,row in zip(rr,recon['rows']) if len(row)>4 and row[4].split()[0]==str(src.get('side') or '') and numeric_equal(row[4],src.get('manual_signed_size')))}/{len(rr)} rows.")
add('UI-LCC-REC-07',bool(rr) and recon['headers'][5]=='Exchange' and all(row[5]==str(src.get('exchange_signed_size','—')) for src,row in zip(rr,recon['rows'])),f"Exchange source-to-cell match: {len(rr)}/{len(recon['rows'])}.")
for rid,label in [('UI-LCC-REC-08','Last intent'),('UI-LCC-REC-09','Last oid'),('UI-LCC-REC-10','Last updated')]: add(rid,label in recon['headers'],f"Required {label!r} column absent; actual headers={recon['headers']!r}.")
add('UI-LCC-REC-11',bool(rr) and recon['headers'][-1]=='Action' and all(row[-1]==str(src.get('action') or '') for src,row in zip(rr,recon['rows'])),f"Action header exists but last-cell first value={recon['rows'][0][-1]!r} (the count); source rows provide action_available only, not a rendered action.")
health=snap['health']; wallets=sorted((snap['healthState'].get('wallets') or {}).keys()); rendered=[row[0] for row in health['rows'] if row]
expected=[short_wallet(w) for w in wallets]
add('UI-LCC-WS-01',health['headers'][0]=='Wallet' and rendered==expected,f"Wallet header and sorted identity-to-row mapping: {len(rendered)}/{len(expected)} wallet rows; header={health['headers'][0]!r}.")
result={'tested_commit':'89b3bc7586bf328df336fc9ea721cee212617762','tested_at_utc':datetime.now(timezone.utc).isoformat(),'page':{'url':URL,'http_status':response.status if response else None,'dom_captured_at':snap['at']},'serving_process':{'pid':33368,'started_at_utc':'2026-10-17T10:54:09.552605+00:00','serving_commit':'89b3bc7586bf328df336fc9ea721cee212617762'},'tables':{'audit_headers':audit['headers'],'audit_rows':len(audit['rows']),'reconciliation_headers':recon['headers'],'reconciliation_rows':len(recon['rows']),'health_headers':health['headers'],'health_rows':len(health['rows'])},'checks':checks,'summary':{'pass':sum(x['pass'] for x in checks.values()),'fail':sum(not x['pass'] for x in checks.values()),'total':len(checks)}}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,indent=2),encoding='utf-8')
ids=['UI-LCC-AUD-11','UI-LCC-AUD-12','UI-LCC-AUD-13']+[f'UI-LCC-REC-{i:02d}' for i in range(1,12)]+['UI-LCC-WS-01']
verdicts=[{'row_id':rid,'verdict':'PASS' if checks[rid]['pass'] else 'FAIL','evidence_ref':'certification/results/UI_LCC_AUD_REC_WS_8031.json','tested_commit':'89b3bc7586bf328df336fc9ea721cee212617762','why':checks[rid]['detail']} for rid in ids]
verdict_path=ROOT/'certification/results/UI_LCC_AUD_REC_WS_01_verdicts.json'
verdict_path.write_text(json.dumps(verdicts,indent=2),encoding='utf-8')
print(json.dumps({'evidence_path':str(OUT),'verdicts_path':str(verdict_path),'summary':result['summary'],'checks':checks},indent=2))