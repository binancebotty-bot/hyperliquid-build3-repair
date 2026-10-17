import json, urllib.request, urllib.error, datetime
base='http://127.0.0.1:8031'
wallet='0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205'
paths={
'UI-SSOT-PAGE-03':'/api/state','UI-SSOT-PAGE-04':'/api/metrics',
'UI-SSOT-PAGE-05':f'/api/trades/{wallet}','UI-SSOT-PAGE-06':f'/api/equity/{wallet}',
'UI-SSOT-PAGE-07':'/api/ui-state','UI-SSOT-PAGE-08':'/api/norm',
'UI-SSOT-PAGE-09':'/api/reset-app-history','UI-SSOT-PAGE-10':'/api/snapshot',
'UI-SSOT-PAGE-11':'/api/live-config','UI-SSOT-PAGE-12':'/api/global-controls',
'UI-SSOT-PAGE-13':'/api/live-ws-health','UI-SSOT-PAGE-14':'/api/live-audit-summary',
'UI-SSOT-PAGE-15':'/', 'UI-TRUTH-001':'/live-copy','UI-TRUTH-002':'/live-copy'}
results=[]
for row,path in paths.items():
 try:
  req=urllib.request.Request(base+path,headers={'User-Agent':'UI19-readonly-probe/1'})
  with urllib.request.urlopen(req,timeout=20) as r:
   raw=r.read(); text=raw.decode('utf-8','replace')
   try: body=json.loads(text); shape=sorted(body.keys()) if isinstance(body,dict) else f'list:{len(body)}'
   except Exception: body=None; shape='html/text'
   results.append({'row_id':row,'path':path,'status':r.status,'content_type':r.headers.get('Content-Type'),'bytes':len(raw),'shape':shape,'body_preview':text[:400]})
 except urllib.error.HTTPError as e:
  raw=e.read(); results.append({'row_id':row,'path':path,'status':e.code,'body_preview':raw[:400].decode('utf-8','replace')})
 except Exception as e: results.append({'row_id':row,'path':path,'error':type(e).__name__+': '+str(e)})
out={'captured_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'base':base,'method':'GET only; no state mutation','tested_commit':'89b3bc7586bf328df336fc9ea721cee212617762','results':results}
with open('EVIDENCE/UI19_probe.json','w',encoding='utf-8') as f: json.dump(out,f,indent=2)
print(json.dumps(out,indent=2))
