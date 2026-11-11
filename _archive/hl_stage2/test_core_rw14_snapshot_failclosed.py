#!/usr/bin/env python3
"""rw14: snapshot-loaded symbol/index rows are READ-ONLY until a valid NONEMPTY authoritative core meta fetch lands.

Startup _fetch_core_meta treats an EMPTY or failed response as failure (caches untouched, _core_meta_fetched stays false, rw11
backoff + single flight). While only the snapshot is loaded, _resolve_coin used for SENDING (entry/add/exit) fails closed for core
rows, @index rows and builder-dex rows, with ONE loud ASSET_META row per window; reads (allow_snapshot) still see the snapshot.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw14_snapshot_failclosed.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. Fake clock + fake requests.post + fake exchange; no network, no orders.
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
A = "0x" + "a" * 40
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
    tmp = Path(tempfile.mkdtemp(prefix="rw14_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_FOLLOWER_DEXES": "xyz", "HL_LIVE_DISABLE_NETWORK_REFRESH": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_HL_PRIVATE_KEY": "0x" + "1" * 64})
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    c.HLAccount, c.HLExchange = object, object
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    clock = [1000.0]
    c.time.monotonic = lambda: clock[0]
    st = {"mode": "ok", "calls": [], "gate": None, "builder_ok": True}

    def fake_post(url, json=None, timeout=None):
        st["calls"].append(dict(json))
        if st["gate"] is not None:
            st["gate"].wait(5)
        is_b = bool(json.get("dex"))
        if is_b:
            if not st["builder_ok"]:
                raise RuntimeError("builder boom")
            return Resp({"universe": [{"name": "%s:SPCX" % json["dex"], "szDecimals": 2}]})
        if st["mode"] == "raise":
            raise RuntimeError("boom")
        if st["mode"] == "429":
            return Resp({}, 429)
        if st["mode"] == "empty":
            return Resp({"universe": []})
        return Resp({"universe": [{"name": "BTC", "szDecimals": 3}, {"name": "ETH", "szDecimals": 4}]})

    c.requests.post = fake_post

    snap = {"symbols": {
        "BTC": {"source": "core_meta", "canonical_symbol": "BTC", "sz_decimals": 1},  # stale on purpose: the live value is 3
        "XYZ:SPCX": {"source": "builder_meta", "canonical_symbol": "XYZ:SPCX", "perp_dex": "xyz", "sz_decimals": 1},
    }, "asset_index_to_symbol": {"0": "BTC", "5": "OLDCOIN"}}

    def mk(n):
        c.atomic_write_json(c.ASSET_UNIVERSE_SNAPSHOT_FILE, snap)
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%d.json" % n)))
        g._load_asset_universe_snapshot()
        return g

    def loud_rows():
        p = Path(c.RECONCILIATION_CSV)
        if not p.exists():
            return []
        with open(p, newline="", encoding="utf-8-sig") as fh:
            return [r for r in csv.DictReader(fh) if "ASSET_META_SNAPSHOT_ONLY" in "|".join(r.values())]

    class Ex:
        def __init__(self):
            self.calls = []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append(coin)
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 3}}]}}}

    def gw_send(g, ex):  # only the resolver is real; everything after it is faked
        g._get_exchange_client = lambda *a, **k: ex
        g._exchange_client_has_symbol = lambda *a, **k: True
        g._validate_final_wire_order = lambda *a, **k: (True, {})
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._exchange_client_for_coin = lambda coin: (ex, coin)
        g._pre_send_ownership_gate = lambda it: (True, {})
        g.leader_reduced_since = lambda f: 0
        g._margin_mode_done = {"BTC", "ETH", "xyz:SPCX"}
        g.cfg.master_switch_now = lambda: True
        g.cfg.liq_parity_enabled = lambda: False

    def mk_intent(iid, coin, kind):
        side = "SELL" if kind == "EXIT" else "BUY"
        fill = c.LeaderFill("f_" + iid, A, coin, side, 100.0, 1.0, c.utc_now_ms(), "TEST")
        return c.Intent(iid, fill, side, 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", kind, "sleeve:%s:%s" % (A, coin), "",
                        "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=%s;" % kind)

    def rd(g, coin):  # the read/UI resolver (a TypeError on the pre-rw14 source becomes a plain assertion failure)
        try:
            return g._resolve_coin(coin, allow_snapshot=True)
        except TypeError:
            return {"ok": False}

    def send(g, iid, coin, kind):
        try:
            return g._send_real(mk_intent(iid, coin, kind))
        except Exception as exc:  # a raise here is still "not sent"; callers assert on the exchange fake
            return False, "RAISED:" + repr(exc)[:80], {}

    # 1 startup EMPTY response: failure, nothing marked fetched, caches untouched, then resolve/send fail closed
    g = mk(1)
    ex = Ex()
    gw_send(g, ex)
    st.update(mode="empty", builder_ok=False)
    g._fetch_core_meta()
    check("S1_EMPTY_STARTUP_NOT_MARKED_FETCHED", g._core_meta_fetched is False)
    check("S1_EMPTY_STARTUP_CACHES_UNTOUCHED", g._index_cache == {0: "BTC", 5: "OLDCOIN"} and g._meta_cache["BTC"]["szDecimals"] == 1)
    check("S1_EXACT_SYMBOL_FAILS_CLOSED", g._resolve_coin("BTC").get("ok") is False)
    check("S1_AT_INDEX_FAILS_CLOSED", g._resolve_coin("@0").get("ok") is False)
    check("S1_BUILDER_ROW_FAILS_CLOSED", g._resolve_coin("XYZ:SPCX").get("ok") is False)
    for kind in ("ENTRY", "ADD", "EXIT"):
        ok, status, res = send(g, "e1" + kind, "BTC", kind)
        check("S1_SEND_%s_BLOCKED_NO_EXCHANGE" % kind, ok is False and not ex.calls and res.get("exchange_called") is not True, "%s %s" % (status, ex.calls))
    check("S1_ONE_LOUD_ROW_PER_WINDOW", len(loud_rows()) == 1, str(len(loud_rows())))
    check("S1_LOUD_ROW_NAMES_THE_COIN", loud_rows() and "BTC" in "|".join(loud_rows()[0].values()))
    check("S1_READ_PATH_MAY_USE_SNAPSHOT", rd(g, "BTC").get("ok") is True
          and rd(g, "@0").get("ok") is True)
    clock[0] += 700  # a new window: the still-blocked state is named again, once
    g._resolve_coin("BTC")
    g._resolve_coin("ETH")
    check("S1_NEW_WINDOW_ONE_MORE_ROW", len(loud_rows()) == 2, str(len(loud_rows())))

    # 2 startup FAILURE (exception and HTTP 429): same, and backoff + single flight are the rw11 helpers
    for label, mode in (("RAISE", "raise"), ("HTTP429", "429")):
        g = mk(2)
        ex = Ex()
        gw_send(g, ex)
        st.update(mode=mode, calls=[])
        clock[0] += 1000
        g._fetch_core_meta()
        check("S2_%s_NOT_MARKED_FETCHED_CACHES_UNTOUCHED" % label,
              g._core_meta_fetched is False and g._index_cache == {0: "BTC", 5: "OLDCOIN"} and "ETH" not in g._meta_cache)
        check("S2_%s_RESOLVE_FAILS_CLOSED" % label, g._resolve_coin("BTC").get("ok") is False and g._resolve_coin("@0").get("ok") is False)
        ok, status, res = send(g, "f2" + label, "BTC", "ENTRY")
        check("S2_%s_SEND_BLOCKED_NO_EXCHANGE" % label, ok is False and not ex.calls, status)
        n = len(st["calls"])
        g._fetch_core_meta()
        check("S2_%s_BACKOFF_NO_REFETCH" % label, len(st["calls"]) == n)
        clock[0] += 20
        g._fetch_core_meta()
        check("S2_%s_RETRIES_AFTER_BACKOFF" % label, len(st["calls"]) == n + 1)

    # 3 single flight on the startup fetch
    g = mk(3)
    st.update(mode="ok", calls=[], gate=threading.Event())
    clock[0] += 1000
    ts = [threading.Thread(target=g._fetch_core_meta) for _ in range(5)]
    for t in ts:
        t.start()
    _t.sleep(0.4)
    check("S3_SINGLE_FLIGHT", len([x for x in st["calls"] if not x.get("dex")]) == 1, str(st["calls"]))
    st["gate"].set()
    for t in ts:
        t.join(5)
    st["gate"] = None

    # 4 a valid NONEMPTY fetch swaps the maps (stale rows dropped, live values win) and sends go through
    g = mk(4)
    ex = Ex()
    gw_send(g, ex)
    st.update(mode="ok", calls=[])
    clock[0] += 1000
    g._fetch_core_meta()
    check("V1_VALID_FETCH_MARKS_FETCHED", g._core_meta_fetched is True and g._meta_fetched is True)
    check("V1_LIVE_VALUES_SWAPPED_STALE_ROWS_GONE", g._meta_cache["BTC"]["szDecimals"] == 3 and g._index_cache == {0: "BTC", 1: "ETH"}
          and "OLDCOIN" not in g._meta_cache)
    check("V1_RESOLVE_OK_CORE_AND_INDEX", g._resolve_coin("BTC").get("ok") is True and g._resolve_coin("@1").get("ok") is True
          and g._resolve_coin("BTC").get("sz_decimals") == 3)
    rows_before = len(loud_rows())
    ok, status, res = send(g, "v1", "BTC", "ENTRY")
    check("V1_SEND_REACHES_EXCHANGE", ok is True and ex.calls == ["BTC"], "%s %s" % (status, ex.calls))
    check("V1_NO_LOUD_ROW_FOR_FETCHED_CORE", len(loud_rows()) == rows_before)

    # 5 builder dex: core fetched but the snapshot-only builder row stays blocked until its own fetch lands
    g = mk(5)
    st.update(mode="ok", calls=[], builder_ok=False)
    clock[0] += 1000
    g._fetch_core_meta()
    r = g._resolve_coin("XYZ:SPCX")
    check("B1_SNAPSHOT_ONLY_BUILDER_BLOCKED_AFTER_CORE_FETCH", r.get("ok") is False and g._resolve_coin("BTC").get("ok") is True, str(r.get("status")))
    check("B1_BUILDER_READ_STILL_SNAPSHOT", rd(g, "XYZ:SPCX").get("ok") is True)
    st["builder_ok"] = True
    n = len(st["calls"])
    check("B1_RESOLVE_ITSELF_MAKES_NO_EXCHANGE_CALL", g._resolve_coin("XYZ:SPCX").get("ok") is False and len(st["calls"]) == n)
    clock[0] += 1000
    g._fetch_builder_meta("xyz")
    r = g._resolve_coin("XYZ:SPCX")
    check("B2_VALID_BUILDER_FETCH_UNBLOCKS", r.get("ok") is True and r.get("sz_decimals") == 2 and r.get("sdk_coin") == "xyz:SPCX", str(r))

    # 6 the periodic refresh (rw13) also clears the snapshot gate
    g = mk(6)
    st.update(mode="ok", calls=[], builder_ok=True)
    clock[0] += 1000
    g._universe_last_refresh_ms = 0
    g.refresh_asset_universe()
    check("R1_REFRESH_CLEARS_GATE", g._resolve_coin("BTC").get("ok") is True and g._resolve_coin("XYZ:SPCX").get("ok") is True)

    # 7 warm_symbol_cache after a failed fetch leaves the refresh timer unset so the periodic refresh retries
    g = mk(7)
    st.update(mode="raise", calls=[], builder_ok=True)
    clock[0] += 1000
    g.warm_symbol_cache()
    check("W1_FAILED_WARM_DOES_NOT_START_REFRESH_TIMER", not g._universe_last_refresh_ms, str(g._universe_last_refresh_ms))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
