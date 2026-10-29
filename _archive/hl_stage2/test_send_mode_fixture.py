"""Offline send-mode fixture for independent Core check()-style tests.

Never import this helper in production. Every test script owns an isolated AUDIT_DIR
and stubs its exchange/network; this fixture deliberately does not bypass the
physical master, wallet or exit-entry margin gates.
"""
from __future__ import annotations

import math


def arm_offline_send(core, wallets, *, global_controls=None, copy_mode="fixed",
                     fixed_notional=1000.0, exchange_positions=None,
                     withdrawable=100000.0, gateway=None, ledger=None):
    """Arm a fresh live_config AND an age-current clearinghouseState snapshot.

    Recreate ConfigManager AFTER writing ON: a config instantiated while OFF
    intentionally remains OFF. Preserve existing scenario positions if caller
    does not explicitly supply exchange_positions.
    """
    names = tuple(core.normalise_wallet(w) for w in wallets)
    if not names or any(not core.is_valid_wallet(w) for w in names):
        raise ValueError("offline fixture requires enabled, valid leader wallet(s)")
    if not math.isfinite(float(withdrawable)) or withdrawable < 0:
        raise ValueError("withdrawable must be a nonnegative finite test balance")
    controls = dict(global_controls or {})
    controls["send_mode"] = "ON"
    core.atomic_write_json(core.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": controls,
        "wallets": {
            w: {"enabled": True, "mode": "ON",
                "copy_mode": copy_mode, "fixed_notional": fixed_notional}
            for w in names
        },
    })
    previous = core.load_json(core.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {})
    previous = previous if isinstance(previous, dict) else {}
    positions = (exchange_positions if exchange_positions is not None
                 else previous.get("positions_by_coin", {}))
    positions = positions if isinstance(positions, dict) else {}
    raw = previous.get("raw") if isinstance(previous.get("raw"), dict) else {}
    raw = dict(raw)
    raw["withdrawable"] = str(withdrawable)  # clearinghouseState TOP LEVEL
    raw["marginSummary"] = {"accountValue": str(max(float(withdrawable), 100000.0))}
    raw["assetPositions"] = [
        {"position": {"coin": str(coin), "szi": str(
            item.get("signed_size", 0.0) if isinstance(item, dict) else item)}}
        for coin, item in positions.items()
    ]
    core.atomic_write_json(core.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {
        "created_at_ms": core.utc_now_ms(),
        "raw": raw,
        "positions_by_coin": positions,
    })
    cfg = core.ConfigManager()
    assert cfg.send_mode_now() == "ON"
    assert all(cfg.wallet_enabled(w) and cfg.wallet_mode(w) == "ON" for w in names)
    if gateway is not None:
        gateway.cfg = cfg
        if ledger is not None:
            gateway.ledger = ledger
    return cfg


def fresh_offline_snapshot(core, *, positions=None, withdrawable=100000.0):
    """Refresh snapshot timestamp without changing the currently armed mode."""
    old = core.load_json(core.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {})
    raw = old.get("raw") if isinstance(old, dict) else None
    raw = dict(raw) if isinstance(raw, dict) else {}
    raw["withdrawable"] = str(withdrawable)
    raw["marginSummary"] = {"accountValue": str(max(float(withdrawable), 100000.0))}
    if positions is None:
        positions = old.get("positions_by_coin", {}) if isinstance(old, dict) else {}
    if not isinstance(positions, dict):
        raise ValueError("positions must be a dict")
    raw["assetPositions"] = [
        {"position": {"coin": str(coin), "szi": str(
            item.get("signed_size", 0.0) if isinstance(item, dict) else item)}}
        for coin, item in positions.items()
    ]
    core.atomic_write_json(core.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {
        "created_at_ms": core.utc_now_ms(),
        "raw": raw,
        "positions_by_coin": positions,
    })


class SleeveLedgerStub:
    """Minimal owned-sleeve stub for audit parity; no exchange truth fabrication."""

    def __init__(self, sleeves=None, coin_nets=None):
        self.sleeves = {(w.lower(), coin.upper()): float(sz)
                        for (w, coin), sz in (sleeves or {}).items()}
        self.coin_nets = {coin.upper(): float(sz)
                          for coin, sz in (coin_nets or {}).items()}

    def sleeve(self, wallet, coin):
        return {"signed_size": self.sleeves.get((wallet.lower(), coin.upper()), 0.0)}

    def coin_net(self, coin):
        key = coin.upper()
        if key in self.coin_nets:
            return self.coin_nets[key]
        return sum(sz for (wallet, c), sz in self.sleeves.items() if c == key)
