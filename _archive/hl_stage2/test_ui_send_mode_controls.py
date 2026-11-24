from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _setup(tmp_path, monkeypatch):
    monkeypatch.setenv("HL_LIVE_AUTO_SEND_ENABLED", "1")
    monkeypatch.setenv("HL_LIVE_POLL_ENABLED", "0")
    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient

    config_path = tmp_path / "live_config.json"
    config_path.write_text(json.dumps({
        "wallets": {"leader": {"enabled": True, "mode": "ON", "fixed_notional": 500}},
        "global_controls": {"send_mode": "OFF", "max_total_live_exposure_usd": 2500},
    }), encoding="utf-8")
    ui.LIVE_COPY_CONFIG_FILE = config_path
    ui.LIVE_COPY_AUDIT_DIR = tmp_path / "audit"
    ui.LIVE_COPY_ORDER_INTENTS_CSV = ui.LIVE_COPY_AUDIT_DIR / "order_intents.csv"
    ui.SEND_ATTEMPTS_CSV = ui.LIVE_COPY_AUDIT_DIR / "send_attempts.csv"
    return ui, TestClient


def test_global_controls_expose_real_send_mode_and_tile_displays_it(tmp_path, monkeypatch):
    ui, TestClient = _setup(tmp_path, monkeypatch)
    with TestClient(ui.app) as client:
        response = client.get("/api/global-controls")

    assert response.status_code == 200
    assert response.json()["send_mode"] == "OFF"
    page = ui.render_live_copy_control_panel()
    assert 'id="lcBannerSending"' in page
    assert "st.send_mode" in page


def test_unconfirmed_send_mode_change_cannot_reach_on(tmp_path, monkeypatch):
    ui, TestClient = _setup(tmp_path, monkeypatch)
    with TestClient(ui.app) as client:
        response = client.post("/api/global-controls", json={"send_mode": "ON"})

    written = json.loads(ui.LIVE_COPY_CONFIG_FILE.read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert response.json()["send_mode"] == "OFF"
    assert written["global_controls"]["send_mode"] == "OFF"


def test_confirmed_off_and_close_only_do_not_place_or_cancel_orders(tmp_path, monkeypatch):
    ui, TestClient = _setup(tmp_path, monkeypatch)
    initial = json.loads(ui.LIVE_COPY_CONFIG_FILE.read_text(encoding="utf-8"))
    for requested, stored, shown in (("OFF", "OFF", "OFF"), ("CLOSE ONLY", "CLOSE", "CLOSE ONLY")):
        with TestClient(ui.app) as client:
            response = client.post("/api/global-controls", json={"send_mode": requested, "confirmed": True})

        written = json.loads(ui.LIVE_COPY_CONFIG_FILE.read_text(encoding="utf-8"))
        assert response.status_code == 200
        assert response.json()["send_mode"] == shown
        assert written["global_controls"]["send_mode"] == stored
        assert written["wallets"] == initial["wallets"]
        assert written["global_controls"]["max_total_live_exposure_usd"] == initial["global_controls"]["max_total_live_exposure_usd"]
    assert not ui.LIVE_COPY_ORDER_INTENTS_CSV.exists()
    assert not ui.SEND_ATTEMPTS_CSV.exists()


def test_confirmed_on_uses_existing_send_mode_control(tmp_path, monkeypatch):
    ui, TestClient = _setup(tmp_path, monkeypatch)
    with TestClient(ui.app) as client:
        response = client.post("/api/global-controls", json={"send_mode": "ON", "confirmed": True})

    written = json.loads(ui.LIVE_COPY_CONFIG_FILE.read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert response.json()["send_mode"] == "ON"
    assert written["global_controls"]["send_mode"] == "ON"


def test_confirmed_invalid_send_mode_fails_closed_to_off(tmp_path, monkeypatch):
    ui, TestClient = _setup(tmp_path, monkeypatch)
    with TestClient(ui.app) as client:
        response = client.post("/api/global-controls", json={"send_mode": "BANANA", "confirmed": True})

    written = json.loads(ui.LIVE_COPY_CONFIG_FILE.read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert response.json()["send_mode"] == "OFF"
    assert written["global_controls"]["send_mode"] == "OFF"


def test_off_and_close_only_buttons_confirm_before_posting(tmp_path, monkeypatch):
    ui, _ = _setup(tmp_path, monkeypatch)
    page = ui.render_live_copy_control_panel()

    assert 'id="lcSendModeOff"' in page
    assert 'id="lcSendModeCloseOnly"' in page
    assert 'id="lcSendModeOn"' in page
    assert "window.confirm" in page
    assert "confirmed:true" in page
    assert "send_mode:mode" in page


def test_invalid_or_missing_send_mode_reads_as_off_even_with_legacy_env_on(tmp_path, monkeypatch):
    ui, _ = _setup(tmp_path, monkeypatch)
    assert ui._send_mode({"global_controls": {"send_mode": "BANANA"}, "auto_send_enabled": True}) == "OFF"
    assert ui._send_mode({"auto_send_enabled": True}) == "OFF"

