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
            return [{"ok": True, "data": {"withdrawable": str(withdrawable)}}]
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
