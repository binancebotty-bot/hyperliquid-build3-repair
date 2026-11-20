"""A stale WS feed blocks entry sends; a reconnect backfill is queued only once."""
from __future__ import annotations

import os
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.update({
    "HL_LIVE_AUDIT_DIR": tempfile.mkdtemp(prefix="ws_gap_replay_"),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LIVE_WS_ENABLED": "1",
    "HL_LIVE_GATES_ALERT_ONLY": "1",
    "HL_LIVE_HOT_SEND_WORKERS": "1",
    "HL_LIVE_EARLY_PREWARM": "0",
    "HL_LIVE_PREWARM_SYMBOL_META": "0",
    "HL_LIVE_PREWARM_SDK_CLIENT": "0",
})

import HL_Live_Copy_Service_Core as c


class WsGapReplayTests(unittest.TestCase):
    def test_stale_ws_feed_blocks_entry_sends(self):
        core = c.LiveCopyCore(source_csv=HERE / "missing_ws_gap_replay.csv")
        try:
            core.ws.write_health = lambda: {"ws_summary": {"worst_health_grade": "DEGRADED"}}
            core.sender.refresh_asset_universe = lambda: None
            core.sender.prune_standing_closes = lambda: None
            core.sender.guard_standing_closes = lambda: None
            core.sender.resting_entries = lambda: []
            core.sender.take_withdrawn_late = lambda: []
            core._daily_loss_block = lambda: ""
            core._scope_sweep_block = lambda: ""

            summary = core.run_cycle(use_source_csv=False, poll_live=False)

            self.assertEqual(summary.entry_sends_blocked_reason, "WS_FEED_STALE")
        finally:
            core.stop()

    def test_reconnect_gap_replay_queues_missed_fill_once(self):
        wallet = "0x" + "a" * 40
        fill = c.LeaderFillIngestor().parse_fill(wallet, {
            "coin": "BTC", "side": "B", "px": "100", "sz": "1",
            "time": c.utc_now_ms(), "tid": 12345,
        }, "POLL")
        self.assertIsNotNone(fill)

        core = object.__new__(c.LiveCopyCore)
        core._queued_lock = threading.Lock()
        core._queued_keys = set()
        core._pending_ts = {}
        core._pending_seen = {}
        core._coin_lane = {}
        core._hot_queues = [c.queue.Queue()]
        core._hot_queue = core._hot_queues[0]
        core._prio_queues = [c.queue.Queue()]
        core._already_handled = lambda _fill: False
        core._is_close_fill = lambda _fill: False

        # The same missed fill arrives from reconnect replay and the REST backfill.
        self.assertTrue(core._dispatch_fill(fill))
        self.assertTrue(core._dispatch_fill(fill))

        self.assertEqual(core._hot_queue.qsize(), 1)


if __name__ == "__main__":
    unittest.main()
