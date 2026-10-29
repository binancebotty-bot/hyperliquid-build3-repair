#!/usr/bin/env python3
"""Offline check for per-fill stage stamps and rejected-send details in proc_end."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from unittest.mock import patch

os.environ.clear()
os.environ.update({
    "HL_LIVE_ENV_FILE": str(Path(tempfile.gettempdir()) / f"codex-no-env-{uuid.uuid4().hex}.env"),
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_AUTO_SEND_ENABLED": "0",
    "HL_LIVE_WS_ENABLED": "0",
})

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import HL_Live_Copy_Service_Core as c  # noqa: E402

FAIL = []
CASES = []


def check(name, cond, detail=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + detail) if detail and not cond else ''))
    CASES.append(name)
    if not cond:
        FAIL.append(name)


class CaptureAudit:
    def __init__(self):
        self.attempts = []
        self.reconciliations = []

    def append_send_attempt(self, row):
        self.attempts.append(row)

    def append_reconciliation(self, *args, **kwargs):
        self.reconciliations.append((args, kwargs))


def make_intent(fill):
    return c.Intent(
        intent_id="intent-1", fill=fill, copy_side="BUY", copy_size=1.0, copy_notional=100.0,
        wallet_mode="LIVE", copy_mode="fixed", decision="ENTRY_ALLOWED", reason="ENTRY",
        sleeve_id="sleeve-1", position_id="", position_direction_before="FLAT",
        wallet_position_before=0.0, coin_net_before=0.0, reduce_only_intended=False,
        reduce_only_sent_planned=False, created_at_ms=1_050,
    )


with tempfile.TemporaryDirectory(prefix="latency_trace_details_") as tmp:
    root = Path(tmp)
    c.CORE_RUNTIME_STATE_FILE = root / "clean_core_runtime_state.json"
    fill = c.LeaderFill(
        "fill-rejected", "wallet-a", "BTC", "BUY", 100.0, 1.0, 1_000,
        "WS_CAPTURED", 1_010,
        {"_stamps": {"enqueued_ms": 1_100, "picked_up_ms": 1_200, "lane_started_ms": 1_300}},
    )
    intent = make_intent(fill)

    sender = object.__new__(c.SenderGateway)
    sender.audit = CaptureAudit()
    sender._append_latency_warning_if_needed = lambda *_args: None

    def reject_during_processing(*_args):
        sender._append_real_attempt(intent, "ORDER_REJECTED", {
            "error": "Insufficient margin",
            "exchange_response": {},
            "exchange_called": True,
            "timing": {"exchange_call_finished_ms": 1_400},
            "wire_size": 1.0,
            "limit_px": 100.0,
        })
        return False, "ORDER_REJECTED", intent

    core = object.__new__(c.LiveCopyCore)
    core._inflight = {}
    core._stuck_dumped = set()
    core._deferred = {}
    core._past_send_keys = set()
    core._fill_trace_condition = threading.Condition()
    core._fill_trace_buffer = deque()
    core._fill_trace_dropped = 0
    core._fill_trace_writer_done = False
    trace_writer = threading.Thread(target=core._fill_trace_writer_loop, daemon=True)
    trace_writer.start()
    core._process_leader_fill_inner = reject_during_processing
    core._rows_for_merged_siblings = lambda *_args: None
    c.LiveCopyCore._process_leader_fill(core, fill)

    trace_path = root / "fill_trace.jsonl"
    def wait_for_trace_rows(expected):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if trace_path.exists():
                rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
                if len(rows) >= expected:
                    return rows
            time.sleep(0.01)
        raise AssertionError(f"fill trace did not reach {expected} rows")

    rows = wait_for_trace_rows(2)
    end = next(row for row in rows if row.get("k") == "proc_end")
    expected = {
        "ws_received_ms": 1_010,
        "leader_fill_ms": 1_000,
        "enqueue_ms": 1_100,
        "pickup_ms": 1_200,
        "lane_start_ms": 1_300,
        "send_real_started_ms": None,
        "reply_ms": 1_400,
    }
    check('proc_end records the per-fill stage stamps', end.get("stage_stamps") == expected,
          f"stage stamps mismatch: {end.get('stage_stamps')}")
    check('proc_end records the terminal status', end.get("status") == "ORDER_REJECTED",
          f"terminal status missing: {end}")
    check('proc_end records the reject category', end.get("reject_category") == "INSUFFICIENT_MARGIN",
          f"reject category missing: {end}")
    check('proc_end records the sanitized reject reason', end.get("reject_reason") == "Insufficient margin",
          f"reject reason missing or unsanitized: {end}")

    blocked = c.LeaderFill(
        "fill-blocked", "wallet-a", "ETH", "BUY", 2_000.0, 1.0, 1_500,
        "WS_CAPTURED", 1_510,
        {
            "_stamps": {"enqueued_ms": 1_600, "picked_up_ms": 1_700, "lane_started_ms": 1_800},
            "_trace_stage_stamps": {"reply_ms": 1_400},
            "_trace_reject": {"category": "INSUFFICIENT_MARGIN", "reason": "old rejection"},
        },
    )
    core._process_leader_fill_inner = lambda *_args: (False, "LIQ_PARITY_BLOCKED", None)
    c.LiveCopyCore._process_leader_fill(core, blocked)
    rows = wait_for_trace_rows(4)
    blocked_end = next(row for row in rows if row.get("id") == "fill-blocked" and row.get("k") == "proc_end")
    check('a blocked send gets no fabricated reply timestamp',
          blocked_end.get("stage_stamps", {}).get("reply_ms") is None,
          f"non-send was given a fabricated reply timestamp: {blocked_end}")
    check('a blocked send inherits no rejection reason',
          "reject_reason" not in blocked_end,
          f"non-reject inherited a rejection reason: {blocked_end}")

    failed = c.LeaderFill(
        "fill-exception", "wallet-a", "SOL", "SELL", 150.0, 1.0, 1_900,
        "WS_CAPTURED", 1_910,
        {"_stamps": {"enqueued_ms": 2_000, "picked_up_ms": 2_100, "lane_started_ms": 2_200}},
    )
    core._process_leader_fill_inner = lambda *_args: (_ for _ in ()).throw(RuntimeError("synthetic"))
    core._terminal_after_exception = lambda *_args: None
    with patch.object(c, "log_error", lambda *_args: None):
        result = c.LiveCopyCore._process_leader_fill(core, failed)
    check('a processing exception returns PROCESS_EXCEPTION', result[1] == "PROCESS_EXCEPTION",
          f"processing exception status missing: {result}")
    rows = wait_for_trace_rows(6)
    failed_end = next(row for row in rows if row.get("id") == "fill-exception" and row.get("k") == "proc_end")
    check('the exception end row says PROCESS_EXCEPTION with no reply timestamp',
          failed_end.get("status") == "PROCESS_EXCEPTION"
          and failed_end.get("stage_stamps", {}).get("reply_ms") is None,
          f"exception end row missing or has a fabricated reply timestamp: {failed_end}")
    with core._fill_trace_condition:
        core._fill_trace_writer_done = True
        core._fill_trace_condition.notify_all()
    trace_writer.join(timeout=2)

print(f"TOTAL={len(CASES)} FAILED={len(FAIL)}")
sys.exit(0 if not FAIL else 1)
