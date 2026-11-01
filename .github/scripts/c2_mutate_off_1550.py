#!/usr/bin/env python3
"""C2 OFFREAD mutation sensitivity. Every Core mutant lives ONLY in a temporary copy."""
from __future__ import annotations
import json, os, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "_archive" / "hl_stage2"
OUT = ROOT / "evidence" / "c2-mutate-off-1550"
OUT.mkdir(parents=True, exist_ok=True)
PINNED = "0a99d215c99b794717ce5b34f46cc299dae09106"
REPAIRS = "b4e63820d14fd99ac2e147fe90b98767054eb362"
SOURCE = subprocess.check_output(
    ["git", "show", PINNED + ":_archive/hl_stage2/HL_Live_Copy_Service_Core.py"],
    cwd=ROOT).decode("utf-8-sig").replace("\r\n", "\n")
FILES = [
    "test_t1a_cloid_pending_row.py",
    "test_readiness1_ambiguous_timeout_no_blind_resend.py",
    "test_core_rw13_recovery_reconcile.py",
    "test_core_off_path_skip.py",
]
OFF_ANCHOR = 'if mode == "OFF":\n            return "MASTER_REAL_ORDERS_OFF"'
OFF_REPLACE = 'if mode == "OFF":\n            pass  # MUTANT: bypass the ONE shared global-OFF physical gate'
MUTANTS = {
 "test_t1a_cloid_pending_row.py": [
   ("global_off_shared_gate", OFF_ANCHOR, OFF_REPLACE, "A8_CLOID_ON_THE_PHYSICAL_CALL"),
   ("drop_pending_durable_audit", "self.audit.append_send_attempt(_row, durable=True)",
    "pass  # MUTANT: omit durable pending record", "A9_ONE_PENDING_ROW_BEFORE_REPLY"),
   ("drop_physical_cloid", 'order_kwargs["cloid"] = sdk_cloid',
    "pass  # MUTANT: exchange never receives physical cloid", "A8_CLOID_ON_THE_PHYSICAL_CALL"),
 ],
 "test_readiness1_ambiguous_timeout_no_blind_resend.py": [
   ("global_off_shared_gate", OFF_ANCHOR, OFF_REPLACE, "B1_OPEN_NO_BLIND_RESEND"),
   ("ignore_original_open_status", 'if status == "open":',
    'if False and status == "open":  # MUTANT: do not recognise original order resting',
    "B2_OPEN_REPORTED_RESTING"),
   ("ignore_original_cloid_fill",
    "if fill is not None:\n            return self._ambiguous_send_landed(",
    "if False and fill is not None:\n            return self._ambiguous_send_landed(",
    "B6_FILL_MATCH_REPORTED_FILLED"),
 ],
 "test_core_rw13_recovery_reconcile.py": [
   ("global_off_shared_gate", OFF_ANCHOR, OFF_REPLACE, "A1_NO_FURTHER_SEND"),
   ("skip_timeout_recovery_reconciliation",
    'if timing.get("send_attempt_id") != _prev_attempt:',
    'if False and timing.get("send_attempt_id") != _prev_attempt:  # MUTANT',
    "A1_RECONCILE_CALLED_WITH_RECOVERY_CLOID"),
   ("forget_recovery_standing_close",
    'if ok and oid and status == "ORDER_RESTING":',
    'if False and ok and oid and status == "ORDER_RESTING":  # MUTANT',
    "A5_STANDING_CLOSE_NOT_REQUEUED"),
 ],
 "test_core_off_path_skip.py": [
   ("global_off_shared_gate", OFF_ANCHOR, OFF_REPLACE,
    "GATE_REFUSAL_SAYS_THE_EXCHANGE_WAS_NOT_CALLED"),
   ("lie_exchange_called_on_off_refusal",
    '"exchange_called": False, "reject_category": "BLOCKED_AT_PLACE_ORDER"',
    '"exchange_called": True, "reject_category": "BLOCKED_AT_PLACE_ORDER"  # MUTANT',
    "GATE_REFUSAL_SAYS_THE_EXCHANGE_WAS_NOT_CALLED"),
   ("stamp_refused_wire_as_sent",
    "if _late_block:\n            # the lease wins the message when both would refuse",
    "if timing is not None and started_key:\n            timing[started_key] = utc_now_ms()  # MUTANT false stamp\n        if _late_block:\n            # the lease wins the message when both would refuse",
    "POST_WAIT_REFUSAL_HAS_NO_CALL_STAMP"),
 ],
}
assert all(len(MUTANTS[f]) == 3 for f in FILES)
RESULT_RE = re.compile(r"RESULT::([A-Za-z0-9_]+)_(PASS|FAIL)(?:\s*\|\s*(.*))?$")
TOTAL_RE = re.compile(r"TOTAL=(\d+)\s+FAILED=(\d+)")
SITE = """import socket
def _deny(*a, **kw):
    raise RuntimeError('C2_OFF_MUTATION_NETWORK_DENIED')
socket.socket.connect = _deny
socket.socket.connect_ex = _deny
socket.create_connection = _deny
"""
# Executed in a completely fresh process (real OS singleton lock, fake exchange).
# The physical ON/OFF guard result is independent of whether one of the four
# existing test files happens to cover OFF. The probe must NOT be counted as
# proof that the original named assertions caught the mutant.
OFF_PROBE = '''
import json, os, tempfile, types
from pathlib import Path
tmp=Path(tempfile.mkdtemp(prefix="offprobe_"))
os.environ.update({"HL_LIVE_AUDIT_DIR":str(tmp), "HL_LIVE_GLOBAL_LOCK_FILE":str(tmp/"sender.lock"),
                   "HL_LIVE_ENV_FILE":str(tmp/"none.env"),"HL_LEADER_NETWORK":"testnet",
                   "HL_FOLLOWER_NETWORK":"testnet","HL_LIVE_AUTO_SEND_ENABLED":"0"})
import HL_Live_Copy_Service_Core as c
c.acquire_global_instance_lock(tmp)
assert c._sender_lease_owned()
class Fake:
    def __init__(self): self.calls=[]
    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        self.calls.append({"coin":coin,"size":size,"tif":tif,"reduce_only":reduce_only})
        return {"status":"ok","response":{"type":"order","data":{"statuses":[{"filled":{"totalSz":"1","avgPx":"100","oid":42}}]}}}
mode={"v":"ON"}
g=c.SenderGateway.__new__(c.SenderGateway)
g.cfg=types.SimpleNamespace(send_mode_now=lambda:mode["v"],wallet_enabled=lambda w:True,wallet_mode=lambda w:"ON")
g.sender_key_invalid=False
g.audit=types.SimpleNamespace(append_reconciliation=lambda *a,**kw:None)
g._reserve_exchange_order_slot=lambda **kw:c.utc_now_ms()
g._note_sender_key_rejection=lambda response:None
intent=types.SimpleNamespace(fill=types.SimpleNamespace(leader_wallet="0x"+"a"*40,coin="BTC"),
                             notes="lifecycle=ENTRY",reason="ENTRY",reduce_only_intended=False,
                             intent_id="off-proof",copy_size=1.0,copy_side="BUY")
def drive(m):
    mode["v"]=m
    ex=Fake()
    res=g._place_order(ex,"BTC",True,1.0,100.0,"Ioc",False,intent=intent,path="shared_global_off_probe")
    return {"mode":m,"calls":len(ex.calls),"exchange_called":res.get("exchange_called"),
            "response":str(res.get("response",""))[:180]}
on=drive("ON")
off=drive("OFF")
print("OFF_PHYSICAL_PROBE "+json.dumps({"on":on,"off":off,"lease":c._sender_lease_owned()},sort_keys=True))
'''

