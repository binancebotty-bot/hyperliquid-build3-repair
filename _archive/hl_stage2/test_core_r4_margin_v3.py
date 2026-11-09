"""R4 v3: cross-process atomic reservation, stale pre-send proof, close isolation."""
import ast
import concurrent.futures
import json
import math
import multiprocessing as mp
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

CORE = Path(__file__).with_name("HL_Live_Copy_Service_Core.py")


def make_gateway(root, withdrawable):
    tree = ast.parse(CORE.read_text(encoding="utf-8-sig"))
    owner = next(n for n in tree.body
                 if isinstance(n, ast.ClassDef) and n.name == "SenderGateway")
    fn = next(n for n in owner.body
              if isinstance(n, ast.FunctionDef)
              and n.name == "_reserve_margin_rest_at_wire")
    mod = ast.fix_missing_locations(ast.Module(body=[
        ast.ClassDef(name="Gateway", bases=[], keywords=[],
                     body=[fn], decorator_list=[])], type_ignores=[]))
    class XNet:
        @staticmethod
        def post_many(fetcher, queries, url, timeout):
            return [{"ok": True, "data": {"withdrawable": str(withdrawable[0] if isinstance(withdrawable, list) else withdrawable)}}]
    env = dict(__builtins__=__builtins__, Intent=object, sqlite3=sqlite3, json=json, math=math,
               hashlib=__import__("hashlib"), AUDIT_DIR=Path(root),
               FOLLOWER_NETWORK="testnet", USER_WALLET="0x" + "a"*40,
               normalise_wallet=lambda v: str(v).lower(),
               utc_now_ms=lambda: 12345, _XNET=XNet(), EXPOSURE_FETCHER=object(),
               HL_INFO_URL="mock", HTTP_TIMEOUT_SEC=1,
               classify_send_lifecycle=lambda intent: intent.reason,
               log_error=lambda *args: None)
    exec(compile(mod, str(CORE), "exec"), env)
    return env["Gateway"]()


def intent(n, life="ENTRY"):
    return SimpleNamespace(intent_id=f"intent-{n}", reason=life,
        fill=SimpleNamespace(coin="BTC"))


def reserve(sender, entry, size, price):
    return sender._reserve_margin_rest_at_wire(
        entry, size, price, attempt_id="attempt-" + entry.intent_id,
        sdk_coin="BTC", is_buy=True, tif="Gtc", reduce_only=False,
        cloid="cloid-" + entry.intent_id)


def process_claim(args):
    root, n = args
    sender = make_gateway(root, 100)
    return reserve(sender, intent(n), 1.0, 70.0)


def test_parallel_processes_cannot_double_spend(tmp_path):
    # Separate spawned Python processes contend on the same SQLite database.
    ctx = mp.get_context("spawn")
    with ctx.Pool(2) as pool:
        winners = pool.map(process_claim, [(str(tmp_path), 1), (str(tmp_path), 2)])
    assert sum(winners) == 1
    assert list(tmp_path.glob("margin_rest_reservations_*.sqlite3"))


def test_restart_still_reserves_collateral(tmp_path):
    sender = make_gateway(tmp_path, 100)
    assert reserve(sender, intent(1), 1, 70)
    restarted = make_gateway(tmp_path, 100)
    assert not reserve(restarted, intent(2), 1, 70)
    assert not reserve(restarted, intent(1), 1, 70)


def test_no_collateral_and_close_not_admitted_as_entry(tmp_path):
    sender = make_gateway(tmp_path, 0)
    assert not reserve(sender, intent(1), 1, 70)
    assert not reserve(sender, intent(1, "EXIT"), 1, 70)


