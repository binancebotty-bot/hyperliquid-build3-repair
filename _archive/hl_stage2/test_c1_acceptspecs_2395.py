#!/usr/bin/env python3
"""TASK-C1-ACCEPTSPECS-2395: fence-pinned acceptance tests, NOT engine fixes.

Rule: RO=True iff wire delta opposes fresh exchange net and qty<=abs(net).
All physical SDK responses are OFFLINE synthetics and use the real pinned
SenderGateway, ConfigManager, IntentBuilder, ManualLedger and poll-wallet method.
Run: python3 -u test_c1_acceptspecs_2395.py
"""
import csv
import json
import os
import sys
import tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import test_core_c7_close_must_send as f
c=f.c
OUT=[]

def check(name, passed, detail=""):
    passed=bool(passed)
    OUT.append((name,passed))
    print("RESULT::%s_%s | %s"%(name,"PASS" if passed else "FAIL",str(detail)[:1250]),flush=True)

def near(a,b):
    try:return abs(float(a)-float(b))<=1e-8
    except (ValueError,TypeError):return False

def rows(path, fid):
    if not Path(path).exists():return []
    with Path(path).open(newline="",encoding="utf-8-sig") as h:
        return [r for r in csv.DictReader(h) if r.get("leader_fill_id")==fid]

def record(fid, area):
    r=rows(c.RECONCILIATION_CSV,fid)
    s=rows(c.SEND_ATTEMPTS_CSV,fid)
    red=[v for v in c.load_json(c.CLOSE_ESCALATIONS_FILE,{}).values()
         if isinstance(v,dict) and v.get("leader_fill_id")==fid]
    print("EVIDENCE::%s %s"%(area,json.dumps({
        "reconciliation":[{k:x.get(k,"") for k in
          ("event","status","action","reject_category","terminal_state","engine_can_send","notes")}
          for x in r[-6:]],
        "send_attempts":[{k:x.get(k,"") for k in
          ("status","copy_size","reduce_only_sent","exchange_order_id","cloid","terminal_state")}
          for x in s[-4:]],"red":red},sort_keys=True)[:3200]),flush=True)
    return r,s,red

def entry(ledger,wallet,fid):
    # Actual IntentBuilder entry, not an invented Intent object. Start flat.
    f.set_sleeve(ledger,wallet,0.0)
    fill=c.LeaderFill(fid,wallet,f.COIN,"BUY",f.PX,1.0,c.utc_now_ms(),"POLL")
    it=c.IntentBuilder(c.ConfigManager(),ledger).build(fill)
    it.intent_id=fid
    it.decision="ENTRY_ALLOWED"
    return it

def a_wallet_mode_unreadable():
    # A1: entry starts authorised with ON, becomes unreadable at the FINAL
    # send-time wallet-mode check. Fail closed and make operator-visible row.
    fid="ACC_A_ENTRY_MODE_UNKNOWN"
    led,ex,net=f.new_ledger(),f.FakeExchange(),[0.0]
    gw=f.make_gateway(ex,led,net)
    it=entry(led,f.A,fid)
    gw.cfg.wallet_mode=lambda _:(_ for _ in ()).throw(RuntimeError("MODE_UNREADABLE"))
    ok,status=gw.send_if_allowed(it)
    rec,send,red=record(fid,"A_ENTRY_UNREADABLE")
    expected="SEND_NOT_ATTEMPTED_WALLET_MODE_UNREADABLE"
    named=[x for x in rec if x.get("status")==expected
           and x.get("action")=="REVIEW_WALLET_MODE_BEFORE_ENTRY"
           and x.get("engine_can_send")=="False"]
    check("A_ENTRY_UNREADABLE_NAMED_FAIL_CLOSED",
          not ok and not ex.calls and status==expected and bool(named),
          "status=%r wire=%r expected_row=%s named=%r"%(status,ex.calls,expected,named))
    # A2: same unreadability while leader EXITs A-owned+2 netted with B-.5;
    # copied leader SELL 2 crosses follower +1.5 -> -.5 (INTENDED flip).
    fid="ACC_A_CLOSE_FLIP_MODE_UNKNOWN"
    led,ex,net=f.new_ledger(),f.FakeExchange(),[1.5]
    f.set_sleeve(led,f.B,-0.5)
    it=f.exit_intent(led,f.A,"SELL",2.0,fid,2.0)
    gw=f.make_gateway(ex,led,net)
    gw.cfg.wallet_mode=lambda _:(_ for _ in ()).throw(RuntimeError("MODE_UNREADABLE"))
    ok,status=gw.send_if_allowed(it)
    rec,send,red=record(fid,"A_CLOSE_UNREADABLE")
    wire=ex.calls
    expected_ro=(net[0]<0) or (2.0<=net[0] and net[0]>0)
    # Explicit governing rule: SELL2 vs +1.5 is NOT reduce-only.
    check("A_CLOSE_UNREADABLE_FOLLOW_OWNED_FLIP_NON_RO",
          ok and len(wire)==1 and wire[0]["is_buy"] is False
          and near(wire[0]["size"],2.0) and wire[0]["reduce_only"] is False
          and not expected_ro and near(led.coin_net(f.COIN),1.5)
          and near(f.sleeve_of(led,f.A),2),
          "status=%r wire=%r ledger=%r (expected signed follower net after fill=-0.5)"%
          (status,wire,led.coin_net(f.COIN)))
    # Contrasting control: an ordinary bounded SELL <= +2.0 is RO True.
    fid="ACC_A_CLOSE_WITHIN_NET"
    led,ex,net=f.new_ledger(),f.FakeExchange(),[2.0]
    it=f.exit_intent(led,f.A,"SELL",1.0,fid,2.0)
    gw=f.make_gateway(ex,led,net)
    ok,status=gw.send_if_allowed(it)
    check("A_RO_BOUNDARY_REFERENCE_REGRESSION",
          ok and len(ex.calls)==1 and ex.calls[0]["reduce_only"] is True
          and near(ex.calls[0]["size"],1.0),
          "status=%r wire=%r"%(status,ex.calls))

