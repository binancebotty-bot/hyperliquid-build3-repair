#!/usr/bin/env python3
"""CTRL-I2: One canonical project role channel each.

The four-surface topology is the company standard: Issue #1 = Operations,
#2 = Registry, #3 = Architect, #4 = MD. Each surface is bound to exactly one
logical role.

Drives: company_transport/control/surfaces.py::ControlSurfaceMap.standard + validate
"""
from __future__ import annotations

import os
import sys
import unittest

MC_ROOT = os.environ.get("MC_ROOT", "C:/Users/wigmore/richard-mission-control-template")
if MC_ROOT not in sys.path:
    sys.path.insert(0, MC_ROOT)

from company_transport.control.surfaces import (  # noqa: E402
    ControlSurface,
    ControlSurfaceMap,
    SurfaceClass,
)

PROJECT = "binancebotty-bot/richard-mission-control-template"


class TestCanonicalTopology(unittest.TestCase):
    def test_standard_topology_is_valid(self):
        m = ControlSurfaceMap.standard(PROJECT, "richard-mission-control-template")
        errors = m.validate()
        self.assertEqual(errors, [], f"Standard topology must be valid: {errors}")

    def test_exactly_one_surface_per_class(self):
        m = ControlSurfaceMap.standard(PROJECT, "richard-mission-control-template")
        for sc in SurfaceClass:
            nums = [n for n, s in m.surfaces.items() if s.surface_class == sc]
            self.assertEqual(len(nums), 1, f"{sc.value} must have exactly 1 surface")

    def test_surface_numbers_match_standard(self):
        m = ControlSurfaceMap.standard(PROJECT, "richard-mission-control-template")
        self.assertEqual(m.operations_surface(), 1)
        self.assertEqual(m.registry_surface(), 2)
        self.assertEqual(m.architect_surface(), 3)
        self.assertEqual(m.md_surface(), 4)

    def test_registry_does_not_accept_operational_mail(self):
        m = ControlSurfaceMap.standard(PROJECT, "richard-mission-control-template")
        registry = m.surface(2)
        self.assertIsNotNone(registry)
        self.assertFalse(registry.accepts_operational_mail)

    def test_duplicate_surface_class_fails_validation(self):
        """Non-vacuous negative: two surfaces with the same class must fail."""
        m = ControlSurfaceMap.standard(PROJECT, "richard-mission-control-template")
        # Corrupt: make issue #4 also OPERATIONS
        m.surfaces[4] = ControlSurface(4, SurfaceClass.OPERATIONS, "company:managing-director", 1, True)
        errors = m.validate()
        self.assertTrue(any("OPERATIONS" in e for e in errors), errors)

    def test_wrong_issue_number_fails_validation(self):
        """Non-vacuous negative: surface key must match issue_number."""
        m = ControlSurfaceMap.standard(PROJECT, "richard-mission-control-template")
        # Corrupt: rename key 3 -> 99
        m.surfaces[99] = m.surfaces.pop(3)
        errors = m.validate()
        self.assertTrue(any("key 99" in e or "issue_number" in e for e in errors), errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
