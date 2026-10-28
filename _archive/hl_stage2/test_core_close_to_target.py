"""Track B close-to-target semantics: exchange RO leg + separately gated entry remainder.

Run offline: python -m pytest _archive/hl_stage2/test_core_close_to_target.py -q
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as core


def make_plan(side, qty, net, sleeve=None, min_ok=lambda size: True):
    # Ledger coin net can differ from this leader's sleeve when USER/other sleeves coexist.
    signed = (qty if side == "SELL" else -qty) if sleeve is None else sleeve
    ledger = SimpleNamespace(sleeve=lambda wallet, coin: {"signed_size": signed},
                             coin_net=lambda coin: signed)
    gateway = SimpleNamespace(ledger=ledger, _reduce_only_for_intent=lambda i: True,
                              _fresh_exchange_net=lambda coin: net,
                              _floor_wire_size=lambda size, digits: round(size, digits),
                              _trackb_split_close=core.SenderGateway._trackb_split_close)
    intent = SimpleNamespace(copy_side=side, copy_size=qty, wallet_position_before=signed,
                             fill=SimpleNamespace(leader_wallet="0xowner", coin="ETH"))
    timing = {}
    result = core.SenderGateway._close_wire_plan(gateway, intent, qty, 3, min_ok, timing)
    return result, timing


def test_reduce_only_uses_actual_exchange_net():
    assert make_plan("SELL", 10, 20)[0] == (True, 10, "")
    assert make_plan("SELL", 10, 10)[0] == (True, 10, "")
    assert make_plan("BUY", 10, -20)[0] == (True, 10, "")


def test_first_leg_reduces_net_and_remainder_is_entry_type():
    first, timing = make_plan("SELL", 10, 4)
    assert first == (True, 4, "")
    assert timing["trackb_close_remainder"] == pytest.approx(6)


def test_exchange_flat_still_requires_a_plain_close_under_section_ten():
    first, timing = make_plan("SELL", 10, 0)
    assert first == (False, 10, "")
    assert timing["trackb_close_remainder"] == 0


def test_net_opposite_direction_never_uses_reduce_only():
    assert make_plan("SELL", 10, -4)[0] == (False, 10, "")


def test_user_inventory_never_expands_the_engine_sleeve_close():
    # USER long 100, engine long 3, exchange long 103.
    assert make_plan("SELL", 15, 103, sleeve=3)[0] == (True, 3, "")


def test_trimmed_dust_never_inflated_past_exchange_net():
    first, timing = make_plan("SELL", 10, 4, min_ok=lambda size: False)
    assert first[1] == 0 and first[2] == "CLOSE_SPLIT_TRIMMED_DUST_ESCALATION"


def test_unreadable_exchange_plain_close_non_ro_not_silent():
    assert make_plan("SELL", 3, None)[0] == (False, 3, "")


def test_missing_ledger_direction_does_not_close_user_inventory():
    assert make_plan("SELL", 10, 40, sleeve=-10)[0][2] == "ENGINE_SLEEVE_NOT_CLOSABLE"
