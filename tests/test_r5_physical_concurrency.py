"""R5 real _place_order -> exchange.order concurrency regression; never uses network."""
import ast
import math
import os
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional, Callable

CORE=Path(__file__).resolve().parents[1]/"_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
tree=ast.parse(CORE.read_text(encoding="utf-8-sig"))
cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SenderGateway")
methods=[next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==n)
         for n in ("_wire_entry_exposure_block","_place_order","_place_order_impl")]
scope={
    "Any":Any,"Dict":Dict,"Optional":Optional,"Callable":Callable,
    "math":math,"os":os,"time":time,
    "FOLLOWER_NETWORK":"testnet","MAINNET_ORDERS_CONFIRMED":False,
    "classify_send_lifecycle":lambda i:i.lifecycle,
    "normalise_wallet":lambda x:str(x).lower(),
    "fnum":lambda x,default=0:float(x if x is not None else default),
    "utc_now_ms":lambda:int(time.time()*1000),
    "_sender_lease_owned":lambda:True,
    "_sdk_cloid":lambda x:x,"_exchange_accepts_cloid":lambda x:False,
    "_open_orders_send_begin":lambda:None,"_open_orders_send_end":lambda:None,
    "log_error":lambda *a:None,
    "PreWireNoCallFault":type("PreWireNoCallFault",(Exception,),{}),
    "PendingSendWriteFailed":type("PendingSendWriteFailed",(Exception,),{}),
}
exec(compile(ast.Module(body=methods,type_ignores=[]),str(CORE),"exec"),scope)

class FakeExchange:
    def __init__(self):self.calls=[];self.lock=threading.Lock()
    def order(self,*args,**kwargs):
        with self.lock:self.calls.append((args,kwargs))
        time.sleep(.025)  # actual exchange observation stays stale
        return {"status":"ok","response":{"type":"order","data":{"statuses":[{"resting":{"oid":123}}]}}}

class Gateway:
    _wire_entry_exposure_block=scope["_wire_entry_exposure_block"]
    _place_order=scope["_place_order"]
    _place_order_impl=scope["_place_order_impl"]
    _reduce_only_for_intent=lambda self,i:i.lifecycle in {"EXIT","REDUCE"}
    _master_gate_reason=lambda self,*a,**k:""
    _final_close_proof=lambda self,*a,**k:""
    _reserve_exchange_order_slot=lambda self,**k:int(time.time()*1000)
    _note_sender_key_rejection=lambda self,response:None
    _gate_refusal_row=lambda self,*a,**k:None
    _journal_authorised_close_refusal=lambda self,*a,**k:None
    def __init__(self):
        self._wire_cap_lock=threading.RLock()
        self._wire_cap_reservations={}
        self.cfg=SimpleNamespace(max_wallet_exposure=lambda w:10.,
                                  max_total_exposure=lambda:10.)
        # Freeze exchange and ledger observations: this is the race the old test missed.
        self.ledger=SimpleNamespace(wallet_abs_exposure_usd=lambda *a:0.)
        self.cap_source=SimpleNamespace(_resting=lambda:{},
                    _exposure_pending=[],
                    follower_exposure=lambda:{"ok":True,"total_usd":0.})
    def _send(self,ex,intent,reduce_only=False):
        return self._place_order(ex,"BTC",True,6.,1.,"Ioc",reduce_only,
                                 timing={},intent=intent,path="r5_test")
def intent(fid,lifecycle="ENTRY"):
    return SimpleNamespace(fill=SimpleNamespace(leader_wallet="w",coin="BTC",leader_fill_id=fid),
                           intent_id="intent-"+fid,lifecycle=lifecycle,
                           reduce_only_intended=lifecycle=="EXIT")

def test_two_simultaneous_distinct_entries_one_physical_call():
    gw=Gateway();ex=FakeExchange();out=[]
    barrier=threading.Barrier(3)
    def run(fid):
        barrier.wait()
        out.append(gw._send(ex,intent(fid)))
    ts=[threading.Thread(target=run,args=(id,)) for id in ("a","b")]
    for t in ts:t.start()
    barrier.wait()
    for t in ts:t.join(timeout=3);assert not t.is_alive()
    assert len(ex.calls)==1, "both entries crossed physical exchange.order with stale observation"
    assert len(gw._wire_cap_reservations)==1

def test_same_intent_duplicate_not_sent_again():
    gw=Gateway();ex=FakeExchange();i=intent("replay")
    gw._send(ex,i);gw._send(ex,i)
    assert len(ex.calls)==1

def test_reduce_only_flag_cannot_bypass_entry_cap():
    gw=Gateway();ex=FakeExchange()
    gw._send(ex,intent("first"))
    gw._send(ex,intent("forged"),reduce_only=True)
    assert len(ex.calls)==1

def test_genuine_close_above_cap_reaches_wire():
    gw=Gateway();ex=FakeExchange()
    gw._wire_cap_reservations[("w","held","held")]={"wallet":"w","notional":20.,"state":"UNKNOWN"}
    gw._send(ex,intent("exit","EXIT"),reduce_only=True)
    assert len(ex.calls)==1

def test_current_builder_reservation_only_counted_once():
    gw=Gateway();i=intent("one")
    gw.cap_source._exposure_pending=[("BTC",6.,1.,time.monotonic(),"one")]
    assert gw._wire_entry_exposure_block(i,6.,1.,False)==""
    gw.cap_source._exposure_pending.append(("BTC",5.,1.,time.monotonic(),"other"))
    assert gw._wire_entry_exposure_block(i,6.,1.,False)=="ENTRY_WALLET_EXPOSURE_CAP"

def test_duplicate_builder_reservation_fails_closed():
    gw=Gateway();i=intent("one")
    gw.cap_source._exposure_pending=[("BTC",6.,1.,time.monotonic(),"one")]*2
    assert gw._wire_entry_exposure_block(i,6.,1.,False)=="ENTRY_CAP_RESERVATION_AMBIGUOUS"
