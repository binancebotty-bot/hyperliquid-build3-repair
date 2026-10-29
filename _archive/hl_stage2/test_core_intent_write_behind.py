#!/usr/bin/env python3
"""Hot path (move 2): the order_intents.csv audit row is written behind the send (single background writer, flushed on
shutdown and before any read of the file), never inside the order's critical path. The pending_send write-ahead row
(crash / duplicate-send protection) is still written, durably, BEFORE the exchange call and never waits on the shared
audit file lock.

Run (from _archive/hl_stage2):  HL_LIVE_ENV_FILE=/nonexistent python3 test_core_intent_write_behind.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. No network, no orders.
"""
from __future__ import annotations

import csv
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


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="iwb_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})

    def mk_intent(iid="i1", notes="lifecycle=ENTRY;", raw=None):
        fill = c.LeaderFill("f_" + iid, A, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", raw=raw)
        return c.Intent(iid, fill, "BUY", 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
                        "sleeve:%s:BTC" % A, "", "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), notes)

    def disk_rows(path):
        if not path.exists():
            return []
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def hold(lock):
        got, release = threading.Event(), threading.Event()

        def run():
            with lock:
                got.set()
                release.wait(20)
        t = threading.Thread(target=run, daemon=True)
        t.start()
        got.wait(5)
        return release, t

    audit = c.AuditLogWriter()

    # ---- W1: the intent append returns at once while the shared audit lock is held by another thread
    release, holder = hold(c.FILE_LOCK)
    t0 = time.monotonic()
    audit.append_order_intent(mk_intent("i1", raw={"dir": "Open Long"}))
    elapsed = time.monotonic() - t0
    check("W1_APPEND_DOES_NOT_WAIT_ON_SHARED_AUDIT_LOCK", elapsed < 0.5, "append took %.2fs" % elapsed)
    release.set()
    holder.join(5)

    # ---- W2: the row is still written (eventually) with the same content
    flushed = c.flush_intent_writer(10.0)
    rows = [r for r in disk_rows(c.ORDER_INTENTS_CSV) if r.get("intent_id") == "i1"]
    row = rows[0] if rows else {}
    check("W2_ROW_WRITTEN_EVENTUALLY_WITH_IDENTICAL_CONTENT",
          flushed and len(rows) == 1 and row.get("leader_fill_id") == "f_i1" and row.get("leader_wallet") == A
          and row.get("coin") == "BTC" and row.get("copy_side") == "BUY" and row.get("decision") == "ENTRY_ALLOWED"
          and row.get("wallet_mode") == "ON" and row.get("copy_mode") == "fixed" and row.get("sleeve_id") == "sleeve:%s:BTC" % A
          and row.get("notes") == 'lifecycle=ENTRY;;leader_dir_json="Open Long"' and row.get("created_at_ms"),
          str(row))

    # ---- W3: shutdown flush: rows queued while the lock was held are on disk after flush; reads see their own writes
    release, holder = hold(c.FILE_LOCK)
    for n in range(3):
        audit.append_order_intent(mk_intent("q%d" % n))
    release.set()
    holder.join(5)
    seen = {r.get("intent_id") for r in c.read_csv_rows(c.ORDER_INTENTS_CSV)}  # a reader flushes the writer first
    check("W3_READERS_SEE_QUEUED_ROWS_AND_FLUSH_DRAINS", {"q0", "q1", "q2"} <= seen and c.flush_intent_writer(5.0), str(sorted(seen)))
    order = [r.get("intent_id") for r in disk_rows(c.ORDER_INTENTS_CSV) if str(r.get("intent_id")).startswith("q")]
    check("W3B_ROWS_KEEP_THEIR_ORDER", order == ["q0", "q1", "q2"], str(order))

    # ---- W4: an intent that carries merged leader fills (read back at restart for idempotency) is written synchronously
    audit.append_order_intent(mk_intent("m1", notes="lifecycle=ENTRY;merged_leader_fills=2:fa,fb;"))
    check("W4_MERGED_FILLS_INTENT_IS_WRITTEN_BEFORE_RETURN",
          any(r.get("intent_id") == "m1" for r in disk_rows(c.ORDER_INTENTS_CSV)))

    # ---- W5: pending_send is durable BEFORE the exchange call and never waits on the shared audit lock
    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
    seen_pending = []

    class FakeExchange:
        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            seen_pending.append([r for r in disk_rows(c.SEND_ATTEMPTS_CSV) if r.get("status") == "pending_send"])
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}]}}}

    fake = FakeExchange()
    g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "l.json"))
    g._resolve_coin = lambda coin: dict(resolved)
    g._get_exchange_client = lambda *a, **k: fake
    g._exchange_client_has_symbol = lambda *a, **k: True
    g._validate_final_wire_order = lambda *a, **k: (True, {})
    g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    g._exchange_client_for_coin = lambda coin: (fake, "BTC")
    g._pre_send_ownership_gate = lambda it: (True, {})
    g.leader_reduced_since = lambda f: 0
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    saved = c.HLAccount, c.HLExchange
    c.HLAccount, c.HLExchange = object, object
    g.schedule_margin_mode_setup("BTC")  # move 1: the margin-mode audit row is written by the background setup, not the send
    g.wait_margin_mode_setup(5.0)
    release, holder = hold(c.FILE_LOCK)  # the shared audit lock is busy for the whole send
    result = {}
    sender = threading.Thread(target=lambda: result.update(r=g._send_real(mk_intent("s1"))), daemon=True)
    t0 = time.monotonic()
    sender.start()
    sender.join(8)
    send_elapsed = time.monotonic() - t0
    release.set()
    holder.join(5)
    c.HLAccount, c.HLExchange = saved
    os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
    check("W5_SEND_DOES_NOT_BLOCK_ON_HELD_AUDIT_LOCK", not sender.is_alive() and send_elapsed < 5.0
          and result.get("r", (False,))[0] is True, "alive=%s elapsed=%.2f r=%s" % (sender.is_alive(), send_elapsed, result.get("r", ("none",))[:2]))
    check("W5B_PENDING_SEND_ROW_DURABLE_BEFORE_EXCHANGE_CALL",
          bool(seen_pending) and any(r.get("intent_id") == "s1" and r.get("cloid") for r in seen_pending[0]), str(seen_pending))

    # ---- W6: stop() flushes the writer
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    flushes = []
    real_flush = c.flush_intent_writer
    c.flush_intent_writer = lambda timeout=None, *a, **k: flushes.append(timeout) or real_flush(timeout, *a, **k)
    try:
        core.stop()
    finally:
        c.flush_intent_writer = real_flush
    check("W6_STOP_FLUSHES_INTENT_WRITER", len(flushes) >= 1, str(flushes))

    # ---- D: Codex findings -----------------------------------------------------------------------------------------
    class RecExchange:
        def __init__(self):
            self.orders = []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.orders.append(time.monotonic())
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 2}}]}}}

    def gw(fake_ex):
        gg = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%d.json" % id(fake_ex))))
        gg._resolve_coin = lambda coin: dict(resolved)
        gg._get_exchange_client = lambda *a, **k: fake_ex
        gg._exchange_client_has_symbol = lambda *a, **k: True
        gg._validate_final_wire_order = lambda *a, **k: (True, {})
        gg._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gg._exchange_client_for_coin = lambda coin: (fake_ex, "BTC")
        gg._pre_send_ownership_gate = lambda it: (True, {})
        gg.leader_reduced_since = lambda f: 0
        gg._margin_mode_done = {"BTC"}
        return gg

    def pending_rows(iid):
        return [r for r in disk_rows(c.SEND_ATTEMPTS_CSV) if r.get("intent_id") == iid and r.get("status") == "pending_send"]

    def send_in_thread(gg, intent, box):
        def run():
            os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
            try:
                box["r"] = gg._send_real(intent)
            except Exception as exc:  # pragma: no cover
                box["exc"] = exc
        t = threading.Thread(target=run, daemon=True)
        t.start()
        return t

    saved2 = c.HLAccount, c.HLExchange
    c.HLAccount, c.HLExchange = object, object
    try:
        # D1 (a): the pending_send row is NOT written while the order waits for its slot / the 429 cooldown; it is written
        # (synchronously) only once the wait is over, immediately before the exchange call
        ex1 = RecExchange()
        g1 = gw(ex1)
        g1._exchange_rate_limit_cooldown_until_ms = c.utc_now_ms() + 1500
        box1 = {}
        t1 = send_in_thread(g1, mk_intent("d1"), box1)
        time.sleep(0.5)
        during_wait = (len(pending_rows("d1")), len(ex1.orders))
        t1.join(10)
        check("D1_NO_PENDING_ROW_WHILE_WAITING_FOR_SLOT_COOLDOWN",
              during_wait == (0, 0) and len(pending_rows("d1")) == 1 and len(ex1.orders) == 1
              and box1.get("r", (False,))[0] is True, "%s %s %s" % (during_wait, len(pending_rows("d1")), box1.get("r", ("none",))[:2]))
        check("D1B_PENDING_ROW_CARRIES_CLOID", bool(pending_rows("d1")[0].get("cloid"))
             )

        # D2: a failed pending_send write still means NO order (fail closed), whichever thread sleeps first
        ex2 = RecExchange()
        g2 = gw(ex2)
        real_append = g2.audit.append_send_attempt

        def boom(row, durable=False):
            raise OSError("disk full")
        g2.audit.append_send_attempt = boom
        box2 = {}
        send_in_thread(g2, mk_intent("d2"), box2).join(10)
        g2.audit.append_send_attempt = real_append
        r2 = box2.get("r", (True, "none", {}))
        check("D2_PENDING_WRITE_FAILURE_SENDS_NOTHING", r2[0] is False and "AUDIT_WRITE_FAILED" in str(r2[1]) and not ex2.orders
              and r2[2].get("exchange_called") is False, str(r2[:2]))

        # D5 (d): the pending_send append is fsynced (default on, HL_LIVE_PENDING_SEND_FSYNC=0 turns it off); the final send row is not
        real_fsync = os.fsync
        calls = []
        os.fsync = lambda fd: (calls.append(fd), real_fsync(fd))[1]
        try:
            gf = gw(RecExchange())
            gf._begin_pending_send(mk_intent("f1"), "Ioc", "REAL_IOC", 100.0, 1.0, "0x" + "ab" * 16, {})
            on = len(calls)
            del calls[:]
            gf.audit.append_send_attempt({"intent_id": "f1", "status": "ORDER_FILLED"})
            final_row = len(calls)
            del calls[:]
            os.environ["HL_LIVE_PENDING_SEND_FSYNC"] = "0"
            gf._begin_pending_send(mk_intent("f2"), "Ioc", "REAL_IOC", 100.0, 1.0, "0x" + "cd" * 16, {})
            off = len(calls)
        finally:
            os.fsync = real_fsync
            os.environ.pop("HL_LIVE_PENDING_SEND_FSYNC", None)
        check("D5_PENDING_SEND_APPEND_IS_FSYNCED_BY_DEFAULT_AND_SWITCHABLE", on >= 1 and final_row == 0 and off == 0,
              "on=%s final=%s off=%s" % (on, final_row, off))
    finally:
        c.HLAccount, c.HLExchange = saved2
        os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)

    # D3 (b): a flush timeout returns False and is reported loudly (errors.csv + alert counter), never silently
    real_append_csv = c.append_csv
    gate = threading.Event()

    def stuck_append(path, fieldnames, row, *a, **k):
        if path == c.ORDER_INTENTS_CSV:
            gate.wait(30)
        return real_append_csv(path, fieldnames, row, *a, **k)
    c.append_csv = stuck_append
    try:
        before_fail = c.audit_write_failure_count()
        before_to = c.intent_writer_status()["flush_timeouts"]
        audit.append_order_intent(mk_intent("stuck1"))
        audit.append_order_intent(mk_intent("stuck2"))
        time.sleep(0.2)
        ok_flush = c.flush_intent_writer(0.3, "test")
        status = c.intent_writer_status()
        errs = [r for r in disk_rows(c.ERRORS_CSV) if r.get("context") == "intent_flush_timeout"]
        check("D3_FLUSH_TIMEOUT_RETURNS_FALSE_AND_IS_REPORTED",
              ok_flush is False and status["flush_timeouts"] == before_to + 1 and status["queued"] + int(status["busy"]) >= 2
              and len(errs) >= 1 and "context=test" in errs[-1].get("message", "") and c.audit_write_failure_count() > before_fail,
              "%s %s %s" % (ok_flush, status, errs[-1:] if errs else "no error row"))
        # D4 (c): stop() with a stuck writer waits a bounded time and reports the rows still queued
        core2 = c.LiveCopyCore(source_csv=tmp / "none2.csv")
        t0 = time.monotonic()
        core2.stop()
        stop_took = time.monotonic() - t0
        errs2 = [r for r in disk_rows(c.ERRORS_CSV) if r.get("context") == "stop_intent_rows_pending"]
        check("D4_STOP_WITH_STUCK_WRITER_IS_BOUNDED_AND_REPORTS_REMAINING", stop_took < 15.0 and len(errs2) >= 1
              and "queued" in errs2[-1].get("message", ""), "%.2f %s" % (stop_took, errs2[-1:] if errs2 else "no row"))
        check("D4B_ATEXIT_DRAIN_REGISTERED_BOUNDED", c._INTENT_STATE["atexit"] is True)
    finally:
        gate.set()
        c.append_csv = real_append_csv
    check("D3B_WRITER_DRAINS_AFTER_RELEASE", c.flush_intent_writer(10.0) is True)

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
