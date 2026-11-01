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

def latest_attempt_rows():
    """Resolve append-only revisions by exact attempt_id, NEVER count old pending as current."""
    latest={}
    for row in read(c.SEND_ATTEMPTS_CSV):
        if row.get("attempt_id"):
            latest[row["attempt_id"]]=row
    return latest

def proven_terminal_attempt(aid,row,original_id,original_cloid,intent_id,live_rows,
                            landed_oid="",recovery_oid=""):
    """Positive, fixture-bounded venue proof, NOT status-is-not-pending.
    One of: proven original CLOID cancelled; original CLOID filled and
    OID matched; recovery OID fully matched. Every other state is UNRESOLVED.
    """
    if not row or row.get("attempt_id")!=aid or row.get("intent_id")!=intent_id:
        return False
    def matched(oid,quantity):
        return bool(oid) and t.approx(sum(
            float(f.get("fill_size") or 0) for f in live_rows
            if f.get("exchange_order_id")==str(oid)
            and f.get("intent_id")==intent_id
            and f.get("ledger_action") in {"UPDATED","CLOSED"}),quantity)
    if aid==original_id:
        if row.get("cloid")!=original_cloid:
            return False
        if landed_oid:
            return (row.get("status")=="ORDER_FILLED"
                    and row.get("terminal_state")=="FILLED_AMBIGUOUS_SEND"
                    and row.get("exchange_order_id")==str(landed_oid)
                    and matched(landed_oid,float(row.get("copy_size") or 0)))
        return (row.get("status")=="ORDER_CANCELLED"
                and row.get("terminal_state")=="SEND_OUTCOME_CONFIRMED_CANCELLED_NO_RETRY"
                and not row.get("exchange_order_id")
                and row.get("operator_action")=="WAIT_FOR_FRESH_REDUCE_ONLY_RECOMPUTE")
    if recovery_oid and row.get("exchange_order_id")==str(recovery_oid):
        return (row.get("status")=="ORDER_FILLED"
                and row.get("terminal_state")=="MATCHED_BY_EXCHANGE_ORDER_ID"
                and matched(recovery_oid,float(row.get("copy_size") or 0)))
    return False

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
    # Startup officially APPENDS ORDER_UNKNOWN against the SAME attempt id.
    # Historical pending_send remains as immutable evidence; latest-by-id is
    # unresolved until original cloid proof, and MUST be terminalised later.
    at_start=latest_attempt_rows().get(pend[0]["attempt_id"])
    check("R_"+landed+"_STARTUP_LATEST_ATTEMPT_IS_UNKNOWN_HELD",
          at_start is not None and at_start.get("status")=="ORDER_UNKNOWN"
          and at_start.get("terminal_state")=="SEND_OUTCOME_UNKNOWN_MANUAL_ALERT"
          and at_start.get("cloid")==pend[0]["cloid"]
          and not read(c.LIVE_FILLS_CSV),
          "latest=%r"%(at_start and {k:at_start.get(k) for k in
                    ("attempt_id","status","terminal_state","cloid")},))
    check("R_"+landed+"_NO_BLIND_RETRY_ON_RESTART",
          not read(c.LIVE_FILLS_CSV) and len([x for x in read(c.SEND_ATTEMPTS_CSV)
                            if x.get("status")=="pending_send" and x.get("attempt_id")==pend[0]["attempt_id"]])==1,
          "append_history=%r live_rows=%r"%
          ([(x.get("attempt_id"),x.get("status")) for x in read(c.SEND_ATTEMPTS_CSV)],
           read(c.LIVE_FILLS_CSV)))
    net=[venue["net"]]
    ex=t.Exchange(net)
    gw=t.f.make_gateway(ex,ledger_before,net)
    gw.cfg.liq_parity_enabled=lambda:False
    gw._close_escalations=c.load_json(c.CLOSE_ESCALATIONS_FILE,{}) or {}
    # The exact production Cloid reconciliation function can now process
    # externally verified orderStatus plus fill completeness. This is a bounded
    # post-restart operator/agent step, NOT a claim of auto-start scheduling.
    cloid=pend[0]["cloid"]
    copied={"coin":COIN,"side":"SELL","sz":1.0,"px":100.0,
            "oid":str(venue["oid"]),"hash":"restartlanded","tid":str(venue["oid"]),
            "time":c.utc_now_ms(),"cloid":venue["cloid"]} if landed=="LANDED" else None
    old_post=c._XNET.post_many
    old_fill_read=c._read_all_copy_fills
    def order_status(_fetcher,payloads,*args,**kwargs):
        assert payloads==[{"type":"orderStatus","user":c.USER_WALLET,"oid":cloid}]
        return [{"ok":True,"data":{"order":{
            "status":"filled" if landed=="LANDED" else "canceled",
            "order":{"oid":venue["oid"] if landed=="LANDED" else "",
                     "limitPx":venue["px"]}}}}]
    c._XNET.post_many=order_status
    c._read_all_copy_fills=lambda *args,**kwargs: (
        ([copied] if copied is not None else []),"FILLS_COMPLETE")
    try:
        outcome=gw._resolve_ambiguous_send_outcome(
            COIN,original_intent,cloid,1.0,float(pend[0]["limit_price"]),
            True,"process died before reply",{"send_real_started_ms":c.utc_now_ms(),
                "send_attempt_id":pend[0]["attempt_id"],"send_cloid":cloid},
            schedule_followup=False,record_hold=False)
    finally:
        c._XNET.post_many=old_post
        c._read_all_copy_fills=old_fill_read
    if landed=="LANDED":
        check("R_LANDED_EXACT_CLOID_PROVES_PRIOR_FILL_NO_RESEND",
              outcome is not None and outcome[0] is True
              and outcome[1]=="ORDER_FILLED"
              and str(outcome[2].get("oid"))==str(venue["oid"])
              and not ex.calls,
              "proof=%r venue=%r calls=%r"%(outcome,venue,ex.calls))
        # User/agent performs read-only cloid+fill lookup above; attach only its
        # proven returned OID to the original durable intent.
        if outcome is not None and outcome[0] is True:
            # This calls production append-only final send writer, retaining
            # the ORIGINAL attempt id from the same send timing.
            gw._append_real_attempt(original_intent,outcome[1],outcome[2])
        last=latest_attempt_rows().get(pend[0]["attempt_id"])
        check("R_LANDED_ORIGINAL_ATTEMPT_TERMINALISED_SAME_ID",
              last is not None
              and last.get("status")=="ORDER_FILLED"
              and last.get("terminal_state")=="FILLED_AMBIGUOUS_SEND"
              and last.get("exchange_order_id")==str(venue["oid"])
              and last.get("cloid")==cloid,
              "history=%r"%([(x.get("attempt_id"),x.get("status"),
                             x.get("terminal_state"),x.get("exchange_order_id"))
                             for x in read(c.SEND_ATTEMPTS_CSV)],))
        copy=copied
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
        check("R_LANDED_POSITIVE_TERMINAL_PLUS_MATCHED_FILL",
              proven_terminal_attempt(
                  pend[0]["attempt_id"],latest_attempt_rows().get(pend[0]["attempt_id"]),
                  pend[0]["attempt_id"],cloid,original_intent.intent_id,final_rows,
                  landed_oid=str(venue["oid"]))
              and len(latest_attempt_rows())==1,
              "terminal=%r oid=%r matched_fills=%r"%
              (latest_attempt_rows()[pend[0]["attempt_id"]].get("terminal_state"),
               venue["oid"],[(x.get("exchange_order_id"),x.get("fill_size"))
                              for x in final_rows]))
    else:
        # Confirmed cancellation of an EXIT is a distinct terminal event:
        # the actual resolver must NOT blindly re-send. The close remains
        # owed and its named convergence re-evaluation is observable.
        cancel=[x for x in read(c.RECONCILIATION_CSV)
                if x.get("status")=="EXIT_CANCELLED_RECOMPUTE_PENDING"]
        check("R_NOT_LANDED_CLOID_CANCELLED_SIGNALS_RECOMPUTE",
              outcome is not None and outcome[0] is False
              and outcome[1]=="ORDER_CANCELLED"
              and outcome[2].get("terminal_state")=="SEND_OUTCOME_CONFIRMED_CANCELLED_NO_RETRY"
              and any(x.get("action")=="WAIT_FOR_FRESH_REDUCE_ONLY_RECOMPUTE" for x in cancel)
              and not ex.calls,
              "proof=%r recompute=%r calls=%r"%(outcome,cancel,ex.calls))
        for x in cancel:exact_row("CANCELLED_RECOMPUTE",x)
        # The Core deferred CLOID recheck loop uses EXACTLY
        # update_send_attempt_row to append a terminal revision on a proven
        # cancelled order. The synchronous restart proof path in this bounded
        # test must do the same; merely writing a reconciliation alert leaves
        # the original attempt UNKNOWN forever, even if later GTC fills.
        closed=False
        if outcome is not None and outcome[1]=="ORDER_CANCELLED":
            src=latest_attempt_rows().get(pend[0]["attempt_id"])
            closed=c.update_send_attempt_row(pend[0]["attempt_id"], {
                "status":"ORDER_CANCELLED",
                "exchange_order_id":outcome[2].get("oid",""),
                "exchange_response":json.dumps(outcome[2].get("exchange_response",{})),
                "terminal_state":outcome[2].get("terminal_state",""),
                "operator_action":outcome[2].get("operator_action",""),
                "notes":outcome[2].get("notes",""),
            },base_row=src,durable=True)
        final_original=latest_attempt_rows().get(pend[0]["attempt_id"])
        check("R_NOT_LANDED_ORIGINAL_PENDING_TERMINALISED_SAME_ID",
              closed and proven_terminal_attempt(
                  pend[0]["attempt_id"],final_original,pend[0]["attempt_id"],
                  cloid,original_intent.intent_id,[])
              and final_original.get("status")=="ORDER_CANCELLED"
              and final_original.get("terminal_state")=="SEND_OUTCOME_CONFIRMED_CANCELLED_NO_RETRY"
              and final_original.get("operator_action")=="WAIT_FOR_FRESH_REDUCE_ONLY_RECOMPUTE"
              and final_original.get("cloid")==cloid
              and len([x for x in latest_attempt_rows().values()
                       if x.get("attempt_id")==pend[0]["attempt_id"]])==1,
              "latest=%r history=%r"%
              (final_original and {k:final_original.get(k) for k in
                 ("attempt_id","status","terminal_state","cloid","operator_action")},
               [(x.get("attempt_id"),x.get("status"),x.get("terminal_state"))
                for x in read(c.SEND_ATTEMPTS_CSV)]))
        check("R_NOT_LANDED_OWED_VISIBLE_NO_ABANDONMENT",
              t.approx(ledger_before.coin_net(COIN),1) and t.approx(net[0],1)
              and bool(alerts) and not ex.calls,
              "owed=1 open_ledger=%r external=%r actionable=%r"%
              (ledger_before.coin_net(COIN),net[0],bool(alerts)))
        # The ORIGINAL cloid has been independently proven CANCELLED. Only NOW
        # can a convergence unit re-read owned+venue truth and re-enter the real
        # GTC recovery sender. This deliberately invokes the production method
        # after proof; automatic scheduling of the callback by a live Core is
        # NOT verified here and cannot be inferred from this bounded witness.
        ready=t.approx(gw._fresh_exchange_net(COIN),1) and t.approx(ledger_before.coin_net(COIN),1)
        ex.script=[t.resting(7777)]
        if ready:
            gw._queue_exit_recovery_if_needed(
                ex,COIN,original_intent,original_intent.fill.price,1.0,{},
                "post-restart cancelled-cloid verified; current truth",sz_dec=3)
        calls=list(ex.calls)
        recovery_rows=[x for x in read(c.RECONCILIATION_CSV)
                       if x.get("status")=="EXIT_RECOVERY_QUEUED"
                       and x.get("leader_fill_id")==fid]
        open_orders=read(c.SEND_ATTEMPTS_CSV)
        check("R_NOT_LANDED_SAFE_POSTPROOF_RECOVERY_WIRE",
              ready and len(calls)==1
              and calls[0]["side"]=="SELL"
              and t.approx(calls[0]["size"],1.0)
              and t.approx(calls[0]["px"],original_intent.fill.price)
              and calls[0]["reduce_only"]
              and calls[0]["tif"].get("limit",{}).get("tif")=="Gtc"
              and any(x.get("exchange_order_id")=="7777" for x in recovery_rows)
              and any(x.get("status")=="ORDER_RESTING"
                      and x.get("exchange_order_id")=="7777" for x in open_orders),
              "ready=%r wire=%r recovery=%r"%
              (ready,calls,recovery_rows))
        if calls:
            net[0]-=1.0  # independently observed venue fill, not SDK resend
            matcher=c.CopyFillMatcher(ledger_before,c.AuditLogWriter())
            match=matcher.match_and_apply({
                "coin":COIN,"side":"SELL","sz":1.0,"px":100.0,
                "oid":"7777","hash":"restartnotlandedfilled","tid":"7777",
                "time":c.utc_now_ms()},
                {original_intent.intent_id:original_intent})
        else:match=False
        check("R_NOT_LANDED_RECOVERY_OID_FILL_CONVERGES",
              match and t.approx(net[0],0) and t.approx(ledger_before.coin_net(COIN),0)
              and len(calls)==1
              and any(x.get("exchange_order_id")=="7777"
                      and x.get("ledger_action")=="CLOSED" for x in read(c.LIVE_FILLS_CSV)),
              "matched=%r venue=%r ledger=%r wires=%r"%
              (match,net[0],ledger_before.coin_net(COIN),calls))
        # Recovery GTC's physical result can leave its own ORDER_RESTING row
        # until the existing real journal sweep matches the durable copy fill.
        # Assert BOTH original cancelled and second OID filled (latest per
        # attempt), no unknown/pending row masked by an unrelated later fill.
        sweep=c.close_orphan_attempt_rows(only_oid="7777",apply=True)
        latest=latest_attempt_rows()
        original=latest.get(pend[0]["attempt_id"])
        gtcs=[(aid,row) for aid,row in latest.items()
              if row.get("exchange_order_id")=="7777"]
        live=read(c.LIVE_FILLS_CSV)
        # The SAME positive proof is used for actual latest journal and both
        # executable mutant controls. Reconstructed success view excludes only
        # the known BASELINE-RED GTC pending (no OID); this calibrates the
        # oracle, but DOES NOT make the real-journal assertion green.
        known={aid:row for aid,row in latest.items()
               if aid==pend[0]["attempt_id"] or
                  row.get("exchange_order_id")=="7777"}
        def all_proven(rows):
            return (len(rows)>=2 and pend[0]["attempt_id"] in rows
                    and any(row.get("exchange_order_id")=="7777"
                            for row in rows.values())
                    and all(proven_terminal_attempt(
                        aid,row,pend[0]["attempt_id"],cloid,
                        original_intent.intent_id,live,recovery_oid="7777")
                        for aid,row in rows.items()))
        calibrated=all_proven(known)
        check("R_NOT_LANDED_POSITIVE_ORACLE_CALIBRATED",
              calibrated and len(known)==2,
              "expected_set=%r actual_full_latest=%r"%
              ([(aid,row.get("status")) for aid,row in known.items()],
               [(aid,row.get("status")) for aid,row in latest.items()]))
        for label,fake_status,fake_terminal in (
            ("RESTING","ORDER_RESTING","ORDER_RESTING"),
            ("UNKNOWN","EXCHANGE_OUTCOME_UNKNOWN","EXCHANGE_OUTCOME_UNKNOWN")):
            forged_id="mutant_extra_"+label.lower()
            forged=dict(next(row for aid,row in gtcs if row.get("status")=="ORDER_FILLED"))
            forged.update(attempt_id=forged_id,status=fake_status,
                          terminal_state=fake_terminal)
            mutant=dict(known)
            mutant[forged_id]=forged
            check("R_NOT_LANDED_"+label+"_MUTANT_REJECTED",
                  calibrated and not all_proven(mutant),
                  "mutant_id=%s status=%s terminal=%s mutated_oracle=%r"%
                  (forged_id,fake_status,fake_terminal,all_proven(mutant)))
        check("R_NOT_LANDED_BOTH_ATTEMPT_IDS_TERMINAL_AFTER_SWEEP",
              all_proven(latest)
              and all(aid!=pend[0]["attempt_id"] for aid,_ in gtcs),
              "sweep=%r original=%r gtc_latest=%r all_latest=%r"%
              (sweep,original and (original.get("status"),original.get("terminal_state")),
               [(aid,row.get("status"),row.get("terminal_state")) for aid,row in gtcs],
               [(aid,row.get("status"),row.get("terminal_state")) for aid,row in latest.items()]))
    # Restarts are bounded operator/agent proof-and-recovery exercises. This
    # file does NOT claim automatic startup scheduling, real exchange or signer.

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
        def expected_stage(status_value,rows,red_rows):
            if label=="DEFICIT_UNSEEN_FILL":
                matching=[x for x in rows
                          if x.get("event")=="CLOSE_ESCALATION"
                          and x.get("status")=="AUTHORISED_CLOSE_REFUSAL"
                          and x.get("reject_category")=="CLOSE_PROOF_HOLD_NET_MISMATCH"
                          and x.get("action")=="RECONCILE_OWED_CLOSE_BEFORE_RETRY"
                          and x.get("engine_can_send")=="False"
                          and x.get("intent_id")==it.intent_id
                          and x.get("leader_fill_id")==fid]
                return (status_value=="SEND_NOT_ATTEMPTED_CLOSE_PROOF_HOLD"
                        and bool(matching) and bool(red_rows)
                        and all(x.get("state")=="OPEN" for x in red_rows))
            if label=="OPPOSITE_SIGN":
                matching=[x for x in rows
                          if x.get("event")=="OWNERSHIP_GATE"
                          and x.get("status")=="OWNERSHIP_GATE_SIGN_CONFLICT"
                          and x.get("terminal_state")=="OWNERSHIP_GATE_SIGN_CONFLICT"
                          and x.get("action")=="NO_SEND_OWNERSHIP_RECONCILIATION_REQUIRED"
                          and x.get("reject_category")=="OWNERSHIP_CONTRACT_BLOCK"
                          and x.get("engine_can_send")=="False"
                          and t.approx(x.get("manual_net"),1.5)
                          and t.approx(x.get("exchange_net"),-0.5)
                          and x.get("intent_id")==it.intent_id]
                return (status_value=="OWNERSHIP_GATE_SIGN_CONFLICT"
                        and bool(matching) and bool(red_rows)
                        and all(x.get("state")=="OPEN" for x in red_rows))
            raise AssertionError("unexpected expected_stage label "+label)
        stage_ok=expected_stage(status,reconc,red)
        check("S_"+label+"_EXACT_NAMED_REASON",
              stage_ok and not ok and not calls
              and t.approx(net[0],actual)
              and t.approx(t.f.sleeve_of(led,A),before),
              "status=%r named=%r red=%r"%
              (status,[(x.get("event"),x.get("status"),x.get("reject_category"),
                        x.get("action"),x.get("manual_net"),x.get("exchange_net"))
                        for x in reconc],red))
        # Executed negative test-seam control: unrelated MASTER_OFF refusal
        # must NEVER be accepted as a proof of the requested drift gate.
        wrong_root,wrong_led,wrong_net,wrong_ex,wrong_gw,wrong_it,wrong_fid=t.make(
            "DRIFT_WRONG_REASON_"+label,1.0,owned_b,actual,qty=1)
        wrong_gw.cfg.master_switch_now=lambda:False
        wrong_ok,wrong_status=wrong_gw.send_if_allowed(wrong_it)
        wrong_recon=t.rows(c.RECONCILIATION_CSV,wrong_fid)
        wrong_red=t.open_red(wrong_fid,wrong_it.intent_id)
        check("S_"+label+"_WRONG_REASON_NEGATIVE_DETECTED",
              not wrong_ok and not wrong_ex.calls
              and wrong_status=="MASTER_REAL_ORDERS_OFF"
              and not expected_stage(wrong_status,wrong_recon,wrong_red),
              "injected_wrong_reason=%r rows=%r"%
              (wrong_status,[(x.get("event"),x.get("status"),x.get("reject_category"))
                             for x in wrong_recon]))
        # The negative fixture switched module-level CSV paths, so restore
        # initial data paths for further evidence and row print.
        t.make("RESTORE_"+label,1.0,owned_b,actual,qty=1)
        for key,name in (
            ("SEND_ATTEMPTS_CSV","send_attempts.csv"),
            ("LIVE_FILLS_CSV","live_fills.csv"),
            ("RECONCILIATION_CSV","reconciliation.csv"),
            ("ORDER_INTENTS_CSV","order_intents.csv"),
            ("CLOSE_ESCALATIONS_FILE","close_escalations.json"),
            ("STANDING_CLOSES_FILE","standing_closes.json")):
            setattr(c,key,root/name)
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
    # The operator-facing RED JSON is a separate surface. The first precise
    # CLOSE_PROOF_HOLD_UNREADABLE_NET reason may be overwritten by the generic
    # SEND_NOT_ATTEMPTED_CLOSE_PROOF_HOLD in _finish. A generic RED reason
    # is NOT adequate as a standalone actionable diagnosis without cross-table
    # joins; require exact root cause in its own row (negative finding).
    red_rows=c.load_json(c.CLOSE_ESCALATIONS_FILE,{})
    exact=next((x for x in red_rows.values() if isinstance(x,dict)
                and x.get("leader_fill_id")==fid),{})
    print("ROW::CLOSE_ESCALATIONS_JSON "+json.dumps(exact,sort_keys=True),flush=True)
    check("H_RED_JSON_RETAINS_SPECIFIC_ROOT_CAUSE",
          exact.get("reason")=="CLOSE_PROOF_HOLD_UNREADABLE_NET"
          and exact.get("state")=="OPEN"
          and exact.get("intent_id")==it.intent_id,
          "red_json_reason=%r expected=CLOSE_PROOF_HOLD_UNREADABLE_NET"%
          exact.get("reason"))
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