def b_no_owned_proof():
    # B1: explicit A owned ZERO BUT another sleeve B still +1 so the coin
    # is not physically flat. Historical A close must NOT be consumed-flat.
    fid="ACC_B_ZERO_OWNED"
    led,ex,net=f.new_ledger(),f.FakeExchange(),[1.0]
    f.set_sleeve(led,f.B,1.0)
    it=f.exit_intent(led,f.A,"SELL",1.0,fid,1.0)
    f.set_sleeve(led,f.A,0.0)
    gw=f.make_gateway(ex,led,net)
    ok,status=gw.send_if_allowed(it)
    rec,send,red=record(fid,"B_ZERO")
    expected="CLOSE_PROOF_HOLD_NO_OWNED_SLEEVE"
    check("B_ZERO_OWNED_NAMED_HOLD_NO_WIRE",
          not ok and not ex.calls
          and any(x.get("reject_category")==expected
                  and x.get("action")=="RECONCILE_OWED_CLOSE_BEFORE_RETRY"
                  for x in rec),
          "status=%r wire=%r rows=%r"%(status,ex.calls,
                  [(x.get("status"),x.get("reject_category")) for x in rec]))
    # B2: A row absent from persisted state, B still+1. No phantom ownership.
    fid="ACC_B_UNPROVABLE_OWNED"
    led,ex,net=f.new_ledger(),f.FakeExchange(),[1.0]
    f.set_sleeve(led,f.B,1.0)
    it=f.exit_intent(led,f.A,"SELL",1.0,fid,1.0)
    led.data["by_wallet"].pop(f.A,None)
    gw=f.make_gateway(ex,led,net)
    ok,status=gw.send_if_allowed(it)
    rec,send,red=record(fid,"B_UNKNOWN")
    check("B_UNPROVABLE_NAMED_HOLD_NO_WIRE",
          not ok and not ex.calls
          and f.A not in led.data.get("by_wallet",{})
          and any(x.get("reject_category")==expected
                  and x.get("action")=="RECONCILE_OWED_CLOSE_BEFORE_RETRY"
                  for x in rec),
          "status=%r wire=%r rows=%r"%(status,ex.calls,
                  [(x.get("status"),x.get("reject_category")) for x in rec]))

