#!/usr/bin/env python3
"""R1 outage-replay durability: the saved leader cursor never moves past a fill that is only in memory.

Test (1) a queued fill holds the cursor at its time; (2) it moves on once the fill is handled
Test (3) another leader's cursor is not held; (4) with nothing pending the cursor moves to the proposal
Test (5) a full-queue rejection leaves nothing pending
Test (6) simulated crash: cursor persisted at poll time is <= every unprocessed fill's time, so a restarted poll re-reads them

Run: python test_core_r1_cursor.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import queue
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40
B = "0x" + "b" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="r1cur_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_HOT_SEND_WORKERS": "2"})
    import HL_Live_Copy_Service_Core as c
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
        A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    core._hot_stop_event.clear()
    core.async_dispatch = True

    now = c.utc_now_ms()
    f1 = c.LeaderFill("r1a", A, "BTC", "BUY", 100.0, 1.0, now - 60000, "TEST", 0, {"oid": "1", "dir": "Open Long"})
    f2 = c.LeaderFill("r1b", A, "ETH", "BUY", 100.0, 1.0, now - 30000, "TEST", 0, {"oid": "2", "dir": "Open Long"})
    check("nothing_pending_cursor_moves", core.leader_cursor_next(A, now) == now)
    core._dispatch_fill(f1)
    core._dispatch_fill(f2)
    check("queued_fill_holds_cursor", core.leader_cursor_next(A, now) == now - 60000, str(core.leader_cursor_next(A, now)))
    check("other_leader_not_held", core.leader_cursor_next(B, now) == now)

    # a crash right now: the cursor that would be saved is not past any unprocessed fill
    saved = core.leader_cursor_next(A, now)
    check("crash_replay_rereads_all_unprocessed", all(f.timestamp_ms >= saved for f in (f1, f2)))

    # worker handles f1 only
    for q in core._hot_queues:
        got = []
        while not q.empty():
            got.append(q.get_nowait())
        for g in got:
            if g.leader_fill_id == "r1a":
                core._release_queued([g], q)
            else:
                q.put_nowait(g)
    check("cursor_advances_to_next_oldest", core.leader_cursor_next(A, now) == now - 30000, str(core.leader_cursor_next(A, now)))
    for q in core._hot_queues:
        got = []
        while not q.empty():
            got.append(q.get_nowait())
        if got:
            core._release_queued(got, q)
    check("handled_cursor_moves_on", core.leader_cursor_next(A, now) == now)

    for q in core._hot_queues:
        q.maxsize = 1
        try:
            q.put_nowait(f1)
        except queue.Full:
            pass
    f3 = c.LeaderFill("r1c", A, "SOL", "BUY", 100.0, 1.0, now - 5000, "TEST", 0, {"oid": "3", "dir": "Open Long"})
    ok = core._dispatch_fill(f3)
    check("full_queue_leaves_nothing_pending", ok is False and core.leader_cursor_next(A, now) == now, str(core._pending_ts))

    # A poll result is not protected by the cursor floor until it has been dispatched.
    poll_fill = [None]
    poll_starts = []
    core.sender.refresh_asset_universe = lambda: None
    core.sender.prune_standing_closes = lambda: None
    core.sender.resting_entries = lambda: []
    core.sender.take_withdrawn_late = lambda: []
    core.ws.write_health = lambda: {"ws_summary": {}}
    core._daily_loss_block = lambda: ""
    core._scope_sweep_block = lambda: ""
    core._leader_poll_due = lambda: True
    core.poll_wallets = lambda: [A]
    def poll_fills(wallet, start_ms, end_ms=None):
        poll_starts.append(start_ms)
        if poll_fill[0] is None:
            poll_fill[0] = c.LeaderFill("r1poll", A, "SOL", "BUY", 100.0, 1.0,
                                        end_ms - c.LEADER_POLL_OVERLAP_MS - 1000,
                                        "POLL", 0, {"oid": "4", "dir": "Open Long", "startPosition": "0"})
        fill = poll_fill[0]
        return ([fill] if start_ms <= fill.timestamp_ms <= end_ms else [], "POLL_OK")
    core.ingestor.poll_hyperliquid_fills = poll_fills
    state = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    state["last_leader_poll_cursor_ms"] = {A: c.utc_now_ms() - c.LEADER_POLL_OVERLAP_MS - 5000}
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, state)
    check("poll_queue_fixture_is_saturated", all(q.full() for q in core._hot_queues))
    first = core.run_cycle(use_source_csv=False, poll_live=True)
    check("poll_fill_was_rejected_for_queue_saturation", poll_fill[0] is not None and first.leader_fills_queued == 0)
    saved = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("last_leader_poll_cursor_ms", {}).get(A, 0)
    check("poll_queue_full_cursor_holds_unqueued_fill", saved <= poll_fill[0].timestamp_ms,
          f"cursor={saved} fill={poll_fill[0].timestamp_ms}")
    core.run_cycle(use_source_csv=False, poll_live=True)
    check("poll_queue_full_retry_window_includes_fill",
          len(poll_starts) == 2 and poll_starts[1] <= poll_fill[0].timestamp_ms,
          f"starts={poll_starts} fill={poll_fill[0].timestamp_ms}")

    # A terminally skipped late entry is handled, not a queue-rejected fill to pin the cursor on.
    late_fill = c.LeaderFill("r1late", A, "SOL", "BUY", 100.0, 1.0,
                             c.utc_now_ms() - 15000, "POLL", 0,
                             {"oid": "5", "dir": "Open Long", "startPosition": "0"})
    poll_fill[0] = late_fill
    poll_starts.clear()
    state = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    state["last_leader_poll_cursor_ms"] = {A: late_fill.timestamp_ms - c.LEADER_POLL_OVERLAP_MS - 5000}
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, state)
    old_late_classifier = c.already_closed_late_entries
    c.already_closed_late_entries = lambda batch, _now: (
        {late_fill.leader_fill_id: "leader subsequently closed"}
        if any(f.leader_fill_id == late_fill.leader_fill_id for f in batch) else {})
    try:
        first_late = core.run_cycle(use_source_csv=False, poll_live=True)
        late_rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
                     if r.get("leader_fill_id") == late_fill.leader_fill_id]
        check("late_closed_fill_writes_terminal_without_queueing",
              first_late.leader_fills_queued == 0 and core._already_handled(late_fill)
              and any(r.get("terminal_state") == "MISSED_ENTRY_LEADER_ALREADY_CLOSED" for r in late_rows),
              f"queued={first_late.leader_fills_queued} handled={core._already_handled(late_fill)} rows={len(late_rows)}")
        core.run_cycle(use_source_csv=False, poll_live=True)
        late_saved = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("last_leader_poll_cursor_ms", {}).get(A, 0)
        check("late_closed_terminal_does_not_pin_cursor",
              len(poll_starts) == 2 and late_saved > late_fill.timestamp_ms,
              f"starts={poll_starts} cursor={late_saved} fill={late_fill.timestamp_ms}")
    finally:
        c.already_closed_late_entries = old_late_classifier

    # EVENT_LOSS: a previously unseen leader CLOSE must enter by the real
    # run_cycle polling/cursor seam, exactly once on repeat intake. Physical
    # owned-fill/CLOID/owed oracle remains RED/NOT_RUN, NOT certified here.
    for q in core._hot_queues:
        held = []
        while not q.empty(): held.append(q.get_nowait())
        if held: core._release_queued(held, q)
    ts = c.utc_now_ms() - 4000
    close = c.LeaderFill("cc1-event-loss-recovered-close", A, "BTC", "SELL",
                         100.0, 0.5, ts, "POLL", 0,
                         {"oid": "cc1-event-loss-oid", "dir": "Close Long", "startPosition": "0.5"})
    check("EVENT_LOSS_CLOSE_UNSEEN_BEFORE_BACKFILL",
          core.hot_backlog() == 0 and not core._already_handled(close))
    polls = []
    def poll_close(wallet, start_ms, end_ms=None):
        polls.append((wallet, start_ms, end_ms))
        return ([close] if wallet == A and start_ms <= ts <= end_ms else [], "POLL_OK")
    def queued_close():
        return sum(1 for q in core._hot_queues for f in list(q.queue)
                   if f.leader_fill_id == close.leader_fill_id)
    core.ingestor.poll_hyperliquid_fills = poll_close
    state = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    state["last_leader_poll_cursor_ms"] = {A: ts - c.LEADER_POLL_OVERLAP_MS - 5000}
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, state)
    core.run_cycle(use_source_csv=False, poll_live=True)
    saved = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get(
        "last_leader_poll_cursor_ms", {}).get(A, 0)
    check("EVENT_LOSS_UNSEEN_CLOSE_RECOVERED_FROM_ACTUAL_POLL_INTAKE",
          queued_close() == 1 and len(polls) == 1
          and close.side == "SELL" and close.raw.get("startPosition") == "0.5")
    check("EVENT_LOSS_CLOSE_CURSOR_NOT_PAST_UNHANDLED_EVENT",
          saved <= ts, f"cursor={saved} event={ts}")
    core.run_cycle(use_source_csv=False, poll_live=True)
    check("EVENT_LOSS_SAME_RECOVERED_CLOSE_NOT_QUEUED_TWICE",
          queued_close() == 1 and len(polls) == 2)

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
