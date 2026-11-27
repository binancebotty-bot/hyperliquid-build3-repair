"""Live Copy activity counters are scoped to the current engine run."""
from __future__ import annotations

import sys
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import HL_Copy_App_SSOT as ui


LEADER_A = "0x" + "a" * 40
LEADER_B = "0x" + "b" * 40


def test_run_activity_counts_trades_skips_reasons_latency_and_each_leader() -> None:
    attempts = [
        {"attempt_id": "old", "created_at_ms": 900, "leader_wallet": LEADER_A,
         "status": "ORDER_FILLED", "send_total_ms": 999},
        # Pending and final rows for the same attempt count once; the latest row wins.
        {"attempt_id": "trade-a", "created_at_ms": 1100, "leader_wallet": LEADER_A,
         "status": "PENDING_SEND"},
        {"attempt_id": "trade-a", "created_at_ms": 1200, "leader_wallet": LEADER_A,
         "status": "ORDER_FILLED", "send_total_ms": 10},
        {"attempt_id": "trade-b", "created_at_ms": 1300, "leader_wallet": LEADER_B,
         "status": "ORDER_FILLED", "send_total_ms": 20},
        {"attempt_id": "block-a", "created_at_ms": 1400, "leader_wallet": LEADER_A,
         "status": "BLOCKED_BY_RISK", "reason": "DAILY_LOSS_LIMIT", "send_total_ms": 30},
        {"attempt_id": "reject-b", "created_at_ms": 1500, "leader_wallet": LEADER_B,
         "status": "ORDER_REJECTED", "reject_category": "TESTNET_REJECT", "send_total_ms": 40},
    ]
    intents = [
        {"created_at_ms": 1600, "leader_wallet": LEADER_A,
         "execution_decision": "DO_NOT_MARKET_COPY", "decision_reason": "LATE_COPY"},
        {"created_at_ms": 950, "leader_wallet": LEADER_B,
         "execution_decision": "MANUAL_REVIEW", "decision_reason": "OLD_REVIEW"},
    ]

    activity = ui._build_live_activity_summary(attempts, intents, started_at_ms=1000)

    assert activity["trade_count"] == 2
    assert activity["skip_count"] == 2
    assert activity["skip_reasons"] == {
        "DAILY_LOSS_LIMIT": 1,
        "LATE_COPY": 1,
    }
    assert activity["rejected_count"] == 1
    assert activity["send_latency_p50_ms"] == 20
    assert activity["send_latency_p95_ms"] == 40
    assert activity["by_leader"][LEADER_A.lower()]["trade_count"] == 1
    assert activity["by_leader"][LEADER_A.lower()]["skip_count"] == 2
    assert activity["by_leader"][LEADER_B.lower()]["trade_count"] == 1
    assert activity["by_leader"][LEADER_B.lower()]["skip_count"] == 0


def test_clean_restart_zeros_activity_without_hiding_persistent_positions() -> None:
    old_attempts = [{"attempt_id": "old", "created_at_ms": 900, "leader_wallet": LEADER_A,
                     "status": "ORDER_FILLED", "send_total_ms": 12}]
    old_intents = [{"created_at_ms": 950, "leader_wallet": LEADER_A,
                    "execution_decision": "DO_NOT_MARKET_COPY", "decision_reason": "OLD_SKIP"}]
    activity = ui._build_live_activity_summary(old_attempts, old_intents, started_at_ms=1000)
    positions = {"by_wallet": {LEADER_A: {
        "BTC": {"signed_size": 1.0, "avg_entry_px": 100.0},
        "ETH": {"signed_size": -2.0, "avg_entry_px": 50.0},
    }}}

    rows = ui._build_live_wallet_rows(
        {"wallets": {LEADER_A: {"enabled": True, "mode": "LIVE"}}},
        [], [], positions, {}, {}, live_leader_performance={LEADER_A: {}}, live_fills=[], live_activity=activity
    )

    assert activity["trade_count"] == 0
    assert activity["skip_count"] == 0
    assert activity["send_latency_p50_ms"] is None
    assert activity["send_latency_p95_ms"] is None
    assert rows[0]["filled_count"] == 0
    assert rows[0]["run_skip_count"] == 0
    assert rows[0]["open_position_count"] == 2
    assert set(rows[0]["open_positions"]) == {"BTC", "ETH"}


def test_clean_restart_ui_reads_zeroed_activity_and_health() -> None:
    now_ms = int(time.time() * 1000)
    started_at_ms = now_ms - 100
    old_attempts = [{"attempt_id": "old", "created_at_ms": started_at_ms - 1,
                     "leader_wallet": LEADER_A, "status": "ORDER_FILLED", "send_total_ms": 12}]
    activity = ui._build_live_activity_summary(old_attempts, [], started_at_ms)
    service_state = {"started_at_ms": started_at_ms, "last_state_write_ms": now_ms}
    integrity = {"status": "GREEN", "available": True,
                 "hard_copy_invariant": {"counts": {"ACTIVE_RED": 0}}}
    status = ui._build_live_top_status(
        {}, {}, service_state, integrity, old_attempts, [],
        [{"created_at_ms": started_at_ms - 1, "status": "CLOSE_FAILED"}],
    )

    assert activity["trade_count"] == 0
    assert activity["skip_count"] == 0
    assert activity["send_latency_p50_ms"] is None
    assert status["health"]["level"] == "green"
    assert status["health"]["text"] == "Healthy"


def test_live_copy_status_renders_run_activity_and_latency_cells() -> None:
    source = (HERE / "HL_Copy_App_SSOT.py").read_text(encoding="utf-8-sig")

    assert "live_activity" in source
    assert "Trades this run" in source
    assert "Skips this run" in source
    assert "Send latency p50 / p95" in source
    assert "by_leader" in source


def test_stale_websocket_health_snapshot_is_not_reported_fresh(tmp_path, monkeypatch) -> None:
    path = tmp_path / "live_ws_health.json"
    path.write_text(json.dumps({
        "overall": "WS_OK",
        "ws_summary": {"ws_status": "WS_OK", "socket_open": True, "thread_alive": True},
        "wallets": {LEADER_A: {"stale_ms": 100, "data_status": "FRESH"}},
    }), encoding="utf-8")
    old = time.time() - 3600
    os.utime(path, (old, old))
    monkeypatch.setattr(ui, "LIVE_COPY_WS_HEALTH_FILE", path)

    health = ui._load_live_ws_health()

    assert health["overall"] == "STALE"
    assert health["ws_summary"]["ws_status"] == "STALE"
    assert health["wallets"][LEADER_A]["data_status"] == "STALE"
    assert health["wallets"][LEADER_A]["transport_stale_ms"] >= 3_600_000


def test_unresolved_active_red_outcome_is_not_reported_healthy() -> None:
    now_ms = int(time.time() * 1000)

    health = ui._build_health_summary(
        {"started_at_ms": now_ms - 1000, "last_state_write_ms": now_ms},
        {"status": "GREEN", "available": True,
         "hard_copy_invariant": {"counts": {"ACTIVE_RED": 2}}},
        now_ms=now_ms,
    )

    assert health["level"] == "red"
    assert "unresolved copy outcomes" in health["text"]
