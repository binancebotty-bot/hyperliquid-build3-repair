"""R4 production-wire no-call proof: exact SenderGateway._place_order and
_reserve_margin_rest_at_wire method AST, with an exchange spy instead of SDK.

No engine startup, signing key, account, or network. Run:
python -m pytest -q _archive/hl_stage2/test_core_r4_physical_order_no_call.py
"""
import ast
import threading
import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional

import pytest

CORE = Path(__file__).with_name("HL_Live_Copy_Service_Core.py")


class ExchangeSpy:
    def __init__(self):
        self.orders = []

    def order(self, *args, **kwargs):
        self.orders.append((args, kwargs))
        return {"status": "ok"}


def build_sender(root, withdrawable):
    source = CORE.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    owner = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "SenderGateway")
    chosen = [x for x in owner.body if isinstance(x, ast.FunctionDef)
              and x.name in {"_place_order", "_place_order_impl", "_reserve_margin_rest_at_wire"}]
    assert {x.name for x in chosen} == {"_place_order", "_place_order_impl", "_reserve_margin_rest_at_wire"}
    gateway_class = ast.ClassDef(name="Gateway", bases=[], keywords=[], body=chosen, decorator_list=[])
    gateway_class.body.insert(0, ast.parse("_wire_cap_lock = threading.RLock()").body[0])
    for _stub in ("_wire_entry_exposure_block = lambda self, *a, **k: ''",
                  "_master_gate_reason = lambda self, *a, **k: ''",
                  "_reserve_exchange_order_slot = lambda self, **k: 0"):
        gateway_class.body.insert(0, ast.parse(_stub).body[0])
    module = ast.fix_missing_locations(ast.Module(body=[gateway_class], type_ignores=[]))

    class XNet:
        @staticmethod
        def post_many(*unused):
            return [{"ok": True, "data": {"withdrawable": str(withdrawable)}}]

    updates = []
    events = []
    env = {
        "__builtins__": __builtins__, "Any": Any, "Callable": Callable,
        "Dict": Dict, "Optional": Optional, "Intent": object,
        "sqlite3": sqlite3, "json": json, "hashlib": hashlib, "math": math,
        "time": time, "threading": threading, "AUDIT_DIR": Path(root),
        "FOLLOWER_NETWORK": "testnet", "MAINNET_ORDERS_CONFIRMED": False,
        "USER_WALLET": "0x" + "a" * 40,
        "normalise_wallet": lambda x: str(x).lower(),
        "classify_send_lifecycle": lambda i: i.reason,
        "utc_now_ms": lambda: 12345, "EXPOSURE_FETCHER": object(),
        "_XNET": XNet(), "HL_INFO_URL": "offline", "HTTP_TIMEOUT_SEC": 1,
        "_sender_lease_owned": lambda: True,
        "_sdk_cloid": lambda x: x,
        "_exchange_accepts_cloid": lambda x: False,
        "_open_orders_send_begin": lambda: events.append("begin"),
        "_open_orders_send_end": lambda: events.append("end"),
        "update_send_attempt_row": lambda *a, **k: updates.append((a, k)) or True,
        "log_error": lambda *args: events.append("error"),
        "PendingSendWriteFailed": type("PendingSendWriteFailed", (Exception,), {}),
        "PreWireNoCallFault": type("PreWireNoCallFault", (Exception,), {}),
    }
    exec(compile(module, str(CORE), "exec"), env)
    sender = env["Gateway"]()
    sender._master_gate_reason = lambda *a, **k: ""
    sender._reserve_exchange_order_slot = lambda **k: 12345
    sender._reduce_only_for_intent = lambda i: i.reason == "EXIT"
    sender._final_close_proof = lambda *a: ""
    sender._terminalise_pending_as_no_call = lambda *a: updates.append(("terminal", a))
    sender._gate_refusal_row = lambda *a: events.append("refusal")
    sender._note_sender_key_rejection = lambda *a: None
    sender._journal_authorised_close_refusal = lambda *a: events.append("close_refusal")
    return sender, updates, events


def make_intent(n, life="ENTRY"):
    return SimpleNamespace(intent_id=f"r4-{n}", reason=life,
                           reduce_only_intended=(life == "EXIT"),
                           fill=SimpleNamespace(coin="BTC"))


def send(sender, exchange, intent, pre_send):
    timing = {"margin_rest_physical_admission": intent.intent_id,
              "send_attempt_id": "attempt-" + intent.intent_id}
    response = sender._place_order(
        exchange, "BTC", True, 1.0, 70.0, "Gtc", False, timing=timing,
        started_key="order_started_ms", pre_send=pre_send, intent=intent,
        path="missed_entry_rest")
    return response, timing


def test_insufficient_collateral_suppresses_production_exchange_order(tmp_path):
    sender, updates, events = build_sender(tmp_path, withdrawable=0)
    exchange = ExchangeSpy()
    called = []
    intent = make_intent("insufficient")
    response, timing = send(sender, exchange, intent, lambda: called.append("pre_send") or "aid-1")
    assert called == ["pre_send"]  # gate is after write-ahead
    assert exchange.orders == []
    assert response["exchange_called"] is False
    assert response["terminal_state"] == "SEND_NOT_ATTEMPTED_MARGIN_REST_NO_COLLATERAL"
    assert timing.get("exchange_order_invoked") is not True
    assert "order_started_ms" not in timing
    assert ("terminal", ("attempt-" + intent.intent_id,
                          "SEND_NOT_ATTEMPTED_MARGIN_REST_NO_COLLATERAL",
                          "MARGIN_REST_PHYSICAL_COLLATERAL_OR_RESERVATION_HOLD")) in updates
    assert "begin" not in events


def test_existing_disk_reservation_suppresses_second_physical_order(tmp_path):
    sender, _, _ = build_sender(tmp_path, withdrawable=100)
    first = ExchangeSpy()
    result, timing = send(sender, first, make_intent("first"), lambda: "aid-first")
    assert result == {"status": "ok"}
    assert len(first.orders) == 1  # positive control: exact same production wire path
    assert timing["exchange_order_invoked"] is True
    # New instance reloads reservation from the SQLite file: no in-memory state.
    restarted, updates, _ = build_sender(tmp_path, withdrawable=100)
    second = ExchangeSpy()
    blocked, later_timing = send(restarted, second, make_intent("second"), lambda: "aid-second")
    assert second.orders == []
    assert blocked["exchange_called"] is False
    assert blocked["terminal_state"] == "SEND_NOT_ATTEMPTED_MARGIN_REST_NO_COLLATERAL"
    assert later_timing.get("exchange_order_invoked") is not True
    assert updates


def test_production_final_reservation_blocks_second_separate_intent(tmp_path):
    sender, _, _ = build_sender(tmp_path, withdrawable=100)
    spy = ExchangeSpy()
    first, _ = send(sender, spy, make_intent("one"), lambda: "aid-one")
    second, _ = send(sender, spy, make_intent("two"), lambda: "aid-two")
    assert first == {"status": "ok"}
    assert second["exchange_called"] is False
    assert len(spy.orders) == 1
