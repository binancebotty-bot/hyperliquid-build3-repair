#!/usr/bin/env python3
"""R96 mutant-killing boundary regressions for the real _final_close_proof body.

No network, no exchange, no live engine import or send. The function AST is
extracted from the pinned same-tree Core, preserving the actual implementation.
Run: python3.11 -m unittest -v test_r96_mutant_guards.py
"""
import ast
import copy
from pathlib import Path
import unittest

CORE = Path(__file__).with_name("HL_Live_Copy_Service_Core.py")


def final_proof_from_source():
    tree = ast.parse(CORE.read_text(encoding="utf-8-sig"), filename=str(CORE))
    owners = [n for n in tree.body
              if isinstance(n, ast.ClassDef) and n.name == "SenderGateway"]
    if len(owners) != 1:
        raise AssertionError("Expected exactly one SenderGateway class")
    methods = [n for n in owners[0].body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and n.name == "_final_close_proof"]
    if len(methods) != 1 or not isinstance(methods[0], ast.FunctionDef):
        raise AssertionError("Expected exactly one synchronous _final_close_proof")
    node = copy.deepcopy(methods[0])
    node.decorator_list = []
    # Strip type annotations solely from the test's isolated AST namespace;
    # the executable function BODY is never modified or emulated.
    node.returns = None
    for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
        arg.annotation = None
    namespace = {"POSITION_EPSILON": 1e-9}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 str(CORE), "exec"), namespace)
    return namespace["_final_close_proof"]


class MutantGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proof = staticmethod(final_proof_from_source())

    def test_mb_wire_proof_reuses_original_ledger_lag_regime(self):
        calls = []

        class Gateway:
            def _close_wire_plan(self, intent, size, dec, timing=None,
                                 ledger_may_lag=False):
                calls.append((size, dec, ledger_may_lag))
                if not ledger_may_lag:
                    return False, 0.0, "CLOSE_PROOF_HOLD_WRONG_REGIME"
                return True, size, ""

        timing = {"close_verified_sz_decimals": 3, "close_ledger_may_lag": True}
        result = self.proof(Gateway(), object(), 2.0, True, timing)
        self.assertEqual(calls, [(2.0, 3, True)])
        self.assertEqual(result, "")

    def test_mc_wire_proof_rejects_reduce_only_change(self):
        calls = []

        class Gateway:
            def _close_wire_plan(self, intent, size, dec, timing=None,
                                 ledger_may_lag=False):
                calls.append(True)
                return False, size, ""

        result = self.proof(Gateway(), object(), 2.0, True,
                            {"close_verified_sz_decimals": 3})
        self.assertEqual(calls, [True])
        self.assertEqual(result, "CLOSE_PROOF_HOLD_WIRE_SIZE_OR_RO_CHANGED")

    def test_mc_wire_proof_rejects_size_change(self):
        class Gateway:
            def _close_wire_plan(self, intent, size, dec, timing=None,
                                 ledger_may_lag=False):
                return True, size + 0.5, ""

        self.assertEqual(
            self.proof(Gateway(), object(), 2.0, True,
                       {"close_verified_sz_decimals": 3}),
            "CLOSE_PROOF_HOLD_WIRE_SIZE_OR_RO_CHANGED")


if __name__ == "__main__":
    unittest.main()
