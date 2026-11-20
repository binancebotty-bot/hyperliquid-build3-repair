"""Offline checks documenting when the final order-notional cap is active."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

os.environ.update({
    "HL_LIVE_AUDIT_DIR": tempfile.mkdtemp(prefix="zero_order_cap_"),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_WS_ENABLED": "0",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
    "HL_LIVE_PREWARM_SYMBOL_META": "0",
    "HL_LIVE_PREWARM_SDK_CLIENT": "0",
    "HL_LIVE_HOT_SEND_WORKERS": "1",
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
    "HL_LIVE_MISSED_ENTRY_RULE": "0",
})

import requests
import HL_Live_Copy_Service_Core as c

LEADER = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40
MIDS = {"BTC": 100.0}
EXP_PAYLOAD = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}
RESOLVED_BTC = {
    "ok": True, "sdk_coin": "BTC", "raw_coin": "BTC", "sz_decimals": 3,
    "price_max_decimals": 2, "perp_dexs": [], "sdk_order_compatible": True,
    "min_order_value_usd": 10.0, "min_size": 0.001, "status": "OK",
}


class FakeExchange:
    def __init__(self):
        self.calls = []

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append((coin, is_buy, size, px, tif, reduce_only))
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
            {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1111}}
        ]}}}


def make_gateway(fake_exchange, max_notional):
    c.HLAccount, c.HLExchange = object, object
    ledger = c.ManualLedger(path=Path(os.environ["HL_LIVE_AUDIT_DIR"]) / "ledger.json")
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    gw.cfg.max_order_notional = lambda: max_notional
    gw._resolve_coin = lambda coin: dict(RESOLVED_BTC)
    gw._get_exchange_client = lambda *a, **k: fake_exchange
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._exchange_client_for_coin = lambda raw_coin: (fake_exchange, "BTC")
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._pre_send_ownership_gate = lambda intent: (True, {})
    gw._validate_final_wire_order = c.SenderGateway._validate_final_wire_order.__get__(gw, c.SenderGateway)
    return gw


def make_intent(size, price=100.0):
    fill = c.LeaderFill("f1", LEADER, "BTC", "BUY", price, size, c.utc_now_ms(), "TEST")
    return c.Intent("i1", fill, "BUY", size, size * price, "LIVE", "fixed", "ENTRY_ALLOWED",
                    "ENTRY", "s1", "", "LONG", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=ENTRY;")


def send_via_send_real(gw, intent):
    return gw._send_real(intent)


@pytest.fixture(autouse=True)
def offline_send_setup(monkeypatch):
    def offline(*_args, **_kwargs):
        raise AssertionError("offline test attempted network access")

    monkeypatch.setattr(requests, "post", offline)
    monkeypatch.setattr(requests, "get", offline)
    monkeypatch.setattr(c.requests, "post", offline)
    monkeypatch.setenv("HL_LIVE_HL_PRIVATE_KEY", "offline")
    monkeypatch.setenv("HL_LIVE_HL_ACCOUNT_ADDRESS", FOLLOWER)
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(MIDS)
    c.LEADER_MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(MIDS)
    c.EXPOSURE_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP_PAYLOAD)
    c.LEADER_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP_PAYLOAD)
    c._FOLLOWER_MIDS.update(px=dict(MIDS), ms=c.utc_now_ms(), scope=[""])
    c._LEADER_MIDS.update(px=dict(MIDS), ms=c.utc_now_ms(), scope=[""])
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": {"symbol_blocklist": [], "min_notional": 1, "marketable_bps": 20},
        "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100}},
    })


def test_zero_max_order_notional_does_not_apply_cap():
    exchange = FakeExchange()
    gw = make_gateway(exchange, 0.0)

    ok, _status, _result = send_via_send_real(gw, make_intent(611.22))

    assert ok
    assert len(exchange.calls) == 1


def test_61121_99_cap_refuses_61122_entry_before_exchange():
    exchange = FakeExchange()
    gw = make_gateway(exchange, 61121.99)

    ok, status, result = send_via_send_real(gw, make_intent(611.22))

    assert not ok
    assert status == "SEND_NOT_ATTEMPTED_MAX_ORDER_NOTIONAL"
    assert result["terminal_state"] == "SEND_NOT_ATTEMPTED_MAX_ORDER_NOTIONAL"
    assert exchange.calls == []
