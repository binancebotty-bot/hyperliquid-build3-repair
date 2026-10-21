#!/usr/bin/env python3
"""Test: Saving controls never drops the runtime send_mode.

This test verifies that when global controls are saved via the API,
the send_mode value (and other un-owned keys like follower_leverage, liq_parity)
are preserved and not dropped.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FAILS = []
PASSES = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print("  PASS " + name)
        PASSES.append(name)
    else:
        print("  FAIL " + name + "  " + detail)
        FAILS.append(name)


def write_cfg(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def simulate_save_handler(config_file: Path, submitted: dict) -> dict:
    """Call the real async endpoint handler, then read its persisted result."""
    import HL_Copy_App_SSOT as UI

    class FakeRequest:
        def __init__(self, body: dict):
            self.body = body

        async def json(self):
            return self.body

    asyncio.run(UI.set_global_controls(FakeRequest(submitted)))
    saved = json.loads(config_file.read_text(encoding="utf-8-sig"))
    return saved["global_controls"]


def main() -> int:
    import HL_Copy_App_SSOT as UI

    with tempfile.TemporaryDirectory() as td:
        # Set up the audit dir and config file
        audit_dir = Path(td) / "hl_live_copy_audit"
        audit_dir.mkdir(parents=True)
        config_file = audit_dir / "live_config.json"

        # Monkey-patch the module's config file path
        UI.LIVE_COPY_CONFIG_FILE = config_file
        UI.LIVE_COPY_AUDIT_DIR = audit_dir
        UI.LIVE_CONFIG_FILE = config_file
        UI.LIVE_CONFIG_DIR = audit_dir

        wallet = "0x" + "a" * 40

        # Initial config with send_mode, follower_leverage, liq_parity (un-owned keys)
        # and some owned global controls
        initial_config = {
            "global_controls": {
                "send_mode": "CLOSE",
                "follower_leverage": 7,
                "liq_parity": True,
                "max_order_notional_usd": 100.0,
                "marketable_bps": 20.0
            },
            "wallets": {
                wallet: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 10}
            }
        }
        write_cfg(config_file, initial_config)

        # Verify initial load preserves un-owned keys
        loaded = UI._load_live_copy_config()
        gc = loaded.get("global_controls", {})
        check("initial load preserves send_mode", gc.get("send_mode") == "CLOSE",
              f"got {gc.get('send_mode')}")
        check("initial load preserves follower_leverage", gc.get("follower_leverage") == 7,
              f"got {gc.get('follower_leverage')}")
        check("initial load preserves liq_parity", gc.get("liq_parity") is True,
              f"got {gc.get('liq_parity')}")
        check("initial load preserves owned max_order_notional_usd", gc.get("max_order_notional_usd") == 100.0,
              f"got {gc.get('max_order_notional_usd')}")

        # First save: change max_order_notional_usd and marketable_slippage_pct
        gc_after_save1 = simulate_save_handler(config_file, {
            "max_order_notional_usd": 200.0,
            "marketable_slippage_pct": 0.30  # 30 bps = 0.30%
        })

        check("send_mode survives save", gc_after_save1.get("send_mode") == "CLOSE",
              f"got {gc_after_save1.get('send_mode')}")
        check("follower_leverage survives save", gc_after_save1.get("follower_leverage") == 7,
              f"got {gc_after_save1.get('follower_leverage')}")
        check("liq_parity survives save", gc_after_save1.get("liq_parity") is True,
              f"got {gc_after_save1.get('liq_parity')}")
        check("owned max_order_notional_usd updated", gc_after_save1.get("max_order_notional_usd") == 200.0,
              f"got {gc_after_save1.get('max_order_notional_usd')}")
        check("owned marketable_bps updated", gc_after_save1.get("marketable_bps") == 30.0,
              f"got {gc_after_save1.get('marketable_bps')}")

        # Second save: change only marketable_slippage_pct
        gc_after_save2 = simulate_save_handler(config_file, {"marketable_slippage_pct": 0.25})  # 25 bps

        check("send_mode survives second save", gc_after_save2.get("send_mode") == "CLOSE",
              f"got {gc_after_save2.get('send_mode')}")
        check("follower_leverage survives second save", gc_after_save2.get("follower_leverage") == 7,
              f"got {gc_after_save2.get('follower_leverage')}")
        check("liq_parity survives second save", gc_after_save2.get("liq_parity") is True,
              f"got {gc_after_save2.get('liq_parity')}")
        check("max_order_notional_usd persists across saves", gc_after_save2.get("max_order_notional_usd") == 200.0,
              f"got {gc_after_save2.get('max_order_notional_usd')}")
        check("marketable_bps updated to 25", gc_after_save2.get("marketable_bps") == 25.0,
              f"got {gc_after_save2.get('marketable_bps')}")

        # Negative control: unknown key submitted directly to API should be ignored
        # (not added to global_controls)
        gc_after_save3 = simulate_save_handler(config_file, {
            "unknown_custom_key": "should_be_ignored", 
            "max_order_notional_usd": 300.0
        })

        check("unknown key not added to global_controls", "unknown_custom_key" not in gc_after_save3,
              f"unknown key found in {list(gc_after_save3.keys())}")
        check("max_order_notional_usd updated to 300", gc_after_save3.get("max_order_notional_usd") == 300.0,
              f"got {gc_after_save3.get('max_order_notional_usd')}")
        check("send_mode still CLOSE after unknown key attempt", gc_after_save3.get("send_mode") == "CLOSE",
              f"got {gc_after_save3.get('send_mode')}")

    print(f"\nTOTAL={len(PASSES) + len(FAILS)} FAILED={len(FAILS)}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())