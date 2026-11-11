#!/usr/bin/env python3
"""rw13 item B: the periodic universe refresh goes through the rw11 meta-fetch helper (single-flight + bounded backoff), treats a
failed or EMPTY core/builder fetch as failure even with a cached index (last-good cache kept, loud once per window), does NOT
advance its timer on failure and DOES on success.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw13_universe_refresh.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. Fake clock + fake requests.post; no network.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import threading
import time as _t
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rw13b_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_FOLLOWER_DEXES": "xyz", "HL_LIVE_DISABLE_NETWORK_REFRESH": "0"})
    import HL_Live_Copy_Service_Core as c

    clock = [1000.0]
    c.time.monotonic = lambda: clock[0]
    st = {"mode": "ok", "calls": [], "gate": None, "builder_ok": True}

    def fake_post(url, json=None, timeout=None):
        st["calls"].append(dict(json))
        if st["gate"] is not None:
            st["gate"].wait(5)
        is_b = bool(json.get("dex"))
        if is_b and not st["builder_ok"]:
            raise RuntimeError("builder boom")
        if not is_b and st["mode"] == "raise":
            raise RuntimeError("boom")
        if not is_b and st["mode"] == "429":
            return Resp({}, 429)
        if not is_b and st["mode"] == "empty":
            return Resp({"universe": []})
        if is_b:
            return Resp({"universe": [{"name": "%s:SPCX" % json["dex"], "szDecimals": 2}]})
        return Resp({"universe": [{"name": "BTC", "szDecimals": 3}, {"name": "ETH", "szDecimals": 4}]})

    c.requests.post = fake_post

    def mk(n):
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%d.json" % n)))
        g._meta_cache = {"BTC": {"canonical_coin": "BTC", "szDecimals": 3, "symbol_source": "core_meta", "perp_dex": ""}}
        g._index_cache = {0: "BTC"}
        g._core_meta_fetched = g._meta_fetched = True
        g._builder_meta_fetched = {"xyz": True, "*": True}
        g._universe_last_refresh_ms = 1  # long overdue
        return g

    def loud_rows():
        p = Path(c.RECONCILIATION_CSV)
        if not p.exists():
            return []
        with open(p, newline="", encoding="utf-8-sig") as fh:
            return [r for r in csv.DictReader(fh) if "ASSET_META_REFRESH_FAILED_USING_LAST_GOOD" in "|".join(r.values())]

    def core_calls():
        return [x for x in st["calls"] if not x.get("dex")]

    # 1 failure: timer unchanged, last good kept, loud once, retried only after the backoff
    g = mk(1)
    st["mode"] = "raise"
    r = g.refresh_asset_universe()
    check("F1_FAILURE_RETURNS_FALSE_TIMER_UNCHANGED", r is False and g._universe_last_refresh_ms == 1, str(g._universe_last_refresh_ms))
    check("F1_LAST_GOOD_CACHE_KEPT", "BTC" in g._meta_cache and g._index_cache == {0: "BTC"} and g._core_meta_fetched)
    check("F1_ONE_LOUD_ROW", len(loud_rows()) == 1, str(len(loud_rows())))
    n = len(st["calls"])
    clock[0] += 5
    g.refresh_asset_universe()
    check("F1_BACKOFF_RESPECTED_NO_NETWORK", len(st["calls"]) == n and g._universe_last_refresh_ms == 1)
    clock[0] += 20
    g.refresh_asset_universe()
    check("F1_RETRIES_AFTER_BACKOFF_STILL_TIMER_UNCHANGED", len(st["calls"]) == n + 1 and g._universe_last_refresh_ms == 1)
    check("F1_LOUD_ONCE_PER_WINDOW", len(loud_rows()) == 1, str(len(loud_rows())))

    # 2 empty core with a cached index is a failure
    g = mk(2)
    st["mode"] = "empty"
    clock[0] += 1000
    r = g.refresh_asset_universe()
    check("E1_EMPTY_CORE_IS_FAILURE_WITH_CACHED_INDEX", r is False and g._universe_last_refresh_ms == 1 and g._index_cache == {0: "BTC"}
          and list(g._meta_cache) == ["BTC"], "r=%s t=%s" % (r, g._universe_last_refresh_ms))

    # 3 HTTP 429 is a failure
    g = mk(3)
    st["mode"] = "429"
    clock[0] += 1000
    r = g.refresh_asset_universe()
    check("H1_HTTP_429_IS_FAILURE", r is False and g._universe_last_refresh_ms == 1 and "ETH" not in g._meta_cache)

    # 4 success advances the timer and swaps the cache; a later tick inside the interval does not refetch
    g = mk(4)
    st.update(mode="ok", calls=[])
    clock[0] += 1000
    before = c.utc_now_ms()
    r = g.refresh_asset_universe()
    check("S1_SUCCESS_ADVANCES_TIMER_AND_SWAPS_CACHE", r is True and g._universe_last_refresh_ms >= before and "ETH" in g._meta_cache
          and g._index_cache.get(1) == "ETH" and "XYZ:SPCX" in g._meta_cache, "r=%s" % r)
    n = len(st["calls"])
    g.refresh_asset_universe()
    check("S1_NO_REFETCH_INSIDE_INTERVAL", len(st["calls"]) == n)

    # 5 builder failure: core swapped but the refresh counts as failed, builder last-good entries survive, timer unchanged
    g = mk(5)
    g._meta_cache["XYZ:SPCX"] = {"canonical_coin": "XYZ:SPCX", "symbol_source": "builder_meta", "perp_dex": "xyz"}
    st.update(mode="ok", calls=[], builder_ok=False)
    clock[0] += 1000
    r = g.refresh_asset_universe()
    check("D1_BUILDER_FAILURE_IS_FAILURE_TIMER_UNCHANGED", r is False and g._universe_last_refresh_ms == 1, "r=%s" % r)
    check("D1_BUILDER_LAST_GOOD_KEPT_AND_FLAG_RESTORED", "XYZ:SPCX" in g._meta_cache and g._builder_meta_fetched.get("xyz") is True)
    n = len(st["calls"])
    g.refresh_asset_universe()
    check("D1_BACKOFF_APPLIES_TO_NEXT_TICK", len(st["calls"]) == n)
    st["builder_ok"] = True

    # 6 single flight
    g = mk(6)
    st.update(mode="ok", calls=[], gate=threading.Event())
    clock[0] += 1000
    ts = [threading.Thread(target=g.refresh_asset_universe) for _ in range(5)]
    for t in ts:
        t.start()
    _t.sleep(0.5)
    check("SF1_SINGLE_FLIGHT", len(core_calls()) == 1, str(len(core_calls())))
    st["gate"].set()
    for t in ts:
        t.join(5)
    st["gate"] = None
    check("SF1_FLIGHT_COMPLETES", g._universe_last_refresh_ms > 1)

    # 7 the startup fetch and the refresh share one backoff
    g = mk(7)
    st.update(mode="raise", calls=[])
    clock[0] += 1000
    g.refresh_asset_universe()
    g._core_meta_fetched = False
    n = len(st["calls"])
    g._fetch_core_meta()
    check("SH1_SHARED_BACKOFF_WITH_STARTUP_FETCH", len(st["calls"]) == n)

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
