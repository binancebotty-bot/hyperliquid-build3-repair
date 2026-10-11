"""Closes are sized to the follower's net target and sent without reduce-only (Boss 2026-10-11); CLOSE ONLY, dust and unreadable
accounts stay reduce-only. Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_close_to_target.py"""
import os, sys, math
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

class Ledger:
    def __init__(self, net): self.net = net
    def coin_net(self, k): return self.net

def plan(side, size, led, ex, mode="ON", dust=False, readable=True, fresh=None, lifecycle_exit=True, sz_dec=2, min_ok=None, env=None, lag=False):
    snap = ({"RESOLV": ex}, "") if readable else ({}, "exchange snapshot unavailable")
    me = SimpleNamespace(ledger=Ledger(led), cfg=SimpleNamespace(wallet_mode=lambda w: mode))
    me._reduce_only_for_intent = lambda i: lifecycle_exit
    me._persisted_exchange_positions = lambda: snap
    me._fresh_exchange_net = lambda coin: (ex if readable else None)
    me._floor_wire_size = lambda s, d: math.floor(s * 10 ** d + 1e-9) / 10 ** d
    intent = SimpleNamespace(fill=SimpleNamespace(leader_wallet="0xabc", coin="RESOLV"), copy_side=side, copy_size=size)
    timing = {"dust_close_below_min_notional": "x"} if dust else {}
    old = os.environ.get("HL_LIVE_CLOSE_TO_TARGET")
    if env is not None: os.environ["HL_LIVE_CLOSE_TO_TARGET"] = env
    try:
        return c.SenderGateway._close_wire_plan(me, intent, size, sz_dec, min_ok, timing, lag)
    finally:
        if env is not None:
            if old is None: os.environ.pop("HL_LIVE_CLOSE_TO_TARGET")
            else: os.environ["HL_LIVE_CLOSE_TO_TARGET"] = old

OK = lambda s: True
check("AGREEING_CLOSE_NOT_REDUCE_ONLY", plan("SELL", 10, 10, 10, min_ok=OK) == (False, 10.0, ""))
check("CLOSE_MAY_INCREASE_EXPOSURE", plan("SELL", 10, 5, 5, min_ok=OK) == (False, 10.0, ""))  # other sleeves net: goes net short 5
check("TRIMMED_TO_EXCHANGE_POSITION", plan("SELL", 10, 10, 4, min_ok=OK) == (False, 4.0, ""))
r = plan("SELL", 10, 10, 0.0, min_ok=OK)
check("EXCHANGE_FLAT_SENDS_NOTHING", r[1] == 0.0 and r[2])
r = plan("SELL", 10, 10, -5.0, min_ok=OK)
check("PAST_TARGET_SENDS_NOTHING", r[1] == 0.0 and r[2])
r = plan("SELL", 10, 10, 100.0, min_ok=OK)
check("NEVER_CLOSES_MORE_THAN_THE_LEADER_CLOSE", r == (False, 10.0, ""), str(r))
check("STALE_RECORDS_HAND_CLOSED_POSITION_SENDS_NOTHING", plan("SELL", 1, 1, 0.0, min_ok=OK)[1] == 0.0)
check("CLOSE_ONLY_STAYS_REDUCE_ONLY", plan("SELL", 10, 10, 10, mode="CLO") == (True, 10, ""))
check("DUST_WHOLE_POSITION_STAYS_REDUCE_ONLY", plan("SELL", 0.01, 0.01, 0.01, dust=True) == (True, 0.01, ""))
check("UNREADABLE_EXCHANGE_FALLS_BACK_REDUCE_ONLY", plan("SELL", 10, 10, 10, readable=False) == (True, 10, ""))
check("ENTRY_IS_UNCHANGED", plan("BUY", 10, 0, 0, lifecycle_exit=False) == (False, 10, ""))
check("SWITCH_OFF_FALLBACK_IS_REDUCE_ONLY", plan("SELL", 10, 10, 10, env="false") == (True, 10, ""))
check("LEDGER_MAY_LAG_FALLS_BACK_REDUCE_ONLY", plan("SELL", 10, 10, 4, lag=True) == (True, 10, ""))
check("TRIM_BELOW_MIN_NOTIONAL_KEEPS_FULL_REDUCE_ONLY", plan("SELL", 10, 10, 4, min_ok=lambda s: False) == (True, 10, ""))
check("TRIM_WITHOUT_MIN_CHECK_KEEPS_FULL_REDUCE_ONLY", plan("SELL", 10, 10, 4) == (True, 10, ""))
check("SHORT_SLEEVE_BUY_CLOSE", plan("BUY", 10, -10, -10, min_ok=OK) == (False, 10.0, ""))
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
