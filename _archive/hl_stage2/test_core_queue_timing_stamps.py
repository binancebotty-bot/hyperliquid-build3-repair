#!/usr/bin/env python3
"""Offline check for queue timing stamps; clears inherited env and never constructs an exchange client."""
from __future__ import annotations

import collections
import json
import os
import queue
import sys
import tempfile
import threading
import time
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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

    # _fill_trace only QUEUES a line; LiveCopyCore.__init__ starts the writer thread that turns the queue
    # into fill_trace.jsonl. This test builds the core with object.__new__ (no __init__), so without the
    # writer below nothing ever reaches disk and the trace read fails with FileNotFoundError. Start it here
    # exactly as __init__ does, and stop it (further down) before the file is read and the temp dir removed.
    core._fill_trace_condition = threading.Condition()
    core._fill_trace_buffer = collections.deque(maxlen=c.FILL_TRACE_QUEUE_MAX)
    core._fill_trace_dropped = 0
    core._fill_trace_writer_done = False
    core._fill_trace_writer = threading.Thread(target=core._fill_trace_writer_loop, daemon=True,
                                               name="test-fill-trace-writer")
    core._fill_trace_writer.start()

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
    # Drain the queue and let the writer exit before reading: _fill_trace is asynchronous, so reading
    # straight after it races the writer (and leaves the handle open when the temp dir is removed).
    with core._fill_trace_condition:
        core._fill_trace_writer_done = True
        core._fill_trace_condition.notify()
    core._fill_trace_writer.join(timeout=10.0)
    if core._fill_trace_writer.is_alive():
        raise AssertionError("fill-trace writer thread did not drain the queue before the trace was read")
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

    with tempfile.TemporaryDirectory(prefix="queue_sampler_start_") as startup_tmp:
        previous_runtime_state = c.CORE_RUNTIME_STATE_FILE
        previous_ws_provider = c.HEADROOM.ws_provider
        startup_core = None
        try:
            c.CORE_RUNTIME_STATE_FILE = Path(startup_tmp) / "runtime_state.json"
            cfg = SimpleNamespace(auto_send_enabled=False, stream_wallets=lambda: [])
            dedupe = SimpleNamespace(dedupe_load_failed=False, live_start_ms=1)
            ws = SimpleNamespace(enabled=False, _subscribed=set(), _refusals=[], _last_refusal="")
            sender = SimpleNamespace(resting_entry_exposure=lambda: None)
            original_fill_trace = c.LiveCopyCore._fill_trace

            def stop_after_queue_sample(self, kind, fill, extra=None):
                original_fill_trace(self, kind, fill, extra)
                if kind == "queue_depth":
                    self._hot_stop_event.set()

            replacements = (
                (c, "ensure_dirs", None),
                (c, "ConfigManager", cfg),
                (c, "ManualLedger", None),
                (c, "AuditLogWriter", SimpleNamespace(replay_all_fallbacks=lambda: None)),
                (c, "LeaderFillIngestor", None),
                (c, "load_json", {}),
                (c, "DedupeStore", dedupe),
                (c, "iter_csv_rows", []),
                (c, "iter_audit_history", []),
                (c, "WSManager", ws),
                (c, "IntentBuilder", None),
                (c, "SenderGateway", sender),
                (c, "CopyAccountIngestor", None),
                (c, "CopyFillMatcher", None),
                (c, "ExchangeReconciler", None),
                (c, "ServiceStateWriter", None),
            )
            with ExitStack() as patches:
                for target, name, replacement in replacements:
                    kwargs = {} if replacement is None else {"return_value": replacement}
                    patches.enter_context(patch.object(target, name, **kwargs))
                patches.enter_context(patch.object(c.LiveCopyCore, "_fill_trace", new=stop_after_queue_sample))
                patches.enter_context(patch.object(c.LiveCopyCore, "_pending_sweeper", new=lambda _self: None))
                patches.enter_context(patch.object(c.LiveCopyCore, "_hot_send_loop", new=lambda _self, _idx: None))
                patches.enter_context(patch.dict(os.environ, {"HL_LIVE_HOT_SEND_WORKERS": "1"}))
                startup_core = c.LiveCopyCore()
                sampler = startup_core._queue_depth_thread
                if sampler.ident is None:
                    raise AssertionError("queue-depth sampler thread was not started")
                startup_trace = Path(startup_tmp) / "fill_trace.jsonl"
                deadline = time.monotonic() + 20.0
                while time.monotonic() < deadline:
                    if startup_trace.exists():
                        try:
                            startup_rows = [json.loads(line) for line in startup_trace.read_text(encoding="utf-8").splitlines()]
                        except json.JSONDecodeError:
                            startup_rows = []  # Ignore a partially appended final JSONL row and retry.
                        if any(row.get("k") == "queue_depth" for row in startup_rows):
                            break
                    time.sleep(0.05)
                else:
                    raise AssertionError("started queue-depth sampler did not emit a row within 2x its 10-second interval")
        finally:
            try:
                if startup_core is not None:
                    startup_core._hot_stop_event.set()
                    sampler = startup_core._queue_depth_thread
                    if sampler.ident is not None:
                        sampler.join(timeout=2.0)
                    for worker in startup_core._hot_threads:
                        if worker.ident is not None:
                            worker.join(timeout=2.0)
                    if (sampler.ident is not None and sampler.is_alive()) or any(
                        worker.ident is not None and worker.is_alive() for worker in startup_core._hot_threads
                    ):
                        raise AssertionError("queue-depth sampler or hot worker leaked after startup check")
            finally:
                c.CORE_RUNTIME_STATE_FILE = previous_runtime_state
                c.HEADROOM.ws_provider = previous_ws_provider
                # __init__ also starts a fill-trace writer for startup_core; stop it before the temp dir goes,
                # or it can still hold fill_trace.jsonl while TemporaryDirectory tries to remove it (WinError 32).
                if startup_core is not None:
                    writer = getattr(startup_core, "_fill_trace_writer", None)
                    if writer is not None and writer.ident is not None:
                        with startup_core._fill_trace_condition:
                            startup_core._fill_trace_writer_done = True
                            startup_core._fill_trace_condition.notify()
                        writer.join(timeout=5.0)
                # The audit writer keeps errors.csv open in a module-level handle table; close every handle
                # before the temp dirs are removed (Windows refuses to unlink an open file).
                for _open_path in list(c._AUDIT_HANDLES):
                    c._close_audit_handle(Path(_open_path))

print("PASS: first-seen queue timing stamps and queue-depth trace")
# C7 gate contract: one machine-readable verdict line and an exit code, so a gate can score this
# file instead of reporting NOT_RUN. One case in this file; it reaches here only when it passes.
print("TOTAL=1 FAILED=0")
sys.exit(0)
