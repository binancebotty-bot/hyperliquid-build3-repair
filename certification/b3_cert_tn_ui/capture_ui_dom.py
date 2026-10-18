'''Serving-build-bound rendered-DOM capture for B3 UI-FP rows. Read-only; safe to re-run.'''
import hashlib, json, os, re, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
import psutil
OUT=os.path.dirname(os.path.abspath(__file__)); PORT=8031; BASE=f'http://127.0.0.1:{PORT}'
CHROME='C:/Program Files/Google/Chrome/Application/chrome.exe'
def get(url,timeout=20):
    with urllib.request.urlopen(url,timeout=timeout) as r: return r.read()
def gj(url,timeout=30): return json.loads(get(url,timeout).decode('utf-8'))
def listener(port):
    for line in subprocess.run(['netstat','-ano'],capture_output=True,text=True).stdout.splitlines():
        p=line.split()
        if len(p)>=5 and p[0].upper()=='TCP' and p[3]=='LISTENING' and p[1].endswith(f':{port}'): return int(p[4])
def proc_info(pid):
    p=psutil.Process(pid); cwd=p.cwd(); cmd=p.cmdline(); started=p.create_time()
    script=next((a for a in cmd[1:] if a.lower().endswith('.py')),None)
    path=os.path.join(cwd,script) if script else None
    d={'pid':pid,'cwd':cwd,'cmdline':cmd,'start_local':datetime.fromtimestamp(started).astimezone().isoformat(),'start_ms':int(started*1000),'script_path':path}
    if path and os.path.exists(path):
        d['size']=os.path.getsize(path); d['mtime_local']=datetime.fromtimestamp(os.path.getmtime(path)).astimezone().isoformat()
        raw=open(path,'rb').read(); d['sha256_lf']=hashlib.sha256(raw).hexdigest()
        src=raw.decode('utf-8','replace'); d['lines']=src.count('\n')+1
        d['has_lcHealthRows']='lcHealthRows' in src; d['has_leader_equity_base']='leader_equity_base' in src
        d['has_reconnects_per_min']='reconnects_per_min' in src; d['has_thread_alive']='thread_alive' in src
    return d
def dom_dump(url,wait=6):
    prof=os.path.join(OUT,'_chrome_profile'); os.makedirs(prof,exist_ok=True)
    cmd=[CHROME,'--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',f'--user-data-dir={prof}',f'--virtual-time-budget={wait*1000}','--dump-dom',url]
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=180,encoding='utf-8',errors='replace')
    return r.stdout or '',r.stderr or '',r.returncode
def strip(f):
    t=re.sub(r'<[^>]+>',' ',f).replace('&amp;','&').replace('&lt;','<').replace('&gt;','>').replace('&nbsp;',' ').replace('&#39;',"'")
    return re.sub(r'\s+',' ',t).strip()