def inventory_hold_paths():
    """High-risk previously omitted durable hold/refusal paths on pinned SenderGateway.

    These are actual send_if_allowed / recovery-method calls, never invented audit
    rows. All account/net reads, SDK and HTTP stay synthetic and fully offline.
    """
    cases=[
        ("MASTER_OFF","MASTER_REAL_ORDERS_OFF","CLOSE_ESCALATION",
         "AUTHORISED_CLOSE_REFUSAL","MASTER_REAL_ORDERS_OFF",
         "RECONCILE_OWED_CLOSE_BEFORE_RETRY","master"),
        ("KEY_INVALID","SEND_BLOCKED_SENDER_KEY_NOT_VALID","CLOSE_ESCALATION",
         "AUTHORISED_CLOSE_REFUSAL","SEND_BLOCKED_SENDER_KEY_NOT_VALID",
         "RECONCILE_OWED_CLOSE_BEFORE_RETRY","key"),
        ("PENDING_EXIT","PENDING_EXIT_GUARD_ACTIVE","SEND_TERMINAL",
         "PENDING_EXIT_GUARD_ACTIVE","PENDING_EXIT_GUARD",
         "NO_SEND_PENDING_EXIT_IN_FLIGHT","pending"),
        ("AUDIT_MISSING","OWNERSHIP_GATE_MISSING_AUDIT_PROOF","OWNERSHIP_GATE",
         "OWNERSHIP_GATE_MISSING_AUDIT_PROOF","OWNERSHIP_CONTRACT_BLOCK",
         "NO_SEND_OWNERSHIP_RECONCILIATION_REQUIRED","audit"),
        ("EXCHANGE_MISSING","OWNERSHIP_GATE_MISSING_EXCHANGE_PROOF","OWNERSHIP_GATE",
         "OWNERSHIP_GATE_MISSING_EXCHANGE_PROOF","OWNERSHIP_CONTRACT_BLOCK",
         "NO_SEND_OWNERSHIP_RECONCILIATION_REQUIRED","exchange"),
        ("ACCOUNT_MISMATCH","SEND_NOT_ATTEMPTED_CLOSE_PROOF_HOLD","CLOSE_ESCALATION",
         "AUTHORISED_CLOSE_REFUSAL","CLOSE_PROOF_HOLD_ACCOUNT_MISMATCH",
         "RECONCILE_OWED_CLOSE_BEFORE_RETRY","account"),
        ("WALLET_OFF","BLOCKED_OFF","SEND_TERMINAL",
         "BLOCKED_OFF","WALLET_MODE_BLOCK",
         "NO_SEND_WALLET_MODE_CHANGED","wallet"),
    ]
    for label,status_expected,event,root_status,reason,action,inject in cases:
        root,led,net,ex,gw,it,fid=t.make("INV_"+label,1,0,1)
        if inject=="master":gw.cfg.master_switch_now=lambda:False
        elif inject=="key":gw.sender_key_invalid=True
        elif inject=="pending":gw._mark_pending_exit(it)
        elif inject=="audit":gw._audit_proof_block_reason=lambda:"audit snapshot not proved"
        elif inject=="exchange":gw._persisted_exchange_positions=lambda:({},"no fresh exchange snapshot")
        elif inject=="account":
            # Real account-mismatch method runs: swap the configured actual
            # follower sender address to a distinct synthetic address; restore.
            saved=os.environ.get("HL_LIVE_HL_ACCOUNT_ADDRESS")
            os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"]=t.f.OTHER_ACCOUNT
        elif inject=="wallet":gw.cfg.wallet_enabled=lambda wallet:False
        try:
            ok,status=gw.send_if_allowed(it)
            observed=read(c.RECONCILIATION_CSV)
            red=t.open_red(fid,it.intent_id)
        finally:
            if inject=="account":
                if saved is None:os.environ.pop("HL_LIVE_HL_ACCOUNT_ADDRESS",None)
                else:os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"]=saved
        match=[row for row in observed
               if row.get("leader_fill_id")==fid
               and row.get("event")==event
               and row.get("status")==root_status
               and row.get("reject_category")==reason
               and row.get("action")==action
               and row.get("engine_can_send")=="False"
               and row.get("intent_id")==it.intent_id]
        check("INV_"+label+"_NAMED_NO_WIRE_DURABLE",
              not ok and status==status_expected and not ex.calls
              and bool(match) and bool(red)
              and all(row.get("state")=="OPEN" for row in red),
              "status=%s match=%r red=%r rows=%r"%(
                  status,bool(match),red,
                  [(x.get("event"),x.get("status"),x.get("reject_category"),
                    x.get("action")) for x in observed]))
        for row in observed:
            if row.get("leader_fill_id")==fid:
                exact_row("INVENTORY_"+label,row)

    # Real G13 partial-fill safety path, but explicitly simulate a current
    # ledger that MAY LAG before actual OID match: no GTC, named durable
    # STANDING_CLOSE_NOT_PLACED plus OPEN RED (never weaken this gate).
    root,led,net,ex,gw,it,fid=t.make("INV_PREMATCH_LAG",1,0,1)
    gw._queue_exit_recovery_if_needed(
        ex,COIN,it,it.fill.price,1.0,t.fstatus(9011,0.6),
        "IOC partially filled before copy poll",remainder=0.4,sz_dec=3)
    observed=read(c.RECONCILIATION_CSV)
    named=[x for x in observed if x.get("event")=="EXIT_RECOVERY"
           and x.get("status")=="STANDING_CLOSE_NOT_PLACED"
           and x.get("action")=="NO_STANDING_CLOSE"
           and "CLOSE_PROOF_HOLD_NO_CURRENT_LEDGER" in (x.get("notes") or "")]
    check("INV_NO_CURRENT_LEDGER_PREMATCH_HOLD_DURABLE",
          not ex.calls and bool(named) and bool(t.open_red(fid,it.intent_id))
          and any(x.get("reject_category")=="CLOSE_PROOF_HOLD_NO_CURRENT_LEDGER"
                  for x in observed if x.get("status")=="AUTHORISED_CLOSE_REFUSAL"),
          "calls=%r named=%r rows=%r"%(ex.calls,named,observed))
    for row in observed:
        if row.get("leader_fill_id")==fid:exact_row("INVENTORY_NO_CURRENT_LEDGER",row)


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
    try:inventory_hold_paths()
    except Exception as exc:check("INV_HARNESS_EXCEPTION",False,repr(exc))
    failed=[name for name,p in RESULTS if not p]
    print("TOTAL=%d FAILED=%d"%(len(RESULTS),len(failed)),flush=True)
    print("FAILED_LABELS="+",".join(failed),flush=True)
    return 1 if failed else 0

if __name__=="__main__":
    if len(sys.argv)==4 and sys.argv[1]=="--crash":
        crash_child(sys.argv[2],sys.argv[3])
    raise SystemExit(main())