def test_physical_order_has_reservation_after_writeahead_and_final_gates():
    tree = ast.parse(CORE.read_text(encoding="utf-8-sig"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "SenderGateway")
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
              and n.name == "_place_order")
    text = ast.get_source_segment(CORE.read_text(encoding="utf-8-sig"), fn)
    # Exact physical call path: pre_send -> final mode/lease/close proof ->
    # durable collateral reservation -> SDK exchange.order.
    assert "pre_send()" in text  # enforce real pre-send hook presence
    assert text.index("pre_send()") < text.index("_reserve_margin_rest_at_wire")
    assert text.index("_final_close_proof") < text.index("_reserve_margin_rest_at_wire")
    assert text.index("_reserve_margin_rest_at_wire") < text.index("exchange.order(")


def make_wire_gateway(tmp_path, withdrawal, rows):
    """Execute the production physical wire method and terminal journal helper."""
    from typing import Callable
    import time
    tree = ast.parse(CORE.read_text(encoding="utf-8-sig"))
    owner = next(n for n in tree.body
                 if isinstance(n, ast.ClassDef) and n.name == "SenderGateway")
    methods = [n for n in owner.body if isinstance(n, ast.FunctionDef)
               and n.name in {"_place_order", "_terminalise_pending_as_no_call"}]
    assert len(methods) == 2
    module = ast.fix_missing_locations(ast.Module(body=[
        ast.ClassDef(name="WireGateway", bases=[], keywords=[],
                     body=methods, decorator_list=[])], type_ignores=[]))
    events = []
    def write_attempt(attempt_id, fields, durable=False):
        assert durable is True
        rows[attempt_id] = dict(fields)
        events.append(("terminal", attempt_id, fields["status"]))
        return True
    env = dict(__builtins__=__builtins__, Any=Any, Dict=Dict,
               Optional=Optional, Callable=Callable, Intent=object,
               FOLLOWER_NETWORK="testnet", MAINNET_ORDERS_CONFIRMED=False,
               time=time, utc_now_ms=lambda: 1000,
               _sender_lease_owned=lambda: True,
               _sdk_cloid=lambda x: x,
               _exchange_accepts_cloid=lambda e: False,
               _open_orders_send_begin=lambda: None,
               _open_orders_send_end=lambda: None,
               update_send_attempt_row=write_attempt,
               PendingSendWriteFailed=RuntimeError,
               PreWireNoCallFault=RuntimeError,
               log_error=lambda *args: None)
    exec(compile(module, str(CORE), "exec"), env)
    sender = env["WireGateway"]()
    admission = make_gateway(tmp_path, withdrawal)
    sender._reserve_margin_rest_at_wire = admission._reserve_margin_rest_at_wire
    sender._master_gate_reason = lambda *args, **kw: ""
    sender._reserve_exchange_order_slot = lambda **kw: 1000
    sender._reduce_only_for_intent = lambda item: item.reason == "EXIT"
    sender._final_close_proof = lambda *args: ""
    sender._note_sender_key_rejection = lambda response: None
    sender._gate_refusal_row = lambda *args: None
    return sender, events


def test_real_wire_collateral_drop_terminalises_without_exchange_order(tmp_path):
    balance = [100]
    records = {}
    gateway, events = make_wire_gateway(tmp_path, balance, records)
    calls = []
    exchange = SimpleNamespace(order=lambda *args, **kw: calls.append((args, kw)))
    entry = intent("collateral-drop")
    entry.reduce_only_intended = False
    timing = {"margin_rest_physical_admission": entry.intent_id,
              "send_attempt_id": "attempt-collateral-drop"}
    def durable_pre_send():
        balance[0] = 0  # collateral disappears during the potentially blocking hook
        return "attempt-collateral-drop"
    result = gateway._place_order(exchange, "BTC", True, 1, 70, "Gtc",
                                  False, timing=timing, pre_send=durable_pre_send,
                                  intent=entry, path="missed_entry_rest")
    assert calls == []
    assert result["exchange_called"] is False
    assert result["operator_action"] == "RECONCILE_RESERVED_MARGIN_BEFORE_RETRY"
    assert records["attempt-collateral-drop"]["status"] == (
        "SEND_NOT_ATTEMPTED_MARGIN_REST_NO_COLLATERAL")
    assert records["attempt-collateral-drop"]["operator_action"] == "NO_EXCHANGE_CALL"
    assert events == [("terminal", "attempt-collateral-drop",
                       "SEND_NOT_ATTEMPTED_MARGIN_REST_NO_COLLATERAL")]
    assert not list(tmp_path.glob("margin_rest_reservations_*.sqlite3")) or (
        __import__("sqlite3").connect(next(tmp_path.glob("margin_rest_reservations_*.sqlite3")))
        .execute("SELECT COUNT(*) FROM reservations").fetchone()[0] == 0)


