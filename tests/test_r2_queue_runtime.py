"""R2 runtime 5,217-fill admission burst; fake audit and no exchange/network."""
import ast
import queue
import threading
import time
from pathlib import Path
from types import SimpleNamespace as NS
from typing import Any, Dict, Tuple, List, Optional
import hashlib
import os

CORE=Path(__file__).resolve().parents[1]/"_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
tree=ast.parse(CORE.read_text(encoding="utf-8-sig"))
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="LiveCopyCore")
def method(name):
    return next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
rows=[]
def durable_append(path,fields,data,**kw):
    assert kw.get("durable") is True
    rows.append(data)
    return True
scope={"queue":queue,"threading":threading,"time":time,"hashlib":hashlib,
       "LeaderFill":NS,
       "os":os,"Any":Any,"Dict":Dict,"Tuple":Tuple,"List":List,
       "canonical_coin_key":lambda coin:coin,
       "utc_now_ms":lambda:int(time.time()*1000),
       "utc_now_iso":lambda:"2026-11-08T00:00:00Z",
       "stamp_fill":lambda *args:None,
       "fnum":lambda x,default=0.:float(x if x is not None else default),
       "RECONCILIATION_CSV":Path("/dev/null"),
       "RECONCILIATION_FIELDS":["event","status","leader_wallet","leader_fill_id","coin","action","notes"],
       "append_csv":durable_append,
       "log_error":lambda *a:None}
exec(compile(ast.Module(body=[method(n) for n in
    ("_dispatch_fill","_release_queued","hot_backlog","_is_close_fill","_shard")],type_ignores=[]),
    str(CORE),"exec"),scope)

class FakeCore:
    _dispatch_fill=scope["_dispatch_fill"]
    _release_queued=scope["_release_queued"]
    hot_backlog=scope["hot_backlog"]
    _shard=scope["_shard"]
    _guard_key=lambda self,f:f.leader_fill_id
    _already_handled=lambda self,f:False
    def _is_close_fill(self,f):return f.raw.get("close",False)
    def __init__(self):
        self._hot_queues=[queue.Queue(maxsize=384)]
        self._prio_queues=[queue.Queue(maxsize=96)]
        self._entry_slots=threading.BoundedSemaphore(384)
        self._close_slots=threading.BoundedSemaphore(96)
        self._queued_lock=threading.Lock()
        self._queued_keys=set()
        self._pending_ts={}
        self._pending_seen={}
        self._pending_rowed=set()
        self._coin_lane={}
        self._queue_slot_kind={}
        self._converge_queued=set()
        self._idem_lock=threading.Lock()
        self._idem_accepted=set()
        self.sender=NS(known_dispatch_reject=lambda f:"")
        self.intent_builder=NS(cfg=NS(wallet_enabled=lambda w:True,
                                      wallet_mode=lambda w:"ON"))
    def _fill_trace(self,*a,**kw):pass

def fill(i,close=False):
    return NS(leader_wallet="wallet",coin="BTC" if not close else "ETH",
              side="SELL" if close else "BUY",
              leader_fill_id="fill-"+str(i),timestamp_ms=1700000000000+i,
              source="POLL",raw={"close":close})

def clear(q,core):
    batch=[]
    while True:
        try:batch.append(q.get_nowait())
        except queue.Empty:break
    if batch:core._release_queued(batch,q)

def test_burst_5217_no_unrecorded_refusals():
    rows.clear();c=FakeCore()
    accepted=0
    for i in range(5217):
        if c._dispatch_fill(fill(i)):accepted+=1
    assert accepted==384
    assert c.hot_backlog()==384
    assert len(rows)==5217-384
    assert all(x["status"]=="HOT_QUEUE_CAP_RETRY" for x in rows)
    clear(c._hot_queues[0],c)
    assert c.hot_backlog()==0
    assert c._dispatch_fill(fill(5218))
    assert c.hot_backlog()==1

def test_close_admitted_during_full_entry_queue():
    c=FakeCore()
    for i in range(384):assert c._dispatch_fill(fill(i))
    assert not c._dispatch_fill(fill(385))
    assert c._dispatch_fill(fill(386,close=True))
    assert c._prio_queues[0].qsize()==1
    clear(c._prio_queues[0],c);clear(c._hot_queues[0],c)
    assert c.hot_backlog()==0

def test_duplicate_is_only_admitted_once():
    c=FakeCore()
    assert c._dispatch_fill(fill(1))
    assert c._dispatch_fill(fill(1))
    assert c.hot_backlog()==1
    clear(c._hot_queues[0],c)

def test_release_uses_admission_kind_not_mutable_position():
    c=FakeCore();f=fill(1,close=True)
    assert c._dispatch_fill(f)
    f.raw["close"]=False
    clear(c._prio_queues[0],c)
    assert c._close_slots.acquire(False)
    c._close_slots.release()
