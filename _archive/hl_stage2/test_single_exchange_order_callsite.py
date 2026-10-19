"""Regression guard for the single authoritative exchange.order call site."""

import ast
import unittest
from pathlib import Path


STAGE2 = Path(__file__).resolve().parent
EXPECTED_FILE = "HL_Live_Copy_Service_Core.py"


def exchange_order_calls():
    calls = []
    for source_path in sorted(STAGE2.rglob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8-sig"), filename=str(source_path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "order"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "exchange"
            ):
                calls.append((source_path.relative_to(STAGE2), node.lineno))
    return calls


class SingleExchangeOrderCallsiteTest(unittest.TestCase):
    def test_only_core_has_the_exchange_order_callsite(self):
        calls = exchange_order_calls()
        self.assertEqual(
            len(calls),
            1,
            "expected exactly one exchange.order(...) call site under "
            f"{STAGE2}; found {calls}",
        )
        self.assertEqual(
            calls[0][0].name,
            EXPECTED_FILE,
            f"exchange.order(...) must remain owned by {EXPECTED_FILE}; found {calls}",
        )


if __name__ == "__main__":
    unittest.main()