def test_real_wire_admitted_and_attempt_receipt_persists(tmp_path):
    balance = [100]
    gateway, _events = make_wire_gateway(tmp_path, balance, {})
    calls = []
    def order(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "ok"}
    exchange = SimpleNamespace(order=order)
    entry = intent("accepted")
    entry.reduce_only_intended = False
    timing = {"margin_rest_physical_admission": entry.intent_id,
              "send_attempt_id": "attempt-accepted"}
    result = gateway._place_order(
        exchange, "BTC", True, 1, 70, "Gtc", False,
        timing=timing, pre_send=lambda: "attempt-accepted",
        intent=entry, path="missed_entry_rest")
    assert result == {"status": "ok"}
    assert len(calls) == 1
    assert timing["exchange_order_invoked"] is True
    with sqlite3.connect(next(tmp_path.glob("margin_rest_reservations_*.sqlite3"))) as db:
        evidence = db.execute(
            "SELECT attempt_id,intent_id,coin,sdk_coin,side,size,price,tif,reduce_only,cloid "
            "FROM reservation_evidence").fetchone()
        hold = db.execute("SELECT state,notional FROM reservations").fetchone()
    assert evidence == ("attempt-accepted", entry.intent_id, "BTC", "BTC",
                        "BUY", 1, 70, "Gtc", 0, "")
    assert hold == ("UNRESOLVED", 70)


def test_real_wire_funded_reduce_close_bypasses_entry_margin_gate(tmp_path):
    gateway, _events = make_wire_gateway(tmp_path, [0], {})
    calls = []
    exchange = SimpleNamespace(order=lambda *args, **kw: (
        calls.append((args, kw)) or {"status": "ok"}))
    closing = intent("funded-close", "EXIT")
    closing.reduce_only_intended = True
    result = gateway._place_order(
        exchange, "BTC", False, 3, 70, "Ioc", True,
        timing={"send_attempt_id": "close-attempt"},
        pre_send=lambda: "close-attempt",
        intent=closing, path="exit")
    assert result == {"status": "ok"}
    assert len(calls) == 1
    assert calls[0][1]["reduce_only"] is True
    assert not list(tmp_path.glob("margin_rest_reservations_*.sqlite3"))


def test_real_wire_conflicting_attempt_ids_never_send(tmp_path):
    gateway, _events = make_wire_gateway(tmp_path, [200], {})
    calls = []
    exchange = SimpleNamespace(order=lambda *a, **k: calls.append((a, k)))
    entry = intent("mismatch")
    entry.reduce_only_intended = False
    records = {}
    # Mock terminal writer is exercised even when the timing hint is stale.
    gateway._terminalise_pending_as_no_call = lambda aid, state, reason: records.update(
        attempt_id=aid, state=state, reason=reason)
    response = gateway._place_order(
        exchange, "BTC", True, 1, 70, "Gtc", False,
        timing={"margin_rest_physical_admission": entry.intent_id,
                "send_attempt_id": "stale-attempt"},
        pre_send=lambda: "durable-attempt",
        intent=entry, path="missed_entry_rest")
    assert calls == []
    assert response["exchange_called"] is False
    assert records["attempt_id"] == "durable-attempt"
    assert records["state"] == "SEND_NOT_ATTEMPTED_MARGIN_REST_NO_COLLATERAL"
    assert not list(tmp_path.glob("margin_rest_reservations_*.sqlite3"))
