"""The exclusion's cache must be warmed OFF the hot path, and the pending marker must stay visible without being
terminal. Two questions from the controller, answered with tests rather than prose."""

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("HL_LIVE_AUDIT_DIR", tempfile.mkdtemp(prefix="warm_"))
os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
import HL_Live_Copy_Service_Core as C   # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + detail) if (detail and not ok) else ""))


# ---------------------------------------------------------------- the config the filter reads
_CFG_DIR = Path(tempfile.mkdtemp(prefix="warm_cfg_"))
_CFG = _CFG_DIR / "live_config.json"
_CFG.write_text(json.dumps({"global_controls": {"min_24h_notional_usd": 3000.0}}), encoding="utf-8")
C.LIVE_CONFIG_FILE = _CFG
C._THRESHOLD_CACHE.update({"mtime": None, "value": 0.0})

# a fake exchange read the warmer will use; it records how often it was called
_CALLS = {"n": 0}


def _fake_fetch(refresh=False, cache_only=False):
    if cache_only:
        if C._VOL_CACHE["ok"]:
            return True, dict(C._VOL_CACHE["vol"]), set(C._VOL_CACHE["listed"])
        return False, {}, set()
    _CALLS["n"] += 1
    vol = {"RICH": 100000.0, "MERL": 10.0}
    listed = {"RICH", "MERL"}
    C._VOL_CACHE.update({"ts": C.utc_now_ms() / 1000.0, "vol": dict(vol), "listed": set(listed), "ok": True})
    return True, vol, listed


C.follower_volumes_24h = _fake_fetch

# ---------------------------------------------------------------- 1. cold cache stands aside, warming makes it bite
C._VOL_CACHE.update({"ts": 0.0, "vol": {}, "listed": set(), "ok": False})
st_cold, _ = C.follower_entry_exclusion("MERL", True, {}, held_net=0.0)
check("A_COLD_CACHE_STANDS_ASIDE", st_cold == "", "a cold cache excluded %r - the filter fetched or guessed" % (st_cold,))

C.warm_follower_volumes()
check("THE_WARMER_POPULATES_THE_CACHE", C._VOL_CACHE["ok"] and "MERL" in C._VOL_CACHE["vol"],
      "cache after warm: ok=%r keys=%r" % (C._VOL_CACHE["ok"], sorted(C._VOL_CACHE["vol"])))

st_warm, note = C.follower_entry_exclusion("MERL", True, {}, held_net=0.0)
check("THE_NEXT_FILL_AFTER_WARMING_IS_EXCLUDED", st_warm == "ILLIQUID_SKIP", "warm result=%r" % (st_warm,))
st_rich, _ = C.follower_entry_exclusion("RICH", True, {}, held_net=0.0)
check("A_DEEP_BOOK_IS_NOT_EXCLUDED", st_rich == "", "RICH was excluded: %r" % (st_rich,))

# the warmer is throttled: a second call inside the window must not refetch
before = _CALLS["n"]
C.warm_follower_volumes()
check("THE_WARMER_IS_THROTTLED", _CALLS["n"] == before, "refetched inside max_age_sec: %d -> %d" % (before, _CALLS["n"]))

# and it is not called from the exclusion itself: only the cycle warms
before = _CALLS["n"]
C.follower_entry_exclusion("MERL", True, {}, held_net=0.0)
check("THE_EXCLUSION_NEVER_FETCHES", _CALLS["n"] == before, "the exclusion triggered a fetch")

# ---------------------------------------------------------------- 2. the unlisted cut needs only the universe, also cached
C._VOL_CACHE.update({"ts": C.utc_now_ms() / 1000.0, "vol": {"RICH": 1.0}, "listed": {"RICH"}, "ok": True})
st_unl, _ = C.follower_entry_exclusion("NOTLISTED", True, {}, held_net=0.0)
check("THE_UNLISTED_CUT_WORKS_FROM_THE_CACHE_ALONE", st_unl == "EXCLUDED_NOT_LISTED_ON_FOLLOWER_NETWORK",
      "got %r" % (st_unl,))
C._VOL_CACHE.update({"ok": False})
st_unl_cold, _ = C.follower_entry_exclusion("NOTLISTED", True, {}, held_net=0.0)
check("THE_UNLISTED_CUT_ALSO_STANDS_ASIDE_COLD", st_unl_cold == "",
      "a cold universe still excluded: %r - that would be a guess" % (st_unl_cold,))

# ---------------------------------------------------------------- 3. the pending marker: visible, not terminal
import inspect
src = inspect.getsource(C.LiveCopyCore._pending_sweeper)
check("THE_PENDING_MARKER_IS_WRITTEN", "FILL_PENDING_QUEUED" in src, "the sweeper no longer writes a marker")
check("THE_PENDING_MARKER_IS_NOT_TERMINAL_STATE", "terminal_state=\"FILL_PENDING_QUEUED\"" not in src,
      "the marker still fills terminal_state, so one fill counts as two outcomes")
check("THE_PENDING_MARKER_STILL_CARRIES_THE_FILL_ID", "leader_fill_id=fid" in src,
      "a waiting fill would become invisible - it must stay findable by fill id")


failed = [n for n, ok in results if not ok]
print("TOTAL=%d FAILED=%d" % (len(results), len(failed)))
if failed:
    print("FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
