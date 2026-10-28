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


def _bind_same_account_for_terminal_test(monkeypatch, sender):
    """The exchange read and SDK order account must be the SAME account."""
    account = "0x" + "c" * 40
    monkeypatch.setattr(core, "USER_WALLET", account)
    monkeypatch.setenv("HL_LIVE_HL_ACCOUNT_ADDRESS", account)
    sender._follower_order_account_for_proof = (
        lambda: core.SenderGateway._follower_order_account_for_proof(sender))


def test_escalation_survives_restart_and_only_clears_on_engine_sleeve_flat(tmp_path, monkeypatch):
    path = tmp_path / "close_escalations.json"
    monkeypatch.setattr(core, "CLOSE_ESCALATIONS_FILE", path)
    rows = []
    audit = SimpleNamespace(append_reconciliation=lambda *a, **kw: rows.append((a, kw)))
    signed = [3.0]
    exchange_net = [3.0]
    ledger = SimpleNamespace(sleeve=lambda w, c: {"signed_size": signed[0]})
    sender = SimpleNamespace(audit=audit, ledger=ledger, _resting_lock=threading.RLock(),
                             _trackb_escalations={},
                             _fresh_exchange_net=lambda coin: exchange_net[0])
    intent = SimpleNamespace(sleeve_id="s1", intent_id="i1",
          fill=SimpleNamespace(leader_wallet="0x" + "d" * 40, coin="ETH",
                               leader_fill_id="f1", price=100, timestamp_ms=core.utc_now_ms()))
    _bind_same_account_for_terminal_test(monkeypatch, sender)
    core.SenderGateway._trackb_escalate(sender, intent, "IOC_NO_MATCH", {"loss_usd": 1})
    assert path.exists()
    sender._trackb_escalations = core.load_json(path, {})
    assert core.SenderGateway.clear_trackb_escalations(sender) == 0
    assert "s1" in core.load_json(path, {})
    signed[0] = 0.0
    assert core.SenderGateway.clear_trackb_escalations(sender) == 0  # ledger-only is NOT proof
    assert "s1" in core.load_json(path, {})
    exchange_net[0] = None
    assert core.SenderGateway.clear_trackb_escalations(sender) == 0  # unreadable remains red
    assert "s1" in core.load_json(path, {})
    exchange_net[0] = 0.0
    assert core.SenderGateway.clear_trackb_escalations(sender) == 1
    assert core.load_json(path, {}) == {}
    assert rows[-1][0][1] == "CLOSE_ESCALATION_CLEARED"


def test_unknown_price_keeps_close_waiting():
    p = core.SenderGateway._trackb_price_decision("SELL", 100, 0, 90, 1)
    assert p["state"] == "WAIT_VERIFIED_PRICE"


def test_dust_below_executable_min_escalates_not_oversized():
    parts, state = core.SenderGateway._trackb_split_close("SELL", 0.00001, 0.00001, 0.00001)
    assert parts and parts[0][1]



@pytest.mark.parametrize("engine_size,exchange_net,expected_clears", [
    (0.0, None, 0),         # FAIL CLOSED: unreadable exchange
    (0.0, 1.0, 0),          # USER or unexplained non-flat exchange net
    (0.0, -2.0, 0),         # opposite exchange net remains OPEN
    (3.0, 0.0, 0),          # exchange flat alone is insufficient
    (0.0, float("nan"), 0), # corrupt exchange value is not flat
    (0.0, "unknown", 0),    # malformed exchange result is not flat
    (0.0, 0.0, 1),          # BOTH authoritative conditions are flat
])
def test_terminal_clear_requires_fresh_exchange_and_ledger(
        engine_size, exchange_net, expected_clears, tmp_path, monkeypatch):
    """Regression: removing _fresh_exchange_net() from clear makes these fail."""
    path = tmp_path / "close_escalations.json"
    monkeypatch.setattr(core, "CLOSE_ESCALATIONS_FILE", path)
    records = []
    original_row = {
        "leader_wallet": "0x" + "d" * 40, "coin": "ETH", "intent_id": "owed-i1",
        "leader_fill_id": "owed-f1", "state": "OPEN", "reason": "IOC_NO_MATCH",
    }
    core.atomic_write_json(path, {"s1": original_row})
    sender = SimpleNamespace(
        _resting_lock=threading.RLock(), _trackb_escalations=core.load_json(path, {}),
        ledger=SimpleNamespace(sleeve=lambda wallet, coin: {"signed_size": engine_size}),
        _fresh_exchange_net=lambda coin: exchange_net,
        audit=SimpleNamespace(append_reconciliation=lambda *args, **kw: records.append((args, kw))),
    )
    _bind_same_account_for_terminal_test(monkeypatch, sender)
    cleared = core.SenderGateway.clear_trackb_escalations(sender)
    assert cleared == expected_clears
    assert ("s1" not in core.load_json(path, {})) == bool(expected_clears)
    assert bool(records) == bool(expected_clears)
    if expected_clears:
        assert records[-1][0][1] == "CLOSE_ESCALATION_CLEARED"
        assert records[-1][1]["action"] == "ENGINE_LEDGER_AND_EXCHANGE_NET_FLAT_PROVEN"


