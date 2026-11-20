from __future__ import annotations

import json


def test_cap_read_error_allows_reduce_only_exit_to_fake_exchange(tmp_path, monkeypatch):
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    import HL_Live_Copy_Service as svcmod

    svcmod.TEST_INJECTION_ENABLED = True
    svcmod.configure_paths(tmp_path, tmp_path / "raw_live_fills.csv")
    (tmp_path / "live_config.json").write_text(json.dumps({
        "wallets": {
            "0xcap-test": {
                "mode": "LIVE", "enabled": True, "copy_mode": "proportional",
                "norm_base": 1000.0, "leader_equity_base": 1000.0,
            },
        },
        "global_controls": {"max_order_notional_usd": 0.0},
    }), encoding="utf-8")

    engine = svcmod.DryRunLiveCopyService()
    engine.lineage_valid = True
    exchange_reads = []
    engine.account_net_provider = lambda coin: exchange_reads.append(coin) or {
        "ok": True, "net": 10.0, "source": "FAKE_EXCHANGE",
    }
    cfg = svcmod.LiveWalletConfig(
        wallet="0xcap-test", mode="LIVE", copy_mode="proportional",
        norm_base=1000.0, leader_equity_base=1000.0, enabled=True,
    )

    def fill(fill_id, side, size, delta, timestamp):
        return svcmod.LeaderFill(
            fill_id=fill_id, wallet="0xcap-test", coin="BTC", side=side,
            price=100.0, size=size, signed_size_delta=delta, timestamp_ms=timestamp,
            timestamp_iso="2026-01-01T00:00:00Z", source="test",
            recording_method="test", raw={},
        )

    engine.account_net_provider = lambda coin: {"ok": True, "net": 0.0, "source": "FAKE_EXCHANGE"}
    engine.process_fill(fill("open", "BUY", 10.0, 10.0, 1000), cfg)
    engine.account_net_provider = lambda coin: exchange_reads.append(coin) or {
        "ok": True, "net": 10.0, "source": "FAKE_EXCHANGE",
    }
    monkeypatch.setattr(engine, "global_order_cap", lambda: None)

    engine.process_fill(fill("reduce", "SELL", 5.0, -5.0, 2000), cfg)

    assert exchange_reads == ["BTC"]
    assert engine.get_position("0xcap-test", "BTC")["signed_size"] == 5.0
    assert engine.state["counters"].get("entries_blocked_global_max_order_notional_cap_read_error", 0) == 0


def test_cap_read_error_blocks_entry_with_explicit_status(tmp_path, monkeypatch):
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    import HL_Live_Copy_Service as svcmod

    svcmod.TEST_INJECTION_ENABLED = True
    svcmod.configure_paths(tmp_path, tmp_path / "raw_live_fills.csv")
    (tmp_path / "live_config.json").write_text(json.dumps({"wallets": {}}), encoding="utf-8")
    engine = svcmod.DryRunLiveCopyService()
    engine.lineage_valid = True
    exchange_reads = []
    engine.account_net_provider = lambda coin: exchange_reads.append(coin) or {
        "ok": True, "net": 0.0, "source": "FAKE_EXCHANGE",
    }
    cfg = svcmod.LiveWalletConfig(
        wallet="0xcap-test", mode="LIVE", copy_mode="proportional",
        norm_base=100.0, leader_equity_base=1000.0, enabled=True,
    )
    fill = svcmod.LeaderFill(
        fill_id="entry", wallet="0xcap-test", coin="BTC", side="BUY",
        price=100.0, size=1.0, signed_size_delta=1.0, timestamp_ms=1000,
        timestamp_iso="2026-01-01T00:00:00Z", source="test",
        recording_method="test", raw={},
    )
    monkeypatch.setattr(engine, "global_order_cap", lambda: None)
    monkeypatch.setattr(engine, "convergence_notional_for_fill", lambda cfg, fill: {
        "ok": True, "notional": 100.0, "reduce_only": False, "side": "BUY", "action": "OPEN",
    })

    engine.process_fill(fill, cfg)

    row = svcmod.last_csv_row(svcmod.ORDER_INTENTS_CSV)
    assert row["status"] == "BLOCKED_GLOBAL_MAX_ORDER_NOTIONAL_CAP_READ_ERROR"
    assert row["decision_reason"] == "GLOBAL_MAX_ORDER_NOTIONAL_CAP_READ_ERROR"
    assert exchange_reads == []
    assert engine.state["counters"].get("entries_blocked_global_max_order_notional_cap_read_error", 0) == 1
