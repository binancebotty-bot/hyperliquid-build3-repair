#!/usr/bin/env python3
"""C1-G13 deterministic offline sequenced witnesses (no engine code edits).
Original Core pinned at 2a188facc73921bb46cea073c1028b7b38f5fb8e.
Run: HL_LIVE_ENV_FILE=/nonexistent python3 -u test_c1_g13_sequences.py
Tests are RED/GREEN as actually observed, not assumed.
"""
from __future__ import annotations
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
os.environ.update({
    "HL_LIVE_ENV_FILE":"/nonexistent",
    "HL_LEADER_NETWORK":"testnet",
    "HL_FOLLOWER_NETWORK":"testnet",
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS":"0",
    "HL_LIVE_RATE_LIMIT_COOLDOWN_MS":"0",
})
sys.path.insert(0,str(HERE))
import test_core_c7_close_must_send as f
c=f.c
A,B,COIN,PX=f.A,f.B,"BTC",100.0
records=[]

def approx(a,b):
    try:return abs(float(a)-float(b))<1e-8
    except (TypeError,ValueError,OverflowError):return False

def check(name,cond,detail=""):
    passed=bool(cond)
    records.append((name,passed))
    print("RESULT::%s_%s | %s"%(name,"PASS" if passed else "FAIL",str(detail)[:1000]),flush=True)

def rows(path,fid):
    p=Path(path)
    if not p.exists():return []
    with p.open(newline="",encoding="utf-8-sig") as handle:
        return [r for r in csv.DictReader(handle) if r.get("leader_fill_id")==fid]

def fstatus(oid,size,price=PX):
    return {"status":"ok","response":{"type":"order","data":{"statuses":[{"filled":{
        "oid":oid,"totalSz":str(size),"avgPx":str(price)}}]}}}

def resting(oid):
    return {"status":"ok","response":{"type":"order","data":{"statuses":[{"resting":{"oid":oid}}]}}}

def rejected(reason):
    return {"status":"ok","response":{"type":"order","data":{"statuses":[{"error":reason}]}}}

class Exchange:
    def __init__(self,net,script=None):
        self.net=net
        self.script=list(script or [])
        self.calls=[]
        self.seq=700
    def update_leverage(self,*args,**kwargs):
        return {"status":"ok"}
    def cancel(self,coin,oid):
        return {"response":{"data":{"statuses":["success"]}}}
    def order(self,coin,is_buy,size,px,tif,reduce_only=False,cloid=None):
        self.seq+=1
        self.calls.append({"coin":coin,"side":"BUY" if is_buy else "SELL",
            "size":float(size),"px":float(px),"tif":tif,"reduce_only":bool(reduce_only),
            "cloid":str(cloid) if cloid is not None else ""})
        result=self.script.pop(0) if self.script else fstatus(self.seq,size,px)
        statuses=((result.get("response") or {}).get("data") or {}).get("statuses") or []
        item=statuses[0] if statuses else {}
        if "filled" in item:
            self.net[0]+=float(item["filled"]["totalSz"])*(1 if is_buy else -1)
        return result

def make(name,a,b,net_value,mode="ON",script=None,side="SELL",qty=None):
    root=Path(tempfile.mkdtemp(prefix="g13_"+name+"_"))
    for key, filename in [
        ("SEND_ATTEMPTS_CSV","send_attempts.csv"),("LIVE_FILLS_CSV","live_fills.csv"),
        ("RECONCILIATION_CSV","reconciliation.csv"),("ORDER_INTENTS_CSV","order_intents.csv"),
        ("CLOSE_ESCALATIONS_FILE","close_escalations.json"),
        ("STANDING_CLOSES_FILE","standing_closes.json")]:
        setattr(c,key,root/filename)
    led=c.ManualLedger(path=root/"manual_ledger.json")
    f.set_sleeve(led,B,b)
    net=[float(net_value)]
    ex=Exchange(net,script)
    gw=f.make_gateway(ex,led,net)
    gw.cfg.send_mode_now=lambda:mode
    gw.cfg.liq_parity_enabled=lambda:False  # explicit testnet config; not a production-gate bypass
    gw._standing_closes={}
    gw._close_escalations={}
    fid="g13-"+name
    it=f.exit_intent(led,A,side,qty if qty is not None else abs(a),fid,a)
    assert approx(led.coin_net(COIN),a+b),(led.coin_net(COIN),a,b)
    return root,led,net,ex,gw,it,fid