def c_global_close_only():
    # C1: A+2,B-.5, net+1.5; top header CLOSE, leader SELL2.
    # Wire only +1.5 until flat; owed .5 persists for A.
    fid="ACC_C_GLOBAL_CLOSE_ONLY"
    led,ex,net=f.new_ledger(),f.FakeExchange(),[1.5]
    f.set_sleeve(led,f.B,-0.5)
    it=f.exit_intent(led,f.A,"SELL",2.0,fid,2.0)
    gw=f.make_gateway(ex,led,net)
    mode=["CLOSE"]
    gw.cfg.send_mode_now=lambda:mode[0]
    ok,status=gw.send_if_allowed(it)
    rec,send,red=record(fid,"C_GLOBAL_CLOSE")
    check("C_HEADER_CLOSE_ONLY_WIRE_1_5_RO_TRUE",
          ok and len(ex.calls)==1 and ex.calls[0]["is_buy"] is False
          and near(ex.calls[0]["size"],1.5)
          and ex.calls[0]["reduce_only"] is True,
          "status=%r wire=%r expected SELL1.5 RO=true"%(status,ex.calls))
    owed_name="GLOBAL_CLOSE_ONLY_OWED_REMAINDER"
    owed=[x for x in rec if x.get("status")==owed_name
          and x.get("intent_id")==it.intent_id
          and "owed_size=0.5" in (x.get("notes") or "")
          and x.get("action")=="RECHECK_WHEN_GLOBAL_CLOSE_ONLY_OFF_OR_FLAT"]
    check("C_OWED_HALF_DURABLE_EXPLICIT",
          bool(owed) and near(f.sleeve_of(led,f.A),2.0),
          "owed=%r expected named %s with owed_size=0.5"%(owed,owed_name))
    # Two independent clearing triggers and their durable acknowledgments.
    # The setter models a permitted operator-mode change only in the isolated
    # config fixture; no production config, engine or exchange is touched.
    mode[0]="ON"
    gw.clear_close_escalations()
    toggled=rows(c.RECONCILIATION_CSV,fid)
    check("C_OWED_ROW_CLEARS_WHEN_GLOBAL_SWITCH_OFF",
          any(x.get("status")=="GLOBAL_CLOSE_ONLY_OWED_CLEARED"
              and x.get("action")=="CLEARED_GLOBAL_CLOSE_ONLY_DISABLED"
              for x in toggled),
          "statuses=%r switch=%s"%([x.get("status") for x in toggled],mode[0]))
    mode[0]="CLOSE"
    f.set_sleeve(led,f.A,0.0)
    f.set_sleeve(led,f.B,0.0)
    net[0]=0.0
    gw.clear_close_escalations()
    flat=rows(c.RECONCILIATION_CSV,fid)
    check("C_OWED_ROW_CLEARS_WHEN_DUAL_FLAT",
          any(x.get("status")=="GLOBAL_CLOSE_ONLY_OWED_CLEARED"
              and x.get("action")=="CLEARED_DUAL_FLAT"
              for x in flat),
          "statuses=%r net=%r owned=%r"%([x.get("status") for x in flat],net[0],f.sleeve_of(led,f.A)))

def cfg_for(wallets):
    p=Path(tempfile.mkdtemp(prefix="c1_accept_cfg_"))/"live_config.json"
    p.write_text(json.dumps({"wallets":{w:{"enabled":True,"mode":mode,
                      "fixed_notional":100.0} for w,mode in wallets.items()},
                      "auto_send_enabled":True,
                      "global_controls":{"send_mode":"ON"}}),encoding="utf-8")
    return c.ConfigManager(p)

