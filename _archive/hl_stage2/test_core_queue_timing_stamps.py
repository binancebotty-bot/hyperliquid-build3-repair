#!/usr/bin/env python3
"""Offline check for queue timing stamps; clears inherited env and never constructs an exchange client."""
from __future__ import annotations

import json
import os
import queue
import sys
import tempfile
import threading
from pathlib import Path

os.environ.clear()

with tempfile.TemporaryDirectory(prefix="queue_timing_stamps_") as tmp:
    os.environ.update({
        "HL_LEADER_NETWORK": "testnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_AUDIT_DIR": tmp,
        "HL_LIVE_ENV_FILE": str(Path(tmp) / "no-env-file"),
        "HL_LIVE_AUTO_SEND_ENABLED": "0",
        "HL_LIVE_WS_ENABLED": "0",
        "HL_LIVE_EARLY_PREWARM": "0",
        "HL_LIVE_PREWARM_SYMBOL_META": "0",
        "HL_LIVE_PREWARM_SDK_CLIENT": "0",
        "HL_LIVE_FOREIGN_WS_SCAN": "0",
        "HL_LIVE_HOT_INNER": "1",
        "HL_LIVE_HOT_BATCH_MAX": "500",
    })
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import HL_Live_Copy_Service_Core as c

    c.CORE_RUNTIME_STATE_FILE = Path(tmp) / "runtime_state.json"
    core = object.__new__(c.LiveCopyCore)
    core._hot_stop_event = threading.Event()
    core._entry_sends_blocked_reason = ""
    core._hot_queues = [queue.Queue(maxsize=10)]
    core._hot_queue = core._hot_queues[0]
    core._prio_queues = [queue.Queue(maxsize=10)]
    core._inflight = {}
    core._coin_locks = {}
    core._coin_locks_guard = threading.Lock()
    core._deferred = {}
    core._drain_priority = lambda _idx: None
    core._plan_batch = lambda batch: list(batch)
    core._already_handled = lambda _fill: True
    core._guard_key = lambda fill: fill.leader_fill_id
    core._release_queued = lambda batch, q: [q.task_done() for _ in batch]

    fills = [
        c.LeaderFill(f"fill-{i}", "wallet-a", f"COIN-{i}", "BUY", 1.0, 1.0,
                     1_800_000_000_000 + i, "WS_CAPTURED", 1_800_000_000_000 + i, {})
        for i in range(2)
    ]
    required = (
        "batch_drained_ms", "lane_assigned_ms", "lane_started_ms",
        "coin_lock_requested_ms", "coin_lock_acquired_ms", "lane_finished_ms", "batch_joined_ms",
    )
    processed = [0]
    process_lock = threading.Lock()

    def fake_process(_fill, _summary=None, _reason=""):
        with process_lock:
            processed[0] += 1
            if processed[0] == len(fills):
                core._hot_stop_event.set()

    core._process_leader_fill = fake_process
    for fill in fills:
        core._hot_queues[0].put_nowait(fill)
    core._hot_send_loop_inner(0)

    snapshots = []
    for fill in fills:
        stamps = (fill.raw or {}).get("_stamps") or {}
        missing = [key for key in required if key not in stamps]
        if missing:
            raise AssertionError(f"missing timing stamps for {fill.leader_fill_id}: {missing}")
        values = [stamps[key] for key in required]
        if values != sorted(values):
            raise AssertionError(f"timing stamps not monotonic for {fill.leader_fill_id}: {values}")
        if set(required) & set(c.SEND_ATTEMPT_FIELDS):
            raise AssertionError("timing diagnostics must not expand the send-attempt CSV schema")
        snapshots.append(dict(stamps))

    clock_fill = c.LeaderFill("clock", "wallet-a", "COIN", "BUY", 1.0, 1.0,
                              1_800_000_000_010, "WS_CAPTURED", 1_800_000_000_010, {})
    original_clock = c.utc_now_ms
    ticks = iter((2_000, 1_000))
    c.utc_now_ms = lambda: next(ticks)
    try:
        c.stamp_fill(clock_fill, "first_ms")
        c.stamp_fill(clock_fill, "second_ms")
    finally:
        c.utc_now_ms = original_clock
    if clock_fill.raw["_stamps"] != {"first_ms": 2_000, "second_ms": 2_000}:
        raise AssertionError("new timing stamps were not monotonic across a backward clock step")

    core._run_plan(0, fills)
    if [dict(fill.raw["_stamps"]) for fill in fills] != snapshots:
        raise AssertionError("replayed attempt overwrote first-seen timing stamps")

    class StopAfterOneSample:
        def __init__(self):
            self.waits = 0

        def wait(self, seconds):
            if seconds != 10.0:
                raise AssertionError(f"queue sampling interval changed: {seconds}")
            self.waits += 1
            return self.waits > 1

    core._hot_stop_event = StopAfterOneSample()
    core._queue_depth_loop()
    core._fill_trace("cycle_start", None, {"cycle_id": 7})
    core._fill_trace("cycle_end", None, {"cycle_id": 7, "duration_ms": 12})
    trace = Path(tmp) / "fill_trace.jsonl"
    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    if not any(row.get("k") == "queue_depth" and row.get("hot_depth") == [0]
               and row.get("priority_depth") == [0] for row in rows):
        raise AssertionError("10-second queue-depth sample was not written to the append-only trace")
    drained_ids = {row.get("id") for row in rows if row.get("k") == "batch_drained"}
    if drained_ids != {fill.leader_fill_id for fill in fills}:
        raise AssertionError("batch-drained trace rows did not cover the source fills")
    joined = [row for row in rows if row.get("k") == "batch_joined"]
    if not all(any(row.get("id") == fill.leader_fill_id and set(required) <= set(row.get("stamps", {}))
                   for row in joined) for fill in fills):
        raise AssertionError("batch-joined trace rows did not include every per-fill timing stamp")
    cycles = {row.get("k"): row for row in rows if row.get("cycle_id") == 7}
    if not {"cycle_start", "cycle_end"} <= set(cycles) or cycles["cycle_end"].get("duration_ms") != 12:
        raise AssertionError("cycle start/end diagnostics were not written with duration")

print("PASS: first-seen queue timing stamps and queue-depth trace")
