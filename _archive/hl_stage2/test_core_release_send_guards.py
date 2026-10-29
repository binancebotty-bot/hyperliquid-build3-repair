"""Release combination: the openOrders cache send guard (begin/end around exchange.order and exchange.cancel) and the
write-behind pending_send pre_send hook live together in SenderGateway._place_order. Required order:
slot + cooldown wait -> pre_send (pending_send write, sync) -> send-in-flight begin -> exchange.order -> finally send end.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_release_send_guards.py"""
import os, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
tmp = Path(tempfile.mkdtemp(prefix="rsg_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
os.environ.pop("HL_LIVE_OPEN_ORDERS_CACHE_SEC", None)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

c.USER_WALLET = "0x" + "c" * 40
c.follower_dex_scope = lambda: [""]
fetches = []
c.OPEN_ORDERS_FETCHER = lambda payload, *a, **k: (fetches.append(payload) or [{"oid": 7, "sz": "1.5"}])
c.invalidate_open_orders_cache()

events = []
def reserve(**k):
    events.append("slot_cooldown_wait"); return 0
# _place_order now consults the master send gate (self._master_gate_reason(intent, path)) at the top and again
# right before the physical call, and journals a refusal through self._gate_refusal_row. The fake gateway must
# answer that gate with the REAL rules - a stub that always allows would delete the check the product added.
# Every call below therefore carries an intent (a gate call without one fails CLOSED as MISSING_INTENT_CONTEXT)
# and a config that says sends are allowed, so the real method answers "" exactly as a live ON/FULL wallet does.
class _AllowAllCfg:
    send_mode_now = staticmethod(lambda: "ON")
    wallet_enabled = staticmethod(lambda _w: True)
    wallet_mode = staticmethod(lambda _w: "FULL")

INTENT = SimpleNamespace(intent_id="intent-1", path="test",
                         fill=SimpleNamespace(leader_wallet=c.USER_WALLET, coin="BTC", leader_fill_id="fill-1"))
gw = SimpleNamespace(_reserve_exchange_order_slot=reserve, _note_sender_key_rejection=lambda r: None,
                     cfg=_AllowAllCfg(), sender_key_invalid=None)
def _gate_refused(intent, path, reason):
    raise AssertionError("master send gate refused the order: %s (path=%s)" % (reason, path))
gw._gate_refusal_row = _gate_refused
gw._master_gate_reason = c.SenderGateway._master_gate_reason.__get__(gw)

probe = {}
class Ex:
    def order(self, *a, **k):
        events.append("exchange.order")
        n = len(fetches)
        c.periodic_open_orders([""]); c.periodic_open_orders([""])
        probe["reads"] = len(fetches) - n
        probe["stored"] = bool(c._OPEN_ORDERS_CACHE)
        probe["in_flight"] = c._OPEN_ORDERS_CACHE_STATE["sends"]
        return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": 9}}]}}}
    def cancel(self, *a, **k):
        n = len(fetches)
        c.periodic_open_orders([""]); c.periodic_open_orders([""])
        probe["cancel_reads"] = len(fetches) - n
        return {"status": "ok"}

def pre_send_ok():
    events.append("pending_send_write")
    probe["in_flight_at_pre_send"] = c._OPEN_ORDERS_CACHE_STATE["sends"]

# G1: a cache hit while exchange.order is in flight is rejected (every sweep re-reads, nothing is stored)
c.invalidate_open_orders_cache()
c.SenderGateway._place_order(gw, Ex(), "BTC", True, 1.0, 100.0, "Gtc", False, pre_send=pre_send_ok, intent=INTENT)
check("G1_CACHE_HIT_REJECTED_DURING_IN_FLIGHT_ORDER", probe.get("reads") == 2 and probe.get("stored") is False, str(probe))
check("G1B_SEND_COUNTER_RAISED_IN_FLIGHT_AND_RELEASED_AFTER",
      probe.get("in_flight") == 1 and c._OPEN_ORDERS_CACHE_STATE["sends"] == 0, str((probe, c._OPEN_ORDERS_CACHE_STATE)))

# G2: the cancel is guarded the same way
c.invalidate_open_orders_cache()
c.SenderGateway._cancel_order(gw, Ex(), "BTC", "9")
check("G2_CACHE_HIT_REJECTED_DURING_IN_FLIGHT_CANCEL",
      probe.get("cancel_reads") == 2 and c._OPEN_ORDERS_CACHE_STATE["sends"] == 0, str(probe))

# G3: order of events: slot/cooldown wait, then pending_send, then the call; pending_send is outside the send guard
check("G3_ORDER_SLOT_THEN_PENDING_SEND_THEN_ORDER",
      events[:3] == ["slot_cooldown_wait", "pending_send_write", "exchange.order"], str(events))
check("G3B_PENDING_SEND_WRITTEN_BEFORE_SEND_GUARD_BEGINS", probe.get("in_flight_at_pre_send") == 0, str(probe))

# G4: a failed pending_send write blocks the order and leaves no guard raised
called = []
class Ex2(Ex):
    def order(self, *a, **k):
        called.append(1); return {"status": "ok"}
def pre_send_fail():
    raise OSError("disk full")
try:
    c.SenderGateway._place_order(gw, Ex2(), "BTC", True, 1.0, 100.0, "Gtc", False, pre_send=pre_send_fail, intent=INTENT)
    raised = None
except Exception as exc:
    raised = exc
check("G4_FAILED_PENDING_SEND_BLOCKS_ORDER", isinstance(raised, c.PendingSendWriteFailed) and not called, repr(raised))
check("G4B_FAILED_PENDING_SEND_LEAVES_NO_GUARD_RAISED", c._OPEN_ORDERS_CACHE_STATE["sends"] == 0, str(c._OPEN_ORDERS_CACHE_STATE))

# G5: an exception from exchange.order still releases the guard (finally)
class Ex3(Ex):
    def order(self, *a, **k): raise RuntimeError("timeout after send")
try:
    c.SenderGateway._place_order(gw, Ex3(), "BTC", True, 1.0, 100.0, "Gtc", False, pre_send=pre_send_ok, intent=INTENT)
except RuntimeError:
    pass
check("G5_GUARD_RELEASED_AFTER_RAISED_ORDER", c._OPEN_ORDERS_CACHE_STATE["sends"] == 0, str(c._OPEN_ORDERS_CACHE_STATE))

# G6: the production order site still passes the pre_send hook
src = open(c.__file__, encoding="utf-8", errors="replace").read()
check("G6_PRODUCTION_SEND_PASSES_PRE_SEND_HOOK", "pre_send=_pending_send" in src)

print("TOTAL=%d FAILED=%d" % (len(R), sum(1 for _, ok in R if not ok)))
sys.exit(1 if any(not ok for _, ok in R) else 0)
