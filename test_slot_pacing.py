#!/usr/bin/env python3
"""
Slot pacing regression tests.

Tests the _reserve_exchange_order_slot method invariants:
1. Concurrent slot reservations produce exactly-spaced slots
2. Cooldown wait then exact spacing from cooldown end
3. Exit orders (wait_for_cooldown=False) bypass cooldown
4. Cancel between orders preserves future reserved slots
5. Multiple threads waking from cooldown don't collide

Prints RESULT:: lines and exits non-zero if any invariant is violated.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import types
from pathlib import Path
from unittest import mock

# Set up test environment
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "_archive" / "hl_stage2"))

_TEST_AUDIT_DIR = tempfile.mkdtemp(prefix="slot_pacing_test_")
os.environ["HL_LIVE_AUDIT_DIR"] = _TEST_AUDIT_DIR
os.environ["HL_LIVE_ENV_FILE"] = str(Path(_TEST_AUDIT_DIR) / "none.env")
os.environ["HL_LEADER_NETWORK"] = "testnet"
os.environ["HL_FOLLOWER_NETWORK"] = "testnet"
os.environ["HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS"] = "100"

import HL_Live_Copy_Service_Core as core  # noqa: E402


class FakeCfg:
    """Minimal config that allows all sends."""
    def send_mode_now(self):
        return "ON"

    def master_switch_now(self):
        return True

    def wallet_mode(self, wallet):
        return "LIVE"

    def wallet_enabled(self, wallet):
        return True


def create_gateway():
    """Create a SenderGateway-like namespace with all required mocks for slot pacing tests."""
    s = types.SimpleNamespace()
    s.cfg = FakeCfg()
    s.sender_key_invalid = False
    s._note_sender_key_rejection = lambda r: None
    s._parse_hl_response = lambda r: (True, "ORDER_RESTING", "1", "")
    s._rows = []

    def append(*a, **k):
        s._rows.append((a, k))

    s.audit = types.SimpleNamespace(append_reconciliation=append)
    s._master_gate_reason = types.MethodType(core.SenderGateway._master_gate_reason, s)
    s._gate_refusal_row = types.MethodType(core.SenderGateway._gate_refusal_row, s)
    s._reserve_exchange_order_slot = types.MethodType(
        core.SenderGateway._reserve_exchange_order_slot, s
    )
    s._reduce_only_for_intent = staticmethod(core.SenderGateway._reduce_only_for_intent)
    s._exchange_order_lock = threading.Lock()
    s._last_exchange_order_ms = 0
    s._exchange_rate_limit_cooldown_until_ms = 0

    return s


def run_concurrent_test(worker_count, gap_ms, now_ms, wait_for_cooldown, cooldown_until_ms=0):
    """Helper to run concurrent slot reservation test."""
    gateway = create_gateway()
    gateway._last_exchange_order_ms = now_ms
    if cooldown_until_ms:
        gateway._exchange_rate_limit_cooldown_until_ms = cooldown_until_ms

    start_barrier = threading.Barrier(worker_count + 1)
    slots = []
    slots_lock = threading.Lock()
    errors = []

    def worker():
        try:
            start_barrier.wait(timeout=3)
            with mock.patch.object(core, "utc_now_ms", new=lambda: now_ms):
                with mock.patch.object(core.time, "sleep", new=lambda _: None):
                    slot = gateway._reserve_exchange_order_slot(wait_for_cooldown=wait_for_cooldown)
            with slots_lock:
                slots.append(slot)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(worker_count)]

    for t in threads:
        t.start()
    start_barrier.wait(timeout=3)
    for t in threads:
        t.join(timeout=5)

    all_finished = all(not t.is_alive() for t in threads)
    no_errors = len(errors) == 0

    return all_finished, no_errors, slots, errors, gateway._last_exchange_order_ms


def test_concurrent_exact_spacing():
    """Test 1: 32 concurrent workers reserve exactly 100ms-spaced slots."""
    print("RESULT::test_concurrent_exact_spacing_start")
    worker_count = 32
    gap_ms = 100
    now_ms = 100000

    all_finished, no_errors, slots, errors, last_ms = run_concurrent_test(
        worker_count, gap_ms, now_ms, wait_for_cooldown=True
    )

    expected_slots = [now_ms + (i + 1) * gap_ms for i in range(worker_count)]
    slots_match = slots == expected_slots
    expected_last = expected_slots[-1]
    last_match = last_ms == expected_last

    passed = all_finished and no_errors and slots_match and last_match

    print(f"RESULT::test_concurrent_exact_spacing_all_finished_{'PASS' if all_finished else 'FAIL'}")
    print(f"RESULT::test_concurrent_exact_spacing_no_errors_{'PASS' if no_errors else 'FAIL'} | errors={errors}")
    print(f"RESULT::test_concurrent_exact_spacing_slots_match_{'PASS' if slots_match else 'FAIL'} | expected={expected_slots} actual={slots}")
    print(f"RESULT::test_concurrent_exact_spacing_last_ms_match_{'PASS' if last_match else 'FAIL'} | expected={expected_last} actual={last_ms}")
    print(f"RESULT::test_concurrent_exact_spacing_complete_{'PASS' if passed else 'FAIL'}")

    return passed


def test_cooldown_then_spacing():
    """Test 2: After cooldown, slots resume at exact spacing from cooldown end."""
    print("RESULT::test_cooldown_then_spacing_start")
    worker_count = 32
    gap_ms = 100
    start_ms = 100000
    cooldown_ms = 1000

    gateway = create_gateway()
    gateway._last_exchange_order_ms = start_ms
    gateway._exchange_rate_limit_cooldown_until_ms = start_ms + cooldown_ms

    start_barrier = threading.Barrier(worker_count + 1)
    slots = []
    slots_lock = threading.Lock()
    errors = []

    clock_ms = {"value": start_ms}
    clock_lock = threading.Lock()

    def virtual_now_ms():
        with clock_lock:
            return clock_ms["value"]

    def virtual_sleep(seconds):
        with clock_lock:
            clock_ms["value"] += int(seconds * 1000)

    def worker():
        try:
            start_barrier.wait(timeout=3)
            with mock.patch.object(core, "utc_now_ms", new=virtual_now_ms):
                with mock.patch.object(core.time, "sleep", new=virtual_sleep):
                    slot = gateway._reserve_exchange_order_slot(wait_for_cooldown=True)
            with slots_lock:
                slots.append(slot)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(worker_count)]

    for t in threads:
        t.start()
    start_barrier.wait(timeout=3)
    for t in threads:
        t.join(timeout=10)

    all_finished = all(not t.is_alive() for t in threads)
    no_errors = len(errors) == 0

    # First slot at cooldown end, then each gap_ms apart
    expected_slots = [start_ms + cooldown_ms + i * gap_ms for i in range(worker_count)]
    slots_match = slots == expected_slots
    expected_last = expected_slots[-1]
    last_match = gateway._last_exchange_order_ms == expected_last

    passed = all_finished and no_errors and slots_match and last_match

    print(f"RESULT::test_cooldown_then_spacing_all_finished_{'PASS' if all_finished else 'FAIL'}")
    print(f"RESULT::test_cooldown_then_spacing_no_errors_{'PASS' if no_errors else 'FAIL'} | errors={errors}")
    print(f"RESULT::test_cooldown_then_spacing_slots_match_{'PASS' if slots_match else 'FAIL'} | expected={expected_slots} actual={slots}")
    print(f"RESULT::test_cooldown_then_spacing_last_ms_match_{'PASS' if last_match else 'FAIL'} | expected={expected_last} actual={gateway._last_exchange_order_ms}")
    print(f"RESULT::test_cooldown_then_spacing_complete_{'PASS' if passed else 'FAIL'}")

    return passed


def test_exit_bypasses_cooldown():
    """Test 3: Exit orders (wait_for_cooldown=False) bypass cooldown."""
    print("RESULT::test_exit_bypasses_cooldown_start")
    gap_ms = 100
    start_ms = 100000
    cooldown_ms = 5000

    gateway = create_gateway()
    gateway._last_exchange_order_ms = start_ms
    gateway._exchange_rate_limit_cooldown_until_ms = start_ms + cooldown_ms

    errors = []
    slots = []
    slots_lock = threading.Lock()

    def worker():
        try:
            with mock.patch.object(core, "utc_now_ms", new=lambda: start_ms):
                with mock.patch.object(core.time, "sleep", new=lambda _: None):
                    slot = gateway._reserve_exchange_order_slot(wait_for_cooldown=False)
            with slots_lock:
                slots.append(slot)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(3)]

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    all_finished = all(not t.is_alive() for t in threads)
    no_errors = len(errors) == 0

    expected_slots = [start_ms + (i + 1) * gap_ms for i in range(3)]
    slots_match = slots == expected_slots
    expected_last = expected_slots[-1]
    last_match = gateway._last_exchange_order_ms == expected_last

    passed = all_finished and no_errors and slots_match and last_match

    print(f"RESULT::test_exit_bypasses_cooldown_all_finished_{'PASS' if all_finished else 'FAIL'}")
    print(f"RESULT::test_exit_bypasses_cooldown_no_errors_{'PASS' if no_errors else 'FAIL'} | errors={errors}")
    print(f"RESULT::test_exit_bypasses_cooldown_slots_match_{'PASS' if slots_match else 'FAIL'} | expected={expected_slots} actual={slots}")
    print(f"RESULT::test_exit_bypasses_cooldown_last_ms_match_{'PASS' if last_match else 'FAIL'} | expected={expected_last} actual={gateway._last_exchange_order_ms}")
    print(f"RESULT::test_exit_bypasses_cooldown_complete_{'PASS' if passed else 'FAIL'}")

    return passed


def test_cancel_preserves_future_slots():
    """Test 4: Cancel between orders preserves future reserved slots."""
    print("RESULT::test_cancel_preserves_future_slots_start")
    gap_ms = 100
    now_ms = 100000

    gateway = create_gateway()
    gateway._last_exchange_order_ms = now_ms

    errors = []
    slots = []

    try:
        with mock.patch.object(core, "utc_now_ms", new=lambda: now_ms):
            with mock.patch.object(core.time, "sleep", new=lambda _: None):
                # First order (entry)
                slot1 = gateway._reserve_exchange_order_slot(wait_for_cooldown=True)
                slots.append(slot1)
                # Cancel (also reserves a slot)
                slot2 = gateway._reserve_exchange_order_slot(wait_for_cooldown=True)
                slots.append(slot2)
                # Second order (exit, wait_for_cooldown=False)
                slot3 = gateway._reserve_exchange_order_slot(wait_for_cooldown=False)
                slots.append(slot3)
    except Exception as exc:
        errors.append(exc)

    no_errors = len(errors) == 0
    expected_slots = [now_ms + gap_ms, now_ms + 2 * gap_ms, now_ms + 3 * gap_ms]
    slots_match = slots == expected_slots
    expected_last = expected_slots[-1]
    last_match = gateway._last_exchange_order_ms == expected_last

    passed = no_errors and slots_match and last_match

    print(f"RESULT::test_cancel_preserves_future_slots_no_errors_{'PASS' if no_errors else 'FAIL'} | errors={errors}")
    print(f"RESULT::test_cancel_preserves_future_slots_slots_match_{'PASS' if slots_match else 'FAIL'} | expected={expected_slots} actual={slots}")
    print(f"RESULT::test_cancel_preserves_future_slots_last_ms_match_{'PASS' if last_match else 'FAIL'} | expected={expected_last} actual={gateway._last_exchange_order_ms}")
    print(f"RESULT::test_cancel_preserves_future_slots_complete_{'PASS' if passed else 'FAIL'}")

    return passed


def test_concurrent_cooldown_wakeup():
    """Test 5: Multiple threads waking from cooldown don't collide."""
    print("RESULT::test_concurrent_cooldown_wakeup_start")
    worker_count = 16
    gap_ms = 100
    start_ms = 100000
    cooldown_ms = 2000

    gateway = create_gateway()
    gateway._last_exchange_order_ms = start_ms
    gateway._exchange_rate_limit_cooldown_until_ms = start_ms + cooldown_ms

    start_barrier = threading.Barrier(worker_count + 1)
    slots = []
    slots_lock = threading.Lock()
    errors = []

    clock_ms = {"value": start_ms}
    clock_lock = threading.Lock()

    def virtual_now_ms():
        with clock_lock:
            return clock_ms["value"]

    def virtual_sleep(seconds):
        with clock_lock:
            clock_ms["value"] += int(seconds * 1000)

    def worker():
        try:
            start_barrier.wait(timeout=3)
            with mock.patch.object(core, "utc_now_ms", new=virtual_now_ms):
                with mock.patch.object(core.time, "sleep", new=virtual_sleep):
                    slot = gateway._reserve_exchange_order_slot(wait_for_cooldown=True)
            with slots_lock:
                slots.append(slot)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(worker_count)]

    for t in threads:
        t.start()
    start_barrier.wait(timeout=3)
    for t in threads:
        t.join(timeout=15)

    all_finished = all(not t.is_alive() for t in threads)
    no_errors = len(errors) == 0

    expected_slots = [start_ms + cooldown_ms + i * gap_ms for i in range(worker_count)]
    slots_match = slots == expected_slots
    expected_last = expected_slots[-1]
    last_match = gateway._last_exchange_order_ms == expected_last

    passed = all_finished and no_errors and slots_match and last_match

    print(f"RESULT::test_concurrent_cooldown_wakeup_all_finished_{'PASS' if all_finished else 'FAIL'}")
    print(f"RESULT::test_concurrent_cooldown_wakeup_no_errors_{'PASS' if no_errors else 'FAIL'} | errors={errors}")
    print(f"RESULT::test_concurrent_cooldown_wakeup_slots_match_{'PASS' if slots_match else 'FAIL'} | expected={expected_slots} actual={slots}")
    print(f"RESULT::test_concurrent_cooldown_wakeup_last_ms_match_{'PASS' if last_match else 'FAIL'} | expected={expected_last} actual={gateway._last_exchange_order_ms}")
    print(f"RESULT::test_concurrent_cooldown_wakeup_complete_{'PASS' if passed else 'FAIL'}")

    return passed


def main():
    """Run all tests and exit with non-zero if any invariant is violated."""
    print("RESULT::slot_pacing_suite_start")

    all_passed = True

    if not test_concurrent_exact_spacing():
        all_passed = False

    if not test_cooldown_then_spacing():
        all_passed = False

    if not test_exit_bypasses_cooldown():
        all_passed = False

    if not test_cancel_preserves_future_slots():
        all_passed = False

    if not test_concurrent_cooldown_wakeup():
        all_passed = False

    print(f"RESULT::slot_pacing_suite_complete_{'ALL_PASS' if all_passed else 'SOME_FAIL'}")

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()