def apply(gw,led,intent,oid,sz,tag):
    match=c.CopyFillMatcher(led,gw.audit)
    return match.match_and_apply({
        "coin":COIN,"side":intent.copy_side,"px":PX,"sz":sz,"oid":str(oid),
        "hash":"g13hash"+tag,"tid":str(oid),"time":c.utc_now_ms()},
        {intent.intent_id:intent})

def open_red(fid,intent_id):
    raw=c.load_json(c.CLOSE_ESCALATIONS_FILE,{})
    return [x for x in (raw.values() if isinstance(raw,dict) else [])
        if isinstance(x,dict) and x.get("state")=="OPEN"
        and x.get("leader_fill_id")==fid and x.get("intent_id")==intent_id]

def g1_close_tolerance():
    root,led,net,ex,gw,it,fid=make("G1",1.0,0.0,1.0)
    gw.cfg.max_close_adverse_diff_pct=lambda:0.25
    before=c.follower_mid
    c.follower_mid=lambda coin:PX
    try:
        ok,status=gw.send_if_allowed(it)
    finally:
        c.follower_mid=before
    wire=ex.calls
    check("G1_INSIDE_ADVERSE_TOLERANCE_STILL_WIRES",
          ok and len(wire)==1 and wire[0]["side"]=="SELL"
          and approx(wire[0]["size"],1.0) and wire[0]["reduce_only"]
          and (PX-wire[0]["px"])/PX*100<0.25,
          "stage=leader_close_after_price_read status=%r wire=%r"%(status,wire))
    applied=apply(gw,led,it,ex.seq,1.0,"g1") if ok and len(wire)==1 else False
    fill=rows(c.LIVE_FILLS_CSV,fid)
    check("G1_MATCHED_FILL_NOT_BLOCKED_BY_TOLERANCE",
          applied and approx(net[0],0) and approx(led.wallet_coin_position(A,COIN),0)
          and any(x["ledger_action"]=="CLOSED" and approx(x["wallet_position_after"],0) for x in fill),
          "stage=fill matched=%r net=%r rows=%r"%(applied,net[0],fill))

def g2_ce1b_resting_leader_price():
    script=[rejected("Could not immediately match."),resting(9002)]
    root,led,net,ex,gw,it,fid=make("G2",1.0,0,1.0,script=script)
    ok,status=gw.send_if_allowed(it)
    calls=list(ex.calls)
    red_at_rest=open_red(fid,it.intent_id)
    standing=c.load_json(c.STANDING_CLOSES_FILE,{})
    rec=rows(c.RECONCILIATION_CSV,fid)
    check("G2_REFUSED_IOC_RESTS_AT_LEADER_PRICE",
          len(calls)>=2
          and calls[0]["tif"].get("limit",{}).get("tif","").lower()=="ioc"
          and calls[1]["tif"].get("limit",{}).get("tif","").lower()=="gtc"
          and calls[1]["side"]=="SELL" and approx(calls[1]["size"],1)
          and approx(calls[1]["px"],it.fill.price),
          "stage=IOC_REJECT_TO_GTC status=%r calls=%r leader_px=%r"%(status,calls,it.fill.price))
    check("G2_STANDING_TRACKED_AND_OPEN_RED",
          not ok and bool(red_at_rest) and bool(standing)
          and any(r.get("status")=="EXIT_RECOVERY_QUEUED" and r.get("exchange_order_id")=="9002" for r in rec),
          "stage=standing red=%r standing=%r recon=%r"%(red_at_rest,standing,rec))
    cleared_before=gw.clear_close_escalations()
    check("G2_RED_REMAINS_UNTIL_SETTLED",cleared_before==0 and bool(open_red(fid,it.intent_id)),
          "stage=unfilled red=%r clear_count=%r"%(open_red(fid,it.intent_id),cleared_before))
    # Simulate an independently observed real copy-account fill of the queued GTC.
    if len(calls)>=2:
        net[0]-=1.0  # separate exchange fill event, NOT a new fake order
        applied=apply(gw,led,it,9002,1.0,"g2")
    else:applied=False
    cleared_after=gw.clear_close_escalations()
    fill=rows(c.LIVE_FILLS_CSV,fid)
    check("G2_RESTING_FILL_MATCHES_AND_CLEARS_ON_DUAL_FLAT",
          applied and cleared_after==1 and not open_red(fid,it.intent_id)
          and approx(led.coin_net(COIN),0) and approx(net[0],0)
          and any(x["ledger_action"]=="CLOSED" for x in fill),
          "stage=filled applied=%r clear=%r net=%r live_rows=%r"%
          (applied,cleared_after,net[0],fill))

