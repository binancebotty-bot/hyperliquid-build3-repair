#!/usr/bin/env python3
"""Boss (Claude 6299368113): no position or sleeve may ever sit below the minimum order notional.

Rule (a) reduce-to-zero: a reduction that would leave a sub-minimum remainder closes the whole remainder.
Rule (b) no dust entries: an entry/add whose size-down trim would fall below the minimum is skipped, never sent.
Rule (c) sub-minimum remainder: a sleeve below the minimum is always a whole-close candidate, even while its
leader still holds the same side, and the audit row names the cause SUB_MINIMUM_REMAINDER.

Drives the real engine (IntentBuilder.build/_decision, SenderGateway._close_wire_plan, LiveCopyCore._converge_candidate).
Offline only: no orders, no keys, no network. Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_no_sub_minimum.py
"""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="nosubmin_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent",
                   "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet"})
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append(bool(ok)); print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))

A = "0x" + "a" * 40
MIN = c.DEFAULT_MIN_NOTIONAL

# ---------------------------------------------------------------- rule (b) + controls (IntentBuilder.build)
def builder(cap_total):
    b = c.IntentBuilder.__new__(c.IntentBuilder)
    b.cfg = SimpleNamespace(max_total_exposure=lambda: cap_total, max_asset_directional_exposure=lambda: 0.0,
                            min_notional=lambda: MIN, wallet_enabled=lambda w: True, wallet_mode=lambda w: "ON",
                            copy_mode=lambda w: "fixed", fixed_notional=lambda w: 12.0,
                            max_order_notional=lambda: 0.0, max_wallet_exposure=lambda w: 0.0, auto_send_enabled=False,
                            is_symbol_allowed=lambda coin: (True, ""))
    b.follower_exposure = lambda: {"ok": True, "total_usd": 1000.0, "by_coin": {"BTC": {"net": 0.0}}}
    b._resting = lambda: {"total_usd": 0.0, "buy_units": {}, "sell_units": {}}
    b._exposure_pending = []
    b.ledger = c.ManualLedger(path=tmp / "led_b.json")
    b.leader_equity = lambda w: None
    b._sizing_block = {}
    b._order_value_px = lambda fill: 100.0
    b._unowned_inventory_block = lambda fill: ""
    b._coin_activity = {}
    return b

def fill(side="BUY"):
    return c.LeaderFill("f1", A, "BTC", side, 100.0, 0.12, c.utc_now_ms(), "T", {})

# (b) cap trim would leave 4.00 < MIN -> skipped, never sent as dust
b = builder(cap_total=1004.0)
c._CAP_TLS.scale = 1.0
i = c.IntentBuilder.build(b, fill())
# rule (b) is already enforced by _exposure_cap_block (a trim below the minimum is refused, not shrunk): guard it
check("B_TRIM_BELOW_MIN_SKIPPED", i.decision == "SEND_BLOCKED_RISK" and not i.send_allowed
      and "max total exposure" in i.reason,
      (i.decision, i.copy_notional, i.reason))
# control: normal-sized entry unchanged
b = builder(cap_total=0.0)
c._CAP_TLS.scale = 1.0
i = c.IntentBuilder.build(b, fill())
check("C_NORMAL_ENTRY_UNCHANGED", i.decision == "ENTRY_ALLOWED" and abs(i.copy_notional - 12.0) < 1e-9, (i.decision, i.copy_notional))
# control: a trim that stays above the minimum is still sized down, not blocked
b = builder(cap_total=1010.0)
c._CAP_TLS.scale = 1.0
i = c.IntentBuilder.build(b, fill())
check("C_TRIM_ABOVE_MIN_SIZED_DOWN", i.decision == "ENTRY_ALLOWED" and abs(i.copy_notional - 10.0) < 1e-6, (i.decision, i.copy_notional))

# ---------------------------------------------------------------- rule (a) + controls (SenderGateway._close_wire_plan)
def gw(ex_net, led_net=None):
    led = c.ManualLedger(path=tmp / "led_g.json")
    g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), led)
    g._fresh_exchange_net = lambda coin: ex_net
    led.coin_net = lambda k: (ex_net if led_net is None else led_net)
    return g

