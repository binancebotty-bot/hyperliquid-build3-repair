"""Regression checks for preserving runtime-owned global controls on UI save."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


@pytest.fixture
def global_controls_client(tmp_path, monkeypatch):
    monkeypatch.setenv("HL_LIVE_AUDIT_DIR", str(tmp_path))
    monkeypatch.setenv("HL_LIVE_AUTO_SEND_ENABLED", "0")
    monkeypatch.setenv("HL_LIVE_POLL_ENABLED", "0")

    import HL_Copy_App_SSOT as ui

    config_path = tmp_path / "live_config.json"
    monkeypatch.setattr(ui, "LIVE_COPY_AUDIT_DIR", tmp_path)
    monkeypatch.setattr(ui, "LIVE_COPY_CONFIG_FILE", config_path)
    client = TestClient(ui.app)
    return client, config_path


def _save_and_read(client, config_path, key, value):
    config_path.write_text(json.dumps({"wallets": {}, "global_controls": {key: value}}), encoding="utf-8")
    response = client.post("/api/global-controls", json={"max_order_notional_usd": 25.0})
    assert response.status_code == 200
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    return saved["global_controls"].get(key)


def test_send_mode_preserved(global_controls_client):
    client, config_path = global_controls_client
    assert _save_and_read(client, config_path, "send_mode", "OFF") == "OFF"


def test_follower_leverage_preserved(global_controls_client):
    client, config_path = global_controls_client
    assert _save_and_read(client, config_path, "follower_leverage", 3) == 3


def test_liq_parity_preserved(global_controls_client):
    client, config_path = global_controls_client
    assert _save_and_read(client, config_path, "liq_parity", True) is True


def test_unknown_runtime_flag_preserved(global_controls_client):
    client, config_path = global_controls_client
    assert _save_and_read(client, config_path, "unknown_runtime_flag", "keep-me") == "keep-me"
