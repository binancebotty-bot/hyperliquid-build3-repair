"""Closes are sized to the follower's net target and sent without reduce-only (Boss 2026-10-11).

CC1-B-CONSOLIDATED-2310: the side flip is INTENDED; the netted sleeves are the source of truth.
reduce_only ONLY when the order truly opposes the real net AND wire <= abs(net); an unreadable net
sends the fill-proven owned size with reduce_only False; foreign/USER units are never consumed.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_close_to_target.py
"""
import os, sys, math
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("HL_USER_WALLET", "0x" + "c" * 40)
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

class Ledger:
    def __init__(self, net, owned=None):
        self.net = net
        self.owned = net if owned is None else owned
        self.data = {"by_wallet": {"0xabc": {"RESOLV": {"signed_size": (net if owned is None else owned), "coin": "RESOLV"}}},
                     "by_coin_net": {"RESOLV": {"signed_size": net}}}
    def coin_net(self, k): return self.net

ESC = []
WIRES = []
def plan(side, size, led, ex, mode="ON", dust=False, readable=True, lifecycle_exit=True, sz_dec=2, min_ok=None, env=None, lag=False, gmode="ON", owned=None, no_ledger=False):
    ESC.clear(); WIRES.clear()
    me = SimpleNamespace(ledger=None if no_ledger else Ledger(led, (size if owned is None else owned)), cfg=SimpleNamespace(wallet_mode=lambda w: mode, send_mode_now=lambda: gmode))
    me._open_close_escalation = lambda intent, reason: ESC.append(reason)
    me._proven_owned_for_sleeve = lambda w, c: None if owned == "UNPROVABLE" else (size if owned is None else owned)
    me._close_proof_account_ok = lambda: True
    me._follower_order_account_for_proof = lambda *a, **k: c.USER_WALLET
    me._reduce_only_for_intent = lambda i: lifecycle_exit
    me._persisted_exchange_positions = lambda: ({"RESOLV": ex}, "")
    me._fresh_exchange_net = lambda coin: (ex if readable else None)
    me._floor_wire_size = lambda s, d: math.floor(s * 10 ** d + 1e-9) / 10 ** d
    intent = SimpleNamespace(fill=SimpleNamespace(leader_wallet="0xabc", coin="RESOLV"), copy_side=side, copy_size=size)
    timing = {"dust_close_below_min_notional": "x"} if dust else {}
    old = os.environ.get("HL_LIVE_CLOSE_TO_TARGET")
    if env is not None: os.environ["HL_LIVE_CLOSE_TO_TARGET"] = env
    try:
        r = c.SenderGateway._close_wire_plan(me, intent, size, sz_dec, min_ok, timing, lag)
    finally:
        if env is not None:
            if old is None: os.environ.pop("HL_LIVE_CLOSE_TO_TARGET")
            else: os.environ["HL_LIVE_CLOSE_TO_TARGET"] = old
    if r[1] > 0: WIRES.append(r[1])  # a HOLD always carries 0.0
    return r

