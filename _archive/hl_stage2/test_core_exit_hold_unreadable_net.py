"""An unreadable or STALE follower net HOLDS the exit (never a guessed reduce_only), names the reason in a row,
emits ONE alert per wallet per window and leaves a replay marker; the readable-net path is unchanged.
No engine is started and no exchange call is made.

Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_exit_hold_unreadable_net.py
"""
import json
import math
import os
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import HL_Live_Copy_Service_Core as c

R = []


def check(name, ok, detail=""):
    R.append((name, bool(ok)))
    print(("PASS" if ok else "FAIL"), name, detail)
    print("RESULT::%s_%s" % (name, "PASS" if ok else "FAIL"))


TMP = Path(tempfile.mkdtemp(prefix="exit_hold_test_"))
ALERTS = TMP / "exit_hold_alerts.jsonl"
REGISTRY = TMP / "exit_held_unreadable_net.json"
c.EXIT_HOLD_ALERTS_FILE = ALERTS
c.EXIT_HOLD_REGISTRY_FILE = REGISTRY


class Audit:
    def __init__(self):
        self.rows = []

    def append_reconciliation(self, event, status, **kw):
        self.rows.append(dict(event=event, status=status, **kw))

    def append_send_attempt(self, row):
        self.rows.append(dict(event="SEND_ATTEMPT", **row))

    def has_fill_row(self, fid):
        return False


class Ledger:
    def __init__(self, net):
        self.net = net

    def coin_net(self, key):
        return self.net


def gateway(led, ex, readable=True, stamp_ms=None, audit=None, lifecycle_exit=True):
    me = object.__new__(c.SenderGateway)
    me.ledger = Ledger(led)
    me.audit = audit or Audit()
    me._net_read_ms = {}
    me._exit_hold = None
    me._exit_hold_lock = threading.RLock()
    me._reduce_only_for_intent = lambda i: lifecycle_exit
    me._floor_wire_size = lambda s, d: math.floor(s * 10 ** d + 1e-9) / 10 ** d
    if readable:
        def _fresh(coin, _ex=ex, _stamp=stamp_ms, _me=me):
            _me._net_read_ms[c.canonical_coin_key(coin)] = int(_stamp or c.utc_now_ms())
            return _ex
        me._fresh_exchange_net = _fresh
    else:
        me._fresh_exchange_net = lambda coin: None
    return me


def intent(side="SELL", size=10.0, coin="RESOLV", wallet="0xabc", iid="i1", sleeve="s1"):
    return SimpleNamespace(
        intent_id=iid, sleeve_id=sleeve, position_id="p1", copy_side=side, copy_size=size,
        copy_notional=size, coin_net_before=0.0, wallet_position_before=0.0, decision="EXIT_ALLOWED",
        reason="EXIT", notes="lifecycle=EXIT", reduce_only_intended=True, send_allowed=True,
        fill=SimpleNamespace(leader_wallet=wallet, coin=coin, leader_fill_id="f1", side=side, price=1.0,
                             size=size, timestamp_ms=0, raw={}),
    )


def plan(me, it, size=10.0, sz_dec=2, min_ok=lambda s: True, timing=None, lag=False, env=None):
    old = os.environ.get("HL_LIVE_CLOSE_TO_TARGET")
    if env is not None:
        os.environ["HL_LIVE_CLOSE_TO_TARGET"] = env
    try:
        return c.SenderGateway._close_wire_plan(me, it, size, sz_dec, min_ok, timing or {}, lag)
    finally:
        if env is not None:
            if old is None:
                os.environ.pop("HL_LIVE_CLOSE_TO_TARGET", None)
            else:
                os.environ["HL_LIVE_CLOSE_TO_TARGET"] = old


def alert_lines():
    if not ALERTS.exists():
        return []
    return [json.loads(x) for x in ALERTS.read_text(encoding="utf-8").splitlines() if x.strip()]


def reset():
    for p in (ALERTS, REGISTRY):
        if p.exists():
            p.unlink()


# ---------------------------------------------------------------- readable net: UNCHANGED
reset()
it = intent()
me = gateway(10.0, 10.0)
check("AGREEING_CLOSE_STILL_SENT", plan(me, it) == (False, 10.0, ""), str(plan(gateway(10.0, 10.0), it)))

