"""Offline regression: a fresh engine heartbeat cannot conceal a failed follower copy poll.

Run: python -m pytest _archive/hl_stage2/test_ui_health_copy_poll_failclosed.py -q
Only the actual UI health function is compiled; no engine import, network or orders.
"""
import ast
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def test_fresh_heartbeat_failed_copy_account_poll_cannot_be_healthy():
    src = Path(__file__).with_name("HL_Copy_App_SSOT.py").read_text(encoding="utf-8-sig")
    func = next(n for n in ast.parse(src).body
                if isinstance(n, ast.FunctionDef) and n.name == "_build_health_summary")
    def number(value, default=0):
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    ns = {"Dict": Dict, "Any": Any, "List": List, "Optional": Optional,
          "time": time, "os": os, "inum": lambda v: int(number(v)), "fnum": number,
          "ENGINE_STALE_SEC": 180, "FOLLOWER_NETWORK": "testnet",
          "_CLOSE_FAILURE_MARKERS": ("MANUAL_EXIT_RECOVERY_REQUIRED", "EXIT_RECOVERY_QUEUE_FAILED"),
          "_iso_to_ms": lambda v: 0, "_plain_integrity_reason": lambda counts: "",
          "_plain_block_reason": lambda code: code}
    exec(compile(ast.Module(body=[func], type_ignores=[]), str(Path(__file__)), "exec"), ns)
    health = ns["_build_health_summary"]
    now_ms = 1_800_000_000_000
    state = {"last_state_write_ms": now_ms, "networks": {"follower": "testnet"},
             "copy_account_status": "COPY_ACCOUNT_POLLED"}
    integrity = {"status": "GREEN", "available": True}
    assert health(state, integrity, now_ms=now_ms)["text"] == "Healthy"
    for status in ("COPY_ACCOUNT_POLL_NETWORK_ERROR", "COPY_ACCOUNT_POLL_PARTIAL",
                   "COPY_ACCOUNT_POLL_DISABLED", "COPY_POLL_THREAD_STARTING", "UNKNOWN", ""):
        failed = health({**state, "copy_account_status": status}, integrity, now_ms=now_ms)
        assert failed["level"] == "amber" and failed["text"].startswith("Needs a look"), (status, failed)
    disabled = health({**state, "copy_account_status": "COPY_ACCOUNT_POLL_DISABLED"}, integrity, now_ms=now_ms)
    assert disabled["level"] == "amber" and disabled["text"] == "Needs a look: copy polling disabled by config", disabled
    # Existing severe conditions must still take precedence over copy-poll degradation.
    stopped = health({**state, "copy_account_status": "COPY_ACCOUNT_POLL_NETWORK_ERROR",
                      "entry_sends_blocked_reason": "COPY_POLL_STALE"}, integrity, now_ms=now_ms)
    assert stopped["level"] == "red" and stopped["text"].startswith("Stopped:"), stopped
