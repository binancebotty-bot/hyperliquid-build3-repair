#!/usr/bin/env python3
"""C1 CLOSEPATHS-2359, test-only exact-source sequence witnesses.
Parent (CI): python3 -u test_c1_closepaths.py
Crash sub-process uses os._exit AFTER durable pending row, with synthetic SDK.
No network, real key, order or engine source modification.
"""
from __future__ import annotations
import csv
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import test_c1_g13_sequences as t
c=t.c
A,B,COIN=t.A,t.B,t.COIN
RESULTS=[]

def check(name,condition,note=""):
    ok=bool(condition)
    RESULTS.append((name,ok))
    print("RESULT::%s_%s | %s"%(name,"PASS" if ok else "FAIL",str(note)[:1600]),flush=True)

def read(p):
    if not Path(p).exists():return []
    with Path(p).open(newline="",encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))

def bind_paths(root):
    root=Path(root)
    for key,filename in [
        ("SEND_ATTEMPTS_CSV","send_attempts.csv"),("LIVE_FILLS_CSV","live_fills.csv"),
        ("RECONCILIATION_CSV","reconciliation.csv"),("ORDER_INTENTS_CSV","order_intents.csv"),
        ("CLOSE_ESCALATIONS_FILE","close_escalations.json"),
        ("STANDING_CLOSES_FILE","standing_closes.json")
    ]:
        setattr(c,key,root/filename)
    c.MANUAL_LEDGER_FILE=root/"manual_ledger.json"
    return root

def exact_row(label,row):
    fields=("event","status","action","reject_category","terminal_state","engine_can_send",
            "manual_net","exchange_net","leader_fill_id","intent_id","coin",
            "exchange_order_id","notes")
    print("ROW::%s %s"%(label,json.dumps({k:row.get(k,"") for k in fields},sort_keys=True)),flush=True)

def crash_child(parent,landed):
    # Parent owns parent/ and observes a genuinely separate process exit.
    root,led,net,ex,gw,it,fid=t.make("RESTART_"+landed,1,0,1)
    led.save(touched_sleeves=[(A,COIN)])
    gw.audit.append_order_intent(it)
    meta={"root":str(root),"fid":fid,"landed":landed,"intent":asdict(it),
          "ledger":str(root/"manual_ledger.json")}
    Path(parent).mkdir(parents=True,exist_ok=True)
    (Path(parent)/"metadata.json").write_text(json.dumps(meta,default=str),encoding="utf-8")
    def stopped_order(coin,is_buy,size,px,tif,reduce_only=False,cloid=None):
        if landed=="LANDED":
            r=ex.__class__.order(ex,coin,is_buy,size,px,tif,reduce_only=reduce_only,cloid=cloid)
            # This is the simulated VENUE's surviving external state, NOT Core's
            # durable send-result or ledger. The SDK never returns to the caller.
            physical={"net":net[0],"oid":ex.seq,"filled":float(size),"px":float(px),
                      "cloid":str(cloid),"side":"BUY" if is_buy else "SELL"}
        else:
            physical={"net":net[0],"oid":None,"filled":0.0,"px":float(px),
                      "cloid":str(cloid),"side":"BUY" if is_buy else "SELL"}
        (Path(parent)/"exchange_truth.json").write_text(json.dumps(physical),encoding="utf-8")
        print("CHILD::KILL_POINT mode=%s venue=%s"%(landed,physical),flush=True)
        os._exit(67 if landed=="LANDED" else 68)
    ex.order=stopped_order
    # If the SDK call is reached, kill occurs inside it; pending_send already
    # durably exists. No _append_real_attempt or matcher execution can run.
    gw.send_if_allowed(it)
    os._exit(99)

def recreate_intent(data):
    obj=dict(data)
    obj["fill"]=c.LeaderFill(**obj["fill"])
    return c.Intent(**obj)

