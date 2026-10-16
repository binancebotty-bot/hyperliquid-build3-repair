#!/usr/bin/env python3
"""CTRL-I1: Authority is logical-role provenance.

A message physically posted on any board retains the provenance of its actual
author; the board never rewrites authority.

Drives: company_transport/control/surfaces.py::ControlPlane.adjudicate_post
"""
from __future__ import annotations

import os
import sys
import unittest

# Make the control-plane code importable
MC_ROOT = os.environ.get(
    "MC_ROOT",
    "C:/Users/wigmore/richard-mission-control-template",
)
if MC_ROOT not in sys.path:
    sys.path.insert(0, MC_ROOT)

from company_transport.control.surfaces import (  # noqa: E402
    ControlPlane,
    ControlPlaneViolation,
    ControlSurfaceMap,
)

PROJECT = "binancebotty-bot/richard-mission-control-template"


class TestAuthorityFromProvenance(unittest.TestCase):
    def setUp(self):
        self.surface_map = ControlSurfaceMap.standard(PROJECT, "richard-mission-control-template")
        self.plane = ControlPlane(self.surface_map)

    def test_authority_comes_from_author_not_surface(self):
        """A message from gpt:reviewer-controller on Issue #1 retains that role."""
        result = self.plane.adjudicate_post(
            project_id=PROJECT,
            issue_number=1,
            from_logical_role="gpt:reviewer-controller",
            target_logical_role="hermes:implementation-owner",
        )
        self.assertTrue(result.allowed, result.reason)
        self.assertEqual(result.effective_authority_role, "gpt:reviewer-controller")

    def test_authority_not_rewritten_by_surface(self):
        """Same author on a DIFFERENT surface still has the same provenance."""
        result = self.plane.adjudicate_post(
            project_id=PROJECT,
            issue_number=3,  # Architect surface
            from_logical_role="gpt:project-architect",
            target_logical_role="hermes:implementation-owner",
        )
        self.assertTrue(result.allowed, result.reason)
        self.assertEqual(result.effective_authority_role, "gpt:project-architect")

    def test_wrong_role_for_surface_fails_closed(self):
        """A message from the wrong role on a surface fails closed."""
        result = self.plane.adjudicate_post(
            project_id=PROJECT,
            issue_number=1,
            from_logical_role="gpt:project-architect",  # Not the bound role for #1
            target_logical_role="hermes:implementation-owner",
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, ControlPlaneViolation.WRONG_ROLE_FOR_SURFACE)
        # Authority is still the author's, not the surface's
        self.assertEqual(result.effective_authority_role, "gpt:project-architect")

    def test_missing_provenance_fails_closed(self):
        result = self.plane.adjudicate_post(
            project_id=PROJECT,
            issue_number=1,
            from_logical_role=None,
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, ControlPlaneViolation.MISSING_PROVENANCE)
        self.assertEqual(result.effective_authority_role, "UNKNOWN_PROVENANCE")

    def test_cross_project_fails_closed(self):
        result = self.plane.adjudicate_post(
            project_id="someone/else",
            issue_number=1,
            from_logical_role="gpt:reviewer-controller",
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.code, ControlPlaneViolation.CROSS_PROJECT)


if __name__ == "__main__":
    unittest.main(verbosity=2)
