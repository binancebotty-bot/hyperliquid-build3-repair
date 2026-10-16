#!/usr/bin/env python3
"""CTRL-I8: Explicit route/type contract.

Every control envelope must carry an explicit TYPE from the allowed set and
all required routing fields. The envelope schema is the contract.

Drives: control_mailbox/envelope.py::build_envelope + parse_envelope
"""
from __future__ import annotations

import json
import os
import sys
import unittest

MC_ROOT = os.environ.get("MC_ROOT", "C:/Users/wigmore/richard-mission-control-template")
if MC_ROOT not in sys.path:
    sys.path.insert(0, MC_ROOT)

from control_mailbox.envelope import (  # noqa: E402
    VALID_TYPES,
    EnvelopeError,
    build_envelope,
    parse_envelope,
)

PROJECT = "binancebotty-bot/richard-mission-control-template"


def _env(**kw):
    base = dict(
        project_id=PROJECT,
        from_logical_role="gpt:reviewer-controller",
        target_logical_role="hermes:implementation-owner",
        message_id="m-1",
        type="DIRECTIVE",
        payload="do the thing",
        sequence=1,
        created_at_utc="2026-10-05T10:00:00Z",
    )
    base.update(kw)
    return build_envelope(**base)


class TestExplicitRouteTypeContract(unittest.TestCase):
    def test_valid_type_accepted(self):
        for t in VALID_TYPES:
            env = _env(type=t)
            parsed = parse_envelope(json.dumps(env))
            self.assertEqual(parsed.get("TYPE"), t)

    def test_invalid_type_rejected(self):
        """Non-vacuous negative: type outside the contract must fail."""
        with self.assertRaises(EnvelopeError) as ctx:
            _env(type="SHOUT")
        self.assertIn("INVALID_TYPE", str(ctx.exception))

    def test_missing_message_id_rejected(self):
        """Non-vacuous negative: missing routing field must fail."""
        env = _env()
        del env["MESSAGE_ID"]
        with self.assertRaises(EnvelopeError) as ctx:
            parse_envelope(json.dumps(env))
        self.assertIn("MISSING_FIELDS", str(ctx.exception))

    def test_missing_project_id_rejected(self):
        env = _env()
        del env["PROJECT_ID"]
        with self.assertRaises(EnvelopeError) as ctx:
            parse_envelope(json.dumps(env))
        self.assertIn("MISSING_FIELDS", str(ctx.exception))

    def test_missing_target_role_rejected(self):
        env = _env()
        del env["TARGET_LOGICAL_ROLE"]
        with self.assertRaises(EnvelopeError) as ctx:
            parse_envelope(json.dumps(env))
        self.assertIn("MISSING_FIELDS", str(ctx.exception))

    def test_tampered_payload_fails_closed(self):
        """Non-vacuous negative: payload mutation breaks the digest."""
        env = _env()
        env["PAYLOAD"] = "tampered"
        with self.assertRaises(EnvelopeError) as ctx:
            parse_envelope(json.dumps(env))
        self.assertIn("DIGEST_MISMATCH", str(ctx.exception))

    def test_wrong_schema_version_rejected(self):
        env = _env()
        env["SCHEMA_VERSION"] = "other/v9"
        env["PAYLOAD_DIGEST"] = "sha256:forged"
        with self.assertRaises(EnvelopeError) as ctx:
            parse_envelope(json.dumps(env))
        self.assertIn("WRONG_SCHEMA", str(ctx.exception))

    def test_roundtrip_preserves_all_fields(self):
        env = _env(
            type="RESULT",
            directive_id="D-1",
            action_id="A-1",
            responds_to_message_id="m-0",
            binding_version=3,
        )
        parsed = parse_envelope(json.dumps(env))
        self.assertEqual(parsed.message_id, "m-1")
        self.assertEqual(parsed.target_role, "hermes:implementation-owner")
        self.assertEqual(parsed.source_role, "gpt:reviewer-controller")
        self.assertEqual(parsed.project_id, PROJECT)
        self.assertEqual(parsed.get("TYPE"), "RESULT")
        self.assertEqual(parsed.get("DIRECTIVE_ID"), "D-1")
        self.assertEqual(parsed.get("RESPONDS_TO_MESSAGE_ID"), "m-0")
        self.assertEqual(parsed.get("BINDING_VERSION"), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
