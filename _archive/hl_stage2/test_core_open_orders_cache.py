"""The two periodic openOrders sweeps (standing-close pruning, resting-size refresh) share a short TTL cache; the startup
orphan check and uncertain-send reconciliation always read fresh; every send/cancel invalidates; failed reads never cache.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_open_orders_cache.py"""
import os, sys, tempfile, threading
from pathlib import Path
from types import SimpleNamespace
tmp = Path(tempfile.mkdtemp(prefix="ooc_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
os.environ.pop("HL_LIVE_OPEN_ORDERS_CACHE_SEC", None)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

c.USER_WALLET = "0x" + "c" * 40
c.follower_dex_scope = lambda: [""]
calls = []
reply = [{"oid": 7, "sz": "1.5"}]  # what the info endpoint returns (exchange_truth wraps it as {"ok": True, "data": ...})
def fetcher(payload, *a, **k):
    calls.append(payload)
    if isinstance(reply, Exception):
        raise reply
    return reply
c.OPEN_ORDERS_FETCHER = fetcher

def fresh():
    calls.clear(); c.invalidate_open_orders_cache()

def sweep_pair(rest_oid="7"):
    """One main cycle: prune then refresh, with one standing close and one resting entry (default dex)."""
    now = c.utc_now_ms()
    me = SimpleNamespace(_resting_lock=threading.RLock(), _row_open_size=c.SenderGateway._row_open_size,
                         _standing_closes={"s1": {"oid": "7", "coin": "BTC", "placed_ms": now - 60000}},
                         _resting_entries={rest_oid: {"oid": rest_oid, "coin": "BTC", "size": 2.0, "placed_ms": now - 60000}})
    c.SenderGateway.prune_standing_closes(me)
    c.SenderGateway.refresh_resting_open_sizes(me)
    return me

# 1. cache hit inside the TTL: two sweeps, one openOrders call
fresh(); sweep_pair()
check("TWO_SWEEPS_ONE_CALL_INSIDE_TTL", len(calls) == 1, str(len(calls)))

# 2. a send invalidates: the next sweep reads again
fresh(); sweep_pair()
class Ex:
    def order(self, *a, **k): return {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": 9}}]}}}
    def cancel(self, *a, **k): return {"status": "ok", "response": {"data": {"statuses": ["success"]}}}
class BadEx(Ex):
    def order(self, *a, **k): raise RuntimeError("timeout after send")
    def cancel(self, *a, **k): raise RuntimeError("timeout after cancel")
# Contract note (CC-1 R35): _place_order now consults the master gate at the one physical call
#   _blocked = self._master_gate_reason(intent, path)
# so a bare SimpleNamespace gateway raises AttributeError before any exchange call, and the cache
# invalidation this test measures never runs. Rather than stub the gate out, bind the REAL gate
# methods and pass a real intent the real gate APPROVES - the send then reaches the exchange
# exactly as before, so SEND_INVALIDATES_CACHE still measures the production path.
SEND_INTENT = SimpleNamespace(
    fill=SimpleNamespace(leader_wallet=c.USER_WALLET, coin="BTC", leader_fill_id="f1"),
    intent_id="i-cache", notes="lifecycle=ENTRY", reason="ENTRY",
    wallet_position_before=0, copy_side="BUY", copy_size=1.0)
gw = SimpleNamespace(
    cfg=SimpleNamespace(send_mode_now=lambda: "ON", wallet_enabled=lambda w: True, wallet_mode=lambda w: "LIVE"),
    sender_key_invalid=False, audit=SimpleNamespace(append_reconciliation=lambda *a, **k: None),
    _gate_journal_failures=0,
    _reserve_exchange_order_slot=lambda **k: 0, _note_sender_key_rejection=lambda r: None)
gw._master_gate_reason = lambda intent, path="": c.SenderGateway._master_gate_reason(gw, intent, path)
gw._gate_refusal_row = lambda intent, path, reason: c.SenderGateway._gate_refusal_row(gw, intent, path, reason)
check("GATE_ALLOWS_THE_TEST_SEND", c.SenderGateway._master_gate_reason(gw, SEND_INTENT, "cache") == "",
      repr(c.SenderGateway._master_gate_reason(gw, SEND_INTENT, "cache")))
before = len(calls)
c.SenderGateway._place_order(gw, Ex(), "BTC", True, 1.0, 100.0, "Gtc", False, intent=SEND_INTENT)
sweep_pair()
check("SEND_INVALIDATES_CACHE", len(calls) == before + 1, str((before, len(calls))))
before = len(calls)
sweep_pair()
check("CACHE_REFILLS_AFTER_SEND_READ", len(calls) == before, str((before, len(calls))))
c.SenderGateway._cancel_order(gw, Ex(), "BTC", "9")
sweep_pair()
check("CANCEL_INVALIDATES_CACHE", len(calls) == before + 1, str((before, len(calls))))
before = len(calls)
# Same gate contract as above: a real intent is required, or the gate refuses before the exchange
# is reached and this case would silently test nothing. Here the send must fail AT THE EXCHANGE.
try: c.SenderGateway._place_order(gw, BadEx(), "BTC", True, 1.0, 100.0, "Gtc", False, intent=SEND_INTENT)
except RuntimeError: pass
sweep_pair()
check("FAILED_SEND_INVALIDATES_CACHE", len(calls) == before + 1, str((before, len(calls))))
before = len(calls)
try: c.SenderGateway._cancel_order(gw, BadEx(), "BTC", "9")
except RuntimeError: pass
sweep_pair()
check("FAILED_CANCEL_INVALIDATES_CACHE", len(calls) == before + 1, str((before, len(calls))))

# 3. a local projection update does not invalidate (the cache would never hit)
fresh(); me = sweep_pair(); n = len(calls)
with me._resting_lock:
    me._resting_entries["7"]["open_size"] = 0.5
sweep_pair()
check("LOCAL_PROJECTION_UPDATE_DOES_NOT_INVALIDATE", len(calls) == n == 1, str(len(calls)))

# 4. orphan check and uncertain-send reconciliation always read fresh, and do not feed the cache
fresh(); sweep_pair(); n = len(calls)
me = SimpleNamespace()
c.SenderGateway._read_open_orders(me); c.SenderGateway._read_open_orders(me)
check("ORPHAN_CHECK_READS_ALWAYS_CALL", len(calls) == n + 2, str((n, len(calls))))
n = len(calls)
c.SenderGateway.find_open_entry_order(me, "BTC", "BTC", "BUY", 100.0, 1.0)
c.SenderGateway.find_open_entry_order(me, "BTC", "BTC", "BUY", 100.0, 1.0)
check("UNCERTAIN_SEND_RECONCILIATION_ALWAYS_CALLS", len(calls) == n + 2, str((n, len(calls))))
fresh(); c.SenderGateway._read_open_orders(me); n = len(calls); sweep_pair()
check("ORPHAN_READ_DOES_NOT_FILL_CACHE", len(calls) == n + 1, str((n, len(calls))))

# 5. a failed or empty-with-error read is not cached and fails the same way as today
fresh()
reply = RuntimeError("429 throttled")
me = sweep_pair(); sweep_pair()
check("FAILED_READ_NOT_CACHED", len(calls) == 4, str(len(calls)))
reply = {"error": "rate limited"}  # an error body is not an order list
fresh(); sweep_pair(); sweep_pair()
check("ERROR_BODY_NOT_CACHED", len(calls) == 4, str(len(calls)))
reply = RuntimeError("429 throttled")
fresh(); me = sweep_pair()
check("FAILED_READ_KEEPS_ROWS_LIKE_TODAY", "s1" in me._standing_closes and "open_size" not in me._resting_entries["7"])
reply = []
fresh(); me = sweep_pair()
check("GENUINE_EMPTY_READ_STILL_PRUNES", "s1" not in me._standing_closes and len(calls) == 1)
reply = [{"oid": 7, "sz": "1.5"}]

# 6. TTL 0 disables; env var is read as configured
fresh(); os.environ["HL_LIVE_OPEN_ORDERS_CACHE_SEC"] = "0"
sweep_pair()
check("TTL_ZERO_DISABLES_CACHE", len(calls) == 2, str(len(calls)))
os.environ.pop("HL_LIVE_OPEN_ORDERS_CACHE_SEC")

# 7. the TTL expires (default 15 s)
fresh(); sweep_pair()
real_now = c.utc_now_ms
c.utc_now_ms = lambda: real_now() + 16000
sweep_pair()
c.utc_now_ms = real_now
check("TTL_EXPIRES_AFTER_15_SECONDS", len(calls) == 2, str(len(calls)))

# 8. a hit while a send is in flight is a miss (the exact interleaving: counter raised, cache not yet cleared)
fresh(); sweep_pair(); n = len(calls)
c._OPEN_ORDERS_CACHE_STATE["sends"] = 1
c.periodic_open_orders([""])
check("HIT_WHILE_SEND_IN_FLIGHT_IS_A_MISS", len(calls) == n + 1 and bool(c._OPEN_ORDERS_CACHE), str((n, len(calls))))
c.periodic_open_orders([""])
check("NO_STORE_WHILE_SEND_IN_FLIGHT", len(calls) == n + 2, str((n, len(calls))))
c._OPEN_ORDERS_CACHE_STATE["sends"] = 0
fresh(); sweep_pair(); n = len(calls)
c._open_orders_send_begin()
check("SEND_BEGIN_CLEARS_CACHE_WITH_COUNTER_RAISED", not c._OPEN_ORDERS_CACHE and c._OPEN_ORDERS_CACHE_STATE["sends"] == 1)
c._open_orders_send_end()
check("SEND_END_RELEASES_COUNTER", c._OPEN_ORDERS_CACHE_STATE["sends"] == 0)

# 9. fetch ordering: a slow OLDER fetch must not overwrite a NEWER cache entry (sequence taken at fetch start)
def run_periodic(box, name):
    box[name] = c.periodic_open_orders([""])
def blocking_fetcher(script):
    """script: list of (started_event, release_event, data) consumed in call order; the fetch blocks on release_event."""
    lock = threading.Lock(); it = iter(script)
    def f(payload, *a, **k):
        with lock: started, release, data = next(it)
        started.set(); assert release.wait(10); return data
    return f
def cached_data():
    return next(iter(c._OPEN_ORDERS_CACHE.values()))[1] if c._OPEN_ORDERS_CACHE else None
real_fetcher = c.OPEN_ORDERS_FETCHER
ev = lambda: threading.Event()
fresh()
a_st, a_rel, b_st, b_rel = ev(), ev(), ev(), ev()
c.OPEN_ORDERS_FETCHER = blocking_fetcher([(a_st, a_rel, [{"oid": "old"}]), (b_st, b_rel, [{"oid": "new"}])])
box = {}
ta = threading.Thread(target=run_periodic, args=(box, "a")); ta.start(); assert a_st.wait(10)
tb = threading.Thread(target=run_periodic, args=(box, "b")); tb.start(); assert b_st.wait(10)
b_rel.set(); tb.join(10)
a_rel.set(); ta.join(10)
check("OLDER_SLOW_FETCH_DOES_NOT_OVERWRITE_NEWER", cached_data() == [{"oid": "new"}], str(cached_data()))
check("OLDER_FETCH_CALLER_STILL_GETS_OWN_DATA", box["a"][0]["data"] == [{"oid": "old"}] and box["b"][0]["data"] == [{"oid": "new"}], str(box))
# reverse order: A completes first, then B: B is stored
fresh()
a_st, a_rel, b_st, b_rel = ev(), ev(), ev(), ev()
c.OPEN_ORDERS_FETCHER = blocking_fetcher([(a_st, a_rel, [{"oid": "old"}]), (b_st, b_rel, [{"oid": "new"}])])
box = {}
ta = threading.Thread(target=run_periodic, args=(box, "a")); ta.start(); assert a_st.wait(10)
tb = threading.Thread(target=run_periodic, args=(box, "b")); tb.start(); assert b_st.wait(10)
a_rel.set(); ta.join(10)
check("REVERSE_ORDER_A_STORED_FIRST", cached_data() == [{"oid": "old"}], str(cached_data()))
b_rel.set(); tb.join(10)
check("REVERSE_ORDER_NEWER_FETCH_STORED", cached_data() == [{"oid": "new"}], str(cached_data()))
# fetch starts before an invalidation, completes after it: not stored
fresh()
a_st, a_rel = ev(), ev()
c.OPEN_ORDERS_FETCHER = blocking_fetcher([(a_st, a_rel, [{"oid": "old"}])])
box = {}
ta = threading.Thread(target=run_periodic, args=(box, "a")); ta.start(); assert a_st.wait(10)
c.invalidate_open_orders_cache()
a_rel.set(); ta.join(10)
check("FETCH_STARTED_BEFORE_INVALIDATE_NOT_STORED", not c._OPEN_ORDERS_CACHE and box["a"][0]["data"] == [{"oid": "old"}], str(c._OPEN_ORDERS_CACHE))
# a later fetch after an invalidation does store
c.OPEN_ORDERS_FETCHER = real_fetcher
fresh(); c.periodic_open_orders([""]); c.periodic_open_orders([""])
check("LATER_FETCH_STORES_AND_HITS", len(calls) == 1, str(len(calls)))

print("TOTAL=%d FAILED=%d" % (len(R), sum(1 for _, ok in R if not ok)))
sys.exit(1 if any(not ok for _, ok in R) else 0)
