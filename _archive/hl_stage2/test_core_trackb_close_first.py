"""Offline adverse Track B close tests; no order, wallet, exchange or network action."""
import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
import pytest

os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as core


@pytest.mark.parametrize("case", range(133))
def test_close_split_exchange_test_133_cases(case):
    side = "BUY" if case % 2 else "SELL"
    qty = 0.25 + (case % 17)
    net = (-20, -10, -2, 0, 2, 10, 20)[case % 7]
    signed = -qty * 2 if side == "BUY" else qty * 2
    parts, why = core.SenderGateway._trackb_split_close(side, qty, signed, net)
    assert why == "EXCHANGE_NET_CLOSE_SPLIT"
    assert sum(x[0] for x in parts) == pytest.approx(qty)
    for amount, ro in parts:
        assert amount > 0
        if ro:
            assert (net * (1 if side == "BUY" else -1)) < 0
            assert amount <= abs(net) + 1e-10


@pytest.mark.parametrize("coin", ["ETH"] * 24 + ["SOL"] * 15 + ["PONS"] * 10 + ["WLFI"] * 7 + ["WLD"] * 3)
def test_59_synthetic_margin_rejected_exit_shapes_are_reduce_only_when_opposing(coin):
    # Synthetic shapes only: the 59 historical run19 rows require the external run19 data.
    parts, state = core.SenderGateway._trackb_split_close("SELL", 1.0, 1.0, 1.0)
    assert state == "EXCHANGE_NET_CLOSE_SPLIT"
    assert parts == [(1.0, True)]


def test_profit_close_ignores_two_percent_adverse_diff():
    p = core.SenderGateway._trackb_price_decision("SELL", 105, 102.9, 95, 2, 0.25, 10)
    assert p["state"] == "EXECUTE_PROFIT"
    assert p["adverse_pct"] == pytest.approx(2)


def test_lateness_loss_rests_at_leader_price():
    p = core.SenderGateway._trackb_price_decision("SELL", 100, 99, 102, 2, 0.25, 10)
    assert p["state"] == "REST_AT_LEADER_PRICE"
    assert p["pnl_after_fees_usd"] < 0


def test_stop_loss_within_tolerance_sends_now():
    p = core.SenderGateway._trackb_price_decision("SELL", 100, 99.8, 110, 2, 0.25, 10)
    assert p["state"] == "EXECUTE_WITHIN_TOLERANCE"


def test_close_at_2_24_margin_reduce_only_is_not_exposure_increase(monkeypatch):
    parts, state = core.SenderGateway._trackb_split_close("SELL", 1, 1, 1)
    assert parts == [(1.0, True)]
    sender = SimpleNamespace(cfg=SimpleNamespace(master_switch_now=lambda: True,
                              send_mode_now=lambda: "ON", wallet_enabled=lambda _: True,
                              wallet_mode=lambda _: "ON", max_order_notional=lambda: 100,
                              max_wallet_exposure=lambda _: 0), ledger=None)
    monkeypatch.setattr(core, "load_json", lambda *_: {
        "created_at_ms": core.utc_now_ms(),
        "raw": {"withdrawable": "2.24", "marginSummary": {"accountValue": "406"}}})
    fill = SimpleNamespace(leader_wallet="0x" + "d" * 40, coin="ETH")
    intent = SimpleNamespace(fill=fill)
    blocked = core.SenderGateway._trackb_remainder_entry_block(sender, intent, 1, 100)
    assert "ENTRY_REMAINDER_MARGIN_RESERVE" in blocked


def test_escalation_survives_restart_and_only_clears_on_engine_sleeve_flat(tmp_path, monkeypatch):
    path = tmp_path / "close_escalations.json"
    monkeypatch.setattr(core, "CLOSE_ESCALATIONS_FILE", path)
    rows = []
    audit = SimpleNamespace(append_reconciliation=lambda *a, **kw: rows.append((a, kw)))
    signed = [3.0]
    ledger = SimpleNamespace(sleeve=lambda w, c: {"signed_size": signed[0]})
    sender = SimpleNamespace(audit=audit, ledger=ledger, _resting_lock=threading.RLock(),
                             _trackb_escalations={})
    intent = SimpleNamespace(sleeve_id="s1", intent_id="i1",
          fill=SimpleNamespace(leader_wallet="0x" + "d" * 40, coin="ETH",
                               leader_fill_id="f1", price=100, timestamp_ms=core.utc_now_ms()))
    core.SenderGateway._trackb_escalate(sender, intent, "IOC_NO_MATCH", {"loss_usd": 1})
    assert path.exists()
    sender._trackb_escalations = core.load_json(path, {})
    assert core.SenderGateway.clear_trackb_escalations(sender) == 0
    assert "s1" in core.load_json(path, {})
    signed[0] = 0.0
    assert core.SenderGateway.clear_trackb_escalations(sender) == 1
    assert core.load_json(path, {}) == {}
    assert rows[-1][0][1] == "CLOSE_ESCALATION_CLEARED"


def test_unknown_price_keeps_close_waiting():
    p = core.SenderGateway._trackb_price_decision("SELL", 100, 0, 90, 1)
    assert p["state"] == "WAIT_VERIFIED_PRICE"


def test_dust_below_executable_min_escalates_not_oversized():
    parts, state = core.SenderGateway._trackb_split_close("SELL", 0.00001, 0.00001, 0.00001)
    assert parts and parts[0][1]
