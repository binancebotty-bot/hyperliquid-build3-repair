#!/usr/bin/env python3
"""CTRL-I6: Deposit is not send; delivery is not consumption.

Observing an item (SEEN) never executes it. Consumption is a separate, monotonic
step that survives restart. Recovery consumes from high-water FORWARD.

Drives: company_transport/control/highwater.py::SurfaceHighWaterStore
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

MC_ROOT = os.environ.get("MC_ROOT", "C:/Users/wigmore/richard-mission-control-template")
if MC_ROOT not in sys.path:
    sys.path.insert(0, MC_ROOT)

from company_transport.control.highwater import (  # noqa: E402
    ConsumptionCode,
    SurfaceHighWaterStore,
)


class TestDepositNotSend(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = SurfaceHighWaterStore(os.path.join(self.tmp, "hw.json"))

    def test_observe_does_not_execute(self):
        """SEEN != CONSUMED: observing an item never executes it."""
        result = self.store.observe(1, "item-1", sequence=5, digest="abc")
        self.assertTrue(result)  # newly seen
        # But it's not consumed yet
        self.assertEqual(self.store.cursor(1), 0)
        self.assertEqual(self.store.unconsumed(1)[0]["item_id"], "item-1")

    def test_consume_after_observe_executes(self):
        self.store.observe(1, "item-1", sequence=5, digest="abc")
        result = self.store.consume(1, "item-1")
        self.assertEqual(result.code, ConsumptionCode.CONSUMED)
        self.assertTrue(result.semantic_execution)
        self.assertEqual(self.store.cursor(1), 5)

    def test_replay_never_reexecutes(self):
        """Non-vacuous negative: consuming twice must not re-execute."""
        self.store.observe(1, "item-1", sequence=5, digest="abc")
        r1 = self.store.consume(1, "item-1")
        r2 = self.store.consume(1, "item-1")
        self.assertTrue(r1.semantic_execution)
        self.assertEqual(r2.code, ConsumptionCode.ALREADY_CONSUMED)
        self.assertFalse(r2.semantic_execution)

    def test_consume_unknown_item_fails(self):
        """Non-vacuous negative: consuming an item that was never seen fails."""
        result = self.store.consume(1, "never-seen")
        self.assertEqual(result.code, ConsumptionCode.UNKNOWN_ITEM)
        self.assertFalse(result.semantic_execution)

    def test_recovery_resumes_from_highwater_forward(self):
        """Recovery consumes from high-water FORWARD, never re-walks history."""
        self.store.observe(1, "item-1", sequence=5, digest="abc")
        self.store.observe(1, "item-2", sequence=10, digest="def")
        self.store.consume(1, "item-1")
        self.store.consume(1, "item-2")
        # Recovery cursor should be past both
        self.assertEqual(self.store.resume_from(1), 11)
        # No unconsumed items
        self.assertEqual(self.store.unconsumed(1), [])

    def test_restart_survives_consumption(self):
        """Consumption is durable across process restart."""
        self.store.observe(1, "item-1", sequence=5, digest="abc")
        self.store.consume(1, "item-1")
        # Simulate restart: new store instance, same file
        store2 = SurfaceHighWaterStore(os.path.join(self.tmp, "hw.json"))
        result = store2.consume(1, "item-1")
        self.assertEqual(result.code, ConsumptionCode.ALREADY_CONSUMED)
        self.assertFalse(result.semantic_execution)


if __name__ == "__main__":
    unittest.main(verbosity=2)
