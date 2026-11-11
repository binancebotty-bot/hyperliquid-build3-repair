#!/usr/bin/env python3
"""rw11: a failed/429'd startup meta fetch must not mark the asset meta cache as fetched. The flag is set only on success;
failure logs one loud rate-limited row per dex, retries only after a bounded per-dex backoff (15 s doubling to 120 s),
single-flight, success resets. Run (from _archive/hl_stage2): env -u HL_LIVE_AUDIT_DIR python test_core_rw11_meta_fetch_retry.py"""
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
        if self.status_code >= 400:
            raise ValueError("not json")
        return self.body


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rw11_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_DISABLE_NETWORK_REFRESH": "1", "HL_FOLLOWER_DEXES": "xyz"})
    import HL_Live_Copy_Service_Core as c

    clock = [1000.0]
    c.time.monotonic = lambda: clock[0]
    state = {"fail": True, "calls": [], "gate": None, "mode": "raise"}

    def fake_post(url, json=None, timeout=None):
        state["calls"].append(dict(json))
        if state["gate"] is not None:
            state["gate"].wait(5)
        if state["fail"]:
            if state["mode"] == "429":
                return Resp({}, 429)
            raise RuntimeError("boom")
        if json.get("dex"):
            return Resp({"universe": [{"name": "%s:SPCX" % json["dex"], "szDecimals": 2}]})
        return Resp({"universe": [{"name": "BTC", "szDecimals": 3}]})

    c.requests.post = fake_post

    def mk(n):
        return c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%d.json" % n)))

    def rows():
        if not Path(c.ERRORS_CSV).exists():
            return []
        with open(c.ERRORS_CSV, newline="", encoding="utf-8") as fh:
            return [r for r in csv.DictReader(fh) if "ASSET_META_FETCH_FAILED" in r.get("message", "")]

    # 1 core
    g = mk(1)
    g._fetch_core_meta()
    check("C1_FAIL_LEAVES_FLAG_UNSET", not g._core_meta_fetched and not g._meta_fetched and not g._meta_cache)
    check("C1_ONE_LOUD_ROW", len(rows()) == 1, str(len(rows())))
    n = len(state["calls"])
    clock[0] += 5
    g._fetch_core_meta()
    check("C1_NO_NETWORK_BEFORE_BACKOFF", len(state["calls"]) == n)
    state["fail"] = False
    clock[0] += 11
    g._fetch_core_meta()
    check("C1_RETRY_AFTER_BACKOFF_SUCCEEDS", len(state["calls"]) == n + 1 and g._core_meta_fetched and g._meta_fetched
          and "BTC" in g._meta_cache and g._index_cache.get(0) == "BTC")
    g._fetch_core_meta()
    check("C4_SUCCESS_ONE_FETCH_NO_REFETCH", len(state["calls"]) == n + 1)

    # 429 counts as failure
    state.update(fail=True, mode="429")
    g429 = mk(2)
    g429._fetch_core_meta()
    check("C1B_HTTP_429_IS_FAILURE", not g429._core_meta_fetched and not g429._meta_cache)

    # 2 builder dex
    state.update(fail=True, mode="raise", calls=[])
    clock[0] += 1000
    g = mk(3)
    g._fetch_builder_meta("xyz")
    check("B1_FAIL_LEAVES_FLAG_UNSET", not g._builder_meta_fetched.get("xyz") and "XYZ:SPCX" not in g._meta_cache)
    check("B1_ONE_LOUD_ROW_FOR_DEX", len([r for r in rows() if "dex=xyz" in r["message"]]) == 1)
    g._fetch_builder_meta("xyz")
    clock[0] += 14
    g._fetch_builder_meta("xyz")
    check("B1_NO_NETWORK_BEFORE_BACKOFF", len(state["calls"]) == 1, str(len(state["calls"])))
    state["fail"] = False
    clock[0] += 2
    r = g._resolve_coin("xyz:SPCX")  # the lazy miss path
    check("B1_LAZY_MISS_RETRIES_AFTER_BACKOFF", len(state["calls"]) == 2 and g._builder_meta_fetched.get("xyz") and r.get("ok"), str(r)[:200])

    # 3 single flight
    state.update(fail=False, calls=[], gate=threading.Event())
    g = mk(4)
    ts = [threading.Thread(target=g._fetch_builder_meta, args=("xyz",)) for _ in range(6)]
    for t in ts:
        t.start()
    _t.sleep(0.5)
    check("F1_SINGLE_FLIGHT", len(state["calls"]) == 1, str(len(state["calls"])))
    state["gate"].set()
    for t in ts:
        t.join(5)
    state["gate"] = None
    check("F1_FLIGHT_COMPLETES", g._builder_meta_fetched.get("xyz") is True)

    # 5 backoff doubles, caps, resets
    state.update(fail=True, calls=[])
    g = mk(5)
    clock[0] += 5000
    waits = []
    for _ in range(7):
        g._fetch_builder_meta("abc")
        waits.append(g._meta_retry["abc"]["next"] - clock[0])
        clock[0] = g._meta_retry["abc"]["next"]
    check("K1_BACKOFF_DOUBLES_AND_CAPS", waits == [15, 30, 60, 120, 120, 120, 120], str(waits))
    state["fail"] = False
    g._fetch_builder_meta("abc")
    check("K1_SUCCESS_RESETS", g._builder_meta_fetched.get("abc") and g._meta_retry["abc"]["delay"] == 0)
    g._builder_meta_fetched.pop("abc")
    state["fail"] = True
    g._fetch_builder_meta("abc")
    check("K1_RESET_BACK_TO_BASE", g._meta_retry["abc"]["next"] - clock[0] == 15)

    # real startup path
    state.update(fail=False, calls=[])
    g = mk(6)
    g.warm_symbol_cache()
    check("W1_WARM_SYMBOL_CACHE_STILL_WORKS", g._core_meta_fetched and "BTC" in g._meta_cache)

    print("TOTAL=%d FAILED=%d" % (len(RESULTS), sum(1 for _n, ok in RESULTS if not ok)))
    sys.exit(1 if any(not ok for _n, ok in RESULTS) else 0)


if __name__ == "__main__":
    main()
