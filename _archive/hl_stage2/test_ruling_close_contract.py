#!/usr/bin/env python3
"""RED-only witnesses for Boss's 18 November DOOR_3 close ruling."""
import os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
TMP = Path(tempfile.mkdtemp(prefix="ruling_close_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(TMP), "HL_LIVE_ENV_FILE": str(TMP / "missing.env"),
 "HL_LEADER_NETWORK":"testnet", "HL_FOLLOWER_NETWORK":"testnet", "HL_LIVE_SCOPE_SWEEP_THREAD":"0",
 "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS":"0", "HL_LIVE_GLOBAL_LOCK_FILE":str(TMP / "lock")})
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as c
from types import SimpleNamespace

RESULTS=[]
def check(name, ok, detail=""):
    RESULTS.append(bool(ok)); print("RESULT::%s_%s%s"%(name,"PASS" if ok else "FAIL",(" | "+str(detail)[:500]) if detail else ""), flush=True)
class Harness:
    def __init__(self, net, owned=0): self.net=net; self.owned=owned; self.rows=[]
    def _fresh_exchange_net(self, coin): return self.net
    def _floor_wire_size(self, size, dec): return round(size, dec or 0)
    def _open_close_escalation(self, intent, reason): self.rows.append(reason)
def intent(): return SimpleNamespace(fill=SimpleNamespace(coin="BTC",leader_wallet="0x"+"a"*40))
def expired(net, requested=10, owned=0):
    h=Harness(net,owned); decision={}
    def decide(kind, amount=0.0, ro=False, why=""):
        decision.update(kind=kind, amount=amount, ro=ro, why=why); return ro,amount,why
    result=c.SenderGateway._close_lag_window_expired(h,intent(),requested,2,-1.0,0.0,decide)
    return h,decision,result

# Clause 1 — owned-size close is sent without reduce_only.
def test_owned_size_no_reduce_only():
    h,d,r=expired(10,10,10); check("RULING_OWNED_SIZE_EQUAL_NET_NOT_REDUCE_ONLY",r==(False,10.0,"") and d.get("amount")==10 and not d.get("ro"),d)
# Clause 2 — divergence is surfaced; neither unclamped 10 nor silently clamped 3 is acceptable.
def test_owned_size_divergence_surfaced():
    h,d,r=expired(3,10,10); check("RULING_OWNED_SIZE_DIVERGENCE_SURFACED",r[1]==10 and not r[0] and bool(h.rows),{"result":r,"escalations":h.rows})
# Clause 3 — readable flat exchange with a ledger sleeve sends nothing.
def test_flat_exchange_sends_nothing():
    h,d,r=expired(0,10,10); check("RULING_READABLE_FLAT_SENDS_NOTHING",r[1]==0 and d.get("kind")=="HOLD",{"result":r,"decision":d})
# Clause 4 — no ownership proof sends nothing and alerts/escalates.
def test_no_ownership_proof_alerts():
    h,d,r=expired(3,10,0); check("RULING_NO_OWNERSHIP_PROOF_NO_SEND_AND_ALERT",r[1]==0 and bool(h.rows),{"result":r,"escalations":h.rows})
# Clause 5 — owned close size must not derive from min(requested, abs(net)).
def test_owned_close_forbids_min_clamp():
    h,d,r=expired(3,10,10); check("RULING_OWNED_CLOSE_FORBIDS_MIN_CLAMP",r[1]!=min(10,abs(3)),r)

for fn in (test_owned_size_no_reduce_only,test_owned_size_divergence_surfaced,test_flat_exchange_sends_nothing,test_no_ownership_proof_alerts,test_owned_close_forbids_min_clamp):
    try: fn()
    except Exception as e: check(fn.__name__,False,"EXCEPTION %s: %s"%(type(e).__name__,e))
print("TOTAL=%d FAILED=%d"%(len(RESULTS),sum(not x for x in RESULTS)),flush=True)
sys.exit(int(any(not x for x in RESULTS)))
