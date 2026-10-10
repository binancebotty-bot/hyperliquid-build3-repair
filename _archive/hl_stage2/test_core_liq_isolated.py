#!/usr/bin/env python3
"""Isolated-only assets (builder-dex xyz:*, onlyIsolated): isolated margin mode, per-asset leverage cap, isolated
liquidation maths, leader read on the right dex, parity gate applied (not skipped).
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_liq_isolated.py"""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
tmp = Path(tempfile.mkdtemp(prefix="liqiso_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LEADER_NETWORK": "testnet",
                   "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_LIQ_PARITY": "1"})
import HL_Live_Copy_Service_Core as c
R = []
def check(n, ok, d=""):
    R.append(bool(ok)); print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))
A = "0x" + "a" * 40
# ---- maths
p = c.project_isolated_liquidation_px
x = p(100.0, True, 3.0, 20.0)       # l=0.025 -> 100 - 100*(0.3333-0.025)/0.975
check("ISO_LONG_3X", x is not None and abs(x - (100 - 100 * (1 / 3 - 0.025) / 0.975)) < 1e-9, x)
y = p(100.0, False, 3.0, 20.0)
check("ISO_SHORT_ABOVE_MARK", y is not None and y > 100 and abs(y - (100 + 100 * (1 / 3 - 0.025) / 1.025)) < 1e-9, y)
check("ISO_HIGHER_LEVERAGE_CLOSER", p(100.0, True, 10.0, 20.0) > x)
check("ISO_BAD_INPUT_NONE", p(0.0, True, 3.0, 20.0) is None and p(100.0, True, 0.0, 20.0) is None)
# ---- gateway behaviour
c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
                                         "wallets": {A: {"enabled": True, "mode": "ON"}}})
g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "l.json"))
g._meta_cache["XYZ:GOLD"] = {"maxLeverage": 20.0, "onlyIsolated": True}
g._meta_cache["BTC"] = {"maxLeverage": 40.0}
check("BUILDER_COIN_IS_ISOLATED_ONLY", g._is_isolated_only("xyz:GOLD") and not g._is_isolated_only("BTC"))
g._meta_cache["WEIRD"] = {"onlyIsolated": True, "maxLeverage": 5.0}
check("FLAGGED_COIN_IS_ISOLATED_ONLY_AND_CAPPED", g._is_isolated_only("WEIRD") and g._copy_leverage("WEIRD") == (3, 5.0))
g._meta_cache["LOWLEV"] = {"maxLeverage": 2.0}
check("LEVERAGE_CAPPED_BY_ASSET_MAX", g._copy_leverage("LOWLEV")[0] == 2)
class Fake:
    def __init__(self): self.calls = []
    def update_leverage(self, leverage, name, is_cross=True):
        self.calls.append((leverage, name, is_cross)); return {"status": "ok"}
def mk(coin, side="BUY", price=100.0):
    fill = c.LeaderFill("f1", A, coin, side, price, 1.0, c.utc_now_ms(), "TEST")
    return c.Intent("i1", fill, side, 1.0, price, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY", "s", "", "FLAT", 0.0, 0.0,
                    False, False, c.utc_now_ms(), "lifecycle=ENTRY;")
f = Fake()
r = g._ensure_margin_mode(f, "xyz:GOLD", mk("xyz:GOLD"), "ENTRY", {})
check("ISOLATED_MARGIN_SET_FOR_BUILDER_ASSET", r is None and f.calls == [(3, "xyz:GOLD", False)], f.calls)
f2 = Fake()
g._ensure_margin_mode(f2, "BTC", mk("BTC"), "ENTRY", {})
check("CROSS_MARGIN_SET_FOR_MAIN_ASSET", f2.calls == [(3, "BTC", True)], f2.calls)
# ---- parity gate on the isolated asset: leader read goes to the xyz dex, follower uses the isolated projection
seen = []
def leader(liq):
    def post(url, json=None, timeout=None):
        seen.append(dict(json or {}))
        class Rr:
            def json(self_inner):
                return {"assetPositions": [{"position": {"coin": "xyz:GOLD", "szi": "1.0", "liquidationPx": str(liq)}}]}
        return Rr()
    return post
c.requests.post = leader(95.0)           # leader liquidation 5% away: follower (~31.6%) is safer -> allowed
g._leader_liq_cache.clear() if hasattr(g, "_leader_liq_cache") else None
ok = g.liq_parity_block(mk("xyz:GOLD"))
check("ISOLATED_PARITY_ALLOWS_SAFER_FOLLOWER", ok is None, ok)
check("LEADER_READ_USES_THE_BUILDER_DEX", seen and seen[0].get("dex") == "xyz", seen)
c.requests.post = leader(20.0)           # leader liquidation 80% away: follower (~31.6%) is worse -> blocked
g._leader_liq_cache.clear()
blk = g.liq_parity_block(mk("xyz:GOLD"))
check("ISOLATED_PARITY_BLOCKS_WORSE_FOLLOWER", blk is not None and blk["status"] == "LIQ_PARITY_BLOCKED", blk)
add = mk("xyz:GOLD"); add.reason = "ADD"; add.notes = "lifecycle=ADD;"
blk2 = g.liq_parity_block(add)
check("ISOLATED_ADD_FAILS_CLOSED_UNTIL_WIRED", blk2 is not None and "extension point" in blk2["notes"], blk2)
# metadata survives a universe refresh path (fields present in the refresh and snapshot code)
src = Path(__file__).with_name("HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
check("REFRESH_KEEPS_LEVERAGE_FACTS", src.count('"maxLeverage": fnum(asset.get("maxLeverage"), 0.0)') >= 2 and '"onlyIsolated": bval(item.get("onlyIsolated"), False)' in src)
print("TOTAL=%d FAILED=%d" % (len(R), R.count(False))); sys.exit(1 if False in R else 0)