def restart_case(landed):
    root=Path(tempfile.mkdtemp(prefix="c1_closepaths_restart_"))
    cmd=[sys.executable,"-u",str(Path(__file__).resolve()),"--crash",str(root),landed]
    child=subprocess.run(cmd,capture_output=True,text=True,timeout=40,env=os.environ.copy())
    meta_file=root/"metadata.json"
    ex_file=root/"exchange_truth.json"
    check("R_"+landed+"_CRASH_AFTER_DURABLE_PREWIRE",
          child.returncode==(67 if landed=="LANDED" else 68)
          and meta_file.exists() and ex_file.exists()
          and "CHILD::KILL_POINT" in child.stdout,
          "child_rc=%r stdout=%r stderr=%r"%(child.returncode,child.stdout[-500:],child.stderr[-500:]))
    if not(meta_file.exists() and ex_file.exists()):return
    meta=json.loads(meta_file.read_text(encoding="utf-8"))
    venue=json.loads(ex_file.read_text(encoding="utf-8"))
    audit_dir=bind_paths(meta["root"])
    fid=meta["fid"]
    first=read(c.SEND_ATTEMPTS_CSV)
    original_intent=recreate_intent(meta["intent"])
    ledger_before=c.ManualLedger(path=Path(meta["ledger"]))
    relevant=[x for x in first if x.get("leader_fill_id")==fid]
    pend=[x for x in relevant if x.get("status")=="pending_send"
          and x.get("terminal_state")=="PENDING_SEND" and x.get("cloid")]
    check("R_"+landed+"_DISK_AT_KILL_PENDING_AND_LEDGER_UNCHANGED",
          len(pend)==1 and len(relevant)==1
          and t.approx(ledger_before.coin_net(COIN),1)
          and t.approx(venue["net"],0 if landed=="LANDED" else 1)
          and not read(c.LIVE_FILLS_CSV),
          "disk_pending=%r venue_net=%r ledger_net=%r live_rows=%r"%
          ([(x.get("attempt_id"),x.get("cloid"),x.get("exchange_order_id"),x.get("status")) for x in relevant],
           venue["net"],ledger_before.coin_net(COIN),read(c.LIVE_FILLS_CSV)))
    if not pend:return
    # This is the same startup alert path called from actual LiveCopyCore.__init__,
    # reading persisted PENDING_SEND from disk. We enter it directly to avoid any
    # live core scheduler/background threads; a subsequent independent process
    # reconstructs gateway/matcher from the serialized disk state.
    c.alert_unresolved_ambiguous_sends(c.AuditLogWriter(),pend)
    alerts=[x for x in read(c.RECONCILIATION_CSV)
            if x.get("status")=="SEND_OUTCOME_UNKNOWN_MANUAL_ALERT"]
    chk=bool(alerts) and any("cloid="+pend[0]["cloid"] in x.get("notes","")
                 and x.get("action")=="MANUAL_REVIEW_CHECK_ORDER_BY_CLOID"
                 for x in alerts)
    check("R_"+landed+"_RESTART_READS_PENDING_AND_EMITS_ACTIONABLE_HOLD",
          chk and all(x.get("engine_can_send","")!="True" for x in alerts),
          "pending_cloid=%s alert=%r"%(pend[0]["cloid"],alerts))
    if alerts:exact_row("RESTART_"+landed,alerts[-1])
    # Actual persisted state just after restart (before explicitly authorised
    # reconciliation) is HOLD: no second send and no auto-ledger fill.
    check("R_"+landed+"_NO_BLIND_RETRY_ON_RESTART",
          not read(c.LIVE_FILLS_CSV) and len(relevant)==1,
          "send_rows=%r live_rows=%r"%(relevant,read(c.LIVE_FILLS_CSV)))
    net=[venue["net"]]
    ex=t.Exchange(net)
    gw=t.f.make_gateway(ex,ledger_before,net)
    gw.cfg.liq_parity_enabled=lambda:False
    gw._close_escalations=c.load_json(c.CLOSE_ESCALATIONS_FILE,{}) or {}
    if landed=="LANDED":
        # User/agent performs a read-only exact cloid + venue fill lookup after
        # restart. Real matcher's action is measured, not inferred from a net.
        copy={"coin":COIN,"side":"SELL","sz":1.0,"px":100.0,
              "oid":str(venue["oid"]),"hash":"restartlanded","tid":str(venue["oid"]),
              "time":c.utc_now_ms(),"cloid":venue["cloid"]}
        matcher=c.CopyFillMatcher(ledger_before,c.AuditLogWriter())
        applied=matcher.match_and_apply(copy,{original_intent.intent_id:original_intent})
        final_rows=read(c.LIVE_FILLS_CSV)
        check("R_LANDED_VENUE_FILL_RECONCILED_AFTER_RESTART",
              applied and t.approx(ledger_before.coin_net(COIN),net[0])
              and t.approx(net[0],0)
              and any(x.get("leader_fill_id")==fid and x.get("exchange_order_id")==str(venue["oid"])
                      for x in final_rows) and not ex.calls,
              "matcher=%r ledger_net=%r venue_net=%r rows=%r"%
              (applied,ledger_before.coin_net(COIN),net[0],final_rows))
        check("R_LANDED_REPLAY_IDEMPOTENT",
              not matcher.match_and_apply(copy,{original_intent.intent_id:original_intent})
              and len(read(c.LIVE_FILLS_CSV))==len(final_rows) and not ex.calls,
              "duplicate live_rows=%r"%(read(c.LIVE_FILLS_CSV),))
    else:
        # The venue shows the original cloid never landed. Hold persists until
        # that proof; do NOT automatically submit a replacement here.
        check("R_NOT_LANDED_OWED_VISIBLE_NO_ABANDONMENT",
              t.approx(ledger_before.coin_net(COIN),1) and t.approx(net[0],1)
              and bool(alerts) and not ex.calls,
              "owed=1 open_ledger=%r external=%r actionable=%r"%
              (ledger_before.coin_net(COIN),net[0],bool(alerts)))
    # Operator intervention is explicitly still needed to resolve the PENDING
    # row's id; this unit does not claim automatic crash recovery.

