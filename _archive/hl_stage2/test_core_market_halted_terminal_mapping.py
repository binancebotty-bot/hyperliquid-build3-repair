"""Regression for market-halted rejected orders on the production classification path.

The test compiles the unchanged production parser and classifier functions from
HL_Live_Copy_Service_Core.py. It fails on integration/r1-ffcc0b0 because the
ORDER_REJECTED terminal mappings lose MARKET_HALTED for ENTRY and ADD.
No network, signer or exchange orders.
"""
import ast
import json
from pathlib import Path
from typing import Any

import pytest

CORE = Path(__file__).with_name("HL_Live_Copy_Service_Core.py")


@pytest.fixture(scope="module")
def real_classifiers():
    tree = ast.parse(CORE.read_text(encoding="utf-8-sig"))
    names = {"_response_text", "classify_reject_category", "classify_terminal_state"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in names]
    assert {node.name for node in nodes} == names
    owner = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                 and node.name == "SenderGateway")
    parse = next(node for node in owner.body if isinstance(node, ast.FunctionDef)
                 and node.name == "_parse_hl_response")
    parser = ast.ClassDef(name="GatewayParser", bases=[], keywords=[],
                          body=[parse], decorator_list=[])
    module = ast.fix_missing_locations(ast.Module(body=nodes + [parser], type_ignores=[]))
    ns = {"Any": Any, "json": json}
    exec(compile(module, str(CORE), "exec"), ns)
    return ns


@pytest.mark.parametrize("lifecycle", ["ENTRY", "ADD"])
def test_halted_exchange_reply_retains_halted_terminal_category(real_classifiers, lifecycle):
    response = {"status": "ok", "response": {"data": {
        "statuses": [{"error": "Trading is halted."}]
    }}}
    ok, status, oid, error = real_classifiers["GatewayParser"]._parse_hl_response(response)
    assert (ok, status, oid) == (False, "ORDER_REJECTED", "")
    category = real_classifiers["classify_reject_category"](error, response)
    assert category == "MARKET_HALTED"
    terminal = real_classifiers["classify_terminal_state"](
        status, category, lifecycle, exchange_called=True)
    assert terminal == "SKIPPED_MARKET_HALTED"


@pytest.mark.parametrize(
    ("lifecycle", "expected"),
    [("ENTRY", "MISSED_ENTRY_EXCHANGE_REJECTED_UNKNOWN"),
     ("ADD", "MISSED_ADD_EXCHANGE_REJECTED_UNKNOWN")],
)
def test_ordinary_reject_keeps_existing_mapping(real_classifiers, lifecycle, expected):
    response = {"status": "ok", "response": {"data": {
        "statuses": [{"error": "Ordinary exchange refusal"}]
    }}}
    ok, status, _, error = real_classifiers["GatewayParser"]._parse_hl_response(response)
    assert ok is False
    assert status == "ORDER_REJECTED"
    category = real_classifiers["classify_reject_category"](error, response)
    assert category == "EXCHANGE_REJECTED_UNKNOWN"
    terminal = real_classifiers["classify_terminal_state"](
        status, category, lifecycle, exchange_called=True)
    assert terminal == expected