def g4_429_reads_then_entry():
    root,led,net,ex,gw,it,fid=make("G4",0.0,0.0,0.0)
    # REAL LeaderFillIngestor.poll_hyperliquid_fills path; replace only HTTP response
    # transport. The 429 is observed in the reader before the independent entry
    # reaches the REAL SenderGateway.send_if_allowed path.
    poll=[]
    class Read429(Exception):
        status_code=429
    class RateLimitedHTTP:
        def post(self,*args,**kwargs):
            poll.append("HTTP_429")
            raise Read429("429 Too Many Requests")
    original_http=c.requests
    c.requests=RateLimitedHTTP()
    try:
        poll.append("START_READ")
        read_fills,read_status=c.LeaderFillIngestor().poll_hyperliquid_fills(
            A,c.utc_now_ms()-5000,c.utc_now_ms())
    finally:
        c.requests=original_http
    is_429=(poll==["START_READ","HTTP_429"] and read_status=="POLL_NETWORK_ERROR"
            and read_fills==[])
    fill=c.LeaderFill("g13-g4-entry",A,COIN,"BUY",PX,1.0,c.utc_now_ms(),"POLL")
    entry=c.Intent("g13-g4-entry",fill,"BUY",1.0,100.0,"ON","fixed",
        "ENTRY_ALLOWED","ENTRY",c.ManualLedger.sleeve_id(A,COIN),"","FLAT",
        0.0,0.0,False,False,c.utc_now_ms(),"lifecycle=ENTRY;")
    ok,status=gw.send_if_allowed(entry)
    check("G4_READ_429_NOT_AN_ENTRY_SEND_GATE",
          is_429 and poll==["START_READ","HTTP_429"] and ok
          and len(ex.calls)==1 and ex.calls[0]["side"]=="BUY",
          "sequence=%r read_status=%r status=%r wire=%r"%
          (poll,read_status,status,ex.calls))
    matched=apply(gw,led,entry,ex.seq,1.0,"g4") if ok and ex.calls else False
    check("G4_LATER_ENTRY_FILLED_AND_ROW",
          matched and approx(net[0],1.0) and approx(led.coin_net(COIN),1.0)
          and any(x.get("ledger_action")=="UPDATED" for x in rows(c.LIVE_FILLS_CSV,entry.fill.leader_fill_id)),
          "stage=after_read_429 filled=%r net=%r ledger=%r"%(matched,net[0],led.coin_net(COIN)))