def stale_case(label,owned_b,actual,expected_send,expected_ro=None):
    root,led,net,ex,gw,it,fid=t.make("DRIFT_"+label,1.0,owned_b,actual,qty=1)
    before=t.f.sleeve_of(led,A)
    ok,status=gw.send_if_allowed(it)
    calls=list(ex.calls)
    if expected_send:
        wire=(ok and len(calls)==1 and calls[0]["side"]=="SELL"
              and t.approx(calls[0]["size"],1) and calls[0]["reduce_only"] is expected_ro)
        check("S_"+label+"_OWNED_WIRE",wire,
              "owned=%r exchange_before=%r status=%r calls=%r"%
              (led.coin_net(COIN),actual,status,calls))
        applied=t.apply(gw,led,it,ex.seq,1.0,"drift"+label) if wire else False
        other=led.coin_net(COIN)
        residue=net[0]-other
        expect_foreign=actual-(1+owned_b)
        check("S_"+label+"_FILL_RETAINS_FOREIGN_RESIDUAL",
              applied and t.approx(t.f.sleeve_of(led,A),0)
              and t.approx(t.f.sleeve_of(led,B),owned_b)
              and t.approx(other,owned_b)
              and t.approx(residue,expect_foreign)
              and len(t.rows(c.LIVE_FILLS_CSV,fid))==1,
              "ledger=%r physical=%r foreign=%r expected_foreign=%r"%
              (other,net[0],residue,expect_foreign))
    else:
        reconc=t.rows(c.RECONCILIATION_CSV,fid)
        red=t.open_red(fid,it.intent_id)
        check("S_"+label+"_DISAGREE_HOLD_ZERO_WIRE",
              not ok and not calls and t.approx(net[0],actual)
              and t.approx(t.f.sleeve_of(led,A),before)
              and bool(red) and bool(reconc),
              "status=%r calls=%r red=%r rows=%r"%(status,calls,red,reconc))
        for row in reconc:
            if row.get("status") in ("AUTHORISED_CLOSE_REFUSAL", "OWNERSHIP_GATE_SIGN_CONFLICT",
                                    "OWNERSHIP_GATE_UNEXPLAINED_EXCHANGE_POSITION"):
                exact_row("STALE_"+label,row)
    return root,led,net,ex,gw,it,fid

