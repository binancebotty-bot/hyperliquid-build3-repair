#!/usr/bin/env python3
"""HOT FIX (controller 6428792047 item 3): the account tile must count EVERY dex the engine reads.

Before this fix the tile was fed by rolling_day_pnl -> portfolio day accountValueHistory, which is the
default-dex portfolio only. On this testnet account xyz held 39.81 of the 972.46 total, so the tile
understated the account. The tile must sum clearinghouseState.marginSummary.accountValue over the
follower dex scope (default + HL_FOLLOWER_DEXES + any dex a held coin belongs to) and add spot USDC,
stamping account_value_source with the parts.

Offline: the fetcher is injected, so no network and no orders.
"""
import os, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + detail) if (detail and not ok) else ""))

ACCT = "0x" + "a" * 40
os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = ACCT
os.environ["HL_FOLLOWER_DEXES"] = "xyz"
import HL_Copy_App_SSOT as UI

check("THE_TILE_HELPER_EXISTS", hasattr(UI, "_follower_account_tile"),
      "no _follower_account_tile: the tile still reads one dex only")
check("THE_TILE_READS_A_DEX_SCOPE", hasattr(UI, "_follower_account_dexes"),
      "no _follower_account_dexes: the tile cannot name the scope it read")

SEEN = []
def fetcher(payload):
    SEEN.append(payload)
    t = payload.get("type")
    if t == "spotClearinghouseState":
        # real shape: total carries the WHOLE account, hold is the perp margin drawn out of it
        return {"balances": [{"coin": "USDC", "total": "972.432572", "hold": "39.792482"}]}
    if t == "clearinghouseState":
        dex = payload.get("dex") or ""
        return {"marginSummary": {"accountValue": "39.792482" if dex == "xyz" else "0.0"}, "assetPositions": []}
    return {}

UI.ACCOUNT_TILE_FETCHER = fetcher
UI._ACCOUNT_TILE_CACHE.clear()
tile = UI._follower_account_tile(force=True)
print("TILE::", {k: tile.get(k) for k in ("ok", "perp_account_value", "spot_usdc", "spot_hold", "free_spot_usdc", "total_account_value", "decomposition_usd", "dexes_read")})
check("THE_TILE_IS_OK", tile.get("ok") is True, str(tile))
check("EVERY_DEX_IN_SCOPE_WAS_READ", sorted(tile.get("dexes_read") or []) == ["default", "xyz"], str(tile.get("dexes_read")))
check("PERP_VALUE_SUMS_THE_SCOPES", abs(float(tile.get("perp_account_value") or 0) - 39.792482) < 1e-6, str(tile.get("perp_account_value")))
check("SPOT_USDC_IS_READ", abs(float(tile.get("spot_usdc") or 0) - 972.432572) < 1e-5, str(tile.get("spot_usdc")))
# D2 DOUBLE COUNT: the whole account is the spot total; perp margin is held INSIDE it, not added to it.
check("TOTAL_IS_NOT_SPOT_PLUS_PERP", abs(float(tile.get("total_account_value") or 0) - 972.432572) < 1e-5, "total %r must be the whole account 972.432572, not spot+perp 1012.22" % tile.get("total_account_value"))
check("THE_DECOMPOSITION_ADDS_BACK_UP", abs(float(tile.get("decomposition_usd") or 0) - 972.432572) < 1e-4, "(total - hold) + perp must reproduce the account: %r" % tile.get("decomposition_usd"))
check("FREE_SPOT_IS_TOTAL_MINUS_HOLD", abs(float(tile.get("free_spot_usdc") or 0) - 932.64009) < 1e-4, str(tile.get("free_spot_usdc")))
check("THE_SOURCE_EXPLAINS_THE_HOLD", "held inside" in str(tile.get("account_value_source")), str(tile.get("account_value_source")))
check("SPOT_WAS_ACTUALLY_QUERIED", any(p.get("type") == "spotClearinghouseState" for p in SEEN), str([p.get("type") for p in SEEN]))
check("THE_XYZ_SCOPE_WAS_ACTUALLY_QUERIED", any((p.get("dex") or "") == "xyz" for p in SEEN), str([p.get("dex") for p in SEEN]))

def dead(payload):
    if payload.get("type") == "spotClearinghouseState":
        return {"balances": [{"coin": "USDC", "total": "900.0"}]}
    dex = payload.get("dex") or ""
    if dex == "xyz":
        raise RuntimeError("boom")
    return {"marginSummary": {"accountValue": "0.0"}, "assetPositions": []}

LINES = UI._account_card_lines()
joined = " ".join(LINES)
check("THE_CARD_SAYS_SPOT_PLUS_PERP", "spot + perp" in joined.lower(), joined[:300])
check("THE_CARD_SHOWS_PERP_BESIDE_IT", "Perp equity" in joined and "39.79" in joined, joined[:400])

UI.ACCOUNT_TILE_FETCHER = dead
UI._ACCOUNT_TILE_CACHE.clear()
bad = UI._follower_account_tile(force=True)
check("AN_UNREADABLE_SCOPE_FAILS_THE_TILE_CLOSED", bad.get("ok") is False and "xyz" in (bad.get("unreadable_dexes") or []), str(bad))
check("AN_UNREADABLE_SCOPE_IS_NAMED_IN_THE_ERRORS", any("xyz" in str(e) for e in (bad.get("errors") or [])), str(bad.get("errors")))

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL::checks=%d failed=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
