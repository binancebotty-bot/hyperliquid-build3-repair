#!/usr/bin/env python3
"""End-status traces retain the follower, gate reason, and leader-fill source."""
import json
import os
import sys
import tempfile
import threading
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix="fill_trace_status_context_") as temp:
    os.environ["HL_LIVE_ENV_FILE"] = str(Path(temp) / "missing.env")
    os.environ["HL_LIVE_AUDIT_DIR"] = str(Path(temp) / "audit")
    sys.path.insert(0, str(ROOT))
    import HL_Live_Copy_Service_Core as C

    follower = "0x" + "c" * 40
    C.USER_WALLET = follower
    fill = C.LeaderFill("trace-context-1", "0x" + "a" * 40, "BTC", "BUY", 100.0, 1.0, 123, "POLL")
    intent = C.Intent(
        intent_id="intent-1", fill=fill, copy_side="BUY", copy_size=1.0, copy_notional=100.0,
        wallet_mode="ON", copy_mode="proportional", decision="SEND_BLOCKED_RISK",
        reason="follower exposure unavailable", sleeve_id="sleeve-1", position_id="position-1",
        position_direction_before="FLAT", wallet_position_before=0.0, coin_net_before=0.0,
        reduce_only_intended=False, reduce_only_sent_planned=False,
    )
    core = object.__new__(C.LiveCopyCore)
    core._fill_trace_condition = threading.Condition()
    core._fill_trace_buffer = deque(maxlen=C.FILL_TRACE_QUEUE_MAX)
    core._fill_trace_dropped = 0

    core._fill_trace("proc_end", fill, {"status_of": (False, "INTENT_NOT_SEND_ALLOWED", intent)})
    record = json.loads(core._fill_trace_buffer.popleft())
    assert record["status"] == "INTENT_NOT_SEND_ALLOWED"
    assert record["follower_wallet_id"] == follower
    assert record["gate_reason"] == "follower exposure unavailable"
    assert record["leader_fill_source"] == "POLL"

    intent.decision = "ENTRY_ALLOWED"
    intent.reason = "ENTRY"
    core._fill_trace("proc_end", fill, {"status_of": (False, "ENTRY_BLOCKED_GLOBAL_CLOSE_ONLY", intent)})
    record = json.loads(core._fill_trace_buffer.popleft())
    assert record["gate_reason"] == "ENTRY_BLOCKED_GLOBAL_CLOSE_ONLY"
    print("RESULT::FILL_TRACE_STATUS_CONTEXT_PASS")
