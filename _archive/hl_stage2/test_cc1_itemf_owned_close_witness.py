"""CC1 Item F: test-only witnesses for fill-owned close planning.

Exercise the production close planner (not a copy of its predicates).  All
exchange reads are synthetic.  No sender, wallet, or live network is used.
"""
import math
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("HL_LEADER_NETWORK", "testnet")
os.environ.setdefault("HL_FOLLOWER_NETWORK", "testnet")
os.environ.setdefault("HL_LIVE_ENV_FILE", str(HERE / "__cc1_itemf_no_live_env__.env"))

import HL_Live_Copy_Service_Core as core  # noqa: E402

WALLET = "0x" + "a" * 40
ACCOUNT = "0x" + "c" * 40
COIN = "BTC"


class SleeveLedger:
    def __init__(self, owned, total):
        self.data = {"by_wallet": {WALLET: {COIN: {"signed_size": owned}}}}
        self.total = total

    def coin_net(self, coin):
        assert coin == COIN
        return self.total


def gateway(monkeypatch, *, owned=10.0, ledger_total=10.0, exchange_net=10.0,
            global_close=False, lag=False):
    monkeypatch.setattr(core, "USER_WALLET", ACCOUNT)
    # Deliberately use a fake self against the real class-qualified planner.
    # The same technique is exercised in test_core_close_to_target.py.
    reads = []
    escalations = []
    obj = SimpleNamespace()
    obj.cfg = SimpleNamespace(send_mode_now=lambda: "CLOSE" if global_close else "ON")
    obj.ledger = None if lag else SleeveLedger(owned, ledger_total)
    obj._reduce_only_for_intent = lambda intent: True
    obj._close_proof_account_ok = lambda: True
    obj._follower_order_account_for_proof = lambda: ACCOUNT
    obj._proven_owned_for_sleeve = lambda wallet, coin: (owned, "fills")
    obj._open_close_escalation = lambda intent, reason: escalations.append(reason)
    obj._floor_wire_size = lambda size, places: math.floor(size * 10**places + 1e-9) / 10**places

    def read(coin):
        assert coin == COIN
        reads.append(coin)
        return exchange_net

    obj._fresh_exchange_net = read
    intent = SimpleNamespace(
        fill=SimpleNamespace(leader_wallet=WALLET, coin=COIN, leader_fill_id="itemf-owned-close"),
        copy_side="SELL", copy_size=10.0)
    return obj, intent, reads, escalations


def plan(obj, intent, *, lag=False):
    timing = {}
    result = core.SenderGateway._close_wire_plan(
        obj, intent, 10.0, 3, lambda remainder: True, timing, lag)
    return result, timing


def test_itemf_owned_close_readable_net_uses_real_net_for_reduce_only(monkeypatch):
    """At 8487/8496/8521: owned +10, net +3 -> send 10, RO false."""
    obj, intent, reads, escalations = gateway(
        monkeypatch, owned=10.0, exchange_net=3.0, lag=True)
    result, timing = plan(obj, intent, lag=True)
    assert reads == [COIN]
    assert result == (False, 10.0, "")
    assert timing["close_decision"] == "SEND"
    assert timing["close_verified_sz_decimals"] == 3
    assert escalations == ["CLOSE_PROOF_LEDGER_LAG_NET_READABLE_NOT_REDUCE_ONLY"]


def test_itemf_owned_close_readable_net_safe_reduce_only(monkeypatch):
    """At 8521: real net +10 permits RO true; no blanket RO suppression."""
    obj, intent, reads, escalations = gateway(
        monkeypatch, owned=10.0, exchange_net=10.0, lag=True)
    result, timing = plan(obj, intent, lag=True)
    assert result == (True, 10.0, "")
    assert reads == [COIN]
    assert timing["close_decision"] == "SEND"
    assert escalations == ["CLOSE_PROOF_LEDGER_LAG_NET_SAFE_REDUCE_ONLY"]


def test_itemf_owned_close_unknown_net_unclamped_send(monkeypatch):
    """At 8487/8530: bounded reread then owned SEND, RO false."""
    obj, intent, reads, escalations = gateway(
        monkeypatch, owned=10.0, exchange_net=None, lag=True)
    result, timing = plan(obj, intent, lag=True)
    assert reads == [COIN, COIN]
    assert result == (False, 10.0, "")
    assert timing["close_decision"] == "SEND"
    assert escalations == ["CLOSE_PROOF_LEDGER_LAG_NET_UNREADABLE_RESTING"]


def test_itemf_global_close_only_clamps_owned_close_to_real_net(monkeypatch):
    """At 8487/8496: CLOSE switch caps 10 to net 3, RO true."""
    obj, intent, reads, escalations = gateway(
        monkeypatch, owned=10.0, exchange_net=3.0, global_close=True, lag=True)
    result, timing = plan(obj, intent, lag=True)
    assert reads == [COIN]
    assert result == (True, 3.0, "")
    assert timing["close_decision"] == "SEND"
    assert escalations == ["CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED"]


def test_itemf_global_close_only_unknown_net_holds_owned_close(monkeypatch):
    """At 8530/8534: unknown real net must HOLD and escalate, never wire."""
    obj, intent, reads, escalations = gateway(
        monkeypatch, owned=10.0, exchange_net=None, global_close=True, lag=True)
    result, timing = plan(obj, intent, lag=True)
    assert reads == [COIN, COIN]
    assert result == (False, 0.0, "CLOSE_PROOF_HOLD_GLOBAL_CLOSE_ONLY_UNKNOWN_NET")
    assert timing["close_decision"] == "HOLD"
    assert escalations == ["CLOSE_PROOF_GLOBAL_CLOSE_ONLY_CLAMPED"]


def test_itemf_normal_ledger_safe_foreign_units_allow_owned_reduction(monkeypatch):
    """Legitimate owned +10 close with foreign same-side +5 must not HOLD."""
    obj, intent, reads, escalations = gateway(
        monkeypatch, owned=10.0, ledger_total=10.0, exchange_net=15.0)
    result, timing = plan(obj, intent)
    assert reads == [COIN]
    assert result == (True, 10.0, "")
    assert timing["close_decision"] == "SEND"


def test_itemf_normal_ledger_unsafe_foreign_units_hold(monkeypatch):
    """A non-safe exchange/ledger discrepancy still refuses the wire."""
    obj, intent, reads, escalations = gateway(
        monkeypatch, owned=10.0, ledger_total=10.0, exchange_net=4.0)
    result, timing = plan(obj, intent)
    assert result == (False, 0.0, "CLOSE_PROOF_HOLD_FOREIGN_UNITS")
    assert timing["close_decision"] == "HOLD"