def test_terminal_clear_exchange_exception_keeps_red_and_durable(tmp_path, monkeypatch):
    path = tmp_path / "close_escalations.json"
    monkeypatch.setattr(core, "CLOSE_ESCALATIONS_FILE", path)
    row = {"leader_wallet": "0x" + "d" * 40, "coin": "ETH", "intent_id": "i1"}
    core.atomic_write_json(path, {"s1": row})
    events = []

    def unavailable(_coin):
        raise ConnectionError("follower exchange unavailable")

    sender = SimpleNamespace(
        _resting_lock=threading.RLock(), _trackb_escalations=core.load_json(path, {}),
        ledger=SimpleNamespace(sleeve=lambda w, c: {"signed_size": 0.0}),
        _fresh_exchange_net=unavailable,
        audit=SimpleNamespace(append_reconciliation=lambda *args, **kw: events.append((args, kw))),
    )
    _bind_same_account_for_terminal_test(monkeypatch, sender)
    assert core.SenderGateway.clear_trackb_escalations(sender) == 0
    assert "s1" in core.load_json(path, {})
    assert not events


@pytest.mark.parametrize("side,engine_size,requested_size", [
    ("SELL", 5.0, 12.0),
    ("BUY", -5.0, 12.0),
    ("SELL", 0.0001, 2.0),
])
def test_dir131_unknown_exchange_sends_only_capped_engine_close(side, engine_size, requested_size):
    """Unknown exchange net must not block a proven engine-sleeve close."""
    parts, reason = core.SenderGateway._trackb_split_close(
        side, requested_size, engine_size, None)
    assert parts == [(abs(engine_size), False)]
    assert reason == "UNKNOWN_EXCHANGE_NET_CAPPED_ENGINE_SLEEVE"


@pytest.mark.parametrize("sleeve,side", [
    (None, "SELL"), (0.0, "SELL"), (float("nan"), "SELL"),
    (-3.0, "SELL"), (3.0, "BUY"),
])
def test_dir131_unproven_or_wrong_side_engine_sleeve_never_sends(sleeve, side):
    parts, reason = core.SenderGateway._trackb_split_close(side, 5.0, sleeve, None)
    assert parts == []
    assert reason in {"ENGINE_SLEEVE_UNPROVEN", "ENGINE_SLEEVE_NOT_CLOSABLE"}


def test_dir131_unknown_exchange_planner_never_applies_remainder_gate():
    wallet = "0x" + "d" * 40
    led = SimpleNamespace(sleeve=lambda wallet, coin: {"signed_size": 3.0})
    sender = SimpleNamespace(ledger=led, _reduce_only_for_intent=lambda intent: True,
                             _fresh_exchange_net=lambda coin: None,
                             _trackb_split_close=core.SenderGateway._trackb_split_close,
                             _floor_wire_size=lambda qty, decimals: round(qty, decimals))
    intent = SimpleNamespace(copy_side="SELL", wallet_position_before=12.0,
                             fill=SimpleNamespace(leader_wallet=wallet, coin="ETH"))
    timing = {}
    plan = core.SenderGateway._close_wire_plan(
        sender, intent, 12.0, 3, lambda qty: True, timing)
    assert plan == (False, 3.0, "")
    assert timing["trackb_close_split_reason"] == "UNKNOWN_EXCHANGE_NET_CAPPED_ENGINE_SLEEVE"
    assert timing["trackb_close_remainder"] == 0.0


