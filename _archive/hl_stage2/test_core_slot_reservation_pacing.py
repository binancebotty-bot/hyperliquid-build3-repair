"""Offline regression tests for exchange order slot reservation and cooldown pacing."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_TEST_AUDIT_DIR = tempfile.mkdtemp(prefix="slot_pacing_test_")
os.environ["HL_LIVE_AUDIT_DIR"] = _TEST_AUDIT_DIR
os.environ["HL_LIVE_ENV_FILE"] = str(Path(_TEST_AUDIT_DIR) / "none.env")
os.environ["HL_LEADER_NETWORK"] = "testnet"
os.environ["HL_FOLLOWER_NETWORK"] = "testnet"

import HL_Live_Copy_Service_Core as core  # noqa: E402


class RecordingSenderGateway(core.SenderGateway):
    def __setattr__(self, name, value):
        if name == "_last_exchange_order_ms" and hasattr(self, "slot_reservations"):
            self.slot_reservations.append(value)
        super().__setattr__(name, value)


class FakeExchange:
    def __init__(self, clock=None):
        self.calls = []
        self._lock = threading.Lock()
        self._clock = clock

    def order(self, *args, **kwargs):
        call_time = self._clock.now_ms() if self._clock else time.perf_counter_ns()
        with self._lock:
            self.calls.append((call_time, args, kwargs))
        return {"status": "ok"}

    def cancel(self, *args, **kwargs):
        with self._lock:
            self.cancels = getattr(self, "cancels", []) + [(args, kwargs)]
        return {"status": "ok"}


class VirtualClock:
    """Deterministic clock that releases concurrent sleeps at their reserved slot times."""

    def __init__(self, start_ms, expected_sleep_count):
        self.current_ms = start_ms
        self.expected_sleep_count = expected_sleep_count
        self.waiters = []
        self.condition = threading.Condition()

    def now_ms(self):
        with self.condition:
            return self.current_ms

    def sleep(self, delay_seconds):
        delay_ms = int(round(delay_seconds * 1000))
        deadline = time.monotonic() + 0.1
        with self.condition:
            waiter = {"target_ms": self.current_ms + delay_ms, "done": False}
            self.waiters.append(waiter)
            self.condition.notify_all()
            while True:
                if len(self.waiters) >= self.expected_sleep_count:
                    if waiter["target_ms"] <= self.current_ms:
                        waiter["done"] = True
                        self.condition.notify_all()
                        return
                    pending_targets = [item["target_ms"] for item in self.waiters if not item["done"]]
                    next_target = min(pending_targets)
                    if next_target > self.current_ms:
                        self.current_ms = next_target
                        self.condition.notify_all()
                        continue
                elif time.monotonic() >= deadline:
                    # Let a serialized baseline run complete so the negative control
                    # fails on its assertions instead of hanging behind the lock.
                    self.current_ms = max(self.current_ms, waiter["target_ms"])
                    waiter["done"] = True
                    self.condition.notify_all()
                    return
                remaining = max(0.0, deadline - time.monotonic())
                self.condition.wait(timeout=min(0.01, remaining))


def sender_gateway():
    gateway = RecordingSenderGateway.__new__(RecordingSenderGateway)
    gateway.slot_reservations = []
    gateway._exchange_order_lock = threading.Lock()
    object.__setattr__(gateway, "_last_exchange_order_ms", 0)
    gateway._exchange_rate_limit_cooldown_until_ms = 0
    gateway.sender_key_invalid = ""
    gateway._note_sender_key_rejection = lambda response: None
    return gateway


class SlotReservationPacingTests(unittest.TestCase):
    def test_32_workers_reserve_exactly_spaced_slots(self):
        worker_count = 32
        gap_ms = 100
        now_ms = 100000
        gateway = sender_gateway()
        object.__setattr__(gateway, "_last_exchange_order_ms", now_ms)
        exchange = FakeExchange()
        start = threading.Barrier(worker_count + 1)
        sleep_calls = []
        sleep_lock = threading.Lock()
        errors = []

        def record_sleep(delay_seconds):
            with sleep_lock:
                sleep_calls.append(delay_seconds)

        def place_order():
            try:
                start.wait(timeout=3)
                gateway._place_order(exchange, "BTC", True, 1.0, 100.0, "Ioc", False)
            except Exception as exc:  # surfaced in the main test thread
                errors.append(exc)

        threads = [threading.Thread(target=place_order) for _ in range(worker_count)]
        with mock.patch.dict(os.environ, {"HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": str(gap_ms)}):
            with mock.patch.object(core, "utc_now_ms", new=lambda: now_ms):
                with mock.patch.object(core.time, "sleep", new=record_sleep):
                    for thread in threads:
                        thread.start()
                    start.wait(timeout=3)
                    for thread in threads:
                        thread.join(timeout=4)

        self.assertTrue(all(not thread.is_alive() for thread in threads), "order worker thread did not finish")
        self.assertEqual(errors, [])
        self.assertEqual(len(sleep_calls), worker_count)
        self.assertTrue(all(delay > 0 for delay in sleep_calls))
        self.assertEqual(len(gateway.slot_reservations), worker_count)
        expected_slots = [now_ms + (index + 1) * gap_ms for index in range(worker_count)]
        self.assertEqual(gateway.slot_reservations, expected_slots, "all 32 integer slots must be exactly gap apart")
        self.assertEqual(len(exchange.calls), worker_count)

    def test_entry_cooldown_slots_and_calls_keep_exact_spacing_for_32_orders(self):
        worker_count = 32
        gap_ms = 100
        clock = VirtualClock(start_ms=100000, expected_sleep_count=worker_count)
        gateway = sender_gateway()
        object.__setattr__(gateway, "_last_exchange_order_ms", clock.now_ms())
        cooldown_until_ms = clock.now_ms() + 1000
        gateway._exchange_rate_limit_cooldown_until_ms = cooldown_until_ms
        exchange = FakeExchange(clock=clock)
        start = threading.Barrier(worker_count + 1)
        sleeps = []
        sleep_lock = threading.Lock()
        errors = []

        def record_virtual_sleep(seconds):
            with sleep_lock:
                sleeps.append(seconds)
            clock.sleep(seconds)

        def place_order():
            try:
                start.wait(timeout=3)
                gateway._place_order(exchange, "BTC", False, 1.0, 100.0, "Ioc", False)
            except Exception as exc:  # surfaced in the main test thread
                errors.append(exc)

        threads = [threading.Thread(target=place_order) for _ in range(worker_count)]
        with mock.patch.dict(os.environ, {"HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": str(gap_ms)}):
            with mock.patch.object(core, "utc_now_ms", new=clock.now_ms):
                with mock.patch.object(core.time, "sleep", new=record_virtual_sleep):
                    for thread in threads:
                        thread.start()
                    start.wait(timeout=3)
                    for thread in threads:
                        thread.join(timeout=5)

        self.assertTrue(all(not thread.is_alive() for thread in threads), "order worker thread did not finish")
        self.assertEqual(errors, [])
        self.assertEqual(len(gateway.slot_reservations), worker_count)
        expected_slots = [cooldown_until_ms + index * gap_ms for index in range(worker_count)]
        self.assertEqual(gateway.slot_reservations, expected_slots, "integer slot spacing must honor gap exactly")
        self.assertGreaterEqual(len(sleeps), worker_count, "cooldown and paced-slot waits should include every order")
        self.assertTrue(all(seconds > 0 for seconds in sleeps), "every recorded order wait should be positive")
        self.assertEqual(len(exchange.calls), worker_count)
        call_times = [call[0] for call in exchange.calls]
        call_gaps_ms = [right - left for left, right in zip(call_times, call_times[1:])]
        self.assertTrue(
            all(abs(gap - gap_ms) <= 2 for gap in call_gaps_ms),
            f"call gaps must stay within 2 ms of {gap_ms}: {call_gaps_ms}",
        )

    def test_cancel_between_orders_preserves_future_reserved_slots(self):
        now_ms = 100000
        gap_ms = 100
        gateway = sender_gateway()
        object.__setattr__(gateway, "_last_exchange_order_ms", now_ms)
        exchange = FakeExchange()

        with mock.patch.dict(os.environ, {"HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": str(gap_ms)}):
            with mock.patch.object(core, "utc_now_ms", new=lambda: now_ms):
                with mock.patch.object(core.time, "sleep", new=lambda _seconds: None):
                    gateway._place_order(exchange, "BTC", True, 1.0, 100.0, "Ioc", False)
                    gateway._cancel_order(exchange, "BTC", "123")
                    gateway._place_order(exchange, "BTC", False, 1.0, 100.0, "Ioc", True)

        self.assertEqual(
            gateway.slot_reservations,
            [now_ms + gap_ms, now_ms + 2 * gap_ms, now_ms + 3 * gap_ms],
            "cancel must consume its own future slot without moving the shared clock backward",
        )
        self.assertEqual(len(exchange.calls), 2)
        self.assertEqual(len(exchange.cancels), 1)

    def test_cancel_sleep_does_not_hold_slot_lock(self):
        gateway = sender_gateway()
        object.__setattr__(gateway, "_last_exchange_order_ms", 100000)
        sleep_started = threading.Event()
        release_sleep = threading.Event()
        errors = []

        def blocked_sleep(_seconds):
            sleep_started.set()
            release_sleep.wait(timeout=2)

        def cancel_order():
            try:
                gateway._cancel_order(FakeExchange(), "BTC", "123")
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=cancel_order)
        with mock.patch.dict(os.environ, {"HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "100"}):
            with mock.patch.object(core, "utc_now_ms", new=lambda: 100000):
                with mock.patch.object(core.time, "sleep", new=blocked_sleep):
                    worker.start()
                    self.assertTrue(sleep_started.wait(timeout=1), "cancel did not wait for its reserved slot")
                    acquired = gateway._exchange_order_lock.acquire(timeout=0.25)
                    if acquired:
                        gateway._exchange_order_lock.release()
                    release_sleep.set()
                    worker.join(timeout=2)

        self.assertFalse(worker.is_alive(), "cancel worker did not finish")
        self.assertEqual(errors, [])
        self.assertTrue(acquired, "cancel held the slot lock while sleeping")


if __name__ == "__main__":
    unittest.main()

