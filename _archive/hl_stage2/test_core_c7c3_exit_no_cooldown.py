#!/usr/bin/env python3
"""C7C commit 3: no EXIT cooldown, no stamped window after a no-send.

Offline fake sender only; no network or exchange orders.
Run: py311 -m pytest -q _archive/hl_stage2/test_core_c7c3_exit_no_cooldown.py
"""
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as core


def _exit_intent(label):
    fill = core.LeaderFill(
        "fill-" + label, "0x" + "a" * 40, "BTC", "BUY",
        100.0, 0.1, core.utc_now_ms(), "TEST")
    return core.Intent(
        "exit-" + label, fill, "BUY", 0.1, 10.0, "CLO", "fixed",
        "EXIT_ALLOWED", "EXIT", "sleeve-BTC", "pos-BTC", "SHORT",
        -0.1, -0.1, True, True, core.utc_now_ms(), "lifecycle=EXIT;")


def _gateway():
    g = core.SenderGateway.__new__(core.SenderGateway)
    g.cfg = SimpleNamespace(
        master_switch_now=lambda: True,
        send_mode_now=lambda: "ON",
        liq_parity_enabled=lambda: False)
    g.sender_key_invalid = ""
    g._pending_exit_lock = threading.Lock()
    g._last_exit_attempt_ms = {}
    g._pre_send_ownership_gate = lambda intent: (True, {})
    g._send_time_wallet_mode_block = lambda *args: None
    g._pending_exit_blocked = lambda intent: (False, "")
    g._mark_pending_exit = lambda intent: None
    g._clear_pending_exit = lambda intent: None
    g._journal_authorised_close_refusal = lambda *args: None
    g._append_real_attempt = lambda *args: None
    g.signal_ambiguous_send_attempt_written = lambda *args: None
    g._report_post_send_bookkeeping_error = lambda *args: None
    g.audit = SimpleNamespace(append_reconciliation=lambda *args, **kwargs: None)
    return g


def test_exit_bypasses_existing_cooldown_stamp_and_attempts_again():
    g = _gateway()
    g._last_exit_attempt_ms["btc"] = core.utc_now_ms()
    called = []

    def _real(intent, timing):
        called.append(intent.intent_id)
        return True, "ORDER_FILLED", {"exchange_called": True}

    g._send_real = _real
    assert g.send_if_allowed(_exit_intent("one")) == (True, "ORDER_FILLED")
    assert g.send_if_allowed(_exit_intent("two")) == (True, "ORDER_FILLED")
    assert called == ["exit-one", "exit-two"]


def test_exit_non_send_never_stamps_cooldown_window():
    g = _gateway()
    g._send_real = lambda intent, timing: (
        False, "SDK_UNAVAILABLE", {"exchange_called": False})
    assert g.send_if_allowed(_exit_intent("no-send")) == (False, "SDK_UNAVAILABLE")
    assert g._last_exit_attempt_ms == {}


def test_pending_exit_guard_refusal_does_not_stamp_window():
    g = _gateway()
    g._pending_exit_blocked = lambda intent: (True, "unreconciled wire")
    def should_not_send(*args):
        raise AssertionError("unreconciled close must not be sent")
    g._send_real = should_not_send
    assert g.send_if_allowed(_exit_intent("guarded")) == (False, "PENDING_EXIT_GUARD_ACTIVE")
    assert g._last_exit_attempt_ms == {}