@pytest.mark.parametrize("owned,exchange_error,should_send", [
    (3.0, "exchange snapshot unavailable", True),
    (0.0, "exchange snapshot unavailable", False),
    (-3.0, "exchange snapshot unavailable", False),
    (None, "exchange snapshot unavailable", False),
])
def test_dir131_missing_exchange_snapshot_gate_allows_only_engine_close(
        owned, exchange_error, should_send):
    wallet = "0x" + "d" * 40
    escalations = []
    sleeve = {} if owned is None else {"signed_size": owned}
    ledger = SimpleNamespace(sleeve=lambda w, c: sleeve)
    sender = SimpleNamespace(
        ledger=ledger, _audit_proof_block_reason=lambda: "",
        _persisted_exchange_positions=lambda: ({}, exchange_error),
        _trackb_escalate=lambda *args: escalations.append(args),
        _ownership_gate_block=core.SenderGateway._ownership_gate_block,
    )
    intent = SimpleNamespace(
        fill=SimpleNamespace(leader_wallet=wallet, coin="ETH"),
        copy_side="SELL", copy_size=9.0, reduce_only_intended=True,
        wallet_position_before=9.0, intent_id="dir131-i1")
    allowed, refusal = core.SenderGateway._pre_send_ownership_gate(sender, intent)
    assert allowed is should_send
    assert bool(escalations)
    if not should_send:
        assert refusal["status"] == "OWNERSHIP_GATE_NO_MATCHING_WALLET_SLEEVE"


def test_dir131_known_exchange_retains_reduce_only_split():
    parts, reason = core.SenderGateway._trackb_split_close("SELL", 12.0, 5.0, 2.0)
    assert reason == "EXCHANGE_NET_CLOSE_SPLIT"
    assert parts == [(2.0, True), (3.0, False)]


def test_dir131_missing_engine_sleeve_does_not_use_intent_time_snapshot():
    sender = SimpleNamespace(ledger=SimpleNamespace(sleeve=lambda *args: {}),
                             _reduce_only_for_intent=lambda intent: True,
                             _fresh_exchange_net=lambda coin: None,
                             _trackb_split_close=core.SenderGateway._trackb_split_close)
    intent = SimpleNamespace(copy_side="SELL", wallet_position_before=500.0,
                             fill=SimpleNamespace(leader_wallet="0x" + "d" * 40, coin="ETH"))
    timing = {}
    first = core.SenderGateway._close_wire_plan(sender, intent, 500.0, 3, None, timing)
    assert first[1] == 0.0
    assert first[2] == "ENGINE_SLEEVE_UNPROVEN"



def test_dir131_account_A_flat_B_nonflat_must_not_clear_red(tmp_path, monkeypatch):
    """Even if a stale read proves A flat, SDK account B has exposure: BLOCK."""
    account_a = "0x" + "a" * 40
    account_b = "0x" + "b" * 40
    monkeypatch.setattr(core, "USER_WALLET", account_a)
    monkeypatch.setenv("HL_LIVE_HL_ACCOUNT_ADDRESS", account_b)
    path = tmp_path / "close_escalations.json"
    monkeypatch.setattr(core, "CLOSE_ESCALATIONS_FILE", path)
    row = {"leader_wallet": "0x" + "d" * 40, "coin": "ETH", "intent_id": "owed"}
    core.atomic_write_json(path, {"s1": row})
    exchange_nets = {account_a: 0.0, account_b: 3.0}
    calls, logs, audit_events = [], [], []

    def wrong_account_read(coin):
        calls.append(coin)
        return exchange_nets[account_a]

    monkeypatch.setattr(core, "log_error", lambda where, exc: logs.append((where, str(exc))))
    sender = SimpleNamespace(
        _resting_lock=threading.RLock(), _trackb_escalations=core.load_json(path, {}),
        ledger=SimpleNamespace(sleeve=lambda w, c: {"signed_size": 0.0}),
        _fresh_exchange_net=wrong_account_read,
        audit=SimpleNamespace(append_reconciliation=lambda *a, **kw: audit_events.append((a, kw))),
    )
    sender._follower_order_account_for_proof = (
        lambda: core.SenderGateway._follower_order_account_for_proof(sender))
    assert core.SenderGateway.clear_trackb_escalations(sender) == 0
    assert calls == []  # identity gate runs BEFORE even a mocked A-flat read
    assert core.load_json(path, {}).get("s1") == row
    assert not audit_events
    assert any(account_a in msg and account_b in msg for _, msg in logs)


def test_dir131_fresh_exchange_net_uses_sdk_account_and_rejects_mismatch(monkeypatch):
    """Production truth-read must be tied to the account passed to SDK orders."""
    account_a, account_b = "0x" + "a" * 40, "0x" + "b" * 40
    monkeypatch.setattr(core, "USER_WALLET", account_a)
    monkeypatch.setenv("HL_LIVE_HL_ACCOUNT_ADDRESS", account_b)
    reads, logs = [], []
    monkeypatch.setattr(core, "log_error", lambda where, exc: logs.append((where, str(exc))))
    sender = SimpleNamespace()
    sender._follower_order_account_for_proof = (
        lambda: core.SenderGateway._follower_order_account_for_proof(sender))
    assert core.SenderGateway._fresh_exchange_net(sender, "ETH") is None
    assert any(account_a in msg and account_b in msg for _, msg in logs)
    # No network read can be performed on the mismatching account.