def execute(file, code, label, probe=False):
    work=Path(tempfile.mkdtemp(prefix="c2_offmut_"))
    started=time.monotonic()
    try:
        (work/"HL_Live_Copy_Service_Core.py").write_text(code,encoding="utf-8")
        shutil.copy2(STAGE/file,work/file)
        for dep in STAGE.glob("*.py"):
            if dep.name not in {file,"HL_Live_Copy_Service_Core.py","sitecustomize.py"}:
                (work/dep.name).symlink_to(dep.resolve())
        (work/"sitecustomize.py").write_text(SITE,encoding="utf-8")
        env=os.environ.copy()
        env.update({"PYTHONPATH":str(work)+os.pathsep+str(STAGE),
                    "HL_LIVE_ENV_FILE":"/nonexistent",
                    "HL_LEADER_NETWORK":"testnet","HL_FOLLOWER_NETWORK":"testnet",
                    "HL_LIVE_AUTO_SEND_ENABLED":"0","HL_LIVE_SCOPE_SWEEP_THREAD":"0",
                    "HL_LIVE_HL_PRIVATE_KEY":"","HL_USER_WALLET":"",
                    "PYTHONDONTWRITEBYTECODE":"1"})
        def call(cmd,timeout):
            try:
                p=subprocess.run(cmd,cwd=work,env=env,text=True,errors="replace",
                                 capture_output=True,timeout=timeout)
                return p.returncode,p.stdout+"\n=== STDERR ===\n"+p.stderr,False
            except subprocess.TimeoutExpired as exc:
                return 124,repr(exc.stdout)+"\n=== TIMEOUT ===\n"+repr(exc.stderr),True
        rc,raw,timed=call([sys.executable,"-u",file],120)
        (OUT/(file+"__"+label+".log")).write_text(raw,encoding="utf-8")
        cases=[]
        for line in raw.splitlines():
            m=RESULT_RE.search(line)
            if m: cases.append({"name":m.group(1),"verdict":m.group(2),"observed_line":line[line.find("RESULT::"):]})
        totals=TOTAL_RE.findall(raw)
        info={"file":file,"mutation":label,"returncode":rc,"timeout":timed,
              "totals":totals[-1] if totals else None,
              "cases_failed":[c for c in cases if c["verdict"]=="FAIL"],
              "cases_passed":sum(c["verdict"]=="PASS" for c in cases),
              "tracebacks":[l for l in raw.splitlines() if
                 any(t in l for t in ("Traceback","SyntaxError:","Error:","Exception:"))][-12:],
              "duration_s":round(time.monotonic()-started,2)}
        if probe:
            pr,prraw,ptimed=call([sys.executable,"-u","-c",OFF_PROBE],18)
            (OUT/(file+"__"+label+".probe.log")).write_text(prraw,encoding="utf-8")
            key=next((l.split("OFF_PHYSICAL_PROBE ",1)[1] for l in prraw.splitlines()
                       if "OFF_PHYSICAL_PROBE " in l),None)
            try: pdata=json.loads(key) if key else None
            except Exception: pdata=None
            info["off_probe"]={"exit":pr,"timeout":ptimed,"result":pdata,
                               "error":None if pdata else prraw[-800:]}
        return info
    finally:
        shutil.rmtree(work,ignore_errors=True)