def d_cap_10():
    ten=["0x%040x"%(0xC100+i) for i in range(10)]
    extra="0x%040x"%(0xC110)
    cfg=cfg_for({**{w:"ON" for w in ten},extra:"ON"})
    check("D_CAP_REAL_CONFIG_HAS_11_LIVE",
          len(cfg.live_wallets())==11 and cfg.live_over_stream_cap()
          and len(cfg.stream_wallets())==10,
          "active=%s live=%s stream=%s"%(len(cfg.active_wallets()),
              len(cfg.live_wallets()),len(cfg.stream_wallets())))
    # D1 original 10 entries must still be actually dispatchable via the
    # real SenderGateway without treating 11th as whole-process fatal.
    successes=[]
    for idx,wallet in enumerate(ten):
        led,ex,net=f.new_ledger(),f.FakeExchange(),[0.0]
        gw=f.make_gateway(ex,led,net)
        gw.cfg=cfg  # real 11-wallet config, not synthetic cap boolean
        gw.cfg.liq_parity_enabled=lambda:False
        it=entry(led,wallet,"ACC_D_TEN_ENTRY_%02d"%idx)
        ok,status=gw.send_if_allowed(it)
        successes.append((wallet,ok,status,ex.calls))
    check("D_TEN_LEGITIMATE_ENTRIES_STILL_WIRE",
          all(ok and len(calls)==1 and calls[0]["is_buy"] is True
              and calls[0]["reduce_only"] is False
              for _,ok,_,calls in successes),
          "10 entry outcomes=%r"%[(w[-4:],o,st,
              [(x["is_buy"],x["size"],x["reduce_only"]) for x in calls])
              for w,o,st,calls in successes])
    # D2 11th still holds an owned sleeve: actual close with real gateway.
    led,ex,net=f.new_ledger(),f.FakeExchange(),[1.0]
    it=f.exit_intent(led,extra,"SELL",1.0,"ACC_D_EXTRA_EXIT",1.0)
    gw=f.make_gateway(ex,led,net)
    gw.cfg=cfg
    ok,status=gw.send_if_allowed(it)
    check("D_ELEVENTH_NONFLAT_EXIT_STILL_WIRES",
          ok and len(ex.calls)==1 and ex.calls[0]["is_buy"] is False
          and near(ex.calls[0]["size"],1.0)
          and ex.calls[0]["reduce_only"] is True,
          "status=%r calls=%r"%(status,ex.calls))
    # D3 11th ON must NOT open additional exposure beyond stream capacity.
    led,ex,net=f.new_ledger(),f.FakeExchange(),[0.0]
    gw=f.make_gateway(ex,led,net)
    gw.cfg=cfg
    it=entry(led,extra,"ACC_D_EXTRA_ENTRY")
    ok,status=gw.send_if_allowed(it)
    rec,send,red=record(it.intent_id,"D_EXTRA_ENTRY")
    check("D_ELEVENTH_ENTRY_EXIT_ONLY_NAMED_BLOCK",
          not ok and not ex.calls
          and any(x.get("status")=="WALLET_CAP_EXIT_ONLY_ENTRY_BLOCKED"
                  and x.get("action")=="NO_SEND_ELEVENTH_WALLET_ENTRY"
                  and x.get("engine_can_send")=="False" for x in rec),
          "status=%r calls=%r rows=%r"%(status,ex.calls,
                                       [(x.get("status"),x.get("action")) for x in rec]))
    # D4 actual leader poll selection: an 11th ON still shows up flat today,
    # a violation, whereas explicit CLO nonflat/flat poll behaviour is a
    # useful regression control (does not by itself prove auto-conversion).
    led=f.new_ledger()
    f.set_sleeve(led,extra,1.0)
    led.save(touched_sleeves=[(extra,f.COIN)])
    core=object.__new__(c.LiveCopyCore)
    core.cfg=cfg
    core.wallets=cfg.stream_wallets()
    core.ledger=led
    os.environ["HL_LIVE_POLL_ALL_ACTIVE"]="1"
    actual_nonflat=c.LiveCopyCore.poll_wallets(core)
    f.set_sleeve(led,extra,0.0)
    led.save(touched_sleeves=[(extra,f.COIN)])
    actual_flat=c.LiveCopyCore.poll_wallets(core)
    check("D_EXTRA_NONFLAT_FOLLOWED_FOR_EXIT",
          len(actual_nonflat)==11 and extra in actual_nonflat
          and set(ten).issubset(set(actual_nonflat)),
          "selected=%r"%actual_nonflat)
    check("D_EXTRA_FLAT_NOT_FOLLOWED",
          len(actual_flat)==10 and extra not in actual_flat
          and set(actual_flat)==set(ten),
          "selected=%r"%actual_flat)
    # D5 known CLO path regression: unlike 11 ON, a proper CLO wallet is
    # REST followed while nonflat, not polled flat, and does not occupy WS.
    clo=cfg_for({**{w:"ON" for w in ten},extra:"CLO"})
    core.cfg=clo
    core.wallets=clo.stream_wallets()
    f.set_sleeve(led,extra,1.0)
    led.save(touched_sleeves=[(extra,f.COIN)])
    clo_live=c.LiveCopyCore.poll_wallets(core)
    f.set_sleeve(led,extra,0.0)
    led.save(touched_sleeves=[(extra,f.COIN)])
    clo_flat=c.LiveCopyCore.poll_wallets(core)
    check("D_KNOWN_CLO_POLL_NONFLAT_ONLY_REGRESSION",
          not clo.live_over_stream_cap() and len(clo.stream_wallets())==10
          and extra in clo_live and extra not in clo_flat
          and set(ten).issubset(set(clo_live))
          and set(clo_flat)==set(ten),
          "clo_nonflat=%r clo_flat=%r"%(clo_live,clo_flat))

def main():
    for name,fn in [("A",a_wallet_mode_unreadable),("B",b_no_owned_proof),
                    ("C",c_global_close_only),("D",d_cap_10)]:
        try:fn()
        except Exception as exc:
            check(name+"_HARNESS_EXCEPTION",False,type(exc).__name__+": "+str(exc))
    failed=[name for name,ok in OUT if not ok]
    print("TOTAL=%d FAILED=%d"%(len(OUT),len(failed)),flush=True)
    print("FAILED_LABELS="+",".join(failed),flush=True)
    return int(bool(failed))

if __name__=="__main__":
    raise SystemExit(main())
