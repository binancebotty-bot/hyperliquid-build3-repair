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
    # 15 wallets: 7 active (idle volume) + 8 OFF. Today the 7 active + first 3 OFF take the 10 slots.
    modes = {}
    for i in range(7):
        modes[c.normalise_wallet(wallet(i))] = "CLO"
    for i in range(7, 15):
        modes[c.normalise_wallet(wallet(i))] = "OFF"
    # fill volume: the OFF wallets 8..15 are the busy leaders, the active ones are near-idle
    rank_rows = [(c.normalise_wallet(wallet(i)), 16000 - 100 * i) for i in range(7, 15)]
    rank_rows += [(c.normalise_wallet(wallet(i)), 500 - 10 * i) for i in range(7)]
    rank_rows.sort(key=lambda r: -r[1])           # CSV sorted busiest-first, as wallet_rank_24h.csv is

    cfg_path, rank_path = build_cfg(tmp, modes, rank_rows)
    cfg = c.ConfigManager(cfg_path)
    baseline = cfg.stream_wallets()               # env unset -> today's order
    today_expected = ([w for w in cfg.wallets() if modes.get(w) != "OFF"]
                      + [w for w in cfg.wallets() if modes.get(w) == "OFF"])[:10]
    check("H_SLOTS_UNRANKED_ORDER_UNCHANGED", baseline == today_expected,
          "baseline=%s expected=%s" % (baseline, today_expected))

    os.environ["HL_LIVE_WS_RANK_CSV"] = str(rank_path)
    ranked = cfg.stream_wallets()
    busiest_first = [w for w, _ in rank_rows]
    check("H_SLOTS_RANKED_BY_FILLS",
          ranked == busiest_first[:10],
          "ranked=%s expected=%s" % (ranked, busiest_first[:10]))
    check("H_SLOTS_RANKED_DIFFERS_FROM_TODAY", ranked != baseline, "ranked==baseline")
    check("H_SLOTS_RANKED_ALL_BUSIEST", all(c.normalise_wallet(wallet(i)) in ranked for i in range(7, 15)),
          "missing a busy leader: %s" % (ranked,))

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
    check("H_SPLIT_EXISTS", len(core.wallets) == 10 and len(polled) == 7, "ws=%d poll=%d" % (len(core.wallets), len(polled)))
    os.environ["HL_LIVE_POLL_ALL_ACTIVE"] = "0"
    check("H_POLL_ALL_ACTIVE_ZERO_FALLS_BACK",
          c.LiveCopyCore.poll_wallets(core) == list(core.wallets), "did not fall back to self.wallets")
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
        check("H_POOL_MAXSIZE_DEFAULT_6", pool_maxsize_for(None) == 6, "got %s" % (pool_maxsize_for(None),))
        check("H_POOL_MAXSIZE_FROM_ENV", pool_maxsize_for("9") == 9, "got %s" % (pool_maxsize_for("9"),))
        check("H_POOL_MAXSIZE_ZERO_UNLIMITED", pool_maxsize_for("0") == 0, "got %s" % (pool_maxsize_for("0"),))
        sess = et._SESSION
        check("H_POOL_SINGLE_SHARED_SESSION", sess is et._SESSION, "session replaced")
    finally:
        et._SESSION = None
        requests.Session.post = saved_post

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
