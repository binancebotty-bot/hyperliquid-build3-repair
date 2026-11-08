"""R5 candidate checks atomic sender contract and reservation identity (offline)."""
import ast
from pathlib import Path
import threading
import time
from types import SimpleNamespace as NS
import math, os
from typing import Any, Dict, Optional, Callable
CORE=Path(__file__).resolve().parents[1]/"_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
txt=CORE.read_text(encoding="utf-8-sig")
tree=ast.parse(txt)
cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SenderGateway")
def meth(name):return next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==name)
scope={"Any":Any,"Optional":Optional,"Dict":Dict,"Callable":Callable,"math":math,
       "os":os,"time":time,"fnum":lambda x,default=0.:float(x if x is not None else default),
       "normalise_wallet":str.lower,"classify_send_lifecycle":lambda i:i.lifecycle}
exec(compile(ast.Module(body=[meth("_wire_entry_exposure_block"),meth("_place_order")],type_ignores=[]),
             str(CORE),"exec"),scope)
class Host:
    _reduce_only_for_intent=lambda self,i:i.lifecycle in {"EXIT","REDUCE"}
    _wire_entry_exposure_block=scope["_wire_entry_exposure_block"]
    _place_order=scope["_place_order"]
    def __init__(self):
        self._wire_cap_lock=threading.Lock()
        self.exposure=0.
        self.cfg=NS(max_wallet_exposure=lambda w:10.,max_total_exposure=lambda:10.)
        self.cap_source=NS(_resting=lambda:{},_exposure_pending=[],
                           follower_exposure=lambda:{"ok":True,"total_usd":self.exposure})
        self.ledger=NS(wallet_abs_exposure_usd=lambda w,p:self.exposure)
    def _place_order_impl(self,ex,coin,buy,size,px,tif,ro,timing,key,cloid,cool,pre,intent,path,leg):
        reason=self._wire_entry_exposure_block(intent,size,px,ro,leg)
        if reason:return reason
        time.sleep(.01)
        self.exposure+=size*px
        return "SENT"
def intent(life="ENTRY",fid="a"):
    return NS(fill=NS(leader_wallet="w",coin="BTC",leader_fill_id=fid),lifecycle=life)
def test_atomic_competing_entries():
    h=Host();out=[]
    def run():out.append(h._place_order(None,"BTC",True,6.,1.,"Ioc",False,intent=intent()))
    ts=[threading.Thread(target=run) for _ in range(2)]
    for t in ts:t.start()
    for t in ts:t.join()
    assert sorted(out)==["ENTRY_WALLET_EXPOSURE_CAP","SENT"]
    assert h.exposure==6.
def test_pending_does_not_double_count_current():
    h=Host()
    h.cap_source._exposure_pending=[("BTC",6.,1.,time.monotonic(),"a")]
    assert h._wire_entry_exposure_block(intent(),6.,1.,False)==""
    h.cap_source._exposure_pending.append(("BTC",5.,1.,time.monotonic(),"b"))
    assert h._wire_entry_exposure_block(intent(),6.,1.,False)=="ENTRY_WALLET_EXPOSURE_CAP"
def test_reduce_only_flag_not_close_proof():
    h=Host();h.exposure=10.
    assert h._wire_entry_exposure_block(intent(),1.,1.,True)=="ENTRY_WALLET_EXPOSURE_CAP"
    assert h._wire_entry_exposure_block(intent("EXIT"),1.,1.,True)==""
def test_gate_twice_inside_physical_path():
    impl=meth("_place_order_impl")
    calls=[x for x in ast.walk(impl) if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)]
    assert sum(x.func.attr=="_wire_entry_exposure_block" for x in calls)==2
