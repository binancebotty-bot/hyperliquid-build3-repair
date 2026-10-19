"""Closes are sized to the follower's net target and sent without reduce-only (Boss 2026-10-11); CLOSE ONLY and dust
stay reduce-only. An unreadable follower net no longer falls back to a reduce-only guess: it HOLDS the close (and is
covered by test_core_exit_hold_unreadable_net.py).
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_close_to_target.py"""
import os, sys, math, threading
from types import SimpleNamespace
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

class Ledger:
    def __init__(self, net): self.net = net
    def coin_net(self, k): return self.net

def plan(side, size, led, ex, mode="ON", dust=False, readable=True, fresh=None, lifecycle_exit=True, sz_dec=2, min_ok=None, env=None, lag=False, gmode="ON"):
    snap = ({"RESOLV": ex}, "") if readable else ({}, "exchange snapshot unavailable")
    me = SimpleNamespace(ledger=Ledger(led), cfg=SimpleNamespace(wallet_mode=lambda w: mode, send_mode_now=lambda: gmode))
    me._reduce_only_for_intent = lambda i: lifecycle_exit
    me._persisted_exchange_positions = lambda: snap
    me._fresh_exchange_net = lambda coin: (ex if readable else None)
    me._floor_wire_size = lambda s, d: math.floor(s * 10 ** d + 1e-9) / 10 ** d
    # the hold/replay/alert helpers are real methods on the gateway (unreadable-net hold); bind them for this probe
    me._net_read_ms = {}
    me._exit_hold = None
    me._exit_hold_lock = threading.RLock()
    me._net_unreadable_reason = lambda coin, key, net: c.SenderGateway._net_unreadable_reason(me, coin, key, net)
    me._net_read_age_ms = lambda coin: c.SenderGateway._net_read_age_ms(me, coin)
    me._hold_exit_unreadable_net = lambda i, reason, sz, timing=None: None
    me._take_exit_hold_replay = lambda i, key, net: False
    me.audit = SimpleNamespace(append_reconciliation=lambda *a, **k: None)
    me._exit_hold_key = lambda i: "test-sleeve"
    intent = SimpleNamespace(intent_id="test-intent", sleeve_id="test-sleeve", fill=SimpleNamespace(leader_wallet="0xabc", coin="RESOLV", leader_fill_id="f-test"), copy_side=side, copy_size=size)
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
check("WALLET_CLOSE_ONLY_CLOSE_IS_SIZED_LIKE_ANY_OTHER", plan("SELL", 10, 10, 10, mode="CLO", min_ok=OK) == (False, 10.0, ""))
check("WALLET_CLOSE_ONLY_CLOSE_MAY_INCREASE_EXPOSURE", plan("SELL", 10, 5, 5, mode="CLO", min_ok=OK) == (False, 10.0, ""))
# header CLOSE ONLY control: leader side only (no leader entries); the follower side is sized like any close
check("HEADER_CLOSE_ONLY_CLOSE_IS_SIZED_LIKE_ANY_OTHER", plan("SELL", 10, 10, 10, gmode="CLOSE", min_ok=OK) == (False, 10.0, ""))
check("HEADER_CLOSE_ONLY_CLOSE_MAY_INCREASE_FOLLOWER_EXPOSURE", plan("SELL", 10, 5, 5, gmode="CLOSE", min_ok=OK) == (False, 10.0, ""))
check("HEADER_CLOSE_ONLY_CLOSE_STILL_NEVER_EXCEEDS_THE_LEADER_CLOSE", plan("SELL", 10, 10, 100.0, gmode="CLOSE", min_ok=OK) == (False, 10.0, ""))
check("HEADER_CLOSE_ONLY_DUST_STAYS_REDUCE_ONLY", plan("SELL", 0.01, 0.01, 0.01, dust=True, gmode="CLOSE") == (True, 0.01, ""))
check("DUST_WHOLE_POSITION_STAYS_REDUCE_ONLY", plan("SELL", 0.01, 0.01, 0.01, dust=True) == (True, 0.01, ""))
# CHANGED by the unreadable-net hold (controller ruling 6278357071): an unreadable net no longer sends a reduce-only
# guess - it HOLDS the close. The hold itself (row + alert + replay) is proved in test_core_exit_hold_unreadable_net.py.
_r = plan("SELL", 10, 10, 10, readable=False)
check("UNREADABLE_EXCHANGE_HOLDS_NOT_SENDS", _r[0] is False and _r[1] == 0.0 and _r[2].startswith("HELD_NET_UNREADABLE"), str(_r))
check("ENTRY_IS_UNCHANGED", plan("BUY", 10, 0, 0, lifecycle_exit=False) == (False, 10, ""))
check("SWITCH_OFF_FALLBACK_IS_REDUCE_ONLY", plan("SELL", 10, 10, 10, env="false") == (True, 10, ""))
check("LEDGER_MAY_LAG_FALLS_BACK_REDUCE_ONLY", plan("SELL", 10, 10, 4, lag=True) == (True, 10, ""))
check("TRIM_BELOW_MIN_NOTIONAL_KEEPS_FULL_REDUCE_ONLY", plan("SELL", 10, 10, 4, min_ok=lambda s: False) == (True, 10, ""))
check("TRIM_WITHOUT_MIN_CHECK_KEEPS_FULL_REDUCE_ONLY", plan("SELL", 10, 10, 4) == (True, 10, ""))
check("SHORT_SLEEVE_BUY_CLOSE", plan("BUY", 10, -10, -10, min_ok=OK) == (False, 10.0, ""))
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