def hold_rows():
    # Three operator-visible cases, including a post-crash unknown outcome,
    # stale exchange truth, and explicit ownership refusal.
    root,led,net,ex,gw,it,fid=t.make("HOLD_UNREADABLE",1.0,0.0,1.0)
    gw._fresh_exchange_net=lambda coin:None
    ok,status=gw.send_if_allowed(it)
    rec=t.rows(c.RECONCILIATION_CSV,fid)
    red=t.open_red(fid,it.intent_id)
    target=[x for x in rec if x.get("status")=="AUTHORISED_CLOSE_REFUSAL"]
    check("H_UNREADABLE_TRUTH_ACTIONABLE_HOLD",
          not ok and not ex.calls and bool(red) and bool(target)
          and any("CLOSE_PROOF_HOLD" in x.get("reject_category","") for x in target)
          and all(x.get("action")=="RECONCILE_OWED_CLOSE_BEFORE_RETRY" for x in target),
          "status=%r rows=%r red=%r"%(status,rec,red))
    for x in rec:
        if x.get("status")=="AUTHORISED_CLOSE_REFUSAL":exact_row("UNREADABLE_NET",x)
    # Named empty/consumed sleeve: terminal NO_SEND, not another RED.
    root,led,net,ex,gw,it,fid=t.make("HOLD_CONSUMED",0.05,0.0,0.05,qty=0.05)
    done,done_status=gw.send_if_allowed(it)
    matched=t.apply(gw,led,it,ex.seq,0.05,"holdflat") if done else False
    n=len(ex.calls)
    again,blocked=gw.send_if_allowed(it)
    named=[x for x in t.rows(c.RECONCILIATION_CSV,fid)
           if x.get("status")=="SEND_NOT_ATTEMPTED_STALE_OR_CONSUMED_FLAT_SLEEVE"]
    check("H_CONSUMED_FLAT_NAMED_NO_SEND",
          matched and not again and len(ex.calls)==n and bool(named)
          and named[-1].get("action")=="NO_SEND_CONSUMED_FLAT_SLEEVE",
          "status=%r rows=%r"%(blocked,named))
    for x in named:exact_row("CONSUMED_FLAT",x)

def main():
    for landed in ("LANDED","NOT_LANDED"):
        try:restart_case(landed)
        except Exception as exc:check("R_"+landed+"_HARNESS_EXCEPTION",False,repr(exc))
    for args in [
        ("SURPLUS_USER",0.5,2.5,True,True),
        ("DEFICIT_UNSEEN_FILL",0.5,0.8,False,None),
        ("OPPOSITE_SIGN",0.5,-0.5,False,None),
    ]:
        try:stale_case(*args)
        except Exception as exc:check("S_"+args[0]+"_HARNESS_EXCEPTION",False,repr(exc))
    try:hold_rows()
    except Exception as exc:check("H_HARNESS_EXCEPTION",False,repr(exc))
    failed=[name for name,p in RESULTS if not p]
    print("TOTAL=%d FAILED=%d"%(len(RESULTS),len(failed)),flush=True)
    print("FAILED_LABELS="+",".join(failed),flush=True)
    return 1 if failed else 0

if __name__=="__main__":
    if len(sys.argv)==4 and sys.argv[1]=="--crash":
        crash_child(sys.argv[2],sys.argv[3])
    raise SystemExit(main())
