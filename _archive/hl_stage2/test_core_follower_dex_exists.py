"""A DEX a leader market names but the follower network does not have is left out of the follower scope (it made every entry fail closed).
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_follower_dex_exists.py"""
import os, sys, tempfile
from pathlib import Path
tmp = Path(tempfile.mkdtemp(prefix="fde_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

calls = {"n": 0, "res": {"ok": True, "dexes": ["", "xyz", "flx"]}}
def fake(*a, **k):
    calls["n"] += 1
    return calls["res"]
c._XNET.list_perp_dexes = fake
c._LEARNED_DEXES.clear(); c._LEARNED_DEXES.update({"io", "xyz"})
c._FOLLOWER_DEX_NAMES.update({"names": None, "ms": 0})
check("MISSING_DEX_DROPPED_REAL_ONE_KEPT", c.follower_dex_scope() == ["", "xyz"], str(c.follower_dex_scope()))
n = calls["n"]; c.follower_dex_scope(); c.follower_dex_scope()
check("LOOKUP_CACHED", calls["n"] == n)
os.environ["HL_FOLLOWER_DEXES"] = "io"
check("EXPLICIT_CONFIG_KEPT", "io" in c.follower_dex_scope())
os.environ.pop("HL_FOLLOWER_DEXES")
# unknown (lookup fails) -> nothing filtered, as before
c._FOLLOWER_DEX_NAMES.update({"names": None, "ms": 0}); calls["res"] = {"ok": False}
check("UNKNOWN_KEEPS_ALL", c.follower_dex_scope() == ["", "io", "xyz"], str(c.follower_dex_scope()))
# injected test fetcher -> no lookup at all
c._FOLLOWER_DEX_NAMES.update({"names": None, "ms": 0}); n = calls["n"]; c.EXPOSURE_FETCHER = lambda p: {}
check("TEST_FETCHER_SKIPS_LOOKUP", c.follower_dex_scope() == ["", "io", "xyz"] and calls["n"] == n)
fails = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(fails)))
sys.exit(1 if fails else 0)
