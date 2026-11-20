#!/usr/bin/env python3
"""Per-wallet and global wallet-exposure caps: the tightest active cap applies."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import HL_Live_Copy_Service_Core as c

WALLET = "0x" + "d" * 40


def wallet_cap(global_cap: float, per_wallet_cap: Optional[float]) -> float:
    cfg = c.ConfigManager.__new__(c.ConfigManager)
    cfg.config = {
        "global_controls": {"max_wallet_exposure_usd": global_cap},
        "wallets": {WALLET: ({"max_wallet_exposure_usd": per_wallet_cap} if per_wallet_cap is not None else {})},
    }
    return cfg.max_wallet_exposure(WALLET)


def test_tighter_global_wallet_cap_applies() -> None:
    assert wallet_cap(500.0, 1000.0) == 500.0


def test_tighter_per_wallet_cap_applies() -> None:
    assert wallet_cap(1000.0, 500.0) == 500.0


def test_zero_per_wallet_cap_leaves_global_cap_active() -> None:
    assert wallet_cap(500.0, 0.0) == 500.0


def test_zero_global_cap_leaves_per_wallet_cap_active() -> None:
    assert wallet_cap(0.0, 500.0) == 500.0


def test_zero_caps_are_both_off() -> None:
    assert wallet_cap(0.0, 0.0) == 0.0