def g5_wallet_cap():
    root=Path(tempfile.mkdtemp(prefix="g13_g5_cap_"))
    def cfg(nlive,nclo=0):
        wallets={}
        for i in range(nlive):
            wallets["0x%040x"%(0xD000+i)]={"enabled":True,"mode":"ON"}
        for i in range(nclo):
            wallets["0x%040x"%(0xE000+i)]={"enabled":True,"mode":"CLO"}
        p=root/("cfg%d_%d.json"%(nlive,nclo))
        p.write_text(json.dumps({"wallets":wallets,"global_controls":{},"auto_send_enabled":False}))
        return c.ConfigManager(p)
    ten,eleven,ten_clo=cfg(10),cfg(11),cfg(10,1)
    check("G5_TEN_LIVE_RESPECT_CAP",len(ten.stream_wallets())==10
          and not ten.live_over_stream_cap(),"stage=ten stream=%r cap=%r"%(len(ten.stream_wallets()),c.MAX_WALLETS))
    check("G5_ELEVENTH_LIVE_EXPLICIT_OVER_CAP",
          eleven.live_over_stream_cap() and len(eleven.stream_wallets())==10
          and len(eleven.live_wallets())==11,
          "stage=eleventh live=%r stream=%r over=%r"%
          (len(eleven.live_wallets()),len(eleven.stream_wallets()),eleven.live_over_stream_cap()))
    check("G5_ELEVENTH_CLO_HAS_NO_WS_SLOT",
          not ten_clo.live_over_stream_cap() and len(ten_clo.stream_wallets())==10
          and len(ten_clo.active_wallets())==11,
          "stage=eleventh_clo active=%r live=%r stream=%r"%
          (len(ten_clo.active_wallets()),len(ten_clo.live_wallets()),len(ten_clo.stream_wallets())))

def g5_real_startup_gate():
    """Execute the EXACT c.main() wallet-limit guard with I/O prerequisites stubbed.
    A sentinel replaces LiveCopyCore AFTER the real gate: 10 reaches it, 11
    must refuse with the production SystemExit before any sender is constructed.
    No network, private keys, process lock, or live core startup occurs.
    """
    import types
    root=Path(tempfile.mkdtemp(prefix="g13_g5_main_"))
    original={
        "ConfigManager":c.ConfigManager,
        "LiveCopyCore":c.LiveCopyCore,
        "acquire_global_instance_lock":c.acquire_global_instance_lock,
        "acquire_instance_lock":c.acquire_instance_lock,
        "install_core_attribution_hooks":c.install_core_attribution_hooks,
        "sender_key_check":c.sender_key_check,
    }
    x_claim=c._XNET.claim_network_stamp
    x_refusal=c._XNET.stamp_state_refusal
    prev_argv=sys.argv
    prev_lock=os.environ.get("HL_LIVE_GLOBAL_LOCK_FILE")
    class ReachedPostCapStartup(Exception):
        pass
    reached=[]
    try:
        c._XNET.claim_network_stamp=lambda *_a,**_k:None
        c._XNET.stamp_state_refusal=lambda *_a,**_k:""
        c.acquire_global_instance_lock=lambda *_a,**_k:None
        c.acquire_instance_lock=lambda *_a,**_k:None
        c.install_core_attribution_hooks=lambda *_a,**_k:None
        c.sender_key_check=lambda:{"ok":True,"detail":"offline_no_key"}
        def stop_before_engine(*args,**kwargs):
            reached.append("CORE_CONSTRUCTION_REACHED")
            raise ReachedPostCapStartup()
        c.LiveCopyCore=stop_before_engine
        for nlive,nclo,label in ((10,0,"TEN"),(11,0,"ELEVEN"),(10,1,"TEN_PLUS_CLO")):
            wallets={}
            for idx in range(nlive):
                wallets["0x%040x"%(0xD000+idx)]={"enabled":True,"mode":"ON"}
            for idx in range(nclo):
                wallets["0x%040x"%(0xE000+idx)]={"enabled":True,"mode":"CLO"}
            cfg=root/("main_config_%s.json"%label)
            cfg.write_text(json.dumps({"wallets":wallets,"global_controls":{},
                                       "auto_send_enabled":False}),encoding="utf-8")
            # The ConfigManager itself and its cap calculation are NOT mocked;
            # only its path is redirected to this synthetic configuration.
            original_cfg=original["ConfigManager"]
            c.ConfigManager=lambda *a, _cfg=cfg, **kw:original_cfg(_cfg)
            sys.argv=["HL_Live_Copy_Service_Core.py","--once"]
            reached.clear()
            outcome=""
            try:
                c.main()
                outcome="RETURNED"
            except SystemExit as exc:
                outcome="REFUSED:"+str(exc)
            except ReachedPostCapStartup:
                outcome="POST_CAP_STARTUP_REACHED"
            expected=(outcome=="POST_CAP_STARTUP_REACHED" and reached==["CORE_CONSTRUCTION_REACHED"]
                      if label!="ELEVEN" else
                      outcome.startswith("REFUSED:TOO_MANY_ACTIVE_WALLETS:")
                      and "11 wallets are LIVE" in outcome and not reached)
            check("G5_REAL_STARTUP_GATE_"+label,expected,
                  "phase=main_wallet_limit config=%s outcome=%s reached=%r"%
                  (label,outcome,reached))
    finally:
        for name,value in original.items():
            setattr(c,name,value)
        c._XNET.claim_network_stamp=x_claim
        c._XNET.stamp_state_refusal=x_refusal
        sys.argv=prev_argv
        if prev_lock is None:os.environ.pop("HL_LIVE_GLOBAL_LOCK_FILE",None)
        else:os.environ["HL_LIVE_GLOBAL_LOCK_FILE"]=prev_lock