OK = lambda s: True
check("AGREEING_CLOSE_NOT_REDUCE_ONLY", plan("SELL", 10, 10, 10, min_ok=OK) == (True, 10.0, ""))
check("CLOSE_MAY_INCREASE_EXPOSURE", plan("SELL", 10, 5, 5, min_ok=OK) == (False, 10.0, ""))
r = plan("SELL", 10, 10, 4, min_ok=OK)
check("FOREIGN_UNITS_HOLD_NAMED", r == (False, 0.0, "CLOSE_PROOF_HOLD_FOREIGN_UNITS") and WIRES == [], str(r))
r = plan("SELL", 10, 10, 0.0, min_ok=OK)
check("EXCHANGE_FLAT_SENDS_NOTHING", r[1] == 0.0 and r[2])
r = plan("SELL", 10, 10, -5.0, min_ok=OK)
check("PAST_TARGET_SENDS_NOTHING", r[1] == 0.0 and r[2])
check("NEVER_CLOSES_MORE_THAN_THE_LEADER_CLOSE", plan("SELL", 10, 10, 100.0, min_ok=OK) == (True, 10.0, ""))
check("STALE_RECORDS_HAND_CLOSED_POSITION_SENDS_NOTHING", plan("SELL", 1, 1, 0.0, min_ok=OK)[1] == 0.0)
check("WALLET_CLOSE_ONLY_CLOSE_IS_SIZED_LIKE_ANY_OTHER", plan("SELL", 10, 10, 10, mode="CLO", min_ok=OK) == (True, 10.0, ""))
check("WALLET_CLOSE_ONLY_CLOSE_MAY_INCREASE_EXPOSURE", plan("SELL", 10, 5, 5, mode="CLO", min_ok=OK) == (False, 10.0, ""))
check("HEADER_CLOSE_ONLY_CLOSE_IS_SIZED_LIKE_ANY_OTHER", plan("SELL", 10, 10, 10, gmode="CLOSE", min_ok=OK) == (True, 10.0, ""))
check("HEADER_CLOSE_ONLY_CLOSE_MAY_INCREASE_FOLLOWER_EXPOSURE", plan("SELL", 10, 5, 5, gmode="CLOSE", min_ok=OK) == (False, 10.0, ""))
check("HEADER_CLOSE_ONLY_CLOSE_STILL_NEVER_EXCEEDS_THE_LEADER_CLOSE", plan("SELL", 10, 10, 100.0, gmode="CLOSE", min_ok=OK) == (True, 10.0, ""))
check("HEADER_CLOSE_ONLY_DUST_STAYS_REDUCE_ONLY", plan("SELL", 0.01, 0.01, 0.01, dust=True, gmode="CLOSE") == (True, 0.01, ""))
check("DUST_WHOLE_POSITION_STAYS_REDUCE_ONLY", plan("SELL", 0.01, 0.01, 0.01, dust=True) == (True, 0.01, ""))
r = plan("SELL", 10, 10, 10, readable=False)
check("UNREADABLE_NET_SENDS_OWNED_NOT_REDUCE_ONLY", r == (False, 10.0, "") and ESC == ["CLOSE_PROOF_UNREADABLE_NET_FALLBACK"], str((r, ESC)))
r = plan("SELL", 10, 10, 10, readable=False, owned=5)
check("UNREADABLE_NET_SENDS_OWNED_WITH_NO_NET_CLAMP", r == (False, 5.0, "") and ESC == ["CLOSE_PROOF_UNREADABLE_NET_FALLBACK"], str((r, ESC)))
r = plan("SELL", 10, 10, 10, readable=False, owned=0)
check("UNREADABLE_NO_OWNED_SLEEVE_HOLDS", r == (False, 0.0, "CLOSE_PROOF_HOLD_NO_OWNED_SLEEVE") and WIRES == [] and ESC == [], str((r, ESC)))
check("ENTRY_IS_UNCHANGED", plan("BUY", 10, 0, 0, lifecycle_exit=False) == (False, 10, ""))
check("SWITCH_OFF_FALLBACK_IS_REDUCE_ONLY", plan("SELL", 10, 10, 10, env="false") == (True, 10, ""))
r = plan("SELL", 2.0, 1.5, 1.5, min_ok=OK, owned=2.0)
check("FLIP_CLOSE_SENDS_FULL_OWNED_REDUCE_ONLY_FALSE", r == (False, 2.0, "") and WIRES == [2.0], str((r, WIRES)))
r = plan("SELL", 2.0, 1.5, 1.5, lag=True, owned=2.0)
check("FLIP_CLOSE_LAG_PATH_SENDS_TWO_NOT_REDUCE_ONLY", r == (False, 2.0, "") and ESC == ["CLOSE_PROOF_LEDGER_LAG_NET_READABLE_NOT_REDUCE_ONLY"], str((r, ESC)))
r = plan("SELL", 10, 10, -3, lag=True)
check("NET_ALREADY_ACROSS_HOLDS_NO_WIRE", r == (False, 0.0, "CLOSE_PROOF_HOLD_NET_NOT_OPPOSING") and ESC == ["CLOSE_PROOF_LEDGER_LAG_NET_NOT_OPPOSING"] and WIRES == [], str((r, ESC)))
r = plan("SELL", 10, 10, 0.0, lag=True)
check("NET_FLAT_HOLDS_NO_WIRE", r == (False, 0.0, "CLOSE_PROOF_HOLD_NET_NOT_OPPOSING") and WIRES == [], str(r))
r = plan("BUY", 10, -10, 3, lag=True, owned=-10)
check("SHORT_SLEEVE_NET_ACROSS_HOLDS", r == (False, 0.0, "CLOSE_PROOF_HOLD_NET_NOT_OPPOSING") and WIRES == [], str(r))
r = plan("SELL", 3, 1, 1, min_ok=OK, owned=3)
check("EQUAL_NET_FLIP_CROSS_IS_NOT_A_BUG", r == (False, 3.0, "") and WIRES == [3.0], str((r, WIRES)))
r = plan("SELL", 10, 10, 10, lag=True)
check("LAG_READABLE_OPPOSING_SENDS_REDUCE_ONLY", r == (True, 10.0, "") and ESC == ["CLOSE_PROOF_LEDGER_LAG_NET_SAFE_REDUCE_ONLY"], str((r, ESC)))
r = plan("SELL", 10, 10, 3, lag=True)
check("LAG_NO_ABS_NET_CAP_SENDS_TEN_NOT_REDUCE_ONLY", r == (False, 10.0, "") and ESC == ["CLOSE_PROOF_LEDGER_LAG_NET_READABLE_NOT_REDUCE_ONLY"], str((r, ESC)))
r = plan("SELL", 10, 10, 3, lag=True, owned=6)
check("LAG_CAPS_TO_MIN_OF_REQUESTED_AND_OWNED", r == (False, 6.0, "") and ESC == ["CLOSE_PROOF_LEDGER_LAG_NET_READABLE_NOT_REDUCE_ONLY"], str((r, ESC)))
r = plan("SELL", 10, 10, 10, lag=True, owned=5)
check("LAG_CLAMPS_TO_PROVEN_OWNED", r == (True, 5.0, ""), str(r))
r = plan("BUY", 10, -10, -10, lag=True, owned=-10)
check("LAG_SHORT_SLEEVE_BUY_CLOSE", r == (True, 10.0, ""), str(r))
r = plan("SELL", 10, 10, 10, lag=True, owned=0)
check("LAG_ZERO_OWNED_HOLDS", r == (False, 0.0, "CLOSE_PROOF_HOLD_NO_OWNED_SLEEVE") and ESC == [] and WIRES == [], str((r, ESC)))
r = plan("SELL", 10, 10, 10, lag=True, owned="UNPROVABLE")
check("LAG_UNPROVABLE_OWNED_HOLDS", r == (False, 0.0, "CLOSE_PROOF_HOLD_NO_OWNED_SLEEVE") and ESC == [] and WIRES == [], str((r, ESC)))
r = plan("SELL", 10, 10, 10, no_ledger=True)
check("NO_LEDGER_OBJECT_SENDS_REDUCE_ONLY", r == (True, 10.0, "") and ESC == ["CLOSE_PROOF_LEDGER_LAG_NET_SAFE_REDUCE_ONLY"], str((r, ESC)))
r = plan("SELL", 10, 10, 4, no_ledger=True)
check("NO_LEDGER_OBJECT_NO_ABS_NET_CAP", r == (False, 10.0, "") and ESC == ["CLOSE_PROOF_LEDGER_LAG_NET_READABLE_NOT_REDUCE_ONLY"], str((r, ESC)))
r = plan("SELL", 10, 10, 10, no_ledger=True, owned=0)
check("NO_LEDGER_OBJECT_ZERO_OWNED_HOLDS", r == (False, 0.0, "CLOSE_PROOF_HOLD_NO_OWNED_SLEEVE") and ESC == [] and WIRES == [], str((r, ESC)))
r = plan("SELL", 10, 10, 10, lag=True, readable=False)
check("LAG_NET_UNREADABLE_SENDS_OWNED_REDUCE_ONLY_FALSE", r == (False, 10.0, "") and ESC == ["CLOSE_PROOF_LEDGER_LAG_NET_UNREADABLE_RESTING"], str((r, ESC)))
r = plan("SELL", 10, 10, 10, lag=True, readable=False, owned=5)
check("LAG_NET_UNREADABLE_NO_NET_CLAMP", r == (False, 5.0, "") and ESC == ["CLOSE_PROOF_LEDGER_LAG_NET_UNREADABLE_RESTING"], str((r, ESC)))
r = plan("SELL", 10, 10, 10, lag=True, readable=False, owned=0)
check("LAG_NET_UNREADABLE_ZERO_OWNED_HOLDS", r == (False, 0.0, "CLOSE_PROOF_HOLD_NO_OWNED_SLEEVE") and WIRES == [], str(r))
r = plan("SELL", 12, 0, 8, min_ok=OK, owned=12)
check("FOREIGN_CROSS_HOLD_NAMED", r == (False, 0.0, "CLOSE_PROOF_HOLD_FOREIGN_CROSS") and WIRES == [], str(r))
check("SAME_SIDE_CLOSE_HOLDS_DIRECTION", plan("BUY", 5, 20, 10, min_ok=OK) == (False, 0.0, "CLOSE_PROOF_HOLD_DIRECTION_OR_SIZE"))
check("TRIM_BELOW_MIN_NOTIONAL_FOREIGN_UNITS_HOLDS", plan("SELL", 10, 10, 4, min_ok=lambda s: False) == (False, 0.0, "CLOSE_PROOF_HOLD_FOREIGN_UNITS"))
check("TRIM_WITHOUT_MIN_CHECK_FOREIGN_UNITS_HOLDS", plan("SELL", 10, 10, 4) == (False, 0.0, "CLOSE_PROOF_HOLD_FOREIGN_UNITS"))
check("SHORT_SLEEVE_BUY_CLOSE", plan("BUY", 10, -10, -10, min_ok=OK, owned=-10) == (True, 10.0, ""))
check("PURE_REDUCTION_OPPOSING_WITHIN_NET_REDUCE_ONLY", plan("SELL", 5, 20, 20, min_ok=OK) == (True, 5.0, ""))
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)

