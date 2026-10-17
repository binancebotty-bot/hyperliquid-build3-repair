#!/usr/bin/env python3
"""Offline coverage for the optional exchange-slot-wait timing stamps."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": tempfile.mkdtemp(prefix="slot_wait_stamps_"),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LIVE_WS_ENABLED": "0",
    "HL_LIVE_AUTO_SEND_ENABLED": "0",
})

import HL_Live_Copy_Service_Core as c  # noqa: E402


class FakeExchange:
    def order(self, *args, **kwargs):
        return {"status": "ok"}


def place_with_flag(flag: str):
    gateway = c.SenderGateway.__new__(c.SenderGateway)
    gateway._exchange_order_lock = threading.Lock()
    timing = {}
    with patch.dict(os.environ, {"HL_LIVE_SLOT_WAIT_TIMING_ENABLED": flag}, clear=False):
        with patch.object(c, "FOLLOWER_NETWORK", "testnet"):
            with patch.object(c.SenderGateway, "_wait_exchange_order_slot", lambda self: None):
                with patch.object(c.SenderGateway, "_note_sender_key_rejection", lambda self, response: None):
                    gateway._place_order(
                        FakeExchange(), "BTC", True, 0.01, 100.0, "Ioc", False,
                        timing, "exchange_call_started_ms",
                    )
    return timing


off = place_with_flag("0")
assert "exchange_slot_wait_started_ms" not in off
assert "exchange_slot_wait_finished_ms" not in off

on = place_with_flag("1")
started = on.get("exchange_slot_wait_started_ms")
finished = on.get("exchange_slot_wait_finished_ms")
assert started is not None and finished is not None
assert finished >= started
assert on["exchange_call_started_ms"] >= finished
assert "exchange_slot_wait_started_ms" in c.SEND_ATTEMPT_FIELDS
assert "exchange_slot_wait_finished_ms" in c.SEND_ATTEMPT_FIELDS
assert "exchange_slot_wait_started_ms" in c.SEND_TIMING_FIELDS
assert "exchange_slot_wait_finished_ms" in c.SEND_TIMING_FIELDS

print("RESULT::SLOT_WAIT_FLAG_OFF_HAS_NO_STAMPS_PASS")
print("RESULT::SLOT_WAIT_FLAG_ON_HAS_ORDERED_STAMPS_PASS")
print("RESULT::SLOT_WAIT_STAMPS_ARE_SERIALIZED_PASS")