def table(dom,bid):
    m=re.search(r'<tbody[^>]*id="'+re.escape(bid)+r'"[^>]*>(.*?)</tbody>',dom,re.S)
    if not m: return None,[]
    return m.group(1),[[strip(td) for td in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>',tr,re.S)] for tr in re.findall(r'<tr[^>]*>(.*?)</tr>',m.group(1),re.S)]
def headers(dom,hint):
    for tbl in re.findall(r'<table[^>]*>(.*?)</table>',dom,re.S):
        if hint in tbl:
            h=[strip(t) for t in re.findall(r'<th[^>]*>(.*?)</th>',tbl,re.S)]
            if h: return h
    return []
def main():
    ev={'captured_at':datetime.now(timezone.utc).isoformat(),'base':BASE}
    pid=listener(PORT); ev['listener_pid']=pid
    if not pid: print('NO LISTENER'); return 2
    ev['process']=proc_info(pid)
    html=get(BASE+'/live-copy').decode('utf-8','replace')
    ev['served_html_len']=len(html); ev['served_html_sha256']=hashlib.sha256(html.encode()).hexdigest()
    ev['served_has_lcHealthRows']='lcHealthRows' in html; ev['served_has_reconnects_per_min']='reconnects_per_min' in html
    ev['served_has_thread_alive']='thread_alive' in html; ev['served_has_leader_equity_base']='leader_equity_base' in html
    ws=gj(BASE+'/api/live-ws-health'); cfg=gj(BASE+'/api/live-config'); aud=gj(BASE+'/api/live-audit-summary')
    ev['api_snapshot_at']=datetime.now(timezone.utc).isoformat(); ev['ws_health_created_at']=(ws.get('health') or {}).get('created_at')
    ev['ws_wallet_count']=len((ws.get('health') or {}).get('wallets') or {}); ev['config_wallet_count']=len((cfg.get('config') or {}).get('wallets') or {})
    dom,err,rc=dom_dump(BASE+'/live-copy',6); ev['chrome_returncode']=rc; ev['dom_len']=len(dom)
    open(os.path.join(OUT,'dom_livecopy.html'),'w',encoding='utf-8').write(dom)
    hh=headers(dom,'lcHealthRows'); hb,hr=table(dom,'lcHealthRows')
    ev['health_headers']=hh; ev['health_rows_count']=len(hr)
    ev['col_thread']=hh.index('Thread') if 'Thread' in hh else None
    ev['col_reconnect_per_min']=hh.index('Reconnect/min') if 'Reconnect/min' in hh else None
    ev['col_wallet']=hh.index('Wallet') if 'Wallet' in hh else None
    wallets=sorted(((ws.get('health') or {}).get('wallets') or {}).items()); binding=[]
    for i,(addr,wh) in enumerate(wallets):
        row=hr[i] if i<len(hr) else []
        rec={'wallet':addr,'api_thread_alive':bool(wh.get('thread_alive') or wh.get('worker_thread_alive')),
             'api_thread_keys':sorted(k for k in wh if 'thread' in k.lower()),
             'api_reconnects_per_min':wh.get('reconnects_per_min'),'api_has_reconnects_key':'reconnects_per_min' in wh,
             'rendered_cells':row}
        if ev['col_wallet'] is not None and row: rec['rendered_wallet_cell']=row[ev['col_wallet']] if ev['col_wallet']<len(row) else None
        if ev['col_thread'] is not None and row: rec['rendered_thread_cell']=row[ev['col_thread']] if ev['col_thread']<len(row) else None
        if ev['col_reconnect_per_min'] is not None and row: rec['rendered_reconnect_cell']=row[ev['col_reconnect_per_min']] if ev['col_reconnect_per_min']<len(row) else None
        binding.append(rec)
    ev['health_wallet_binding']=binding
    cw=((cfg.get('config') or {}).get('wallets') or {})
    ev['ui_fp_193']={'api_has_key_any_wallet':any('leader_equity_base' in v for v in cw.values()),
        'api_wallet_keys_sample':sorted(list(cw.values())[0].keys()) if cw else [],
        'served_html_mentions':ev['served_has_leader_equity_base'],'dom_mentions':'leader_equity_base' in dom,
        'dom_display_text':bool(re.search(r'leader\s+equity\s+base',dom,re.I)),
        'dom_inputs':re.findall(r'<input[^>]*id="[^"]*equity[^"]*"[^>]*>',dom,re.I)[:5]}
    ev['ui_fp_167_168']={'headers_contain_Thread':'Thread' in hh,'headers_contain_Reconnect/min':'Reconnect/min' in hh,
        'health_empty_marker':'WS service not running or no wallet health file found' in (hb or ''),
        'thread_cells':[r.get('rendered_thread_cell') for r in binding],
        'reconnect_cells':[r.get('rendered_reconnect_cell') for r in binding]}
    pos=aud.get('manual_positions') if isinstance(aud,dict) else None
    ev['manual_positions_total']=aud.get('manual_positions_total') if isinstance(aud,dict) else None
    ev['manual_reconciliation_rows_count']=len(aud.get('manual_reconciliation_rows') or []) if isinstance(aud,dict) else 0
    pb,pr=table(dom,'lcPosRows'); ev['positions_rendered_row_count']=len(pr); ev['positions_rendered_rows']=pr[:5]
    out=os.path.join(OUT,'ui_serving_dom_capture.json')
    json.dump(ev,open(out,'w',encoding='utf-8'),indent=1,default=str)
    print('WROTE',out); print('HEADERS',hh); print('ROWS',len(hr))
    return 0
if __name__=='__main__': sys.exit(main())
