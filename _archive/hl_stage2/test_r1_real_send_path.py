"""Real SenderGateway wire-cap coverage using only a fake exchange client."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# Keep module-level paths isolated before importing the production sender.
_AUDIT_DIR = Path(tempfile.mkdtemp(prefix="r1_real_send_path_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(_AUDIT_DIR),
    "HL_LIVE_ENV_FILE": str(_AUDIT_DIR / "no-secrets.env"),
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
})

import HL_Live_Copy_Service_Core as c


RESOLVED_BTC = {
    "ok": True,
    "sdk_coin": "BTC",
    "raw_coin": "BTC",
    "sz_decimals": 3,
    "price_max_decimals": 2,
    "perp_dexs": [""],
    "sdk_order_compatible": True,
    "min_order_value_usd": 10.0,
    "min_size": 0.001,
    "status": "OK",
}


class FakeExchange:
    def __init__(self) -> None:
        self.order_calls = []

    def update_leverage(self, leverage, name, is_cross=True):
        return {"status": "ok"}

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, **kwargs):
        self.order_calls.append({
            "coin": coin,
            "is_buy": is_buy,
            "size": size,
            "px": px,
            "tif": (tif.get("limit") or {}).get("tif"),
            "reduce_only": reduce_only,
        })
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
            {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}
        ]}}}


def _make_send(tmp_path, monkeypatch, cap: float):
    config_path = tmp_path / "live_config.json"
    config_path.write_text(json.dumps({
        "global_controls": {"max_order_notional_usd": cap, "marketable_bps": 0},
        "wallets": {},
    }), encoding="utf-8")
    cfg = c.ConfigManager(config_path=config_path)
    sender = c.SenderGateway(cfg, c.AuditLogWriter(), c.ManualLedger(path=tmp_path / "ledger.json"))
    exchange = FakeExchange()

    # This is a fake-client test: present a non-secret configured sentinel and never
    # construct the SDK client or sign anything.
    getenv = os.getenv

    def fake_getenv(name, default=None):
        if name == "HL_LIVE_HL_PRIVATE_KEY":
            return "test-only-configured-sentinel"
        if name == "HL_LIVE_HL_ACCOUNT_ADDRESS":
            return ""
        if name == "HL_LIVE_MISSED_ENTRY_RULE":
            return "0"
        return getenv(name, default)

    monkeypatch.setattr(c.os, "getenv", fake_getenv)
    monkeypatch.setattr(c, "HLAccount", object)
    monkeypatch.setattr(c, "HLExchange", object)
    monkeypatch.setattr(c, "LEADER_NETWORK", "testnet")
    monkeypatch.setattr(c, "FOLLOWER_NETWORK", "testnet")
    monkeypatch.setattr(c, "follower_mid", lambda _coin: 110.22)

    sender._resolve_coin = lambda _coin: dict(RESOLVED_BTC)
    sender._get_exchange_client = lambda *args, **kwargs: exchange
    sender._exchange_client_has_symbol = lambda *_args, **_kwargs: True
    sender._pre_exchange_asset_safety = lambda *_args, **_kwargs: (True, {})
    sender._ensure_margin_mode = lambda *_args, **_kwargs: None
    sender._symbol_reject_circuit_active = lambda *_args, **_kwargs: False

    fill = c.LeaderFill("fill-r1", "test-leader", "BTC", "BUY", 110.22, 10.0,
                        c.utc_now_ms(), "TEST")
    intent = c.Intent(
        "intent-r1", fill, "BUY", 10.0, 1102.20, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
        "test-sleeve", "", "LONG", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=ENTRY;",
    )
    return sender, exchange, intent


def test_over_cap_real_send_is_refused_before_fake_exchange_order(tmp_path, monkeypatch):
    sender, exchange, intent = _make_send(tmp_path, monkeypatch, cap=1005.0)

    ok, status, result = sender._send_real(intent)

    assert not ok
    assert status in {
        "MAX_ORDER_NOTIONAL_EXCEEDED_AT_WIRE",
        "SEND_NOT_ATTEMPTED_MAX_ORDER_NOTIONAL",
    }
    assert result.get("exchange_called") is False
    assert exchange.order_calls == []


def test_mutating_cap_check_off_allows_order_to_reach_fake_exchange(tmp_path, monkeypatch):
    sender, exchange, intent = _make_send(tmp_path, monkeypatch, cap=1005.0)
    # Mutation control: remove the configured cap condition while leaving the real
    # final-wire validator and the rest of the production send path in place.
    monkeypatch.setattr(sender.cfg, "max_order_notional", lambda: 0.0)

    ok, status, _result = sender._send_real(intent)

    assert ok
    assert status == "ORDER_FILLED"
    assert len(exchange.order_calls) == 1
    assert exchange.order_calls[0]["reduce_only"] is False


def test_zero_max_order_notional_disables_wire_cap(tmp_path, monkeypatch):
    sender, exchange, intent = _make_send(tmp_path, monkeypatch, cap=0.0)

    ok, status, _result = sender._send_real(intent)

    assert ok
    assert status == "ORDER_FILLED"
    assert len(exchange.order_calls) == 1
    assert exchange.order_calls[0]["reduce_only"] is False
