#!/usr/bin/env python3
"""Wallet config loading and per-wallet pause regressions; offline only."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="wallet_load_gaps_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)
    os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
    os.environ["HL_LIVE_POLL_ENABLED"] = "0"
    os.environ["HL_LIVE_WALLET_GATE_FILE"] = str(tmp / "wallet_gate.json")

    import HL_Live_Copy_Service as svcmod

    good_wallet = "0x" + "a" * 40
    malformed_wallet = "0x" + "b" * 40
    paused_wallet = "0x" + "c" * 40
    other_wallet = "0x" + "d" * 40

    (tmp / "live_config.json").write_text(json.dumps({"wallets": {
        malformed_wallet: "malformed-wallet-config",
        good_wallet: {"mode": "LIVE", "enabled": True, "copy_mode": "fixed"},
    }}), encoding="utf-8")
    svcmod.configure_paths(tmp, tmp / "no_fills.csv")
    service = svcmod.DryRunLiveCopyService()
    loaded = service.load_config()
    check("MALFORMED_WALLET_ENTRY_SKIPPED_WITHOUT_AFFECTING_OTHERS",
          malformed_wallet not in loaded and good_wallet in loaded and loaded[good_wallet].enabled,
          f"loaded={sorted(loaded)}")

    (tmp / "live_config.json").write_text(json.dumps({"wallets": {
        paused_wallet: {"mode": "LIVE", "enabled": True, "copy_mode": "fixed"},
        other_wallet: {"mode": "LIVE", "enabled": True, "copy_mode": "fixed"},
    }}), encoding="utf-8")
    (tmp / "wallet_gate.json").write_text(json.dumps({paused_wallet: {"mode": "OFF"}}), encoding="utf-8")
    service = svcmod.DryRunLiveCopyService()
    configs = service.load_config()
    service.process_fill(svcmod.LeaderFill(
        fill_id="paused-wallet-fill", wallet=paused_wallet, coin="BTC", side="BUY",
        price=100.0, size=1.0, signed_size_delta=1.0, timestamp_ms=1,
        timestamp_iso="2026-01-01T00:00:00Z", source="test", recording_method="test", raw={},
    ), configs[paused_wallet])
    other_cfg = service.apply_wallet_gate(configs[other_wallet])
    check("PAUSE_BLOCKS_ONLY_SELECTED_WALLET",
          service.state["counters"].get("fills_skipped_off", 0) == 1
          and service.get_position(paused_wallet, "BTC").get("signed_size", 0.0) == 0.0
          and other_cfg.mode == "LIVE" and other_cfg.enabled,
          f"skipped={service.state['counters'].get('fills_skipped_off', 0)} other_mode={other_cfg.mode}")

    failed = [name for name, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
