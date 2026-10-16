#!/usr/bin/env python3
"""CTRL-I5: Remote-ref absence must be proven.

A push is only authority-bearing if it targets exactly refs/heads/control-mailbox.
Any other ref (or absence of the ref) is transport noise and must not wake.

Drives: control_mailbox/push_gate.py::decide_push (WRONG_REF check)
"""
from __future__ import annotations

import json
import os
import sys
import unittest

MC_ROOT = os.environ.get("MC_ROOT", "C:/Users/wigmore/richard-mission-control-template")
if MC_ROOT not in sys.path:
    sys.path.insert(0, MC_ROOT)

from control_mailbox.envelope import build_envelope  # noqa: E402
from control_mailbox.push_gate import decide_push  # noqa: E402

PROJECT = "binancebotty-bot/richard-mission-control-template"


def _envelope_text(message_id="m-1", project=PROJECT):
    return json.dumps(build_envelope(
        project_id=project,
        from_logical_role="gpt:reviewer-controller",
        target_logical_role="hermes:implementation-owner",
        message_id=message_id,
        type="DIRECTIVE",
        payload="do the thing",
        sequence=1,
        created_at_utc="2026-10-05T10:00:00Z",
    ))


def _push(paths, *, ref="refs/heads/control-mailbox", repo=PROJECT, deleted=False):
    return {
        "ref": ref,
        "deleted": deleted,
        "repository": {"full_name": repo},
        "commits": [{"added": list(paths), "modified": []}],
    }


def _reader_for(mapping):
    def _read(path):
        return mapping.get(path)
    return _read


class TestRemoteRefAbsenceProven(unittest.TestCase):
    def test_correct_ref_accepted(self):
        p = "control_mailbox/inbox/a.json"
        d = decide_push(_push([p], ref="refs/heads/control-mailbox"),
                        project_id=PROJECT, file_reader=_reader_for({p: _envelope_text()}))
        self.assertTrue(d.accepted)

    def test_wrong_ref_rejected(self):
        """Non-vacuous negative: wrong ref must fail closed."""
        p = "control_mailbox/inbox/a.json"
        d = decide_push(_push([p], ref="refs/heads/main"),
                        project_id=PROJECT, file_reader=_reader_for({p: _envelope_text()}))
        self.assertFalse(d.accepted)
        self.assertEqual(d.reason, "WRONG_REF")

    def test_missing_ref_rejected(self):
        """Non-vacuous negative: absent ref must fail closed."""
        p = "control_mailbox/inbox/a.json"
        d = decide_push(_push([p], ref=""),
                        project_id=PROJECT, file_reader=_reader_for({p: _envelope_text()}))
        self.assertFalse(d.accepted)
        self.assertEqual(d.reason, "WRONG_REF")

    def test_deletion_rejected(self):
        """Non-vacuous negative: branch deletion is not authority."""
        p = "control_mailbox/inbox/a.json"
        d = decide_push(_push([p], deleted=True),
                        project_id=PROJECT, file_reader=_reader_for({p: _envelope_text()}))
        self.assertFalse(d.accepted)
        self.assertEqual(d.reason, "DELETION_NOT_AUTHORITY")

    def test_wrong_project_rejected(self):
        p = "control_mailbox/inbox/a.json"
        d = decide_push(_push([p], repo="someone/else"),
                        project_id=PROJECT, file_reader=_reader_for({p: _envelope_text()}))
        self.assertFalse(d.accepted)
        self.assertEqual(d.reason, "WRONG_PROJECT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
