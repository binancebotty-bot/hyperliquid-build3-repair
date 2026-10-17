"""EXIT path timing stamps: the two un-bracketed network round-trips before every close are now timed.

Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_exit_timing_stamps.py
"""
import os, sys, math
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import HL_Live_Copy_Service_Core as c

R = []


def check(n, ok, d=""):
    R.append((n, bool(ok)))
    print(("PASS" if ok else "FAIL"), n, d)
    print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))


NEW_KEYS = ["standing_close_started_ms", "standing_close_finished_ms",
            "close_plan_started_ms", "close_plan_finished_ms",
            "exchange_net_started_ms", "exchange_net_finished_ms"]

for k in NEW_KEYS:
    check("FIELD_LISTED_SEND_ATTEMPT::" + k, k in c.SEND_ATTEMPT_FIELDS)
    check("FIELD_LISTED_SEND_TIMING::" + k, k in c.SEND_TIMING_FIELDS)


class Ledger:
    def __init__(self, net):
        self.net = net

    def coin_net(self, k):
        return self.net


def plan(timing, led=10.0, ex=10.0):
    me = SimpleNamespace(ledger=Ledger(led), cfg=SimpleNamespace(wallet_mode=lambda w: "ON", send_mode_now=lambda: "ON"))
    me._reduce_only_for_intent = lambda i: True
    me._fresh_exchange_net = lambda coin: ex
    me._floor_wire_size = lambda s, d: math.floor(s * 10 ** d + 1e-9) / 10 ** d
    intent = SimpleNamespace(fill=SimpleNamespace(leader_wallet="0xabc", coin="RESOLV"),
                             copy_side="SELL", copy_size=10.0)
    old = os.environ.get("HL_LIVE_CLOSE_TO_TARGET")
    os.environ["HL_LIVE_CLOSE_TO_TARGET"] = "1"
    try:
        return c.SenderGateway._close_wire_plan(me, intent, 10.0, 2, lambda s: True, timing)
    finally:
        if old is None:
            os.environ.pop("HL_LIVE_CLOSE_TO_TARGET", None)
        else:
            os.environ["HL_LIVE_CLOSE_TO_TARGET"] = old


t = {}
plan(t)
check("EXCHANGE_NET_STAMPED", "exchange_net_started_ms" in t and "exchange_net_finished_ms" in t)
check("EXCHANGE_NET_ORDERED", t.get("exchange_net_finished_ms", 0) >= t.get("exchange_net_started_ms", 1) > 0)

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "HL_Live_Copy_Service_Core.py"),
           encoding="utf-8-sig", errors="replace").read()
check("SEND_REAL_STAMPS_STANDING_CLOSE",
      'timing["standing_close_started_ms"]' in src and 'timing["standing_close_finished_ms"]' in src)
check("SEND_REAL_STAMPS_CLOSE_PLAN",
      'timing["close_plan_started_ms"]' in src and 'timing["close_plan_finished_ms"]' in src)

bad = [n for n, ok in R if not ok]
print("\n%d checks, %d failed" % (len(R), len(bad)))
if bad:
    for n in bad:
        print("  FAILED:", n)
    sys.exit(1)
print("ALL_EXIT_TIMING_STAMP_CHECKS_PASS")
