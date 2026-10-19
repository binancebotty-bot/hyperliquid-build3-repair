"""Offline regression tests for exchange order slot reservation and cooldown pacing."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
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


class FakeExchange:
    def __init__(self):
        self.calls = []
        self._lock = threading.Lock()

    def order(self, *args, **kwargs):
        with self._lock:
            self.calls.append((args, kwargs))
        return {"status": "ok"}


def sender_gateway():
    gateway = core.SenderGateway.__new__(core.SenderGateway)
    gateway._exchange_order_lock = threading.Lock()
    gateway._last_exchange_order_ms = 0
    gateway._exchange_rate_limit_cooldown_until_ms = 0
    gateway.sender_key_invalid = ""
    gateway._note_sender_key_rejection = lambda response: None
    return gateway


class SlotReservationPacingTests(unittest.TestCase):
    def test_concurrent_workers_reserve_separate_slots_before_waiting(self):
        gap_ms = 4000
        gateway = sender_gateway()
        initial_slot_ms = core.utc_now_ms() + 10000
        gateway._last_exchange_order_ms = initial_slot_ms
        exchange = FakeExchange()
        first_sleep = threading.Event()
        second_sleep = threading.Event()
        release_sleeps = threading.Event()
        sleep_calls = []
        sleep_calls_lock = threading.Lock()
        errors = []

        def controlled_sleep(delay_seconds):
            with sleep_calls_lock:
                sleep_calls.append(delay_seconds)
                if len(sleep_calls) == 1:
                    first_sleep.set()
                elif len(sleep_calls) == 2:
                    second_sleep.set()
            release_sleeps.wait(timeout=3)

        def place_order():
            try:
                gateway._place_order(exchange, "BTC", True, 1.0, 100.0, "Ioc", False)
            except Exception as exc:  # surfaced in the main test thread
                errors.append(exc)

        threads = [threading.Thread(target=place_order) for _ in range(2)]
        with mock.patch.dict(os.environ, {"HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": str(gap_ms)}):
            with mock.patch.object(core.time, "sleep", new=controlled_sleep):
                try:
                    threads[0].start()
                    self.assertTrue(first_sleep.wait(timeout=1), "first worker did not wait for its reserved slot")
                    threads[1].start()
                    self.assertTrue(
                        second_sleep.wait(timeout=1),
                        "second worker could not reserve a slot while the first waited",
                    )
                    reserved_through_ms = gateway._last_exchange_order_ms
                finally:
                    release_sleeps.set()
                    for thread in threads:
                        if thread.ident is not None:
                            thread.join(timeout=3)

        self.assertTrue(all(not thread.is_alive() for thread in threads), "order worker thread did not finish")
        self.assertEqual(errors, [])
        self.assertGreaterEqual(reserved_through_ms, initial_slot_ms + 2 * gap_ms)
        self.assertEqual(len(exchange.calls), 2)

    def test_rate_limit_cooldown_is_a_reserved_slot_lower_bound(self):
        gateway = sender_gateway()
        now_ms = core.utc_now_ms()
        gateway._last_exchange_order_ms = now_ms
        cooldown_until_ms = now_ms + 5000
        gateway._exchange_rate_limit_cooldown_until_ms = cooldown_until_ms
        exchange = FakeExchange()
        sleeps = []

        with mock.patch.dict(os.environ, {"HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "250"}):
            with mock.patch.object(core.time, "sleep", new=lambda seconds: sleeps.append(seconds)):
                gateway._place_order(exchange, "BTC", False, 1.0, 100.0, "Ioc", True)

        self.assertGreaterEqual(gateway._last_exchange_order_ms, cooldown_until_ms)
        self.assertTrue(sleeps, "cooldown slot should make the sender wait before exchange.order")
        self.assertEqual(len(exchange.calls), 1)


if __name__ == "__main__":
    unittest.main()
