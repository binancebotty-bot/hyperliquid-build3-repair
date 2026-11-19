#!/usr/bin/env python3
"""rw15: an EMPTY/invalid/HTTP>=400 builder-dex meta response is a FAILURE (rw11 backoff), never "fetched".

Before: _fetch_builder_meta accepted HTTP 200 with an empty universe, set _builder_meta_fetched[dex]=True (retries suppressed for the
process lifetime) so snapshot-only builder symbols stayed blocked. Now the cache and the flag are untouched, the failure is loud once
per window, and a later valid fetch after backoff unblocks sends.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw15_builder_empty.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. Fake clock + fake requests.post; no network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rw15_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_FOLLOWER_DEXES": "xyz", "HL_LIVE_DISABLE_NETWORK_REFRESH": "0",
                       "HL_LIVE_HL_PRIVATE_KEY": "0x" + "1" * 64})
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    c.HLAccount, c.HLExchange = object, object
    clock = [1000.0]
    c.time.monotonic = lambda: clock[0]
    st = {"mode": "ok", "calls": []}
    logs = []
    c.log_error = lambda src, msg, *a, **k: logs.append((src, msg))

    def fake_post(url, json=None, timeout=None):
        st["calls"].append(dict(json))
        if not json.get("dex"):
            return Resp({"universe": [{"name": "BTC", "szDecimals": 3}]})
        m = st["mode"]
        if m == "empty":
            return Resp({"universe": []})
        if m == "nouniverse":
            return Resp({})
        if m == "list":
            return Resp([])
        if m == "garbage":
            return Resp({"universe": [None, 3, {"name": ""}, "x"]})
        if m == "http":
            return Resp({}, 503)
        return Resp({"universe": [{"name": "%s:SPCX" % json["dex"], "szDecimals": 2}]})

    c.requests.post = fake_post
    snap = {"symbols": {"BTC": {"source": "core_meta", "canonical_symbol": "BTC", "sz_decimals": 3},
                        "XYZ:SPCX": {"source": "builder_meta", "canonical_symbol": "XYZ:SPCX", "perp_dex": "xyz", "sz_decimals": 1}},
            "asset_index_to_symbol": {"0": "BTC"}}

    def mk(n):
        c.atomic_write_json(c.ASSET_UNIVERSE_SNAPSHOT_FILE, snap)
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%s.json" % n)))
        g._load_asset_universe_snapshot()
        g._fetch_core_meta()  # core is live; only the builder row is snapshot-only
        return g

    def builder_logs():
        return [m for s, m in logs if s == "asset_meta_fetch" and "dex=xyz" in m]

    for label in ("empty", "nouniverse", "list", "garbage", "http"):
        clock[0] += 10000
        logs.clear()
        st.update(mode=label, calls=[])
        g = mk(label)
        st["calls"].clear()
        before = dict(g._meta_cache)
        g._fetch_builder_meta("xyz")
        L = label.upper()
        check("E_%s_FLAG_STAYS_FALSE" % L, not g._builder_meta_fetched.get("xyz"))
        check("E_%s_CACHE_UNTOUCHED_LAST_GOOD_KEPT" % L, g._meta_cache == before and g._meta_cache["XYZ:SPCX"]["szDecimals"] == 1)
        check("E_%s_SNAPSHOT_BUILDER_STILL_BLOCKED" % L, g._resolve_coin("XYZ:SPCX").get("ok") is False)
        check("E_%s_LOUD_ONCE" % L, len(builder_logs()) == 1, str(logs))
        n = len(st["calls"])
        g._fetch_builder_meta("xyz")
        check("E_%s_BACKOFF_NO_REFETCH_NO_REPEAT_LOG" % L, len(st["calls"]) == n and len(builder_logs()) == 1)
        clock[0] += 20
        g._fetch_builder_meta("xyz")
        check("E_%s_RETRIES_AFTER_BACKOFF" % L, len(st["calls"]) == n + 1 and not g._builder_meta_fetched.get("xyz"))
        st["mode"] = "ok"
        clock[0] += 500
        g._fetch_builder_meta("xyz")
        r = g._resolve_coin("XYZ:SPCX")
        check("E_%s_LATER_VALID_FETCH_SUCCEEDS_AND_UNBLOCKS" % L,
              g._builder_meta_fetched.get("xyz") is True and r.get("ok") is True and r.get("sz_decimals") == 2, str(r))
        n = len(st["calls"])
        g._fetch_builder_meta("xyz")
        check("E_%s_NO_REFETCH_ONCE_FETCHED" % L, len(st["calls"]) == n)

    # the periodic refresh must keep the last-good builder copy and flag when the builder answers empty
    clock[0] += 10000
    st.update(mode="ok", calls=[])
    g = mk("refresh")
    g._fetch_builder_meta("xyz")
    check("R_SETUP_BUILDER_FETCHED", g._builder_meta_fetched.get("xyz") is True)
    st["mode"] = "empty"
    clock[0] += 10000
    g._universe_last_refresh_ms = 0
    check("R_REFRESH_RETURNS_FALSE_ON_EMPTY_BUILDER", g.refresh_asset_universe() is False)
    check("R_LAST_GOOD_BUILDER_KEPT_AND_FLAG_RESTORED",
          g._meta_cache["XYZ:SPCX"]["szDecimals"] == 2 and g._builder_meta_fetched.get("xyz") is True)

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