def intent(side="SELL"):
    f = c.LeaderFill("f2", A, "BTC", side, 1.0, 10.0, c.utc_now_ms(), "T", {})
    return c.Intent("i2", f, side, 10.0, 10.0, "ON", "fixed", "EXIT_ALLOWED", "EXIT", "s", "", "LONG",
                    1.0, 1.0, True, True, c.utc_now_ms(), "lifecycle=EXIT;")

# price 1.0 so size == notional; min 10 means anything under 10 units is dust
ok_size = lambda sz: abs(sz * 1.0) >= MIN

# (a) close 10 of a 12 position -> the remaining 2 would be dust -> close the whole 12
ro, sz, skip = gw(12.0)._close_wire_plan(intent(), 10.0, 4, ok_size)
check("A_PARTIAL_REDUCTION_CLOSES_WHOLE_REMAINDER", abs(sz - 12.0) < 1e-9 and ro is True and not skip, (ro, sz, skip))
# control: remainder above the minimum -> unchanged (close 10 of 100)
ro, sz, skip = gw(100.0)._close_wire_plan(intent(), 10.0, 4, ok_size)
check("C_REDUCTION_ABOVE_MIN_UNCHANGED", abs(sz - 10.0) < 1e-9 and not skip, (ro, sz, skip))
# control: full close unchanged
ro, sz, skip = gw(12.0)._close_wire_plan(intent(), 12.0, 4, ok_size)
check("C_FULL_CLOSE_UNCHANGED", abs(sz - 12.0) < 1e-9 and ro is True and not skip, (ro, sz, skip))
# netting invariant: a whole-remainder close never flips the account (reduce-only, size <= |net|)
ro, sz, skip = gw(12.0)._close_wire_plan(intent(), 10.0, 4, ok_size)
check("C_WHOLE_REMAINDER_NEVER_FLIPS", ro is True and abs(sz) <= 12.0 + 1e-9, (ro, sz))
# partial-fill path (ledger may lag): exchange 12 left, remainder 10 -> whole 12, reduce-only
ro, sz, skip = gw(12.0)._close_wire_plan(intent(), 10.0, 4, ok_size, ledger_may_lag=True)
check("A_PARTIAL_FILL_LAG_CLOSES_WHOLE_REMAINDER", abs(sz - 12.0) < 1e-9 and ro is True and not skip, (ro, sz, skip))

# ---------------------------------------------------------------- rule (c) (LiveCopyCore._converge_candidate)
stub = SimpleNamespace(cfg=SimpleNamespace(min_notional=lambda: MIN))
_cand_fn = getattr(c.LiveCopyCore, "_converge_candidate", None)
cand = lambda size, px, lead: (_cand_fn(stub, size, px, lead) if _cand_fn else (False, "MISSING"))
# sub-minimum sleeve is a candidate even while the leader still holds the same side
ok_, reason = cand(0.05, 100.0, +5.0)
check("C_SUBMIN_SLEEVE_IS_CANDIDATE", ok_ is True and reason == "SUB_MINIMUM_REMAINDER", (ok_, reason))
# control: normal sleeve whose leader still holds the same side is NOT a candidate
ok_, reason = cand(1.0, 100.0, +5.0)
check("C_LEADER_HOLDS_NOT_CANDIDATE", ok_ is False, (ok_, reason))
# leader flat / opposite still close a normal sleeve (unchanged behaviour)
ok_, reason = cand(1.0, 100.0, 0.0)
check("C_LEADER_FLAT_UNCHANGED", ok_ is True and reason == "LEADER_FLAT", (ok_, reason))
ok_, reason = cand(1.0, 100.0, -5.0)
check("C_LEADER_OPPOSITE_UNCHANGED", ok_ is True and reason == "LEADER_OPPOSITE_SIDE", (ok_, reason))

print("TOTAL=%d FAILED=%d" % (len(R), R.count(False)))
sys.exit(1 if False in R else 0)
