#!/usr/bin/env python3
"""Leader poll overlap scales with the polling interval in use: overlap = interval_ms + LEADER_POLL_OVERLAP_MS.

Test (1) cursor 1,000,000, pinned clock, healthy poll 120 s later: a fill stamped 969,999 that is visible only at that
poll is recovered (a fixed 30 s overlap would start at 970,000 and miss it)
Test (2) the extra rows re-read by the wider window do not produce duplicate work (already-handled fills are dropped)
Test (3) no feed configured (interval 0): the overlap is the bare 30 s
Test (4) a partial poll moves the cursor to newest fill + the same scaled overlap

Run: python test_core_poll_overlap_scaling.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="pollovl_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_HOT_SEND_WORKERS": "2", "HL_LIVE_LEADER_POLL_INTERVAL_SEC": "120"})
    os.environ.pop("HL_LIVE_LEADER_POLL_NOFEED_SEC", None)
    import HL_Live_Copy_Service_Core as c
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
        A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    core.async_dispatch = False
    core.sender.refresh_asset_universe = lambda: None
    core.sender.prune_standing_closes = lambda: None
    core.sender.resting_entries = lambda: []
    core.sender.take_withdrawn_late = lambda: []
    core.ws.write_health = lambda: {"ws_summary": {}}
    core._daily_loss_block = lambda: ""
    core._scope_sweep_block = lambda: ""
    core._leader_poll_due = lambda force=False: True
    core.poll_wallets = lambda: [A]
    core._poll_wallet_selection_changed = False
    core.state_writer.write = lambda *a, **k: None  # its async read-modify-write would race the cursor this test seeds
    # healthy feed: the poll runs at the 120 s backstop interval
    core.ws.enabled, core.ws._socket_open, core.ws._subscribed = True, True, {A}
    core.wallets = [A]
    check("interval_is_120s", core.leader_poll_interval_sec() == 120.0, str(core.leader_poll_interval_sec()))

    NOW = 1_120_000
    c.utc_now_ms = lambda: NOW
    c.LEADER_POLL_RETENTION_MS = 10_000_000
    late = c.LeaderFill("ovl_late", A, "SOL", "BUY", 100.0, 1.0, 969_999, "POLL", 0,
                        {"oid": "11", "dir": "Open Long", "startPosition": "0"})
    old = c.LeaderFill("ovl_old", A, "ETH", "BUY", 100.0, 1.0, 900_000, "POLL", 0,
                       {"oid": "12", "dir": "Open Long", "startPosition": "0"})
    rows = [old, late]
    starts = []
    processed = []
    status = ["POLL_OK"]

    def poll_fills(wallet, start_ms, end_ms=None):
        starts.append(start_ms)
        return ([f for f in rows if start_ms <= f.timestamp_ms <= end_ms], status[0])

    def process(fill, summary=None, entry_block_reason=""):
        processed.append(fill.leader_fill_id)
        with core._idem_lock:
            core._idem_accepted.add(core._guard_key(fill))
        return True, "", None
    core.ingestor.poll_hyperliquid_fills = poll_fills
    core._process_leader_fill = process
    with core._idem_lock:
        core._idem_accepted.add(core._guard_key(old))  # handled by an earlier poll / the live feed

    def set_cursor(ms):
        state = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
        state["last_leader_poll_cursor_ms"] = {A: ms}
        c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, state)

    def saved_cursor():
        return c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("last_leader_poll_cursor_ms", {}).get(A, 0)

    set_cursor(1_000_000)
    summary = core.run_cycle(use_source_csv=False, poll_live=True)
    check("window_starts_interval_plus_30s_back", starts[:1] == [1_000_000 - 120_000 - 30_000], str(starts))
    check("fill_969999_recovered_at_120s_poll", processed == ["ovl_late"], str(processed))
    check("already_handled_extra_row_deduped_not_reprocessed", summary.leader_fills_deduped >= 1
          and processed.count("ovl_old") == 0, f"{processed} deduped={summary.leader_fills_deduped}")
    core.run_cycle(use_source_csv=False, poll_live=True)
    check("repeat_poll_produces_no_duplicate", processed == ["ovl_late"], str(processed))

    # partial poll: the cursor lands at newest fill + the same scaled overlap (next start = that fill)
    status[0] = "POLL_PARTIAL"
    core._idem_accepted.clear()
    core._idem_accepted.add(core._guard_key(old))
    core._idem_accepted.add(core._guard_key(late))
    set_cursor(1_000_000)
    core.run_cycle(use_source_csv=False, poll_live=True)
    check("partial_cursor_uses_scaled_overlap", saved_cursor() == 969_999 + 120_000 + 30_000, str(saved_cursor()))

    # no feed configured: interval 0, the overlap is the bare 30 s
    status[0] = "POLL_OK"
    core.ws.enabled = False
    starts.clear()
    set_cursor(1_000_000)
    core.run_cycle(use_source_csv=False, poll_live=True)
    check("no_feed_overlap_is_30s", starts[:1] == [1_000_000 - 30_000], str(starts))
    core.stop()
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
