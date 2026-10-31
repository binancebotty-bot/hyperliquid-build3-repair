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

    def stop_copy_thread(core) -> None:
        """Stop and join the core's copy-poll thread, then drain the async status writers.

        Without this the thread started for the measurement keeps polling into every later phase: it rewrites
        copy_poll_state.json and (through the ServiceStateWriter worker) clean_core_runtime_state.json, so a
        before/after read taken in S1/P1 races a background write and the result depends on timing.
        No Core change: this drives the same stop flag and bounded join that Core.stop() uses."""
        ct = getattr(core, "_copy_thread", None)
        core._hot_stop_event.set()
        if ct is not None and ct.is_alive() and ct is not threading.current_thread():
            ct.join(timeout=30)
        core._copy_thread = None
        # A state write queued by the last cycle runs on a status worker thread; it must land BEFORE the
        # before/after reads, otherwise it is the "copy thread" that appears to change the runtime state.
        # Core's own drain uses a 1 s shared deadline; here the join can afford to be generous.
        for worker in list(c._STATUS_WRITE_WORKERS):
            if not worker.join_until(time.monotonic() + 30):
                raise RuntimeError(f"status writer {worker.name} did not drain before the assertions")

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
            st = c.load_json(c.COPY_POLL_STATE_FILE, {})
            st["copy_poll_stats"] = []
            c.atomic_write_json(c.COPY_POLL_STATE_FILE, st)
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
        stats = c.load_json(c.COPY_POLL_STATE_FILE, {}).get("copy_poll_stats") or []
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
    stats = c.load_json(c.COPY_POLL_STATE_FILE, {}).get("copy_poll_stats") or []
    check("M5_LAG_RECORD_KEPT_FOR_THE_PC", stats and {"http_ms", "lock_wait_ms_max", "fill_to_ledger_lag_ms_max", "window_ms",
                                                      "send_lock_hold_ms_max"} <= set(stats[-1]), str(stats[-1:]))

    # ---- D1: the copy thread owns a fill while the main cycle is stuck -----------------------------------------
    # The integrity rebuild and the state write both run on background writers now, so replacing
    # write_live_integrity_status no longer blocks the CYCLE thread -- that is why this check was red with
    # alive=False. Block a step the cycle thread itself performs (state_writer.submit) instead, so "the main
    # cycle is stuck" is a fact and not a 60 s sleep. Every wait below is bounded.
    stop_copy_thread(new)        # the M measurement's poll thread must not bleed into this phase
    new._hot_stop_event.clear()  # stop_copy_thread sets it; this phase starts a fresh poll thread
    new.start_copy_poll_thread(0.1)
    cycle_at_state_write = threading.Event()
    real_state_write = new.state_writer.write

    def write_then_block(summary, dedupe, cfg=None):
        cycle_at_state_write.set()
        real_state_write(summary, dedupe, cfg)  # blocks on state_writer._worker._lock, held below
    new.state_writer.write = write_then_block
    cycle_block = new.state_writer._worker._lock
    cycle_block.acquire()
    cyc = threading.Thread(target=lambda: new.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False), daemon=True)

    def owned1():
        return str(oid1) in {r.get("exchange_order_id") for r in c.read_csv_rows(c.LIVE_FILLS_CSV)}
    try:
        cyc.start()
        cycle_at_state_write.wait(10)  # bounded: the cycle reached its state write and is now stuck
        oid1, side1 = engine_order()
        land(oid1, side1)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not owned1():
            time.sleep(0.05)
        stuck = cyc.is_alive()
        check("D1_FILL_OWNED_WHILE_THE_MAIN_CYCLE_IS_STUCK",
              cycle_at_state_write.is_set() and stuck and owned1())
        print("D1DEBUG blocked=%s alive=%s owned=%s" % (cycle_at_state_write.is_set(), stuck, owned1()))
    finally:
        cycle_block.release()
        cyc.join(30)
        new.state_writer.write = real_state_write
    stop_copy_thread(new)  # S1/P1 read the state files: no background writer may be alive for them

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
    # W1 asserts the LOOKBACK THE CODE DERIVES, not a ceiling on a wall-clock measurement. The old form was
    #   max(s['window_ms'] for s in hot) <= COPY_POLL_HOT_OVERLAP_MS + 5000
    # which went red on a loaded machine at [22350, 37210] vs 25000. window_ms is poll_end_ms - start_ms, i.e.
    # (the overlap) + (how long after the previous read this one actually ran), so its size is scheduling delay,
    # not a lookback error: 22350 = 20000 + 2.35 s, 37210 = 20000 + 17.2 s of thread starvation. Nothing the
    # code computed was wrong, so no thread fix can make that ceiling green on a busy box. Replaced by an exact
    # probe: pin the stored cursor to a known value, read, and require start_ms == cursor - overlap for the hot
    # read and cursor - POLL_OVERLAP_MS for the sweep.
    hot = [s for s in stats if s.get('hot') and not s.get('sweep')]
    sweeps = [s for s in stats if s.get('sweep')]
    probe_starts = []

    class ProbeIngestor:
        def poll_copy_account_fills(self, user_wallet, start_ms, end_ms=None, **_k):
            probe_starts.append(start_ms)
            return [], 'COPY_ACCOUNT_POLLED'

    real_ing_w = new.copy_ingestor
    new.copy_ingestor = ProbeIngestor()
    probe_cursor = c.utc_now_ms() - 60000  # a fixed, known cursor: the read start is this minus the overlap

    def probe(force_sweep):
        with c.RUNTIME_STATE_LOCK:
            st = c.load_json(c.COPY_POLL_STATE_FILE, {})
            st['last_copy_poll_ms'] = probe_cursor
            c.atomic_write_json(c.COPY_POLL_STATE_FILE, st)
        new._last_copy_sweep = 0.0 if force_sweep else time.monotonic()
        probe_starts.clear()
        new.copy_poll_once(hot=True)
        last = (c.load_json(c.COPY_POLL_STATE_FILE, {}).get('copy_poll_stats') or [{}])[-1]
        return (probe_starts[-1] if probe_starts else None), last

    start_hot, st_hot = probe(False)
    start_sweep, st_sweep = probe(True)
    new._last_copy_sweep = time.monotonic()
    new.copy_ingestor = real_ing_w
    check('W1_HOT_READ_GOES_BACK_ABOUT_20S',
          start_hot == probe_cursor - c.COPY_POLL_HOT_OVERLAP_MS
          and start_sweep == probe_cursor - c.POLL_OVERLAP_MS
          and st_hot.get('hot') is True and st_hot.get('sweep') is False
          and st_sweep.get('sweep') is True
          and c.COPY_POLL_HOT_OVERLAP_MS <= st_hot.get('window_ms', -1) < c.POLL_OVERLAP_MS,
          'hot_start=%s want=%s sweep_start=%s want=%s hot_flags=%s sweep_flags=%s' % (
              start_hot, probe_cursor - c.COPY_POLL_HOT_OVERLAP_MS, start_sweep,
              probe_cursor - c.POLL_OVERLAP_MS, (st_hot.get('hot'), st_hot.get('sweep')),
              (st_sweep.get('hot'), st_sweep.get('sweep'))))
    # the M-run's own recorded hot windows: at least the 20 s lookback, never a full 5-minute sweep. A range,
    # not a fixed ceiling -- load stretches the top without the lookback changing.
    hot_wins = [s['window_ms'] for s in hot]
    check('W1B_RECORDED_HOT_WINDOWS_STAY_UNDER_A_SWEEP',
          bool(hot_wins) and all(c.COPY_POLL_HOT_OVERLAP_MS <= w < c.POLL_OVERLAP_MS for w in hot_wins),
          str(hot_wins[:5]))
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
    newest = c.copy_cursor_ms() - c.COPY_POLL_HOT_OVERLAP_MS

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
    # The copy-poll thread is stopped and joined above, and the read/modify/read runs under RUNTIME_STATE_LOCK,
    # so no other writer can land between the two reads. write_startup is the SYNCHRONOUS writer: submit() would
    # queue the write on a worker and it would land after the reads, racing them by construction.
    with c.RUNTIME_STATE_LOCK:
        before = c.load_json(c.COPY_POLL_STATE_FILE, {})
        new.state_writer.write_startup(c.CycleSummary(), new.dedupe, new.cfg)
        after = c.load_json(c.COPY_POLL_STATE_FILE, {})
        rt_s1 = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    check("S1_CYCLE_STATE_WRITE_KEEPS_COPY_CURSOR_AND_LAG_RECORD",
          after == before and rt_s1.get("last_copy_poll_ms") == before.get("last_copy_poll_ms"),
          "copy_poll_state_same=%s runtime_last_copy_poll_ms=%r expected=%r"
          % (after == before, rt_s1.get("last_copy_poll_ms"), before.get("last_copy_poll_ms")))
    # P: the copy thread never rewrites the (multi-MB on the PC) runtime state; each poll names its slowest sections.
    # Compare CONTENT, not st_mtime_ns: atomic_write_json replaces the file, so mtime is not a content witness.
    with c.RUNTIME_STATE_LOCK:
        rt_before = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    oid2, side2 = engine_order()
    land(oid2, side2)
    # Snapshot the profiler counters at the instant prof_take() runs, so P2 can check the sample against the raw
    # numbers instead of against its own idea of which section ought to be slowest.
    raw_sections = []
    real_prof_take = c.prof_take

    def spy_prof_take(top: int = 8):
        with c._PROF_LOCK:
            raw_sections.append([(k, int(v[0]), float(v[1]), float(v[2])) for k, v in c._PROF.items()])
        return real_prof_take(top)

    c.prof_take = spy_prof_take
    try:
        st2 = new.copy_poll_once(hot=True)
    finally:
        c.prof_take = real_prof_take
    with c.RUNTIME_STATE_LOCK:
        rt_after = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    check("P1_HOT_POLL_LEAVES_THE_RUNTIME_STATE_ALONE", rt_after == rt_before and isinstance(st2.get("at_ms"), int),
          "runtime_state_changed=%s poll_at_ms=%r" % (rt_after != rt_before, st2.get("at_ms")))
    # P2: the poll reports the sections it profiled -- a NON-EMPTY sample, every row reproducing its own counters.
    # It deliberately does NOT assert WHICH section is slowest: prof_take ranks BY MEASURED max_ms, so on a loaded
    # box "replace:copy_poll_state.json" (14 ms) and "copy_state_write" (14-30 ms) trade places run to run. That is
    # load-dependent by construction -- no thread fix can make a measured ordering deterministic. What is asserted:
    # the reported list is exactly the top-8 of the counters at take time (the ranking RULE, not its outcome), each
    # row is the counter triple for that section (n >= 1, total_ms >= max_ms >= 0), and the two sections this poll
    # must profile are present in the counters.
    slow = st2.get("slowest_sections")
    raw = raw_sections[-1] if raw_sections else []
    raw_by = {k: (n, int(tot), int(mx)) for k, n, tot, mx in raw}
    expected_order = [k for k, _n, _tot, _mx in sorted(raw, key=lambda r: -r[3])][:8]
    check("P2_POLL_REPORTS_THE_SECTIONS_IT_PROFILED",
          isinstance(slow, list) and len(slow) > 0
          and all(isinstance(s, dict) and set(s) == {"section", "n", "total_ms", "max_ms"} for s in slow)
          and [s["section"] for s in slow] == expected_order
          and all(isinstance(s["n"], int) and isinstance(s["total_ms"], int) and isinstance(s["max_ms"], int)
                  for s in slow)
          and all(s["n"] >= 1 and 0 <= s["max_ms"] <= s["total_ms"] for s in slow)
          and all(raw_by.get(s["section"]) == (s["n"], s["total_ms"], s["max_ms"]) for s in slow)
          and "copy_state_write" in raw_by and "send_lock:copy_fill_apply" in raw_by,
          "reported=%s expected=%s raw=%s" % (slow, expected_order, raw))
    # P3: parsing a big audit CSV does not hold the file lock (every append on the send path waits for it)
    held = []
    real_reader = c.csv.DictReader

    def spy_reader(*a, **k):
        held.append(c.FILE_LOCK._is_owned())
        return real_reader(*a, **k)
    c.csv.DictReader = spy_reader
    c.read_csv_rows(c.LIVE_FILLS_CSV)
    c.csv.DictReader = real_reader
    check("P3_CSV_PARSE_OUTSIDE_THE_FILE_LOCK", held == [False], str(held))
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