def partial_close():
    """Safety-ordered IOC 0.6 -> pre-match HOLD/RED -> ledger proof -> real GTC
    recovery trigger -> GTC fill -> dual-flat RED clear. No blind pre-match retry.
    The test invokes the real recovery method AFTER proof; automatic scheduling
    of this trigger by the copy-poll loop is NOT proved in this bounded unit.
    """
    script=[fstatus(9201,0.6),resting(9202)]
    root,led,net,ex,gw,it,fid=make("PARTIAL",1.0,0.0,1.0,script=script,qty=1.0)
    ok,status=gw.send_if_allowed(it)
    first_calls=list(ex.calls)
    attempt_rows=rows(c.SEND_ATTEMPTS_CSV,fid)
    completed=[x for x in attempt_rows if x.get("status")=="ORDER_FILLED"
               and x.get("exchange_order_id")=="9201"]
    def stored_owed(row):
        response=json.loads(row.get("exchange_response") or "{}")
        filled=(response["response"]["data"]["statuses"][0]["filled"])
        return float(row["copy_size"])-float(filled["totalSz"])
    known_owed=stored_owed(completed[-1]) if completed else None
    red0=open_red(fid,it.intent_id)
    rec0=rows(c.RECONCILIATION_CSV,fid)
    check("P_PREMATCH_NO_BLIND_SECOND_SEND",
          ok and status=="ORDER_FILLED" and len(first_calls)==1
          and first_calls[0]["side"]=="SELL"
          and first_calls[0]["tif"].get("limit",{}).get("tif")=="Ioc"
          and approx(first_calls[0]["size"],1.0)
          and bool(red0)
          and any(x.get("status")=="STANDING_CLOSE_NOT_PLACED"
                  and "CLOSE_PROOF_HOLD_NO_OWNED_SLEEVE" in str(x.get("notes") or "")
                  for x in rec0),
          "phase=pre_match calls=%r red=%r recon=%r"%(first_calls,red0,rec0))
    check("P_DURABLE_EVENT_CORRELATED_OWED_0_4",
          approx(known_owed,0.4) and bool(completed)
          and all(x.get("leader_fill_id")==fid and x.get("intent_id")==it.intent_id
                  for x in completed)
          and bool(red0),
          "phase=durable_owed stored_order_qty=1 response_fill=0.6 derived_owed=%r red=%r"%
          (known_owed,red0))
    applied=apply(gw,led,it,9201,0.6,"partial") if ok else False
    fill=rows(c.LIVE_FILLS_CSV,fid)
    check("P_MATCH_PROVES_LEDGER_EXCHANGE_REMAINDER_0_4",
          applied and approx(net[0],0.4) and approx(led.coin_net(COIN),0.4)
          and approx(led.wallet_coin_position(A,COIN),0.4)
          and any(approx(x["fill_size"],0.6)
                  and approx(x["wallet_position_after"],0.4) for x in fill)
          and len(ex.calls)==1,
          "phase=post_match matched=%r ledger=%r exchange=%r calls=%r"%
          (applied,led.coin_net(COIN),net[0],ex.calls))

    # THE REAL recovery-placement method is invoked only after live fill ledger
    # proof and account-net agree. The earlier ledger_may_lag=True safety hold is
    # never disabled in the engine. Use leader PX rather than initial IOC PX.
    fresh=gw._fresh_exchange_net(COIN)
    ready=applied and approx(fresh,0.4) and approx(led.coin_net(COIN),fresh)
    if ready:
        gw._queue_exit_recovery_if_needed(
            ex,COIN,it,it.fill.price,0.4,fstatus(9201,0.6),
            "POST_MATCH_RECONCILED_LEDGER",remainder=None,sz_dec=3)
    calls=list(ex.calls)
    rec=rows(c.RECONCILIATION_CSV,fid)
    standing=c.load_json(c.STANDING_CLOSES_FILE,{})
    all_attempts=rows(c.SEND_ATTEMPTS_CSV,fid)
    expected_gtc=(len(calls)==2 and
                  calls[1]["tif"].get("limit",{}).get("tif")=="Gtc"
                  and calls[1]["side"]=="SELL"
                  and approx(calls[1]["size"],0.4)
                  and approx(calls[1]["px"],it.fill.price)
                  and calls[1]["reduce_only"])
    check("P_POSTPROOF_RECOVERY_GTC_AT_LEADER_PRICE",
          ready and expected_gtc
          and any(x.get("status")=="EXIT_RECOVERY_QUEUED"
                  and x.get("exchange_order_id")=="9202"
                  and x.get("intent_id")==it.intent_id for x in rec),
          "phase=post_proof ready=%r calls=%r rec=%r"%(ready,calls,rec))
    check("P_GTC_DURABLE_OID_AND_RED_UNTIL_FLAT",
          bool(standing) and bool(open_red(fid,it.intent_id))
          and any(x.get("status")=="ORDER_RESTING"
                  and x.get("exchange_order_id")=="9202"
                  and approx(x.get("copy_size"),0.4)
                  and x.get("intent_id")==it.intent_id for x in all_attempts)
          and gw.clear_close_escalations()==0,
          "phase=resting standing=%r red=%r attempts=%r"%
          (standing,open_red(fid,it.intent_id),
           [(x.get("status"),x.get("copy_size"),x.get("exchange_order_id"))
            for x in all_attempts]))
    if expected_gtc:
        net[0]-=0.4  # independently observed GTC venue fill
        matched_rest=apply(gw,led,it,9202,0.4,"partialgtc")
    else:
        matched_rest=False
    cleared=gw.clear_close_escalations()
    final_rows=rows(c.LIVE_FILLS_CSV,fid)
    check("P_GTC_FILL_DUAL_FLAT_CLEARS_RED",
          matched_rest and cleared==1 and not open_red(fid,it.intent_id)
          and approx(net[0],0) and approx(led.coin_net(COIN),0)
          and approx(led.wallet_coin_position(A,COIN),0)
          and any(approx(x.get("fill_size"),0.4) and x.get("ledger_action")=="CLOSED"
                  for x in final_rows),
          "phase=converged matcher=%r cleared=%r net=%r ledger=%r fills=%r"%
          (matched_rest,cleared,net[0],led.coin_net(COIN),final_rows))


