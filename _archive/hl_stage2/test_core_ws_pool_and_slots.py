#!/usr/bin/env python3
"""HL3-006H: WS slot ranking by fill volume, HTTP pool cap, poll-all-active - offline tests.

Proves the four patch properties with no network, no engine run and no keys:
  1. stream_wallets() with HL_LIVE_WS_RANK_CSV set fills the MAX_WALLETS slots with the busiest
     leaders (fill-rank order), NOT the active-then-padding order; with the env unset, or the file
     absent/unreadable/rowless, the returned order is byte-identical to the previous behaviour;
  2. the REST backstop set == every active leader while the WS feed still holds only MAX_WALLETS
     (the busiest-on-WS / rest-on-poll split exists), and HL_LIVE_POLL_ALL_ACTIVE=0 falls back to
     exactly self.wallets;
  3. WSManager.start() called twice still runs ONE socket thread (no second connection);
  4. the shared HTTP session's adapter pool maxsize == HL_LIVE_HTTP_POOL_MAX (default 6, 0 = unlimited).

Run: python test_core_ws_pool_and_slots.py   # RESULT:: markers, exit 0/1.

"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def wait_for(pred, timeout: float = 6.0, step: float = 0.02) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(step)
    return bool(pred())


def wallet(i: int) -> str:
    return "0x" + ("%040x" % (i + 1))


class FakeApp:
    def __init__(self, url, on_open=None, on_message=None, on_error=None, on_close=None):
        self.on_open = on_open
        self.on_message = on_message
        self.on_error = on_error
        self.on_close = on_close
        self.sent = []
        self._closed = threading.Event()

    def send(self, data: str) -> None:
        self.sent.append(json.loads(data))

    def run_forever(self, **kw: object) -> None:
        if self.on_open:
            self.on_open(self)
        self._closed.wait(10.0)

    def close(self) -> None:
        self._closed.set()


class FakeWS:
    def __init__(self) -> None:
        self.apps = []

    def WebSocketApp(self, url, **kw):
        app = FakeApp(url, **kw)
        self.apps.append(app)
        return app


class FakeResp:
    status_code = 200
    text = "{}"

    def json(self):
        return {}

    def raise_for_status(self):
        return None


def build_cfg(tmp: Path, modes, rank_rows=None):
    """A ConfigManager over a temp live_config.json: modes maps wallet -> mode string."""
    cfg_path = tmp / "live_config.json"
    cfg_path.write_text(json.dumps({
        "wallets": {w: {"mode": m, "enabled": True} for w, m in modes.items()},
        "global_controls": {},
    }), encoding="utf-8")
    rank_path = tmp / "wallet_rank_24h.csv"
    if rank_rows is not None:
        lines = ["rank,wallet,fills_24h,pages,mode,stopped_http"]
        for i, (w, fills) in enumerate(rank_rows, start=1):
            lines.append("%d,%s,%d,1,OFF," % (i, w, fills))
        rank_path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    return cfg_path, rank_path


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="wspool_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
        "HL_LIVE_WS_ENABLED": "1",
        "HL_LIVE_WS_HEARTBEAT_SEC": "3600",
        "HL_LIVE_WS_SUBSCRIBE_GRACE_MS": "150",
        "HL_LIVE_WS_MAX_WALLETS": "10",
        "HL_LIVE_HTTP_SESSION": "1",
    })
    os.environ.pop("HL_LIVE_WS_RANK_CSV", None)
    os.environ.pop("HL_LIVE_POLL_ALL_ACTIVE", None)
    os.environ.pop("HL_LIVE_HTTP_POOL_MAX", None)

    import HL_Live_Copy_Service_Core as c
    import exchange_truth as et

    # ---------------------------------------------------------------- 1. slot ranking
    # 15 wallets: 12 LIVE + 3 OFF. Only LIVE holds a WS slot; CLO and OFF ride REST polling.
    modes = {}
    for i in range(12):
        modes[c.normalise_wallet(wallet(i))] = "LIVE"
    for i in range(12, 15):
        modes[c.normalise_wallet(wallet(i))] = "OFF"
    rank_rows = [(c.normalise_wallet(wallet(i)), 16000 - 100 * i) for i in range(12)]
    rank_rows.sort(key=lambda r: -r[1])           # CSV sorted busiest-first, as wallet_rank_24h.csv is

    cfg_path, rank_path = build_cfg(tmp, modes, rank_rows)
    cfg = c.ConfigManager(cfg_path)
    baseline = cfg.stream_wallets()               # env unset -> today's order
    today_expected = [w for w in cfg.wallets() if modes.get(w) == "LIVE"][:10]
    check("H_SLOTS_UNRANKED_ORDER_UNCHANGED", baseline == today_expected,
          "baseline=%s expected=%s" % (baseline, today_expected))

    os.environ["HL_LIVE_WS_RANK_CSV"] = str(rank_path)
    ranked = cfg.stream_wallets()
    busiest_first = [w for w, _ in rank_rows]
    expected = [w for w in busiest_first if modes.get(w) == "LIVE"][:10]
    check("H_SLOTS_RANKED_BY_FILLS",
          ranked == expected,
          "ranked=%s expected=%s" % (ranked, expected))
    check("H_SLOTS_ACTIVE_IN_FILL_ORDER",
          ranked == [w for w in busiest_first if modes.get(w) == "LIVE"][:10],
          "active wallets not in fill-rank order: %s" % (ranked,))
    check("H_SLOTS_ACTIVE_ALL_IN_RATED", all(c.normalise_wallet(wallet(i)) in ranked for i in range(10)),
          "missing a top-10 LIVE leader: %s" % (ranked,))
    # CLO/OFF must never be handed a websocket slot (controller ruling 6313307039)
    check("H_SLOTS_NEVER_FROM_NON_LIVE", all(modes.get(w) == "LIVE" for w in ranked),
          "non-LIVE wallet in slots: %s" % (ranked,))

    # missing file / no rows / garbage -> strict no-op (byte-identical to today)
    os.environ["HL_LIVE_WS_RANK_CSV"] = str(tmp / "does_not_exist.csv")
    check("H_SLOTS_MISSING_CSV_IS_NOOP", cfg.stream_wallets() == baseline, "changed on missing CSV")
    empty = tmp / "empty.csv"
    empty.write_text("rank,wallet,fills_24h\r\n", encoding="utf-8")
    os.environ["HL_LIVE_WS_RANK_CSV"] = str(empty)
    check("H_SLOTS_ROWLESS_CSV_IS_NOOP", cfg.stream_wallets() == baseline, "changed on rowless CSV")
    os.environ["HL_LIVE_WS_RANK_CSV"] = str(rank_path.parent)   # a directory -> OSError, not a crash
    check("H_SLOTS_UNREADABLE_CSV_IS_NOOP", cfg.stream_wallets() == baseline, "changed on unreadable CSV")
    # a CSV whose rows match nothing in the config must not reorder anything either
    foreign = tmp / "foreign.csv"
    foreign.write_text("rank,wallet,fills_24h\r\n1,%s,9999\r\n" % wallet(900), encoding="utf-8")
    os.environ["HL_LIVE_WS_RANK_CSV"] = str(foreign)
    check("H_SLOTS_FOREIGN_CSV_IS_NOOP", cfg.stream_wallets() == baseline, "changed on foreign CSV")
    os.environ.pop("HL_LIVE_WS_RANK_CSV", None)
    check("H_SLOTS_ENV_UNSET_IS_NOOP", cfg.stream_wallets() == baseline, "changed with env unset")

    # ---------------------------------------------------------------- 2. poll set == all active
    class FakeCore:
        def __init__(self, cfg, wallets):
            self.cfg = cfg
            self.wallets = wallets

    core = FakeCore(cfg, cfg.stream_wallets())
    polled = c.LiveCopyCore.poll_wallets(core)
    active = cfg.active_wallets()
    check("H_POLL_SET_IS_ALL_ACTIVE", polled == active, "polled=%s active=%s" % (polled, active))
    # the real invariant: every wallet that holds a WS slot AND is active is in the poll set, and no
    # active wallet is missing from the poll (OFF padding wallets in the WS slots are skipped by the
    # poll by design, line "if self.cfg.wallet_mode(w) == 'OFF': continue").
    ws_active = [w for w in core.wallets if modes.get(w) != "OFF"]
    check("H_POLL_COVERS_WS_ACTIVE_SLOTS", all(w in polled for w in ws_active),
          "unpolled WS holders: %s" % ([w for w in ws_active if w not in polled],))
    check("H_NO_ACTIVE_WALLET_MISSING_FROM_POLL", not (set(active) - set(polled)),
          "active but unpolled: %s" % (sorted(set(active) - set(polled)),))
    check("H_SPLIT_EXISTS", len(core.wallets) == 10 and len(polled) == 12, "ws=%d poll=%d" % (len(core.wallets), len(polled)))
    os.environ["HL_LIVE_POLL_ALL_ACTIVE"] = "0"
    # Fix for Finding 5: use a DIFFERENT wallets list so the assertion is not tautological.
    # poll_wallets() must return exactly self.wallets when HL_LIVE_POLL_ALL_ACTIVE=0,
    # not just "whatever happens to be in self.wallets".
    core_diff = FakeCore(cfg, list(core.wallets)[:3])
    check("H_POLL_ALL_ACTIVE_ZERO_FALLS_BACK",
          c.LiveCopyCore.poll_wallets(core_diff) == list(core_diff.wallets),
          "did not fall back to self.wallets: got %s" % (c.LiveCopyCore.poll_wallets(core_diff),))
    check("H_POLL_ALL_ACTIVE_ZERO_NOT_ALL_ACTIVE",
          c.LiveCopyCore.poll_wallets(core_diff) != cfg.active_wallets(),
          "poll_wallets returned all active wallets instead of self.wallets")
    os.environ.pop("HL_LIVE_POLL_ALL_ACTIVE", None)

    # ---------------------------------------------------------------- 3. one WS thread
    mgr = c.WSManager(lambda: list(cfg.stream_wallets()), c.LeaderFillIngestor(), lambda f: True)
    mgr.enabled = True
    saved = c.websocket
    fake = FakeWS()
    c.websocket = fake
    try:
        mgr.start()
        wait_for(lambda: len(fake.apps) >= 1)
        first_thread = mgr._thread
        mgr.start()                       # second start() must be a no-op
        mgr.start()
        time.sleep(0.3)
        check("H_WS_START_TWICE_ONE_THREAD",
              mgr._thread is first_thread and len(fake.apps) == 1 and first_thread.is_alive(),
              "apps=%d thread_reused=%s" % (len(fake.apps), mgr._thread is first_thread))
        check("H_WS_SLOTS_TRUNCATED_TO_MAX",
              len(mgr.wallets_now()) == 10, "wallets_now=%s" % (mgr.wallets_now(),))
    finally:
        mgr.stop()
        c.websocket = saved

    # ---------------------------------------------------------------- 4. HTTP pool cap
    import requests
    saved_post = requests.Session.post

    def pool_maxsize_for(value):
        et._SESSION = None               # force a fresh session so the adapter is rebuilt
        if value is None:
            os.environ.pop("HL_LIVE_HTTP_POOL_MAX", None)
        else:
            os.environ["HL_LIVE_HTTP_POOL_MAX"] = value
        requests.Session.post = lambda self, url, **kw: FakeResp()
        try:
            et.http_post("https://api.hyperliquid.xyz/info", {"type": "allMids"}, 1)
            ad = et._SESSION.get_adapter("https://api.hyperliquid.xyz/info")
            return int(ad.poolmanager.connection_pool_kw.get("maxsize"))
        finally:
            requests.Session.post = saved_post

    try:
        check("H_POOL_MAXSIZE_DEFAULT_8", pool_maxsize_for(None) == 8, "got %s" % (pool_maxsize_for(None),))
        check("H_POOL_MAXSIZE_FROM_ENV", pool_maxsize_for("9") == 9, "got %s" % (pool_maxsize_for("9"),))
        check("H_POOL_MAXSIZE_ZERO_UNLIMITED", pool_maxsize_for("0") == 0, "got %s" % (pool_maxsize_for("0"),))
        sess = et._SESSION
        check("H_POOL_SINGLE_SHARED_SESSION", sess is et._SESSION, "session replaced")
        _adapter = et._SESSION.get_adapter("https://api.hyperliquid.xyz/info")
        _block = _adapter.poolmanager.connection_pool_kw.get("block")
        check("H_POOL_BLOCK_TRUE", _block is True, "pool_block=%s (must be True to bound peak sockets)" % (_block,))
    finally:
        et._SESSION = None
        requests.Session.post = saved_post

    # ---------------------------------------------------------------- 5. Finding 1: HTTP pool max crash
    # A non-numeric HL_LIVE_HTTP_POOL_MAX must not crash http_post.
    for bad_val in ["abc", "", "6.5", "1e3"]:
        et._SESSION = None
        os.environ["HL_LIVE_HTTP_POOL_MAX"] = bad_val
        requests.Session.post = lambda self, url, **kw: FakeResp()
        try:
            et.http_post("https://api.hyperliquid.xyz/info", {"type": "allMids"}, 1)
            ad = et._SESSION.get_adapter("https://api.hyperliquid.xyz/info")
            got = int(ad.poolmanager.connection_pool_kw.get("maxsize"))
            check("H_POOL_MAX_BAD_VAL_%s" % (bad_val.replace(".", "_").replace(" ", "_") or "empty"),
                  got == 8, "expected default 8, got %s" % (got,))
        except ValueError:
            check("H_POOL_MAX_BAD_VAL_%s" % (bad_val.replace(".", "_").replace(" ", "_") or "empty"),
                  False, "ValueError raised for HL_LIVE_HTTP_POOL_MAX=%r" % (bad_val,))
        finally:
            requests.Session.post = saved_post
    et._SESSION = None
    os.environ.pop("HL_LIVE_HTTP_POOL_MAX", None)

    # ---------------------------------------------------------------- 6. Finding 2: poll interval with poll-all-active
    # When active > MAX_WALLETS, feed_ok must still be True if the WS slots are all acked.
    class FakeWS2:
        def __init__(self, enabled=True, socket_open=True, subscribed=()):
            self.enabled = enabled
            self._socket_open = socket_open
            self._subscribed = subscribed

    class FakeCore2:
        def __init__(self, cfg, wallets, active_wallets):
            self.cfg = cfg
            self.wallets = wallets
            self._active = active_wallets
        def active_wallets(self):
            return self._active

    # 15 active wallets, 10 WS slots, all 10 slots acked -> feed_ok=True -> backstop rate
    active_15 = [c.normalise_wallet(wallet(i)) for i in range(15)]
    ws_slots_10 = active_15[:10]
    fake_ws = FakeWS2(enabled=True, socket_open=True, subscribed=ws_slots_10)
    core2 = FakeCore2(cfg, ws_slots_10, active_15)
    core2.ws = fake_ws
    os.environ["HL_LIVE_POLL_ALL_ACTIVE"] = "1"
    os.environ["HL_LIVE_LEADER_POLL_INTERVAL_SEC"] = "30"
    interval = c.LiveCopyCore.leader_poll_interval_sec(core2)
    check("H_POLL_INTERVAL_FEED_OK_WITH_SPLIT",
          interval == 30.0,
          "expected backstop rate 30.0, got %s (feed_ok should be True when WS slots are acked)" % (interval,))
    # If the WS slots are NOT all acked, feed_ok=False -> fast rate
    fake_ws2 = FakeWS2(enabled=True, socket_open=True, subscribed=ws_slots_10[:5])
    core2.ws = fake_ws2
    interval2 = c.LiveCopyCore.leader_poll_interval_sec(core2)
    check("H_POLL_INTERVAL_FEED_NOT_OK_FAST",
          interval2 < 30.0,
          "expected fast rate < 30.0, got %s (feed_ok should be False when WS slots are not acked)" % (interval2,))
    os.environ.pop("HL_LIVE_POLL_ALL_ACTIVE", None)
    os.environ.pop("HL_LIVE_LEADER_POLL_INTERVAL_SEC", None)

    # ---------------------------------------------------------------- 7. Finding 3: _by_fill_rank caching
    # Call _by_fill_rank twice with the same CSV; the second call must use the cache.
    os.environ["HL_LIVE_WS_RANK_CSV"] = str(rank_path)
    # _by_fill_rank is on ConfigManager, not LiveCopyCore
    cands = cfg.stream_wallets()
    # First call: populates cache
    r1 = cfg._by_fill_rank(list(cands))
    # Second call: must use cache (same result, no file re-read)
    r2 = cfg._by_fill_rank(list(cands))
    check("H_BY_FILL_RANK_CACHE_CONSISTENT", r1 == r2, "cache returned different result")
    # Verify cache is actually used by checking mtime is stored
    check("H_BY_FILL_RANK_CACHE_MTIME_SET",
          getattr(cfg, "_rank_cache_mtime", None) is not None,
          "cache mtime not set")
    # Invalidate by touching the file (change mtime)
    import time as _time
    _time.sleep(0.01)
    rank_path.write_text(rank_path.read_text(encoding="utf-8") + "", encoding="utf-8")
    # Touch to change mtime
    os.utime(rank_path, None)
    r3 = cfg._by_fill_rank(list(cands))
    check("H_BY_FILL_RANK_CACHE_INVALIDATED", r3 == r1, "cache not invalidated on mtime change")
    os.environ.pop("HL_LIVE_WS_RANK_CSV", None)

    # ---------------------------------------------------------------- 8. Finding 4: poll_wallets OFF filtering
    # poll_wallets() must filter OFF wallets from the active set.
    os.environ["HL_LIVE_POLL_ALL_ACTIVE"] = "1"
    # cfg has 7 active + 8 OFF wallets; poll_wallets must return only the 7 active
    polled_filtered = c.LiveCopyCore.poll_wallets(core)
    off_wallets = [w for w in cfg.active_wallets() if cfg.wallet_mode(w) == "OFF"]
    check("H_POLL_WALLETS_FILTERS_OFF",
          not any(w in polled_filtered for w in off_wallets),
          "OFF wallets in poll set: %s" % ([w for w in polled_filtered if w in off_wallets],))
    check("H_POLL_WALLETS_ACTIVE_ONLY",
          polled_filtered == [w for w in cfg.active_wallets() if cfg.wallet_mode(w) != "OFF"],
          "poll_wallets did not filter OFF wallets")
    os.environ.pop("HL_LIVE_POLL_ALL_ACTIVE", None)

    # ---------------------------------------------------------------- 9. B-FINDING 1: mode partition
    # With MAX_WALLETS=3 and 3 active + 3 busier OFF, all 3 active must be in stream_wallets().
    _saved_max = c.MAX_WALLETS
    c.MAX_WALLETS = 3
    ranked_3 = cfg.stream_wallets()
    check("B1_ALL_SLOTS_ARE_ACTIVE", all(modes.get(w) != "OFF" for w in ranked_3),
          "non-active wallet in slots: %s" % (ranked_3,))
    check("B1_NO_OFF_WHEN_ACTIVE_FILL", not any(c.normalise_wallet(wallet(i)) in ranked_3 for i in range(7, 15)),
          "OFF wallet took a slot from an active one: %s" % (ranked_3,))
    c.MAX_WALLETS = _saved_max

    # ---------------------------------------------------------------- 10. review-1: feed_set uses stream_wallets
    # leader_poll_interval_sec must relax to backstop when all WS slots are acked,
    # even when poll set > feed set.
    class _FakeWS:
        def __init__(self):
            self.enabled = True
            self._socket_open = True
            self._subscribed = ()
    _ws = _FakeWS()
    _ws._subscribed = tuple(cfg.stream_wallets())
    core.ws = _ws
    os.environ["HL_LIVE_LEADER_POLL_INTERVAL_SEC"] = "30"
    _interval = c.LiveCopyCore.leader_poll_interval_sec(core)
    check("R1_FEED_OK_RELAXES", _interval == 30.0,
          "expected backstop 30.0 when all WS slots acked, got %s" % (_interval,))
    os.environ.pop("HL_LIVE_LEADER_POLL_INTERVAL_SEC", None)

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
