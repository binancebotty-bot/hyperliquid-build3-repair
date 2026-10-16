#!/usr/bin/env python3
"""CTRL-I7: One logical message, one semantic execution.

The same envelope seen via primary and secondary transport (or after a restart)
collapses to one execution; the same identity with a different digest fails closed.

Drives: company_transport/resilience/paths.py::ControlTransport.deliver
        company_transport/state/idempotency.py::IdempotencyStore
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

MC_ROOT = os.environ.get("MC_ROOT", "C:/Users/wigmore/richard-mission-control-template")
if MC_ROOT not in sys.path:
    sys.path.insert(0, MC_ROOT)

from company_transport.resilience.paths import (  # noqa: E402
    ControlPath,
    ControlTransport,
    PathKind,
    TransportCode,
)
from company_transport.resilience.spool import DurableSpool  # noqa: E402
from company_transport.state.idempotency import IdempotencyStore  # noqa: E402
from company_transport.resilience.health import TransportHealthState  # noqa: E402

PROJECT = "binancebotty-bot/richard-mission-control-template"


def _make_envelope(message_id="m-1", payload="do the thing"):
    return {
        "MESSAGE_ID": message_id,
        "PROJECT_ID": PROJECT,
        "TYPE": "DIRECTIVE",
        "PAYLOAD": payload,
        "PAYLOAD_DIGEST": "sha256:abc123",
    }


class TestOneMessageOneExecution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.spool = DurableSpool(os.path.join(self.tmp, "spool"))
        self.idem = IdempotencyStore(os.path.join(self.tmp, "idem.db"))
        self.health = TransportHealthState(project_id=PROJECT)
        self.primary = ControlPath("PRIMARY", name="primary")
        self.secondary = ControlPath("SECONDARY", name="secondary")
        self.transport = ControlTransport(
            project_id=PROJECT,
            primary=self.primary,
            secondary=self.secondary,
            spool=self.spool,
            idempotency=self.idem,
            health=self.health,
        )

    def test_first_delivery_executes(self):
        env = _make_envelope()
        result = self.transport.deliver(env)
        self.assertEqual(result.code, TransportCode.WRITTEN_PRIMARY)
        self.assertTrue(result.semantic_execution)

    def test_duplicate_delivery_never_reexecutes(self):
        """Non-vacuous negative: same envelope twice = one execution."""
        env = _make_envelope()
        r1 = self.transport.deliver(env)
        r2 = self.transport.deliver(env)
        self.assertTrue(r1.semantic_execution)
        self.assertEqual(r2.code, TransportCode.DEDUPED_ALREADY_CONSUMED)
        self.assertFalse(r2.semantic_execution)

    def test_same_identity_different_digest_fails_closed(self):
        """Non-vacuous negative: same MESSAGE_ID + different digest = CONFLICT."""
        env1 = _make_envelope(message_id="m-1", payload="original")
        env1["PAYLOAD_DIGEST"] = "sha256:aaa"
        env2 = _make_envelope(message_id="m-1", payload="tampered")
        env2["PAYLOAD_DIGEST"] = "sha256:bbb"
        r1 = self.transport.deliver(env1)
        self.assertTrue(r1.semantic_execution)
        r2 = self.transport.deliver(env2)
        self.assertEqual(r2.code, TransportCode.CONFLICT_FAIL_CLOSED)
        self.assertFalse(r2.semantic_execution)

    def test_cross_path_delivery_never_duplicates(self):
        """Same envelope via primary then secondary = one execution."""
        env = _make_envelope()
        r1 = self.transport.deliver(env)
        self.assertTrue(r1.semantic_execution)
        # Simulate secondary delivery of the same envelope
        r2 = self.transport.deliver(env)
        self.assertEqual(r2.code, TransportCode.DEDUPED_ALREADY_CONSUMED)
        self.assertFalse(r2.semantic_execution)

    def test_restart_survives_idempotency(self):
        """Non-vacuous negative: after restart, replay must not re-execute."""
        env = _make_envelope()
        self.transport.deliver(env)
        # Simulate restart: new transport, same idempotency store
        idem2 = IdempotencyStore(os.path.join(self.tmp, "idem.db"))
        health2 = TransportHealthState(project_id=PROJECT)
        transport2 = ControlTransport(
            project_id=PROJECT,
            primary=ControlPath("PRIMARY", name="primary"),
            secondary=ControlPath("SECONDARY", name="secondary"),
            spool=DurableSpool(os.path.join(self.tmp, "spool2")),
            idempotency=idem2,
            health=health2,
        )
        r2 = transport2.deliver(env)
        self.assertEqual(r2.code, TransportCode.DEDUPED_ALREADY_CONSUMED)
        self.assertFalse(r2.semantic_execution)


if __name__ == "__main__":
    unittest.main(verbosity=2)
