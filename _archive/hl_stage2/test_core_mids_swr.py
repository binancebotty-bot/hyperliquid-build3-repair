#!/usr/bin/env python3
"""Core engine: follower/leader mids are served stale-while-revalidate inside the max-age bound.

Before: every order that found the 2 s mids cache stale queued on one refresh lock, so each paid a whole allMids read
per DEX scope (profile 16 Oct: lock waits in follower_mid / leader_mid were a main part of the 3.6 s reply time).
Now: inside HL_LIVE_MIDS_MAX_AGE_SEC the cached mid is used at once and one background refresh runs; beyond it, or with
nothing cached, the caller still waits for a fresh read. HL_LIVE_MIDS_SWR=0 restores the old behaviour.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_mids_swr.py   # RESULT:: markers, exit 0/1. No network.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="midswr_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0"})
    import HL_Live_Copy_Service_Core as c

    state = {"px": 100.0, "delay": 0.0, "calls": 0}

    def fetcher(p):
        if p.get("type") == "perpDexs":
            return []
        state["calls"] += 1
        time.sleep(state["delay"])
        return {"BTC": str(state["px"])}
    c.MIDS_FETCHER = fetcher
    c._follower_dex_names = lambda: set()
    os.environ["HL_LIVE_MIDS_CACHE_TTL_SEC"] = "2"
    os.environ["HL_LIVE_MIDS_MAX_AGE_SEC"] = "5"
    m = c._FOLLOWER_MIDS

    first = c.follower_mid("BTC")
    check("EMPTY_CACHE_WAITS_FOR_READ", first == 100.0, str(first))

    # cache 3 s old: past the 2 s TTL, inside the 5 s max age -> served at once, refreshed behind
    m["ms"] = c.utc_now_ms() - 3000
    state["px"], state["delay"], calls0 = 101.0, 1.0, state["calls"]
    t0 = time.time()
    got = c.follower_mid("BTC")
    took = time.time() - t0
    check("STALE_INSIDE_MAX_AGE_NOT_BLOCKED", took < 0.5 and got == 100.0, "took=%.2fs got=%s" % (took, got))
    time.sleep(1.6)
    check("BACKGROUND_REFRESH_LANDS", c.follower_mid("BTC") == 101.0 and state["calls"] > calls0, "calls=%s px=%s" % (state["calls"], m["px"].get("BTC")))

    # past the max age -> the caller waits for a fresh read (the freshness bound is unchanged)
    m["ms"] = c.utc_now_ms() - 6000
    state["px"], state["delay"] = 102.0, 0.3
    t0 = time.time()
    got = c.follower_mid("BTC")
    check("BEYOND_MAX_AGE_WAITS_FOR_FRESH", got == 102.0 and time.time() - t0 >= 0.25, "got=%s took=%.2f" % (got, time.time() - t0))

    # switch off -> old blocking behaviour
    os.environ["HL_LIVE_MIDS_SWR"] = "0"
    m["ms"] = c.utc_now_ms() - 3000
    state["px"], state["delay"] = 103.0, 0.3
    t0 = time.time()
    got = c.follower_mid("BTC")
    check("SWR_OFF_BLOCKS_AS_BEFORE", got == 103.0 and time.time() - t0 >= 0.25, "got=%s took=%.2f" % (got, time.time() - t0))
    os.environ.pop("HL_LIVE_MIDS_SWR")

    # nothing returned past max age with a dead feed: still 0.0 (no price), never a stale one
    state["delay"] = 0.0
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else (_ for _ in ()).throw(RuntimeError("down"))
    m["ms"] = c.utc_now_ms() - 7000
    check("DEAD_FEED_PAST_MAX_AGE_IS_NO_PRICE", c.follower_mid("BTC") == 0.0)

    bad = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
