#!/usr/bin/env python3
"""CTRL-I4: Event push is the normal delivery trigger.

A GitHub push to refs/heads/control-mailbox carrying valid envelopes is the
normal delivery path. The push gate selects and orders envelopes for consumption.

Drives: control_mailbox/push_gate.py::decide_push
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


def _envelope_text(message_id="m-1", project=PROJECT, target="hermes:implementation-owner",
                   created="2026-10-05T10:00:00Z", payload="do the thing"):
    return json.dumps(build_envelope(
        project_id=project,
        from_logical_role="gpt:reviewer-controller",
        target_logical_role=target,
        message_id=message_id,
        type="DIRECTIVE",
        payload=payload,
        sequence=1,
        created_at_utc=created,
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


class TestEventPushIsNormalTrigger(unittest.TestCase):
    def test_valid_push_to_control_branch_accepted(self):
        p = "control_mailbox/inbox/20261005T100000Z-m-1.json"
        d = decide_push(_push([p]), project_id=PROJECT,
                        file_reader=_reader_for({p: _envelope_text()}))
        self.assertTrue(d.accepted)
        self.assertEqual(d.count, 1)
        self.assertEqual(d.envelopes[0].message_id, "m-1")

    def test_multi_file_push_deterministic_order(self):
        paths = ["control_mailbox/inbox/b.json", "control_mailbox/inbox/a.json",
                 "control_mailbox/inbox/c.json"]
        mapping = {paths[0]: _envelope_text("m-b"),
                   paths[1]: _envelope_text("m-a"),
                   paths[2]: _envelope_text("m-c")}
        d1 = decide_push(_push(paths), project_id=PROJECT, file_reader=_reader_for(mapping))
        d2 = decide_push(_push(list(reversed(paths))), project_id=PROJECT, file_reader=_reader_for(mapping))
        self.assertTrue(d1.accepted and d2.accepted)
        self.assertEqual([e.message_id for e in d1.envelopes], ["m-a", "m-b", "m-c"])
        self.assertEqual([e.message_id for e in d1.envelopes],
                         [e.message_id for e in d2.envelopes])

    def test_wrong_ref_rejected(self):
        """Non-vacuous negative: push to wrong branch must not trigger."""
        p = "control_mailbox/inbox/a.json"
        d = decide_push(_push([p], ref="refs/heads/main"), project_id=PROJECT,
                        file_reader=_reader_for({p: _envelope_text()}))
        self.assertFalse(d.accepted)
        self.assertEqual(d.reason, "WRONG_REF")

    def test_product_push_never_wakes(self):
        d = decide_push(_push(["src/app.py", "README.md"]), project_id=PROJECT,
                        file_reader=_reader_for({}))
        self.assertFalse(d.accepted)
        self.assertEqual(d.reason, "NO_CONTROL_FILES")


if __name__ == "__main__":
    unittest.main(verbosity=2)
