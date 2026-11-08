"""R5: sender wire-cap regression tests; AST-load only one method (no network)."""
import ast
import math
import os
import time
from pathlib import Path
from types import SimpleNamespace

CORE = Path(__file__).resolve().parents[1] / "_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
module = ast.parse(CORE.read_text(encoding="utf-8-sig"))
cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == "SenderGateway")
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_wire_entry_exposure_block")
scope = {"Any": __import__("typing").Any, "math": math, "time": time, "os": os,
         "fnum": lambda x, default=0: float(x if x is not None else default),
         "normalise_wallet": str.lower,
         "classify_send_lifecycle": lambda intent: intent.lifecycle}
exec(compile(ast.Module(body=[method], type_ignores=[]), str(CORE), "exec"), scope)

def gate(wallet_cap=100, total_cap=200, wallet_used=0, total_used=0, resting=0,
         pending=0, lifecycle="ENTRY", reduce_only=False, entry_leg=False, truth=True):
    source = SimpleNamespace(
        _resting=lambda: {"total_usd": resting, "by_wallet_usd": {"w": resting}},
        _exposure_pending=[("BTC", pending, 1., time.monotonic())],
        follower_exposure=lambda: {"ok": truth, "total_usd": total_used})
    cfg = SimpleNamespace(max_wallet_exposure=lambda w: wallet_cap,
                          max_total_exposure=lambda: total_cap)
    self = SimpleNamespace(cfg=cfg, cap_source=source,
                           ledger=SimpleNamespace(wallet_abs_exposure_usd=lambda w, p: wallet_used))
    intent = SimpleNamespace(fill=SimpleNamespace(leader_wallet="w", coin="BTC"), lifecycle=lifecycle)
    return scope["_wire_entry_exposure_block"](self, intent, 1., 10., reduce_only, entry_leg)

def test_wallet_cap_at_wire_closes_exempt():
    assert gate(wallet_used=95) == "ENTRY_WALLET_EXPOSURE_CAP"
    assert gate(wallet_used=95, lifecycle="EXIT", reduce_only=True) == ""

def test_total_cap_counts_pending_and_resting():
    assert gate(wallet_cap=0, total_cap=100, total_used=75, pending=10, resting=10) == "ENTRY_TOTAL_EXPOSURE_CAP"
    assert gate(wallet_cap=0, total_cap=100, total_used=75) == ""

def test_unreadable_truth_fails_closed_entry_only():
    assert gate(wallet_cap=0, truth=False) == "ENTRY_TOTAL_EXPOSURE_UNREADABLE"
    assert gate(wallet_cap=0, truth=False, lifecycle="EXIT", reduce_only=True) == ""

def test_split_close_excess_is_entry():
    assert gate(wallet_used=100, lifecycle="EXIT", entry_leg=True) == "ENTRY_WALLET_EXPOSURE_CAP"
