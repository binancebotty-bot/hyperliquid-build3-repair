#!/usr/bin/env python3
"""A PARTIAL POST to /api/global-controls must not reset the owned risk caps it omits to 0 (0 means OFF).

GPT requirement (issue #14, CID 7097514856): omitted risk caps were reset to their 0.0 defaults on save, which silently
switches the caps off. Also holds a negative regression control: the OLD merge (_normalise_global_controls(submitted)
alone) is run against the same assertions and must FAIL them, proving the test detects the bad behaviour.

Run (from _archive/hl_stage2): python test_ui_global_controls_partial_post.py   # isolated temp config, no network or orders.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
CAPS = {
    "max_total_live_exposure_usd": 5000.0,
    "max_asset_directional_exposure_usd": 1500.0,
    "max_daily_loss_usd": 250.0,
    "max_wallet_exposure_usd": 800.0,
    "max_order_notional_usd": 1000.0,
    "max_close_adverse_diff_pct": 0.3,
    "symbol_allowlist": ["BTC", "ETH"],
    "symbol_blocklist": ["DOGE"],
    "marketable_bps": 35.0,
}


def caps_kept(controls: dict, expect_changed: dict) -> dict:
    want = {**CAPS, **expect_changed}
    return {k: controls.get(k) == v for k, v in want.items()}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="global_controls_partial_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp / "audit")
    os.environ["HL_LIVE_AUTO_SEND_ENABLED"] = "0"
    os.environ["HL_LIVE_POLL_ENABLED"] = "0"
    config_path = tmp / "live_config.json"
    config_path.write_text(json.dumps({"wallets": {}, "global_controls": {**CAPS, "send_mode": "CLOSE"}}), encoding="utf-8")

    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient

    ui.LIVE_COPY_CONFIG_FILE = config_path
    results = {}
    with TestClient(ui.app) as client:
        r = client.post("/api/global-controls", json={"max_order_notional_usd": 1250.0})
        written = json.loads(config_path.read_text(encoding="utf-8"))["global_controls"]
        results["save_succeeded"] = r.status_code == 200 and r.json().get("ok") is True
        results["submitted_value_applied"] = written.get("max_order_notional_usd") == 1250.0
        for name, ok in caps_kept(written, {"max_order_notional_usd": 1250.0}).items():
            results[f"omitted_{name}_kept"] = ok
        results["unowned_send_mode_kept"] = written.get("send_mode") == "CLOSE"

        # the slippage alias alone must not reset the other caps either, and still applies
        client.post("/api/global-controls", json={"marketable_slippage_pct": 0.5})
        written = json.loads(config_path.read_text(encoding="utf-8"))["global_controls"]
        results["alias_applied"] = written.get("marketable_bps") == 50.0
        for name, ok in caps_kept(written, {"max_order_notional_usd": 1250.0, "marketable_bps": 50.0}).items():
            results[f"after_alias_{name}_kept"] = ok

        # an explicit zero IS honoured (the operator turns a cap off on purpose) and leaves the others alone
        client.post("/api/global-controls", json={"max_daily_loss_usd": 0})
        written = json.loads(config_path.read_text(encoding="utf-8"))["global_controls"]
        results["explicit_zero_honoured"] = written.get("max_daily_loss_usd") == 0.0
        results["explicit_zero_leaves_others"] = written.get("max_wallet_exposure_usd") == 800.0

    # NEGATIVE REGRESSION CONTROL: the old merge resets omitted caps; the assertions above would fail on it.
    old = ui._normalise_global_controls({"max_order_notional_usd": 1250.0})
    old_kept = caps_kept(old, {"max_order_notional_usd": 1250.0})
    results["control_old_merge_is_detected_as_bad"] = (not all(old_kept.values())) and old.get("max_total_live_exposure_usd") == 0.0

    for name, passed in results.items():
        print(f"RESULT::{name}_{'PASS' if passed else 'FAIL'}")
    print(f"TOTAL={len(results)} FAILED={sum(not v for v in results.values())}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
