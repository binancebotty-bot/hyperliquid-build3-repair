"""A close with no wallet ownership record must be blocked and alerted."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import HL_Live_Copy_Service_Core as c


LEADER = "0x" + "a" * 40


class FakeExchange:
    def __init__(self) -> None:
        self.calls = []

    def order(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"status": "ok"}


def test_no_owner_close_sends_nothing_and_writes_alert(tmp_path, monkeypatch):
    monkeypatch.setenv("HL_LIVE_UNEXPLAINED_WAIT_SEC", "0")
    monkeypatch.setenv("HL_LIVE_TEST_LOCAL_BLOCK_SEND_ATTEMPT", "0")
    monkeypatch.setattr(c, "ORDER_INTENTS_CSV", tmp_path / "order_intents.csv")
    monkeypatch.setattr(c, "SEND_ATTEMPTS_CSV", tmp_path / "send_attempts.csv")
    monkeypatch.setattr(c, "LIVE_FILLS_CSV", tmp_path / "live_fills.csv")
    reconciliation_path = tmp_path / "reconciliation.csv"
    monkeypatch.setattr(c, "RECONCILIATION_CSV", reconciliation_path)
    monkeypatch.setattr(c, "EXCHANGE_ACCOUNT_SNAPSHOT_FILE", tmp_path / "exchange.json")

    config_path = tmp_path / "live_config.json"
    c.atomic_write_json(config_path, {"global_controls": {"send_mode": "ON"}})
    c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {
        "positions_by_coin": {"BTC": {"signed_size": 1.0}},
    })
    ledger = c.ManualLedger(path=tmp_path / "ledger.json")
    exchange = FakeExchange()
    gateway = c.SenderGateway(c.ConfigManager(config_path), c.AuditLogWriter(), ledger)
    gateway.sender_key_invalid = False
    gateway._get_exchange_client = lambda *args, **kwargs: exchange

    fill = c.LeaderFill("fill-no-owner", LEADER, "BTC", "SELL", 100.0, 1.0, c.utc_now_ms(), "TEST")
    intent = c.Intent(
        "intent-no-owner", fill, "SELL", 1.0, 100.0, "LIVE", "fixed", "EXIT_ALLOWED", "EXIT",
        "sleeve-no-owner", "", "LONG", 1.0, 1.0, True, True, c.utc_now_ms(), "lifecycle=EXIT;",
    )

    ok, status = gateway.send_if_allowed(intent)

    assert not ok
    assert status == "OWNERSHIP_GATE_NO_MATCHING_WALLET_SLEEVE"
    assert exchange.calls == []
    with reconciliation_path.open(newline="", encoding="utf-8") as record_file:
        alerts = list(csv.DictReader(record_file))
    assert any(
        row.get("event") == "ALERT"
        and row.get("status") == "OWNERSHIP_GATE_NO_MATCHING_WALLET_SLEEVE"
        and row.get("action") == "NO_SEND_NO_WALLET_OWNED_POSITION"
        for row in alerts
    )
