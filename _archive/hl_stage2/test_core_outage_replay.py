#!/usr/bin/env python3
"""E3 outage replay against the engine (offline).

The engine already has these seams, so this is a deterministic offline replay, not a re-implementation:

* network: MIDS_FETCHER / LEADER_MIDS_FETCHER / EXPOSURE_FETCHER / LEADER_FETCHER are stubbed and the
  module's ``requests`` is made to raise, so no socket can open.
* exchange: the engine's own mock sender (``HL_LIVE_MOCK_SEND=1`` -> SenderGateway._append_mock_attempt)
  answers every order; the pre-send ownership gate (a live exchange read) is stubbed to allow, exactly as
  the other test_core_*.py files do.
* cutover: ``clean_core_runtime_state.json`` is seeded with ``live_start_ms=1`` (the engine's own test
  seam, used by its self-tests) so the 0-120 s old replay fills are post-cutover and are actually copied.

Replay: 300 leader fills over 20 coins, timestamps 0-120 s old, alternating BUY "Open Long" / SELL
"Close Long" (so consecutive same-coin fills never merge: every fill keeps its own copy). A few coins start
with an owned sleeve, so their "Close Long" fills are real reduce-only exits rather than no-sleeve skips.

Assertions (the task's four):
  1. every fill ends in EXACTLY ONE terminal row: a send_attempt (sent/resting) or a reconciliation row
     carrying a terminal_state (skipped with reason) -- and never two, never zero;
  2. none is processed twice when the same fills are offered again (poll re-read): no second send, no new
     terminal row, and a fill still waiting is never queued twice;
  3. the saved leader cursor (leader_cursor_next) never passes an unprocessed fill, checked while fills are
     still queued;
  4. total wall time reported.

Run (from _archive/hl_stage2):
    HL_LIVE_ENV_FILE=/nonexistent python -u test_core_outage_replay.py

Prints RESULT:: lines and TOTAL=/FAILED=, exit 0/1. No network, no orders, no key. If it fails it reports
the failing fills; it never weakens the assertions to pass.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "a" * 40
N_FILLS = max(2, int(os.getenv("HL_E3_FILLS", "300")))
N_COINS = 20
AGE_MIN_MS, AGE_MAX_MS = 400, 120000          # fills are 0-120 s old
SEEDED_COINS = 5                              # first N coins own a sleeve: their closes are real exits
SEED_SIZE = 5.0
STEP = 25                                     # fills pulled per lane per drain step


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="e3replay_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "testnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
        "HL_LIVE_WS_ENABLED": "0",
        "HL_LIVE_MOCK_SEND": "1",
        "HL_LIVE_HOT_SEND_WORKERS": "4",
        "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
        "HL_LIVE_PREWARM_SYMBOL_META": "0",
        "HL_LIVE_PREWARM_SDK_CLIENT": "0",
    })
    os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"   # never read a real .env / key

    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*_a, **_k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    requests.get = offline
    c.requests.post = offline

    c.USER_WALLET = FOLLOWER
    coins = [f"BN{i:02d}" for i in range(N_COINS)]
    px = {name: 100.0 for name in coins}
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {k: str(v) for k, v in px.items()}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    exposure = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}
    c.EXPOSURE_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(exposure)
    c.LEADER_FETCHER = c.EXPOSURE_FETCHER

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": {"min_notional": 1, "max_order_notional_usd": 100000},
        "wallets": {LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}},
    })
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, {"live_start_ms": 1})

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.sender._pre_send_ownership_gate = lambda intent: (True, {})   # live exchange read, stubbed
    # take the hot workers out of the loop so this test drives _plan_batch/_run_plan deterministically
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    core._hot_stop_event.clear()   # the workers have returned; _run_plan's lane loop needs this clear

    for coin in coins[:SEEDED_COINS]:   # these coins own a sleeve: the leader's close is a real exit
        core.ledger.sleeve(LEADER, coin)["signed_size"] = SEED_SIZE
    core.ledger._recompute_net(core.ledger.data)

    now = c.utc_now_ms()
    span = max(1, AGE_MAX_MS - AGE_MIN_MS)
    fills = []
    for i in range(N_FILLS):
        coin = coins[i % N_COINS]
        # a distinct direction tag per fill keeps consecutive same-coin entries from merging (mergeable_fills
        # requires the same dir), so every replay fill keeps its own copy and its own terminal row.
        side = "BUY" if (i // N_COINS) % 2 == 0 else "SELL"
        d = f"Open Long {i}" if side == "BUY" else f"Close Long {i}"
        ts = now - AGE_MAX_MS + int(span * i / max(1, N_FILLS - 1))
        fills.append(c.LeaderFill(f"E3-{i:03d}", LEADER, coin, side, 100.0, 0.1, ts, "POLL", 0,
                                  {"oid": str(1000 + i), "dir": d}))
    by_id = {f.leader_fill_id: f for f in fills}
    check("REPLAY_FILLS_ARE_0_TO_120S_OLD",
          min(f.timestamp_ms for f in fills) >= now - AGE_MAX_MS
          and max(f.timestamp_ms for f in fills) <= now - AGE_MIN_MS)
    check("REPLAY_HAS_BOTH_OPEN_AND_CLOSE_FILLS",
          any(f.raw["dir"].startswith("Open Long") for f in fills)
          and any(f.raw["dir"].startswith("Close Long") for f in fills))

    # ---- replay: dispatch the burst into the real hot queues ------------------------------------------------
    for f in fills:
        core._dispatch_fill(f)
    check("ALL_FILLS_QUEUED_ONCE", core.hot_backlog() == N_FILLS, str(core.hot_backlog()))
    for f in fills:                      # the backstop poll re-reads the same fills while they still wait
        core._dispatch_fill(f)
    check("WAITING_FILL_NEVER_QUEUED_TWICE", core.hot_backlog() == N_FILLS, str(core.hot_backlog()))

    # ---- cursor: with everything still queued it may not pass the oldest unprocessed fill --------------------
    def remaining_min_ts():
        lo = None
        for q in list(core._hot_queues) + list(core._prio_queues):
            held = []
            while True:
                try:
                    held.append(q.get_nowait())
                except Exception:
                    break
            for f in held:
                lo = f.timestamp_ms if lo is None else min(lo, f.timestamp_ms)
            for f in held:
                q.put_nowait(f)
        return lo

    cur = core.leader_cursor_next(LEADER, now)
    rmin = remaining_min_ts()
    check("CURSOR_HELD_AT_OLDEST_UNPROCESSED_FILL_WHILE_ALL_QUEUED", rmin is not None and cur <= rmin,
          f"cursor={cur} oldest_unprocessed={rmin}")

    # ---- drain: pull each lane's closes (priority) then its entries, checking the cursor after every step ---
    t0 = time.perf_counter()
    cursor_ok = {"n": 0, "bad": None}
    while core.hot_backlog() > 0:
        for idx in range(len(core._hot_queues)):
            for q in (core._prio_queues[idx], core._hot_queues[idx]):
                batch = []
                while len(batch) < STEP:
                    try:
                        batch.append(q.get_nowait())
                    except Exception:
                        break
                if not batch:
                    continue
                plan = core._plan_batch(batch)
                core._run_plan(idx, plan)
                core._release_queued(batch, q)
                rmin = remaining_min_ts()
                cur = core.leader_cursor_next(LEADER, now)
                if rmin is not None and cur > rmin:
                    cursor_ok["bad"] = f"cursor={cur} oldest_unprocessed={rmin}"
                cursor_ok["n"] += 1
    drain_s = time.perf_counter() - t0
    check("ENGINE_QUEUES_EMPTY_AFTER_DRAIN", core.hot_backlog() == 0, str(core.hot_backlog()))
    check("CURSOR_NEVER_PASSED_AN_UNPROCESSED_FILL", cursor_ok["bad"] is None,
          f"{cursor_ok['bad']} (checked {cursor_ok['n']} times)")
    check("CURSOR_FREED_TO_PROPOSAL_ONCE_ALL_HANDLED", core.leader_cursor_next(LEADER, now) == now,
          str(core.leader_cursor_next(LEADER, now)))
    check("EVERY_FILL_MARKED_HANDLED", all(f.leader_fill_id in core._idem_accepted for f in fills))

    # ---- terminal rows: one and only one per fill -----------------------------------------------------------
    def journal():
        per = defaultdict(list)
        sa = c.read_csv_rows(c.SEND_ATTEMPTS_CSV)
        rec = c.read_csv_rows(c.RECONCILIATION_CSV)
        for r in sa:
            fid = str(r.get("leader_fill_id") or "").strip()
            if fid:
                status = str(r.get("status") or "")
                kind = "diff/resting" if status == "ORDER_RESTING" else "sent"
                per[fid].append((kind, status, str(r.get("terminal_state") or "")))
        for r in rec:
            fid = str(r.get("leader_fill_id") or "").strip()
            state = str(r.get("terminal_state") or "").strip()
            if fid and state:                       # a terminal reconciliation row, not a warning
                kind = "diff/resting" if "DIFF" in str(r.get("event") or "").upper() else "skipped"
                per[fid].append((kind, str(r.get("status") or ""), state))
        return per, len(sa), len(rec)

    per, sa_n, rec_n = journal()
    counts = Counter(len(v) for v in per.values())
    missing = [fid for fid in by_id if len(per.get(fid, [])) != 1]
    check("EVERY_FILL_ENDS_IN_EXACTLY_ONE_TERMINAL_ROW", not missing and len(per) == N_FILLS,
          f"terminal-per-fill histogram={dict(counts)} fills_with_wrong_count={missing[:8]} (of {len(missing)})")
    kinds = Counter(k for v in per.values() for (k, _s, _t) in v)
    check("REPLAY_PRODUCED_SENT_AND_SKIPPED_TERMINALS", kinds.get("sent", 0) > 0 and kinds.get("skipped", 0) > 0,
          str(dict(kinds)))
    # no fill may carry two outcomes (e.g. both a send_attempt and a terminal reconciliation)
    check("NO_FILL_TERMINALISED_TWICE", not [fid for fid, v in per.items() if len(v) > 1])

    # ---- re-read after processing: nothing is processed a second time ---------------------------------------
    for f in fills:
        assert core._dispatch_fill(f) is True, f  # already handled -> accepted without queueing
    check("RE_OFFERED_FILLS_ARE_NOT_REQUEUED", core.hot_backlog() == 0, str(core.hot_backlog()))
    check("RE_OFFERED_FILLS_PLAN_TO_NOTHING", core._plan_batch(list(fills)) == [])
    per2, sa_n2, rec_n2 = journal()
    check("RE_READ_ADDED_NO_SECOND_SEND", sa_n2 == sa_n, f"send_attempts {sa_n}->{sa_n2}")
    check("RE_READ_LEFT_EVERY_TERMINAL_ROW_AT_ONE",
          len(per2) == len(per) and all(len(v) == 1 for v in per2.values()),
          str(Counter(len(v) for v in per2.values())))
    check("RE_READ_ADDED_NO_TERMINAL_ROW", rec_n2 == rec_n,
          f"reconciliation {rec_n}->{rec_n2}")

    total_s = time.perf_counter() - t0
    print("MEASURE:: replay=%d fills over %d coins, workers=%d, drain=%.3fs, total_wall=%.3fs"
          % (N_FILLS, N_COINS, core.hot_send_workers, drain_s, total_s))
    print("MEASURE:: terminals=%s (send_attempts=%d reconciliation=%d)"
          % (dict(kinds), sa_n, rec_n))
    core.stop()

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
