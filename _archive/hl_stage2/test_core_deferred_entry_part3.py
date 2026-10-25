#!/usr/bin/env python3
"""Part three: cache-miss retention, fresh mid on every retry, refresh-worker lock and cap.

Item 4: SEND_NOT_ATTEMPTED_UNSUPPORTED_SYMBOL from SYMBOL_CACHE_MISS(_NEEDS_REFRESH) is transient and
refreshable -> retained as UNIVERSE_STALE. SYMBOL_UNRESOLVED / not-listed is a named skip: no retention,
no retry. Item 5: the IOC retry and any replay re-read the follower mid at the moment of the send; the
stale computed price is never re-used. Item 6: the seq check and the publish share one lock; live workers
are capped by thread.is_alive() at a small fixed maximum, and a read past its wall-clock deadline is dropped.

Run (from _archive/hl_stage2): env -u HL_LIVE_AUDIT_DIR python3 test_core_deferred_entry_part3.py
No network, no orders: every send goes to a fake exchange.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + str(detail)) if (detail and not cond) else ""))


IOC_REJECT = {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"error": "could not immediately match"}]}}}
FILLED = {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"filled": {"oid": "1", "totalSz": "1", "avgPx": "100"}}]}}}


class Ex:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def update_leverage(self, leverage, name, is_cross=True):
        return {"status": "ok"}

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        self.calls.append({"px": px, "tif": tif, "cloid": str(cloid) if cloid is not None else None})
        return self.replies.pop(0) if self.replies else FILLED


def main():
    tmp = Path(tempfile.mkdtemp(prefix="deferred_part3_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
                       "HL_LIVE_INTENT_DURABLE_WAIT_MS": "2000", "HL_LIVE_MISSED_ENTRY_RULE": "0",
                       "HL_LIVE_RATE_LIMIT_COOLDOWN_MS": "0", "HL_LIVE_MIDS_CACHE_TTL_SEC": "-1",
                       "HL_LIVE_MIDS_MAX_AGE_SEC": "5", "HL_LIVE_UNIVERSE_REFRESH_COOLDOWN_SEC": "30"})
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {"marketable_bps": 0},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    c.HLAccount, c.HLExchange = object, object

    mids = {"BTC": "100"}
    c._XNET.post_many = lambda fetcher, payloads, url, timeout=None: [
        {"ok": True, "data": dict(mids)} for _ in (payloads if isinstance(payloads, list) else [payloads])]

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def gateway(ex, resolve=None):
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%s.json" % id(ex))))
        g._resolve_coin = resolve or (lambda coin: dict(resolved))
        g._get_exchange_client = lambda *a, **k: ex
        g._exchange_client_has_symbol = lambda *a, **k: True
        g._validate_final_wire_order = lambda *a, **k: (True, {})
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._exchange_client_for_coin = lambda coin: (ex, "BTC")
        g._pre_send_ownership_gate = lambda it: (True, {})
        g.leader_reduced_since = lambda f: 0
        g._margin_mode_done = {"BTC"}
        g.cfg.master_switch_now = lambda: True
        g.cfg.liq_parity_enabled = lambda: False
        return g

    def mk_intent(iid, fid=None, price=100.0):
        fill = c.LeaderFill(fid or ("f_" + iid), A, "BTC", "BUY", price, 1.0, c.utc_now_ms(), "TEST", 0,
                            {"dir": "Open Long"})
        return c.Intent(iid, fill, "BUY", 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
                        "sleeve:%s:BTC" % A, "", "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=ENTRY;")

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    try:
        # ---- ITEM 4a. a symbol CACHE MISS is retained as a refreshable reason ------------------------
        miss = {"ok": False, "status": "SYMBOL_CACHE_MISS_NEEDS_REFRESH", "error": "absent from local cache"}
        g = gateway(Ex([FILLED]), resolve=lambda coin: dict(miss))
        g.retain_deferred_entry = core._retain_deferred_entry
        it = mk_intent("miss-1", fid="miss-1")
        c.AuditLogWriter().append_order_intent(it)
        sent, status = g.send_if_allowed(it)
        check("CACHE_MISS_SEND_STATUS_IS_UNSUPPORTED_SYMBOL", sent is False and status == "SEND_NOT_ATTEMPTED_UNSUPPORTED_SYMBOL", (sent, status))
        check("CACHE_MISS_MAPS_TO_A_RETAINED_REASON", c.deferred_entry_reason_for(status, it) == "UNIVERSE_STALE",
              c.deferred_entry_reason_for(status, it))
        core._append_send_terminal(it.fill, it, status)   # the real core call site
        item = core.retention.snapshot().get("miss-1") or {}
        check("CACHE_MISS_TERMINAL_ROW_IS_A_RETAINED_ITEM", item.get("reason") == "UNIVERSE_STALE", item)
        it2 = mk_intent("miss-2", fid="miss-2")
        it2.terminal_hint = "SYMBOL_CACHE_MISS_NEEDS_REFRESH"
        check("CACHE_MISS_NEEDS_REFRESH_STATUS_ALSO_RETAINED",
              c.deferred_entry_reason_for("SEND_NOT_ATTEMPTED_UNSUPPORTED_SYMBOL", it2) == "UNIVERSE_STALE")
        check("CACHE_MISS_ITEM_IS_OFFERED_ON_THE_NEXT_PUBLISH",
              core._retention_trigger(core.retention.snapshot()["miss-1"], c.utc_now_ms()).startswith("universe:"))
        core.retention.drop("miss-1", "test cleanup")

        # ---- ITEM 4b. NOT LISTED is a named skip: NO retention, NO retry -----------------------------
        unresolved = {"ok": False, "status": "SYMBOL_UNRESOLVED", "error": "not in the follower meta"}
        g2 = gateway(Ex([FILLED]), resolve=lambda coin: dict(unresolved))
        g2.retain_deferred_entry = core._retain_deferred_entry
        it3 = mk_intent("unl-1", fid="unl-1")
        c.AuditLogWriter().append_order_intent(it3)
        sent3, status3 = g2.send_if_allowed(it3)
        check("NOT_LISTED_IS_A_NAMED_SKIP", sent3 is False and status3 == "SEND_NOT_ATTEMPTED_SYMBOL_UNRESOLVED", (sent3, status3))
        check("NOT_LISTED_HAS_NO_RETENTION_REASON", c.deferred_entry_reason_for(status3, it3) == "",
              c.deferred_entry_reason_for(status3, it3))
        core._append_send_terminal(it3.fill, it3, status3)
        check("NOT_LISTED_WRITES_NO_RETENTION_ITEM", "unl-1" not in core.retention.snapshot(), sorted(core.retention.snapshot()))
        check("NOT_LISTED_NEVER_ENTERS_THE_RETENTION_STORE", core.retention.retain(it3.fill, "SYMBOL_NOT_LISTED") is False)
        check("NOT_LISTED_RETRY_IS_NEVER_OFFERED", core._retention_trigger(
            {"reason": "SYMBOL_NOT_LISTED", "coin": "BTC", "triggers_done": []}, c.utc_now_ms()) == "")

        # ---- ITEM 5a. the IOC retry re-reads the follower mid --------------------------------------
        mids["BTC"] = "100"
        ex5 = Ex([IOC_REJECT, FILLED])
        g5 = gateway(ex5)
        it5 = mk_intent("retry-2")
        c.AuditLogWriter().append_order_intent(it5)
        real_mid = c.follower_mid
        seen = []

        def tracking_mid(coin):
            if len(seen) == 1:   # the market moves between the first refusal and the retry read
                mids["BTC"] = "120"
            px = real_mid(coin)
            seen.append(px)
            return px
        c.follower_mid = tracking_mid
        try:
            ok5, st5, res5 = g5._send_real(it5, {"send_cloid": c.generate_cloid(it5.intent_id)})
        finally:
            c.follower_mid = real_mid
        check("IOC_RETRY_RE_READS_THE_FOLLOWER_MID", len(seen) >= 2 and seen[1] == 120.0, seen)
        check("IOC_FIRST_ATTEMPT_PRICE_IS_THE_FIRST_MID", ex5.calls and ex5.calls[0]["px"] == 100.0, ex5.calls)
        check("IOC_RETRY_IS_PRICED_FROM_THE_FRESH_MID_NOT_THE_STALE_ONE",
              ok5 is True and len(ex5.calls) == 2 and ex5.calls[1]["px"] == 121.2, ex5.calls)

        # ---- ITEM 5b. a replay (a second send of the same fill) re-prices from a fresh mid ----------
        mids["BTC"] = "100"
        ex6 = Ex([FILLED, FILLED])
        g6 = gateway(ex6)
        it6 = mk_intent("replay-1")
        c.AuditLogWriter().append_order_intent(it6)
        g6._send_real(it6, {"send_cloid": c.generate_cloid(it6.intent_id)})
        mids["BTC"] = "130"
        g6._send_real(it6, {"send_cloid": c.generate_cloid(it6.intent_id)})
        check("REPLAY_USES_A_FRESHLY_READ_MID", [call["px"] for call in ex6.calls] == [100.0, 130.0], ex6.calls)

        # ---- ITEM 6a. the seq check and the publish are ONE critical section ------------------------
        class _Resp:
            status_code = 200

            def __init__(self, name):
                self.name = name

            def json(self):
                return {"universe": [{"name": self.name}]}

        real_post = c.requests.post
        try:
            c._AUTHORITATIVE_UNIVERSE.pop("", None)
            c._UNIVERSE_REFRESH[""] = {"until": 0, "seq": 1}
            c.requests.post = lambda *a, **k: _Resp("GAPCOIN")
            real_lock = threading.Lock()

            class NewerBeforeLock:   # a newer refresh lands exactly before the critical section is taken
                def __enter__(self):
                    c._UNIVERSE_REFRESH[""]["seq"] = 2
                    return real_lock.__enter__()

                def __exit__(self, *exc):
                    return real_lock.__exit__(*exc)
            c._UNIVERSE_REFRESH_LOCKS[""] = NewerBeforeLock()
            c._universe_refresh_worker("", 1)
            check("STALE_SEQ_CANNOT_PUBLISH_UNDER_THE_SAME_LOCK", "" not in c._AUTHORITATIVE_UNIVERSE,
                  sorted(c._AUTHORITATIVE_UNIVERSE))
            c._UNIVERSE_REFRESH[""]["seq"] = 1
            c._UNIVERSE_REFRESH_LOCKS[""] = real_lock
            c._universe_refresh_worker("", 1)
            check("CURRENT_SEQ_PUBLISHES_UNDER_ITS_OWN_LOCK", "GAPCOIN" in c._AUTHORITATIVE_UNIVERSE.get("", {}).get("symbols", set()),
                  sorted(c._AUTHORITATIVE_UNIVERSE))
        finally:
            c.requests.post = real_post
            c._UNIVERSE_REFRESH_LOCKS.pop("", None)
            c._UNIVERSE_REFRESH.pop("", None)

        # ---- ITEM 6b. a small FIXED cap on live workers, counted by is_alive() ---------------------
        gate = threading.Event()
        live = []
        for i in range(c._UNIVERSE_REFRESH_MAX_LIVE):
            t = threading.Thread(target=lambda: gate.wait(5.0), daemon=True, name="fakerefresh-%d" % i)
            t.start()
            live.append(t)
            c._UNIVERSE_REFRESH_THREADS["capdex%d" % i] = t
        check("CAP_IS_A_SMALL_FIXED_NUMBER", isinstance(c._UNIVERSE_REFRESH_MAX_LIVE, int)
              and 0 < c._UNIVERSE_REFRESH_MAX_LIVE <= 4, c._UNIVERSE_REFRESH_MAX_LIVE)
        check("CAP_REFUSES_A_NEW_WORKER_WHEN_FULL", c.refresh_authoritative_universe("capdexnew") is False)
        gate.set()
        for t in live:
            t.join(5.0)
        check("CAP_RECOUNTS_BY_IS_ALIVE_NOT_BY_A_WEAKENED_RULE", c.refresh_authoritative_universe("capdexnew") is True,
              sorted(c._UNIVERSE_REFRESH_THREADS))
        c._universe_refresh_join("capdexnew", 5.0)
        for k in [k for k in list(c._UNIVERSE_REFRESH_THREADS) if k.startswith("capdex")]:
            c._UNIVERSE_REFRESH_THREADS.pop(k, None)

        # ---- ITEM 6c. a read past its hard wall-clock deadline is dropped ---------------------------
        real_timeout = c._universe_refresh_timeout
        try:
            c._AUTHORITATIVE_UNIVERSE.pop("late", None)
            c._UNIVERSE_REFRESH["late"] = {"until": 0, "seq": 1}
            c._UNIVERSE_REFRESH_LOCKS["late"] = threading.Lock()
            c._universe_refresh_timeout = lambda: 0.05
            c.requests.post = lambda *a, **k: (time.sleep(0.2), _Resp("LATECOIN"))[1]
            c._universe_refresh_worker("late", 1)
            check("DEADLINE_DROPS_A_LATE_PUBLISH", "late" not in c._AUTHORITATIVE_UNIVERSE)
        finally:
            c._universe_refresh_timeout = real_timeout
            c.requests.post = real_post
            c._UNIVERSE_REFRESH.pop("late", None)
    finally:
        core.stop()

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
