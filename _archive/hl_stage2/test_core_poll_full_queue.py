#!/usr/bin/env python3
"""A full poll window of fills already in the hot queue must not be re-offered.

Run: python test_core_poll_full_queue.py   # no network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
WALLET = "0x" + "a" * 40


def main():
    tmp = Path(tempfile.mkdtemp(prefix="pollfull_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                       "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_HOT_SEND_WORKERS": "2"})
    import HL_Live_Copy_Service_Core as c

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
        WALLET: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_stop_event.set()
    for thread in core._hot_threads:
        thread.join(timeout=2)
    core.async_dispatch = True
    core.sender.refresh_asset_universe = lambda: None
    core.sender.prune_standing_closes = lambda: None
    core.sender.resting_entries = lambda: []
    core.sender.take_withdrawn_late = lambda: []
    core.sender.stop_cancel_resting_entries = lambda: []
    core.ws.write_health = lambda: {"ws_summary": {}}
    core._daily_loss_block = lambda: ""
    core._scope_sweep_block = lambda: ""
    core._leader_poll_due = lambda: True
    core.poll_wallets = lambda: [WALLET]
    now = c.utc_now_ms()
    fills = [c.LeaderFill(f"queued-{i}", WALLET, "BTC", "BUY", 100.0, 1.0, now - i,
                          "POLL", 0, {"oid": str(i), "dir": "Open Long"}) for i in range(5000)]
    for i, fill in enumerate(fills):
        key = core._guard_key(fill)
        core._queued_keys.add(key)
        core._pending_ts[key] = (WALLET, fill.timestamp_ms)
        core._hot_queues[i % len(core._hot_queues)].put_nowait(fill)
    core.ingestor.poll_hyperliquid_fills = lambda *_args: (fills, "POLL_OK")
    offered = []
    dispatch = core._dispatch_fill
    core._dispatch_fill = lambda fill: (offered.append(fill.leader_fill_id), dispatch(fill))[1]
    core.state_writer.write = lambda summary, dedupe, cfg: core.state_writer._write_now(summary, dedupe, cfg)

    started = time.monotonic()
    summary = core.run_cycle(use_source_csv=False, poll_live=True)
    elapsed = time.monotonic() - started
    state = c.load_json(c.SERVICE_STATE_FILE, {})
    ok = (summary.ok and elapsed < 1.0 and not offered
          and summary.leader_fills_queued == 0 and summary.leader_fills_deduped == 5000
          and state.get("cycle") == "run_cycle")
    print("RESULT::already_queued_%s | elapsed=%.3fs offered=%d queued=%d deduped=%d cycle=%s" % (
        "PASS" if ok else "FAIL", elapsed, len(offered), summary.leader_fills_queued,
        summary.leader_fills_deduped, state.get("cycle")))

    # A distinct poll window must stop offering after the first rejected fill, yet keep
    # the persisted cursor behind that fill so the next cycle can retry it.
    for q in core._hot_queues:
        while not q.empty():
            q.get_nowait()
        q.maxsize = 1
    core._queued_keys.clear()
    core._pending_ts.clear()
    core._pending_seen.clear()
    core._coin_lane.clear()
    blocker = c.LeaderFill("queue-blocker", WALLET, "ETH", "BUY", 100.0, 1.0, now,
                           "TEST", 0, {"oid": "blocker", "dir": "Open Long"})
    core._hot_queues[0].put_nowait(blocker)
    overflow_now = c.utc_now_ms()
    overflow = [c.LeaderFill(f"overflow-{i}", WALLET, "SOL", "BUY", 100.0, 1.0,
                             overflow_now - i, "POLL", 0,
                             {"oid": f"overflow-{i}", "dir": "Open Long"}) for i in range(5000)]
    poll_starts = []
    def poll_overflow(_wallet, start_ms, end_ms=None):
        poll_starts.append(start_ms)
        return (overflow, "POLL_OK") if start_ms <= min(f.timestamp_ms for f in overflow) else ([], "POLL_OK")
    core.ingestor.poll_hyperliquid_fills = poll_overflow
    offered.clear()
    overflow_cycles = []
    offers_per_cycle = []
    core._dispatch_fill = dispatch
    current_cycle_offers = []
    def tripwire_dispatch(fill):
        current_cycle_offers.append(fill.leader_fill_id)
        offered.append(fill.leader_fill_id)
        if len(current_cycle_offers) > 1:
            raise AssertionError("cycle retried dispatch after the full queue rejected its first fill")
        return dispatch(fill)
    core._dispatch_fill = tripwire_dispatch
    for cycle_no in range(2):
        current_cycle_offers.clear()
        started = time.monotonic()
        cycle = core.run_cycle(use_source_csv=False, poll_live=True)
        overflow_cycles.append((time.monotonic() - started, cycle))
        offers_per_cycle.append(len(current_cycle_offers))
        runtime = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
        saved = runtime.get("last_leader_poll_cursor_ms", {}).get(WALLET, 0)
        state = c.load_json(c.SERVICE_STATE_FILE, {})
        overflow_ok = (cycle.ok and overflow_cycles[-1][0] < 1.0 and cycle.leader_fills_queued == 0
                       and saved <= min(f.timestamp_ms for f in overflow)
                       and state.get("cycle") == "run_cycle")
        if cycle_no == 0:
            first_state_ms = state.get("created_at_ms", 0)
        else:
            overflow_ok = overflow_ok and state.get("created_at_ms", 0) > first_state_ms
        if not overflow_ok:
            break
        time.sleep(0.01)
    overflow_ok = (len(overflow_cycles) == 2 and offers_per_cycle == [1, 1] and len(offered) == 2
                   and offered[0] == offered[1]
                   and len(poll_starts) == 2
                   and all(start <= min(f.timestamp_ms for f in overflow) for start in poll_starts)
                   and all(elapsed < 1.0 for elapsed, _cycle in overflow_cycles))
    print("RESULT::full_queue_retries_%s | cycles=%d offered=%d seconds=%s cursor_starts=%s" % (
        "PASS" if overflow_ok else "FAIL", len(overflow_cycles), len(offered),
        [round(elapsed, 3) for elapsed, _cycle in overflow_cycles], poll_starts))
    core.stop()
    sys.exit(0 if ok and overflow_ok else 1)


if __name__ == "__main__":
    main()
