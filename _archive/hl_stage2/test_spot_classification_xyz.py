"""Spot-vs-perp classification, incl. builder perps (xyz:) and a cold meta cache.

Controller requirement: prove that xyz builder perps and plain perps are NOT
classified spot, and that real spot pairs ARE -- because a false refusal would
block the 8 xyz positions we hold and the roster will copy them.
"""

import importlib.util
import os
import sys

CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HL_Live_Copy_Service_Core.py")

spec = importlib.util.spec_from_file_location("hl_core_spot_cls", CORE)
core = importlib.util.module_from_spec(spec)
sys.modules["hl_core_spot_cls"] = core
spec.loader.exec_module(core)

is_spot_pair = core.is_spot_pair

PASS = 0
FAIL = 0


def check(label, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print("PASS %s" % label)
    else:
        FAIL += 1
        print("FAIL %s | got=%r want=%r" % (label, got, want))


print("--- NOT spot: builder perps (xyz:) ---")
for c in ("xyz:HOOD", "xyz:MSTR", "xyz:COPPER", "xyz:INTC", "xyz:PLTR", "xyz:MSFT", "xyz:LLY", "xyz:SKHX"):
    check("NOT_SPOT[%s]" % c, is_spot_pair(c), False)

print("--- NOT spot: plain perps ---")
for c in ("BTC", "ETH", "kPEPE", "DOGE", "SOL", "HYPE", "FARTCOIN"):
    check("NOT_SPOT[%s]" % c, is_spot_pair(c), False)

print("--- NOT spot: empty / junk must not raise ---")
for c in ("", None, "   "):
    check("EMPTY_NOT_SPOT[%r]" % (c,), is_spot_pair(c), False)

print("--- ARE spot ---")
for c in ("PURR/USDC", "@107", "@306", "@151", "PURR", "@0", "HYPE/USDC", "UBTC/USDT"):
    check("IS_SPOT[%s]" % c, is_spot_pair(c), True)

print("--- cold start: empty meta cache must not change classification ---")
# is_spot_pair is pure string logic; prove it consults no metadata cache by
# clearing every module-level cache we can find and re-running the same cases.
cleared = []
for name in dir(core):
    if "CACHE" in name.upper() or "UNIVERSE" in name.upper():
        val = getattr(core, name)
        if isinstance(val, dict):
            val.clear()
            cleared.append(name)
        elif isinstance(val, (list, set)):
            try:
                val.clear()
                cleared.append(name)
            except Exception:
                pass
print("   cleared module caches:", cleared or "(none found)")
for c in ("xyz:HOOD", "xyz:MSTR", "xyz:COPPER", "BTC", "PURR/USDC", "@107"):
    check("COLD_CACHE[%s]" % c, is_spot_pair(c), c.startswith("PURR") or c.startswith("@"))

print("--- case/space tolerance ---")
check("LOWER[purr/usdc]", is_spot_pair("purr/usdc"), True)
check("SPACED[  @107  ]", is_spot_pair("  @107  "), True)
check("LOWER[xyz:hood]", is_spot_pair("xyz:hood"), False)

print("\nTOTAL=%d FAILED=%d" % (PASS + FAIL, FAIL))
sys.exit(1 if FAIL else 0)
