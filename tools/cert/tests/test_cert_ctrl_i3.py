#!/usr/bin/env python3
"""CTRL-I3: Git is durable truth; chat is an interface.

Notification channels (Telegram/SMS/email/chat/browser) can never acknowledge
or authorize a control message. Only the canonical control surface can.

Drives: company_transport/resilience/health.py::is_authority_channel
        company_transport/resilience/paths.py::ControlTransport.acknowledge
"""
from __future__ import annotations

import os
import sys
import unittest

MC_ROOT = os.environ.get("MC_ROOT", "C:/Users/wigmore/richard-mission-control-template")
if MC_ROOT not in sys.path:
    sys.path.insert(0, MC_ROOT)

from company_transport.resilience.health import is_authority_channel  # noqa: E402
from company_transport.resilience.paths import ControlPath, ControlTransport  # noqa: E402
from company_transport.resilience.spool import DurableSpool  # noqa: E402
from company_transport.state.idempotency import IdempotencyStore  # noqa: E402
from company_transport.resilience.health import TransportHealthState  # noqa: E402

PROJECT = "binancebotty-bot/richard-mission-control-template"


class TestGitIsDurableTruth(unittest.TestCase):
    def test_notification_channels_cannot_acknowledge(self):
        for channel in ("telegram", "notification", "notify", "sms", "email", "chat", "browser"):
            self.assertFalse(is_authority_channel(channel), f"{channel} must not be authority")

    def test_authority_channel_can_acknowledge(self):
        self.assertTrue(is_authority_channel("github"))
        self.assertTrue(is_authority_channel("control-surface"))

    def test_transport_acknowledge_rejects_notification(self):
        """Non-vacuous negative: ControlTransport.acknowledge returns False for notifications."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            spool = DurableSpool(os.path.join(tmp, "spool"))
            idem = IdempotencyStore(os.path.join(tmp, "idem.db"))
            health = TransportHealthState(project_id=PROJECT)
            primary = ControlPath("PRIMARY", name="primary")
            secondary = ControlPath("SECONDARY", name="secondary")
            transport = ControlTransport(
                project_id=PROJECT,
                primary=primary,
                secondary=secondary,
                spool=spool,
                idempotency=idem,
                health=health,
            )
            self.assertFalse(transport.acknowledge("m-1", channel="telegram"))
            self.assertFalse(transport.acknowledge("m-1", channel="email"))
            self.assertTrue(transport.acknowledge("m-1", channel="github"))
            idem.close()  # release SQLite handle before temp cleanup


if __name__ == "__main__":
    unittest.main(verbosity=2)
