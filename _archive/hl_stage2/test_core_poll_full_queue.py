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
    print("RESULT::full_queue_cycle_%s | elapsed=%.3fs offered=%d queued=%d deduped=%d cycle=%s" % (
        "PASS" if ok else "FAIL", elapsed, len(offered), summary.leader_fills_queued,
        summary.leader_fills_deduped, state.get("cycle")))
    core.stop()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
