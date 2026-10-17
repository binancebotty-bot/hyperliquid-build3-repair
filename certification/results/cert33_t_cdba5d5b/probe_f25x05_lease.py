import os,re,subprocess,sys,json,hashlib,pathlib,time
ROOT='C:/Users/wigmore/.hermes/cache/scratch/b3_clean'
REG='b142cf88d389e791160f691aac3d936852b99975'
W=ROOT+'/_cert33/lp'
def src():
    return subprocess.run(['git','show',REG+':_archive/hl_stage2/HL_Live_Copy_Service_Core.py'],cwd=ROOT,capture_output=True).stdout.decode()
def fn():
    s=src(); m=re.search(r'\ndef acquire_instance_lock\(state_dir: Path\) -> None:.*?\n    _INSTANCE_LOCK = fh\n',s,re.S); assert m; return m.group(0)
FN=fn()
def load():
    ns={'os':os,'Path':pathlib.Path,'_INSTANCE_LOCK':None}
    exec('from pathlib import Path\n'+FN,ns); return ns['acquire_instance_lock']
if len(sys.argv)>1 and sys.argv[1]=='hold':
    a=load(); os.makedirs(W,exist_ok=True); a(pathlib.Path(W)); print('HELD',flush=True); time.sleep(6); sys.exit(0)
if len(sys.argv)>1 and sys.argv[1]=='take':
    a=load()
    try:
        a(pathlib.Path(W)); print('ACQUIRED')
    except SystemExit as e: print('REFUSED '+str(e))
    sys.exit(0)
os.makedirs(W,exist_ok=True)
for f in os.listdir(W):
    try: os.remove(W+'/'+f)
    except OSError: pass
r={'engine_sha256':hashlib.sha256(src().encode()).hexdigest(),'fn_sha256':hashlib.sha256(FN.encode()).hexdigest()}
h=subprocess.Popen([sys.executable,__file__,'hold'],stdout=subprocess.PIPE)
r['holder']=h.stdout.readline().decode().strip()
p=subprocess.run([sys.executable,__file__,'take'],capture_output=True)
r['second_start_while_held']=(p.stdout+p.stderr).decode().strip()[-200:]
r['lockfile_exists']=os.path.exists(W+'/instance.lock')
try:
    open(W+'/instance.lock','rb').read(); r['readable_while_held']=True
except PermissionError: r['readable_while_held']=False
h.wait()
open(W+'/instance.lock','w').write('PID=999999\n')
q=subprocess.run([sys.executable,__file__,'take'],capture_output=True)
r['stale_file_take']=(q.stdout+q.stderr).decode().strip()[-200:]
r['fn_mentions_pid']=bool(re.search('(?i)pid',FN))
r['fn_text']=FN
print(json.dumps(r,indent=1))