report={"source_sha":PINNED,"source_blob":"e470862a291bbf241e22d8011b757ed9c2b53d68",
        "repaired_test_sha":REPAIRS,"baseline":[],"mutations":[]}
for file in FILES:
    b=execute(file,SOURCE,"baseline",probe=True)
    report["baseline"].append(b)
    print("BASELINE "+json.dumps({k:v for k,v in b.items() if k not in ("tracebacks","cases_failed")},sort_keys=True),flush=True)
    for label,anchor,replacement,expected in MUTANTS[file]:
        count=SOURCE.count(anchor)
        if count!=1:
            r={"file":file,"mutation":label,"classification":"INVALID_ANCHOR",
               "anchor_count":count,"expected_case":expected}
        else:
            m=execute(file,SOURCE.replace(anchor,replacement,1),label,
                      probe=(label=="global_off_shared_gate"))
            m["expected_case"]=expected
            m["original_baseline_green"]=bool(b["totals"] and b["totals"][1]=="0" and b["returncode"]==0)
            m["expected_case_red"]=any(c["name"]==expected for c in m["cases_failed"])
            if not m["original_baseline_green"]:
                m["classification"]="BASELINE_RED_CANNOT_SCORE"
            elif m["expected_case_red"]:
                m["classification"]="CAUGHT_NAMED_ASSERTION"
            elif m["cases_failed"]:
                m["classification"]="CAUGHT_OTHER_ASSERTION_REVIEW"
            elif m["returncode"]!=0 or m["timeout"]:
                m["classification"]="CRASH_INCONCLUSIVE"
            else:
                m["classification"]="MISSED_FALSE_GREEN"
            r=m
        report["mutations"].append(r)
        print("MUTANT "+json.dumps({
            "file":r["file"],"mutation":r["mutation"],"classification":r["classification"],
            "expected":r.get("expected_case"),"total":r.get("totals"),
            "observed":[c["observed_line"] for c in r.get("cases_failed",[])][:6],
            "off_probe":r.get("off_probe"),"errors":r.get("tracebacks",[])[:2]
        },sort_keys=True),flush=True)
        (OUT/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
(OUT/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
with (OUT/"summary.tsv").open("w",encoding="utf-8") as f:
    f.write("file\tmutation\tclassification\texpected\tobserved\n")
    for m in report["mutations"]:
        obs=next((v["observed_line"] for v in m.get("cases_failed",[])
                  if v["name"]==m.get("expected_case")),None)
        if not obs: obs=next((v["observed_line"] for v in m.get("cases_failed",[])),None)
        if not obs: obs="TOTAL=%s FAILED=%s" % tuple(m.get("totals") or ("?", "?"))
        f.write("\t".join(str(x).replace("\t"," ").replace("\n"," ") for x in
                (m["file"],m["mutation"],m["classification"],m.get("expected_case",""),obs))+"\n")
print("MUTATION_SUMMARY "+json.dumps({
    k:sum(r.get("classification")==k for r in report["mutations"])
    for k in sorted(set(r["classification"] for r in report["mutations"]))
},sort_keys=True),flush=True)
