"""C7-DIR-198/204: offline close refusal and venue-minimum dust safety.

Run: python -m pytest -q _archive/hl_stage2/test_core_c7w_close_dust.py
No API, orders, credentials or runtime interaction. These cases are NOT a
substitute for controller-run full suite or multi-wallet batch certification.
"""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent/c7w-test.env")
os.environ.setdefault("HL_LEADER_NETWORK", "testnet")
os.environ.setdefault("HL_FOLLOWER_NETWORK", "testnet")
import HL_Live_Copy_Service_Core as core

WALLET = "0x" + "d" * 40
USER = "0x" + "e" * 40
ACCOUNT = "0x" + "c" * 40


class FakeLedger:
    def __init__(self, signed=-0.1, user=-10.4):
        self.signed = signed
        self.user = user

    def sleeve(self, wallet, coin):
        return {"signed_size": self.user if wallet == USER else self.signed}


class Audit:
    def __init__(self):
        self.rows = []

    def append_reconciliation(self, event, status, **kwargs):
        self.rows.append((event, status, kwargs))


def setup(monkeypatch, tmp_path, size=-0.1, account_net=-10.5):
    monkeypatch.setattr(core, "CLOSE_DUST_HOLDS_FILE", tmp_path / "dust.json")
    monkeypatch.setattr(core, "CLOSE_ESCALATIONS_FILE", tmp_path / "owed.json")
    monkeypatch.setattr(core, "CLOSE_RESERVATIONS_FILE", tmp_path / "claims.json")
    monkeypatch.setenv("HL_LIVE_HL_ACCOUNT_ADDRESS", ACCOUNT)
    monkeypatch.setattr(core, "USER_WALLET", ACCOUNT)
    audit, ledger, net = Audit(), FakeLedger(signed=size), [account_net]
    g = core.SenderGateway(core.ConfigManager(), audit, ledger)
    g._fresh_exchange_net = lambda coin: net[0]
    g._follower_order_account_for_proof = lambda **kw: ACCOUNT
    return g, ledger, audit, net


def intent(fid="f1", size=0.1):
    fill = SimpleNamespace(leader_wallet=WALLET, leader_fill_id=fid, coin="NEAR",
                           price=4.4, timestamp_ms=core.utc_now_ms(), raw={})
    return SimpleNamespace(fill=fill, intent_id="i-" + fid, sleeve_id="s-NEAR",
                           position_id="pos-NEAR", copy_side="BUY", copy_size=size,
                           copy_notional=size * 4.4, wallet_position_before=-size,
                           coin_net_before=-size, reduce_only_intended=True,
                           send_allowed=True, notes="lifecycle=EXIT", reason="EXIT",
                           created_at_ms=core.utc_now_ms(), wallet_mode="CLO")


@pytest.mark.parametrize("reason", [
    "DUST_CLOSE_HELD_BELOW_VENUE_MINIMUM",
    "REAL_SENDER_NOT_CONFIGURED",
    "SEND_BLOCKED_SENDER_KEY_NOT_VALID",
    "EXCHANGE_ERROR",
    "SEND_NOT_ATTEMPTED_INVALID_SIZE",
    "EXIT_ATTEMPT_COOLDOWN",
])
def test_all_authorised_unsendable_close_reasons_named_and_durable_red(
        reason, monkeypatch, tmp_path):
    g, _, audit, _ = setup(monkeypatch, tmp_path)
    i = intent()
    g._send_if_allowed_impl = lambda *args, **kwargs: (False, reason)
    assert g.send_if_allowed(i) == (False, reason)
    assert any(status == "AUTHORISED_CLOSE_NOT_SENT"
               and row["reject_category"] == reason
               for _, status, row in audit.rows)
    assert core.load_json(core.CLOSE_ESCALATIONS_FILE, {})["s-NEAR"]["state"] == "OPEN"
    restarted = core.SenderGateway(core.ConfigManager(), Audit(), g.ledger)
    assert restarted._trackb_escalations["s-NEAR"]["state"] == "OPEN"


def test_refusal_survives_broken_audit_writer(monkeypatch, tmp_path):
    g, _, _, _ = setup(monkeypatch, tmp_path)
    i = intent()
    g._send_if_allowed_impl = lambda *args, **kwargs: (False, "SDK_UNAVAILABLE")
    del g.audit  # a pre-existing regression seam
    assert g.send_if_allowed(i) == (False, "SDK_UNAVAILABLE")
    assert core.load_json(core.CLOSE_ESCALATIONS_FILE, {})["s-NEAR"]["state"] == "OPEN"


