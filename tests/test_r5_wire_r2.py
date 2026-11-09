"""R5: atomic reservations with frozen exchange truth; offline AST extraction.

These tests intentionally do NOT increment ledger/exchange exposure on a fake wire call.
The second send can be refused only by a separately-held intent reservation.
See test_r5_physical_concurrency.py for the actual _place_order -> exchange.order path.
"""
import ast
from pathlib import Path
import threading
import time
from types import SimpleNamespace as NS
import math
import os
from typing import Any, Dict, Optional, Callable

CORE = Path(__file__).resolve().parents[1] / "_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
txt = CORE.read_text(encoding="utf-8-sig")
tree = ast.parse(txt)
cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == "SenderGateway")
def meth(name):
    return next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == name)
scope = {"Any": Any, "Optional": Optional, "Dict": Dict, "Callable": Callable,
         "math": math, "os": os, "time": time,
         "fnum": lambda x, default=0: float(x if x is not None else default),
         "normalise_wallet": str.lower,
         "classify_send_lifecycle": lambda intent: intent.lifecycle}
exec(compile(ast.Module(body=[meth("_wire_entry_exposure_block"), meth("_place_order")],
                        type_ignores=[]), str(CORE), "exec"), scope)

def intent(life="ENTRY", fid="a", attempt=None):
    return NS(fill=NS(leader_wallet="w", coin="BTC", leader_fill_id=fid),
              intent_id=attempt or "intent-" + fid, lifecycle=life,
              reduce_only_intended=life in {"EXIT", "REDUCE"})

class Host:
    _reduce_only_for_intent = lambda self, intent: intent.lifecycle in {"EXIT", "REDUCE"}
    _wire_entry_exposure_block = scope["_wire_entry_exposure_block"]
    _place_order = scope["_place_order"]

    def __init__(self):
        self._wire_cap_lock = threading.RLock()
        self._wire_cap_reservations = {}
        self.wire_count = 0
        self.cfg = NS(max_wallet_exposure=lambda wallet: 10.,
                      max_total_exposure=lambda: 10.)
        self.cap_source = NS(
            _resting=lambda: {},
            _exposure_pending=[],
            follower_exposure=lambda: {"ok": True, "total_usd": 0.})
        self.ledger = NS(wallet_abs_exposure_usd=lambda wallet, marks: 0.)

    def _place_order_impl(self, ex, coin, buy, size, px, tif, ro, timing, key,
                          cloid, cool, pre, current_intent, path, entry_leg):
        # Simulate the last physical sender gate. Unlike rev1, the ledger and
        # exchange observations NEVER advance as a result of this fake send.
        reason = self._wire_entry_exposure_block(
            current_intent, size, px, ro, entry_leg, reserve=True)
        if reason:
            return reason
        time.sleep(.01)  # simultaneous threads overlap before exchange confirmation
        self.wire_count += 1
        return "SENT"

def test_atomic_competing_entries():
    h = Host()
    outcome = []
    barrier = threading.Barrier(3)
    def send(fid):
        barrier.wait()
        outcome.append(h._place_order(None, "BTC", True, 6., 1., "Ioc",
                                      False, intent=intent(fid=fid)))
    threads = [threading.Thread(target=send, args=(fid,)) for fid in ("a", "b")]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=3.)
        assert not thread.is_alive()
    assert sorted(outcome) == ["ENTRY_WALLET_EXPOSURE_CAP", "SENT"]
    assert h.wire_count == 1
    assert len(h._wire_cap_reservations) == 1

def test_pending_does_not_double_count_current():
    h = Host()
    i = intent(fid="a")
    h.cap_source._exposure_pending = [("BTC", 6., 1., time.monotonic(), "a")]
    assert h._wire_entry_exposure_block(i, 6., 1., False) == ""
    h.cap_source._exposure_pending.append(("BTC", 5., 1., time.monotonic(), "b"))
    assert h._wire_entry_exposure_block(i, 6., 1., False) == "ENTRY_WALLET_EXPOSURE_CAP"
    h.cap_source._exposure_pending.pop()
    h.cap_source._exposure_pending.append(("BTC", 6., 1., time.monotonic(), "a"))
    assert h._wire_entry_exposure_block(i, 6., 1., False) == "ENTRY_CAP_RESERVATION_AMBIGUOUS"

def test_reduce_only_flag_not_close_proof():
    h = Host()
    h._wire_cap_reservations[("w", "held", "intent-held")] = {
        "wallet": "w", "notional": 10., "state": "UNKNOWN_UNTIL_PROVEN"}
    # A forged reduce_only=True on an ENTRY is an entry, not a close.
    assert h._wire_entry_exposure_block(intent("ENTRY"), 1., 1., True) == "ENTRY_WALLET_EXPOSURE_CAP"
    # A real EXIT with an independently validated lifecycle remains exempt.
    assert h._wire_entry_exposure_block(intent("EXIT"), 1., 1., True) == ""
    # Split excess leg does not get the close exemption.
    assert h._wire_entry_exposure_block(intent("EXIT"), 1., 1., True, entry_leg=True) == "ENTRY_WALLET_EXPOSURE_CAP"

def test_gate_twice_inside_physical_path():
    impl = meth("_place_order_impl")
    calls = [node for node in ast.walk(impl)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
    assert sum(node.func.attr == "_wire_entry_exposure_block" for node in calls) == 2
    assert sum(node.func.attr == "order" for node in calls) == 1
