"""DOOR_3 close rulings exercised at SenderGateway._close_wire_plan.
No exchange, network, keys, or live engine. Run with the repository Python.
"""
import os, sys, math
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("HL_USER_WALLET", "0x" + "c" * 40)
import HL_Live_Copy_Service_Core as c

R = []
def check(name, ok, clause, detail=""):
    R.append(bool(ok))
    marker = "GREEN_BY_CODE" if ok else "RED"
    result = "PASS" if ok else "FAIL"
    print(f"RESULT::{name}_{result} {marker} clause={clause} {detail}")

class Ledger:
    def __init__(self, net, sleeve):
        self.data = {"by_wallet": {"0xabc": {"RESOLV": {"signed_size": sleeve}}}}
        self.net = net
    def coin_net(self, coin): return self.net

def plan(owned, net, ledger_sleeve=None, requested=12, readable=True):
    ledger_sleeve = owned if ledger_sleeve is None else ledger_sleeve
    g = SimpleNamespace(ledger=Ledger(net, ledger_sleeve), cfg=SimpleNamespace())
    g._reduce_only_for_intent = lambda intent: True
    g._proven_owned_for_sleeve = lambda wallet, coin: (owned, "fills")
    g._close_proof_account_ok = lambda: True
    g._follower_order_account_for_proof = lambda *a, **k: c.USER_WALLET
    g._persisted_exchange_positions = lambda: ({"RESOLV": net}, "")
    g._fresh_exchange_net = lambda coin: net if readable else None
    g._floor_wire_size = lambda size, dec: math.floor(size * 10**dec + 1e-9) / 10**dec
    g._open_close_escalation = lambda *a: None
    g._journal_authorised_close_refusal = lambda *a: None
    g.audit = SimpleNamespace(write=lambda row: None)
    intent = SimpleNamespace(fill=SimpleNamespace(leader_wallet="0xabc", coin="RESOLV"), copy_side="SELL", copy_size=requested)
    timing = {}
    result = c.SenderGateway._close_wire_plan(g, intent, requested, 2, lambda size: True, timing)
    return result, timing, g, intent

# CC1-B-CONSOLIDATED-2310 item 3 / engine-owned fill proof: exact owned close.
r, _, _, _ = plan(10, 10, requested=12)
check("OWNED_EXACT_SIZE", r == (True, 10.0, ""), "CC1-B-CONSOLIDATED-2310 item 3", repr(r))
# CC1-B-CONSOLIDATED-2310 item 3: exchange-net divergence must not clamp owned units.
r, timing, _, _ = plan(10, 3, requested=12)
check("OWNED_NET_DIVERGENCE", r == (False, 10.0, "") and ("diverg" in str(timing).lower() or "10" in str(r)), "CC1-B-CONSOLIDATED-2310 item 3", repr((r, timing)))
# DOOR_3 readable-flat ruling: no order against an already-flat exchange account.
r, _, _, _ = plan(10, 0, requested=10)
check("READABLE_FLAT_REFUSES", r[1] == 0 and bool(r[2]), "DOOR_3 readable-flat exchange", repr(r))
# DOOR_3 no ownership proof ruling: hold and emit a named alert row.
r, timing, _, _ = plan(0, 0, ledger_sleeve=5, requested=5)
check("NO_OWNERSHIP_ALERT", r[1] == 0 and bool(r[2]) and any("alert" in str(v).lower() for v in timing.values()), "DOOR_3 unproven ownership must refuse and alert", repr((r, timing)))
# DOOR_3 ledger-only ruling: ledger sleeve is not engine-origin exchange fill ownership.
r, timing, _, _ = plan(0, 0, ledger_sleeve=5, requested=5)
check("LEDGER_ONLY_ZERO_ENGINE_FILLS_REFUSES", r[1] == 0 and bool(r[2]) and any("alert" in str(v).lower() for v in timing.values()), "DOOR_3 ledger-only sleeve with zero engine-origin exchange fills", repr((r, timing)))
# DOOR_3 lag-expiry fallback ruling: reduce-only remains valid for genuinely unproven ownership.
# This invokes the production seam with ledger_may_lag=True (never the lag helper directly).
r, _, _, intent = plan(0, 10, ledger_sleeve=0, requested=10)
g = SimpleNamespace(ledger=None, _reduce_only_for_intent=lambda i: True,
    _close_proof_account_ok=lambda: True,
    _follower_order_account_for_proof=lambda *a, **k: c.USER_WALLET,
    _proven_owned_for_sleeve=lambda w, coin: (0, "no_proof"),
    _persisted_exchange_positions=lambda: ({"RESOLV": 10}, ""),
    _fresh_exchange_net=lambda coin: 10, _floor_wire_size=lambda s,d: s,
    _open_close_escalation=lambda *a: None)
lag = c.SenderGateway._close_wire_plan(g, intent, 10, 2, lambda size: True, {}, True)
check("UNPROVEN_LAG_FALLBACK_REDUCE_ONLY", lag[0] is True, "DOOR_3 lag-expiry fallback is not a defect", repr(lag))
print(f"TOTAL=6 FAILED={sum(not x for x in R)}")
raise SystemExit(1 if not all(R) else 0)