def test_40_distinct_point_one_dust_closes_combine_but_replay_cannot_overclaim(
        monkeypatch, tmp_path):
    g, ledger, audit, exchange_net = setup(monkeypatch, tmp_path, size=-4.0, account_net=-4.0)
    total = 0.0
    for n in range(40):
        i = intent("unique-fill-" + str(n))
        total = g._record_close_dust_hold(i, 0.1, 4.4, "DUST_HELD")
        assert total <= 4.0 + 1e-9
    assert total == pytest.approx(4.0)
    assert total * 4.4 >= 10.0
    assert g._record_close_dust_hold(intent("unique-fill-0"), 0.1, 4.4, "REPLAY") == pytest.approx(4.0)
    rows = core.load_json(core.CLOSE_DUST_HOLDS_FILE, {})
    assert len(rows) == 40
    assert all(r["coin"] == "NEAR" and r["size"] == 0.1
               and r["notional"] == pytest.approx(0.44) and r["age_ms"] >= 0
               and r["first_seen_ms"] <= r["last_seen_ms"] for r in rows.values())
    # The combined 4.0 can be reserved against the real -4.0 ENGINE sleeve.
    ok, why = g._reserve_close_wire(i, "NEAR", True, total, 4.4, True, "0x" + "1" * 32, 10)
    assert ok, why
    g._trackb_escalate(i, "DUST_WAITING_FOR_COPY_FILL")
    assert "s-NEAR" in core.load_json(core.CLOSE_ESCALATIONS_FILE, {})
    # Simulate the independently proven exchange fill and copy-fill ledger update.
    ledger.signed, exchange_net[0] = 0.0, 0.0
    assert g.clear_trackb_escalations() == 1
    assert core.load_json(core.CLOSE_DUST_HOLDS_FILE, {}) == {}
    assert core.load_json(core.CLOSE_ESCALATIONS_FILE, {}) == {}


def test_single_point_one_whole_exchange_position_exempt_from_ten_dollar_min(
        monkeypatch, tmp_path):
    g, ledger, _, net = setup(monkeypatch, tmp_path, size=-0.1, account_net=-0.1)
    i = intent()
    resolved = {"raw_coin": "NEAR", "min_order_value_usd": 10.0}
    ok, row = g._validate_final_wire_order(i, resolved, "NEAR", 0.1, 4.4, {},
                                            wire_reduce_only=True)
    assert ok, row
    allowed, why = g._reserve_close_wire(i, "NEAR", True, 0.1, 4.4,
                                         True, "0x" + "2" * 32, 10)
    assert allowed, why
    assert g._verify_close_reserved_wire(i, "0x" + "2" * 32, True, .1, True,
                                         4.4, 10, size_decimals=1)
    g._trackb_escalate(i, "AWAIT_COPY_FILL")
    ledger.signed, net[0] = 0.0, 0.0
    assert g.clear_trackb_escalations() == 1
    assert not core.load_json(core.CLOSE_DUST_HOLDS_FILE, {})
    assert not core.load_json(core.CLOSE_ESCALATIONS_FILE, {})


def test_partial_dust_cannot_borrow_user_residual_or_round_up(monkeypatch, tmp_path):
    g, ledger, _, net = setup(monkeypatch, tmp_path, size=-0.1, account_net=-10.5)
    i = intent()
    resolved = {"raw_coin": "NEAR", "min_order_value_usd": 10.0}
    ok, block = g._validate_final_wire_order(i, resolved, "NEAR", .1, 4.4, {},
                                             wire_reduce_only=True)
    assert not ok and block["status"] == "SEND_NOT_ATTEMPTED_BELOW_MIN_NOTIONAL"
    reserved, why = g._reserve_close_wire(i, "NEAR", True, .1, 4.4,
                                          True, "0x" + "3" * 32, 10)
    assert not reserved and why == "PARTIAL_REDUCE_ONLY_DUST_HELD"
    for n in range(40):
        total = g._record_close_dust_hold(intent("replayed-" + str(n)), .1, 4.4, "HELD")
    assert total == pytest.approx(.1)  # 40 different ids still only one owned 0.1
    assert ledger.user == -10.4
    assert core.load_json(core.CLOSE_RESERVATIONS_FILE, {}) == {}
