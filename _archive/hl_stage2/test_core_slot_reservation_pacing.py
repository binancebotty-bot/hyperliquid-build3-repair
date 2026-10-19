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
                self.condition.wait(timeout=3)


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
    def test_32_workers_release_slot_lock_before_sleeping(self):
        worker_count = 32
        gateway = sender_gateway()
        object.__setattr__(gateway, "_last_exchange_order_ms", core.utc_now_ms() + 10000)
        exchange = FakeExchange()
        start = threading.Barrier(worker_count + 1)
        sleepers_ready = threading.Event()
        sleep_lock = threading.Lock()
        sleep_calls = []
        sleep_timeouts = []
        errors = []

        def hold_sleep_until_all_workers_arrive(delay_seconds):
            with sleep_lock:
                sleep_calls.append(delay_seconds)
                if len(sleep_calls) == worker_count:
                    sleepers_ready.set()
            if not sleepers_ready.wait(timeout=3):
                sleep_timeouts.append(True)

        def place_order():
            try:
                start.wait(timeout=3)
                gateway._place_order(exchange, "BTC", True, 1.0, 100.0, "Ioc", False)
            except Exception as exc:  # surfaced in the main test thread
                errors.append(exc)

        threads = [threading.Thread(target=place_order) for _ in range(worker_count)]
        with mock.patch.dict(os.environ, {"HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "100"}):
            with mock.patch.object(core.time, "sleep", new=hold_sleep_until_all_workers_arrive):
                for thread in threads:
                    thread.start()
                start.wait(timeout=3)
                for thread in threads:
                    thread.join(timeout=4)

        self.assertTrue(all(not thread.is_alive() for thread in threads), "order worker thread did not finish")
        self.assertEqual(errors, [])
        self.assertEqual(sleep_timeouts, [], "a sender held the slot lock while waiting")
        self.assertEqual(len(sleep_calls), worker_count)
        self.assertTrue(all(delay > 0 for delay in sleep_calls))
        self.assertEqual(len(gateway.slot_reservations), worker_count)
        slot_gaps = [right - left for left, right in zip(gateway.slot_reservations, gateway.slot_reservations[1:])]
        self.assertTrue(all(gap >= 100 for gap in slot_gaps), f"reserved slot gaps were {slot_gaps}")
        self.assertEqual(len(exchange.calls), worker_count)

    def test_cooldown_slots_and_calls_keep_exact_spacing_for_32_orders(self):
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
                gateway._place_order(exchange, "BTC", False, 1.0, 100.0, "Ioc", True)
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
        self.assertEqual(len(sleeps), worker_count, "count of orders waiting behind cooldown sleep must equal orders")
        self.assertTrue(all(seconds > 0 for seconds in sleeps), "every order should wait behind the active cooldown")
        self.assertEqual(len(exchange.calls), worker_count)
        call_times = [call[0] for call in exchange.calls]
        call_gaps_ms = [right - left for left, right in zip(call_times, call_times[1:])]
        self.assertTrue(
            all(abs(gap - gap_ms) <= 2 for gap in call_gaps_ms),
            f"call gaps must stay within 2 ms of {gap_ms}: {call_gaps_ms}",
        )


if __name__ == "__main__":
    unittest.main()

