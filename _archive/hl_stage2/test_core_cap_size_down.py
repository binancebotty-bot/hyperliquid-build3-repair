#!/usr/bin/env python3
"""Exposure cap rule (Boss 16 Oct): the last order is sized down to the remaining allowance; once the allowance is
spent increases are blocked; reductions never reach the cap; an unreadable exposure is held (deferred), not blocked.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_cap_size_down.py"""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="cap_size_down_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
os.environ.pop("HL_LIVE_CAP_SIZE_DOWN", None)
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append(bool(ok)); print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))

def builder(total=1000.0, net_btc=1.0, cap_total=1050.0, cap_asset=0.0, min_n=10.0, ok=True, resting_total=0.0):
    b = c.IntentBuilder.__new__(c.IntentBuilder)
    b.cfg = SimpleNamespace(max_total_exposure=lambda: cap_total, max_asset_directional_exposure=lambda: cap_asset,
                            min_notional=lambda: min_n)
    b.follower_exposure = lambda: ({"ok": True, "total_usd": total, "by_coin": {"BTC": {"net": net_btc}}} if ok
                                   else {"ok": False, "status": "UNAVAILABLE"})
    b._resting = lambda: {"total_usd": resting_total, "buy_units": {}, "sell_units": {}}
    b._exposure_pending = []
    return b

def fill(side="BUY"):
    return SimpleNamespace(price=100.0, side=side, coin="BTC")

def run(b, notional, side="BUY"):
    c._CAP_TLS.scale = 1.0
    r = c.IntentBuilder._exposure_cap_block(b, fill(side), notional, 100.0)
    return r, c._CAP_TLS.scale

# 1. fits: unchanged
r, s = run(builder(total=1000.0), 12.0)
check("FITS_UNCHANGED", r == "" and s == 1.0, (r, s))
# 2. last order: 50 allowance left, 80 order -> sized to 50/80
r, s = run(builder(total=1000.0), 80.0)
check("LAST_ORDER_SIZED_TO_REMAINING", r == "" and abs(s - 50.0 / 80.0) < 1e-9, (r, s))
# 3. remaining below min notional: blocked
r, s = run(builder(total=1045.0), 80.0)
check("BELOW_MIN_NOTIONAL_BLOCKS", "max total exposure" in r, (r, s))
# 4. above the cap: blocked
r, s = run(builder(total=1100.0), 12.0)
check("ABOVE_CAP_BLOCKS_INCREASES", "max total exposure" in r, (r, s))
# 5. pending (same cycle) counts: first takes 40, second sized to the 10 left (>= min 10)
b = builder(total=1000.0)
r1, s1 = run(b, 40.0)
r2, s2 = run(b, 40.0)
check("PENDING_COUNTS_BURST", r1 == "" and s1 == 1.0 and r2 == "" and abs(s2 - 10.0 / 40.0) < 1e-9, (r1, s1, r2, s2))
# 6. per-asset cap: net 1 BTC at 100 = 100 allowed 130 -> a 60 order sized to 30
r, s = run(builder(total=0.0, cap_total=0.0, cap_asset=130.0, net_btc=1.0), 60.0)
check("ASSET_CAP_SIZED", r == "" and abs(s - 0.5) < 1e-6, (r, s))
# 7. per-asset cap already breached long: a BUY blocks, a SELL (reduces net) passes
r, s = run(builder(total=0.0, cap_total=0.0, cap_asset=90.0, net_btc=1.0), 20.0)
check("ASSET_CAP_BREACHED_BLOCKS_BUY", "asset directional" in r, (r, s))
r, s = run(builder(total=0.0, cap_total=0.0, cap_asset=90.0, net_btc=1.0), 20.0, side="SELL")
check("ASSET_CAP_SELL_REDUCES_PASSES", r == "", (r, s))
# 8. cap 0 = off
r, s = run(builder(total=5000.0, cap_total=0.0, cap_asset=0.0), 500.0)
check("CAP_OFF_UNCHANGED", r == "" and s == 1.0, (r, s))
# 9. unreadable exposure keeps the "unavailable" text that the deferral hold matches
r, s = run(builder(ok=False), 12.0)
check("UNREADABLE_IS_DEFERRABLE", any(m in r.lower() for m in c.IntentBuilder._TRUTH_UNREADABLE_MARKERS) if hasattr(c.IntentBuilder, "_TRUTH_UNREADABLE_MARKERS") else "unavailable" in r.lower(), r)
# 10. kill switch restores block-whole
os.environ["HL_LIVE_CAP_SIZE_DOWN"] = "0"
r, s = run(builder(total=1000.0), 80.0)
check("KILL_SWITCH_BLOCKS_WHOLE", "max total exposure" in r and s == 1.0, (r, s))
os.environ.pop("HL_LIVE_CAP_SIZE_DOWN", None)

print("TOTAL=%d FAILED=%d" % (len(R), R.count(False))); sys.exit(1 if False in R else 0)
