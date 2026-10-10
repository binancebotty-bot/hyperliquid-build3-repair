#!/usr/bin/env python3
"""Run 5 (2026-10-10): the engine's own fills reach the ledger within seconds under load.

Run 5 on the PC: under load live_fills stood still for ~60 s while fills landed, and the fill-to-ledger lag reached
~90 s. Cause: the copy poll ran inside the main cycle, behind the leader polls, the integrity rebuild (it re-reads the
growing audit CSVs) and the state write, then waited for the send lock for its whole batch; each read also re-fetched
the last 5 minutes of fills. Now in loop mode the copy poll has its own thread (every 1 s), reads back 20 s (the full
5 minutes once a minute), and takes the send lock per fill.

M  measurement under simulated load (20 engine fills/s, 150 ms exchange reads, send workers holding the send lock,
   a main cycle taking 3 s): the old in-cycle poll vs the copy thread, fill-to-ledger lag printed for both.
G  a fill whose order is not in the send history yet is left for the next read (not consumed unmatched), then owned
   by order id once the send row exists.
W  the hot read goes back 20 s; the full 5-minute read happens once a sweep interval.
S  the cycle's state write keeps the copy thread's cursor and lag record; the de-dup sets can be exported while the
   copy thread adds to them.

Run: python test_core_fill_lag.py   # RESULT:: markers, exit 0/1. No network, no orders.
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
FOLLOWER = "0x" + "c" * 40
A = "0x" + "a" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="filllag_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_SNAPSHOT_REFRESH_INTERVAL_SEC": "100000"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
        A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    slow_cycle = {"sec": 0.0}
    real_integrity = c.write_live_integrity_status

    def heavy_integrity(*a, **k):  # the run-5 cycle: integrity rebuild over large audit CSVs
        time.sleep(slow_cycle["sec"])
        return real_integrity(*a, **k)
    c.write_live_integrity_status = heavy_integrity

    exchange_fills = []
    ex_lock = threading.Lock()
    reads = []

    class FakeCopyIngestor:
        def poll_copy_account_fills(self, user_wallet, start_ms, end_ms=None, **_k):
            time.sleep(0.15)  # one exchange read
            reads.append((start_ms, end_ms))
            with ex_lock:
                rows = [dict(f) for f in exchange_fills if start_ms <= f["time"] <= (end_ms or c.utc_now_ms())]
            for r in rows:
                r["timestamp_ms"] = r["time"]
                r["copy_fill_id"] = f"{r['hash']}:{r['tid']}"
            return rows, "COPY_ACCOUNT_POLLED"

    seq = [0]

    def engine_order(record_send=True):
        seq[0] += 1
        oid = 100000 + seq[0]
        if record_send:
            c.AuditLogWriter().append_send_attempt({
                "created_at_ms": c.utc_now_ms(), "intent_id": f"i{seq[0]}", "leader_fill_id": f"lf{seq[0]}",
                "leader_wallet": A, "coin": "BTC", "side": "BUY" if seq[0] % 2 else "SELL", "copy_size": 0.001,
                "limit_price": 100.0, "status": "ORDER_FILLED", "exchange_order_id": str(oid),
                "terminal_state": "FILLED_AWAITING_COPY_POLL", "notes": "lifecycle=ENTRY"})
        return oid, ("B" if seq[0] % 2 else "A")

    def land(oid, side):
        with ex_lock:
            exchange_fills.append({"coin": "BTC", "side": side, "sz": "0.001", "px": "100", "oid": oid,
                                   "hash": f"0xh{oid}", "tid": oid, "time": c.utc_now_ms(), "fee": "0", "closedPnl": "0"})

    def new_core():
        core = c.LiveCopyCore(source_csv=tmp / "none.csv")
        core.copy_ingestor = FakeCopyIngestor()
        core.dedupe.copy_account_baseline_set = True
        return core

    def load_run(core, use_thread: bool, seconds: float = 8.0, rate: float = 20.0):
        """Fills land at `rate`/s; send workers hold the send lock 50 ms of every 60 ms; the main cycle takes 3 s."""
        stop = threading.Event()
        landed = []

        def sender():
            while not stop.is_set():
                with core._send_lock:
                    time.sleep(0.05)
                time.sleep(0.01)

        def producer():
            while not stop.is_set():
                oid, side = engine_order()
                land(oid, side)
                landed.append(oid)
                time.sleep(1.0 / rate)

        def main_loop():
            nxt = 0.0
            while not stop.is_set():
                if use_thread:
                    core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False)
                elif time.monotonic() >= nxt:
                    core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=True)
                    nxt = time.monotonic() + 1.0
                time.sleep(0.05)
        with c.RUNTIME_STATE_LOCK:  # this run's lag record only
            st = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
            st["copy_poll_stats"] = []
            c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, st)
        threads = [threading.Thread(target=t, daemon=True) for t in (sender, producer, main_loop)]
        slow_cycle["sec"] = 3.0
        if use_thread:
            core.start_copy_poll_thread(2.0)  # the production default
        for t in threads:
            t.start()
        time.sleep(seconds)
        stop.set()
        for t in threads:
            t.join(timeout=10)
        slow_cycle["sec"] = 0.0
        deadline = time.monotonic() + 60  # wait for the last fills to be owned (no timing threshold: a slow PC passes)
        while time.monotonic() < deadline:
            owned_now = {r.get("exchange_order_id") for r in c.read_csv_rows(c.LIVE_FILLS_CSV)}
            if all(str(o) in owned_now for o in landed):
                break
            if not use_thread:
                core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=True)
            time.sleep(0.5)
        stats = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("copy_poll_stats") or []
        lags = [s.get("fill_to_ledger_lag_ms_max") for s in stats if s.get("fill_to_ledger_lag_ms_max") is not None]
        meds = [s.get("fill_to_ledger_lag_ms_median") for s in stats if s.get("fill_to_ledger_lag_ms_median") is not None]
        owned = {r.get("exchange_order_id") for r in c.read_csv_rows(c.LIVE_FILLS_CSV)}
        return landed, lags, meds, owned

    # ---- M: old in-cycle poll vs the copy thread ------------------------------------------------------------
    old = new_core()
    landed_old, lags_old, _m, owned_old = load_run(old, use_thread=False)
    old.stop()
    worst_old = max(lags_old) if lags_old else None
    new = new_core()
    landed_new, lags_new, meds_new, owned_new = load_run(new, use_thread=True)
    worst_new = max(lags_new) if lags_new else None
    med_new = sorted(meds_new)[len(meds_new) // 2] if meds_new else None
    print(f"MEASURE:: old in-cycle poll: worst fill-to-ledger lag {worst_old} ms over {len(landed_old)} fills")
    print(f"MEASURE:: copy thread: worst {worst_new} ms, median of poll medians {med_new} ms over {len(landed_new)} fills")
    check("M1_COPY_THREAD_OWNS_EVERY_FILL", all(str(o) in owned_new for o in landed_new),
          f"{sum(str(o) not in owned_new for o in landed_new)} missing")
    # the lag figures above are a measurement (printed), not a pass/fail threshold: they depend on the machine.
    # What the fix guarantees is checked deterministically below (D1, D2).
    check("M1_OLD_IN_CYCLE_POLL_OWNS_EVERY_FILL_TOO", all(str(o) in owned_old for o in landed_old))
    stats = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("copy_poll_stats") or []
    check("M5_LAG_RECORD_KEPT_FOR_THE_PC", stats and {"http_ms", "lock_wait_ms_max", "fill_to_ledger_lag_ms_max", "window_ms",
                                                      "send_lock_hold_ms_max"} <= set(stats[-1]), str(stats[-1:]))

    # ---- D1: the copy thread owns a fill while the main cycle is stuck -----------------------------------------
    gate = threading.Event()
    blocked = threading.Event()

    def stuck_integrity(*a, **k):
        blocked.set()
        gate.wait(60)
    c.write_live_integrity_status = stuck_integrity
    cyc = threading.Thread(target=lambda: new.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False), daemon=True)
    cyc.start()
    blocked.wait(30)
    oid1, side1 = engine_order()
    land(oid1, side1)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and str(oid1) not in {r.get("exchange_order_id") for r in c.read_csv_rows(c.LIVE_FILLS_CSV)}:
        time.sleep(0.1)
    check("D1_FILL_OWNED_WHILE_THE_MAIN_CYCLE_IS_STUCK", blocked.is_set() and cyc.is_alive()
          and str(oid1) in {r.get("exchange_order_id") for r in c.read_csv_rows(c.LIVE_FILLS_CSV)})
    gate.set()
    cyc.join(30)
    c.write_live_integrity_status = heavy_integrity

    # ---- D2: no exchange read while a send worker holds the send lock ---------------------------------------------
    under_lock = []

    def mids(p):
        under_lock.append(("mids", new._send_lock.held_by_me()))
        return [] if p.get("type") == "perpDexs" else {"BTC": "100"}

    def positions(p):
        under_lock.append(("positions", new._send_lock.held_by_me()))
        if p.get("type") != "clearinghouseState":
            return []
        return {"assetPositions": [], "marginSummary": {"accountValue": "1000"}}
    c.MIDS_FETCHER, c.EXPOSURE_FETCHER = mids, positions
    c._FOLLOWER_MIDS.update(px={}, ms=0)
    new.intent_builder._exposure, new.intent_builder._exposure_prefetched = None, None
    for i in range(3):
        lf = c.LeaderFill(f"lag-d2-{i}", A, "BTC", "BUY", 100.0, 0.5, c.utc_now_ms(), "TEST", 0, {})
        new._process_leader_fill(lf, c.CycleSummary(), "")
    check("D2_EXCHANGE_READS_HAPPEN_BEFORE_THE_SEND_LOCK", under_lock and not any(held for _n, held in under_lock),
          str(under_lock))


    # ---- W: hot window 20 s, full sweep once a minute --------------------------------------------------------
    hot = [s for s in stats if s.get("hot") and not s.get("sweep")]
    sweeps = [s for s in stats if s.get("sweep")]
    check("W1_HOT_READ_GOES_BACK_ABOUT_20S", hot and max(s["window_ms"] for s in hot) <= c.COPY_POLL_HOT_OVERLAP_MS + 5000,
          str([s["window_ms"] for s in hot][:5]))
    check("W2_FIRST_READ_IS_A_FULL_SWEEP", sweeps and sweeps[0]["window_ms"] >= c.POLL_OVERLAP_MS, str(sweeps[:1]))

    # ---- W3: a page-capped read resumes at its newest fill, so the next hot read misses nothing ---------------
    real_ing = new.copy_ingestor

    class CappedIngestor:
        def poll_copy_account_fills(self, user_wallet, start_ms, end_ms=None, **_k):
            return [{"coin": "BTC", "side": "B", "sz": "0.001", "px": "100", "oid": 1, "hash": "0xcap", "tid": 1,
                     "time": start_ms + 1000, "timestamp_ms": start_ms + 1000, "copy_fill_id": "0xcap:1"}], "COPY_ACCOUNT_POLL_PARTIAL"
    new.copy_ingestor = CappedIngestor()
    seen_starts = []
    capped = new.copy_poll_once(hot=True)
    newest = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("last_copy_poll_ms") - c.COPY_POLL_HOT_OVERLAP_MS

    class Spy:
        def poll_copy_account_fills(self, user_wallet, start_ms, end_ms=None, **_k):
            seen_starts.append(start_ms)
            return [], "COPY_ACCOUNT_POLLED"
    new.copy_ingestor = Spy()
    new.copy_poll_once(hot=True)
    check("W3_PAGE_CAPPED_READ_RESUMES_AT_ITS_NEWEST_FILL", seen_starts and seen_starts[0] <= newest, f"{seen_starts} {newest} {capped}")
    new.copy_ingestor = real_ing

    # ---- G: a fill whose send row is not written yet waits for it ----------------------------------------------
    oid, side = engine_order(record_send=False)
    land(oid, side)
    r1 = new.copy_poll_once(hot=True)
    check("G1_UNKNOWN_ORDER_FILL_LEFT_FOR_THE_NEXT_READ", r1.get("deferred") == 1
          and str(oid) not in {x.get("exchange_order_id") for x in c.read_csv_rows(c.LIVE_FILLS_CSV)}, str(r1))
    c.AuditLogWriter().append_send_attempt({
        "created_at_ms": c.utc_now_ms(), "intent_id": f"i{seq[0]}", "leader_fill_id": f"lf{seq[0]}", "leader_wallet": A,
        "coin": "BTC", "side": "BUY" if side == "B" else "SELL", "copy_size": 0.001, "limit_price": 100.0,
        "status": "ORDER_FILLED", "exchange_order_id": str(oid), "terminal_state": "FILLED_AWAITING_COPY_POLL",
        "notes": "lifecycle=ENTRY"})
    new.copy_poll_once(hot=True)
    check("G2_OWNED_BY_ORDER_ID_ONCE_THE_SEND_ROW_EXISTS",
          str(oid) in {x.get("exchange_order_id") for x in c.read_csv_rows(c.LIVE_FILLS_CSV)})
    new.stop()

    # ---- S: state write keeps the copy thread's fields; export while adding is safe -----------------------------
    before = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    new.state_writer.write(c.CycleSummary(), new.dedupe, new.cfg)
    after = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    check("S1_CYCLE_STATE_WRITE_KEEPS_COPY_CURSOR_AND_LAG_RECORD",
          after.get("last_copy_poll_ms") == before.get("last_copy_poll_ms") and after.get("copy_poll_stats") == before.get("copy_poll_stats"))
    d = c.DedupeStore({})
    errors = []

    def adder():
        for i in range(200000):
            d.accept_copy(f"x{i}")

    t = threading.Thread(target=adder)
    t.start()
    try:
        while t.is_alive():
            d.export()
    except Exception as exc:  # "set changed size during iteration" before the lock
        errors.append(repr(exc))
    t.join()
    check("S2_EXPORT_WHILE_COPY_THREAD_ADDS_IS_SAFE", not errors, str(errors[:1]))

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