def leader_flip():
    root,led,net,ex,gw,it,fid=make("FLIP",1.0,0.0,1.0,qty=1.0)
    ok1,status1=gw.send_if_allowed(it)
    applied1=apply(gw,led,it,ex.seq,1.0,"flipclose") if ok1 else False
    # Distinct genuine leader reversal event after close is settled: new short entry.
    new=c.LeaderFill("g13-FLIP-entry",A,COIN,"SELL",PX,1.0,c.utc_now_ms(),"POLL")
    entry=c.Intent("g13-FLIP-entry",new,"SELL",1.0,100.0,"ON","fixed",
        "ENTRY_ALLOWED","ENTRY",c.ManualLedger.sleeve_id(A,COIN),"","FLAT",
        0.0,0.0,False,False,c.utc_now_ms(),"lifecycle=ENTRY;")
    ok2,status2=gw.send_if_allowed(entry)
    applied2=apply(gw,led,entry,ex.seq,1.0,"flipentry") if ok2 else False
    check("F_LEADER_FLIP_CLOSE_THEN_SHORT_ENTRY",
          applied1 and applied2 and len(ex.calls)==2
          and all(x["side"]=="SELL" and approx(x["size"],1) for x in ex.calls)
          and ex.calls[0]["reduce_only"] and not ex.calls[1]["reduce_only"]
          and approx(net[0],-1) and approx(led.coin_net(COIN),-1),
          "stage=leader_close_then_reverse status=%r/%r wire=%r exchange=%r owned=%r"%
          (status1,status2,ex.calls,net[0],led.coin_net(COIN)))
    check("F_LEADER_FLIP_DISTINCT_COPY_FILL_ROWS",
          len(rows(c.LIVE_FILLS_CSV,fid))==1
          and len(rows(c.LIVE_FILLS_CSV,new.leader_fill_id))==1
          and approx(led.wallet_coin_position(A,COIN),-1),
          "stage=rows closed=%r new=%r ledger=%r"%
          (rows(c.LIVE_FILLS_CSV,fid),rows(c.LIVE_FILLS_CSV,new.leader_fill_id),led.wallet_coin_position(A,COIN)))