me = gateway(5.0, 5.0)
res = plan(me, it)
check("NETTING_CLOSE_STILL_SENT", res == (False, 10.0, ""), str(res))  # other sleeves net: goes net short 5, not reduce-only
check("NETTING_CLOSE_WROTE_NO_HOLD", not [r for r in me.audit.rows if r["event"] == "EXIT_HOLD"])
check("NETTING_CLOSE_EMITTED_NO_ALERT", alert_lines() == [])

me = gateway(10.0, 10.0)
res = plan(me, it, size=10.0)
check("NORMAL_REDUCING_CLOSE_STILL_SENT", res[1] == 10.0 and res[2] == "", str(res))  # sized like before, no skip

me = gateway(10.0, 10.0)
res = plan(me, it, size=0.01, timing={"dust_close_below_min_notional": "x"})
check("DUST_CLOSE_STAYS_REDUCE_ONLY", res == (True, 0.01, ""), str(res))

me = gateway(10.0, 10.0)
res = plan(me, it, env="false")
check("CLOSE_TO_TARGET_OFF_STAYS_REDUCE_ONLY", res == (True, 10.0, ""), str(res))

# ---------------------------------------------------------------- unreadable net: HOLD + row + alert + replay marker
reset()
me = gateway(10.0, None, readable=False)
it = intent()
res = plan(me, it)
check("UNREADABLE_NET_HOLDS", res[0] is False and res[1] == 0.0 and res[2].startswith(c.EXIT_HOLD_SKIP_PREFIX), str(res))
holds = [r for r in me.audit.rows if r["event"] == "EXIT_HOLD" and r["status"] == "HELD_NET_UNREADABLE"]
check("UNREADABLE_NET_ROW_NAMES_REASON", len(holds) == 1 and "could not be read" in str(holds[0].get("notes")),
      str(holds[:1]))
check("UNREADABLE_NET_ROW_TERMINAL", bool(holds) and holds[0].get("terminal_state") == "HELD_NET_UNREADABLE"
      and holds[0].get("engine_can_send") == "False", str(holds[:1]))
check("UNREADABLE_NET_ONE_ALERT", len(alert_lines()) == 1, str(len(alert_lines())))
reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
check("UNREADABLE_NET_REPLAY_MARKER", bool(reg["held"].get("s1")) and reg["held"]["s1"]["replay_pending"] is True,
      str(reg.get("held")))

# second unreadable episode in the same window: still exactly ONE alert
it2 = intent(coin="HYPE", iid="i2")
me2 = gateway(3.0, None, readable=False)
plan(me2, it2)
reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
check("SECOND_UNREADABLE_SAME_WINDOW_NO_SECOND_ALERT", len(alert_lines()) == 1 and reg["alerts"]["0xabc"]["suppressed"] >= 1,
      "alerts=%d marks=%s" % (len(alert_lines()), reg["alerts"].get("0xabc")))

# ---------------------------------------------------------------- readable again: replay exactly once
me3 = gateway(10.0, 10.0)
me3._exit_hold = json.loads(REGISTRY.read_text(encoding="utf-8"))
res = plan(me3, intent())
check("REPLAY_SENDS_WHEN_NET_READABLE", res == (False, 10.0, ""), str(res))
replays = [r for r in me3.audit.rows if r["event"] == "EXIT_HOLD_REPLAY"]
check("REPLAY_FIRES_ONCE", len(replays) == 1, str(len(replays)))
reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
check("REPLAY_MARKER_WRITTEN", "s1" in reg["replays"] and "s1" not in reg["held"], str(reg["replays"]))
me4 = gateway(10.0, 10.0)
plan(me4, intent())
check("SECOND_READABLE_PLAN_NO_SECOND_REPLAY", not [r for r in me4.audit.rows if r["event"] == "EXIT_HOLD_REPLAY"])

# ---------------------------------------------------------------- stale net read: HOLD
reset()
os.environ["HL_LIVE_NET_READ_MAX_AGE_MS"] = "1000"
try:
    me5 = gateway(10.0, 10.0, stamp_ms=c.utc_now_ms() - 60000)
    res = plan(me5, intent())
finally:
    os.environ.pop("HL_LIVE_NET_READ_MAX_AGE_MS", None)
check("STALE_NET_HOLDS", res[1] == 0.0 and "_STALE" in res[2], str(res))
check("STALE_NET_ALERTED", len(alert_lines()) == 1, str(len(alert_lines())))

# unreadable hold must never become a reduce_only send
check("HOLD_NEVER_REDUCE_ONLY", res[0] is False and res[1] == 0.0, str(res))

failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
print("TMPDIR=" + str(TMP))
raise SystemExit(1 if failed else 0)