def dust_flat():
    root,led,net,ex,gw,it,fid=make("DUST",0.05,0.0,0.05,qty=0.05)
    ok,status=gw.send_if_allowed(it)
    matched=apply(gw,led,it,ex.seq,0.05,"dust") if ok and ex.calls else False
    check("D_SUBMIN_WHOLE_ACCOUNT_DUST_REDUCE_ONLY",
          ok and len(ex.calls)==1 and ex.calls[0]["reduce_only"]
          and approx(ex.calls[0]["size"],0.05)
          and matched and approx(net[0],0.0) and approx(led.coin_net(COIN),0.0),
          "stage=whole_owned_dust status=%r calls=%r physical=%r"%(status,ex.calls,net[0]))
    before=len(ex.calls)
    ok2,status2=gw.send_if_allowed(it)
    check("D_FLAT_REPLAY_NEVER_REOPENS_DUST",
          not ok2 and len(ex.calls)==before
          and approx(led.wallet_coin_position(A,COIN),0),
          "stage=flat_replay ok=%r status=%r calls=%r"%(ok2,status2,ex.calls))

def main():
    cases=[("G1",g1_close_tolerance),("G2",g2_ce1b_resting_leader_price),
           ("G4",g4_429_reads_then_entry),("G5",g5_wallet_cap),("G5_STARTUP",g5_real_startup_gate),
           ("PARTIAL",partial_close),("LEADER_FLIP",leader_flip),("DUST",dust_flat)]
    for label,fn in cases:
        try:fn()
        except Exception as exc:
            check(label+"_HARNESS_EXCEPTION",False,"%s: %s"%(type(exc).__name__,exc))
    fails=[x for x,passed in records if not passed]
    print("TOTAL=%d FAILED=%d"%(len(records),len(fails)),flush=True)
    print("FAILED_LABELS=%s"%(",".join(fails)),flush=True)
    return int(bool(fails))

if __name__=="__main__":
    raise SystemExit(main())
