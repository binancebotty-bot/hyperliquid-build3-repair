"""Shared offline-only send arming for standalone legacy Core test scripts.

Tests supply their own fake exchange and block network I/O. This helper does NOT
stub the physical order gate or bypass the OFF/CLO switch. Never use in runtime.
"""
from __future__ import annotations


def arm_offline_send(core, wallets, *, global_controls=None, copy_mode="fixed",
                     fixed_notional=1000.0, gateway=None, ledger=None):
    """Write an explicitly armed ON config and return a FRESH ConfigManager.

    A config created while OFF never arms merely because its on-disk file later
    changes: ConfigManager.send_mode_now() intentionally fails closed. Rebind
    gateway.cfg when passing an existing gateway.
    """
    names = tuple(core.normalise_wallet(w) for w in wallets)
    if not names or any(not core.is_valid_wallet(w) for w in names):
        raise ValueError("offline fixture needs valid, enabled leader wallets")
    gc = dict(global_controls or {})
    gc["send_mode"] = "ON"
    core.atomic_write_json(core.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": gc,
        "wallets": {w: {"enabled": True, "mode": "ON", "copy_mode": copy_mode,
                        "fixed_notional": fixed_notional} for w in names},
    })
    cfg = core.ConfigManager()
    assert cfg.send_mode_now() == "ON", "offline fixture is not armed"
    assert all(cfg.wallet_enabled(w) and cfg.wallet_mode(w) == "ON" for w in names)
    if gateway is not None:
        gateway.cfg = cfg
        if ledger is not None:
            gateway.ledger = ledger
    return cfg


class SleeveLedgerStub:
    """Minimal copy-owned sleeve for tests that do not exercise ledger accounting.

    Keyed by (leader wallet, coin). No pretend account/exchange proof is created.
    """

    def __init__(self, sleeve_sizes=None, coin_nets=None):
        self.sleeve_sizes = {
            (str(w).lower(), str(c).upper()): float(size)
            for (w, c), size in (sleeve_sizes or {}).items()
        }
        self.coin_nets = {str(c).upper(): float(net)
                          for c, net in (coin_nets or {}).items()}

    def sleeve(self, wallet, coin):
        return {"signed_size": self.sleeve_sizes.get(
            (str(wallet).lower(), str(coin).upper()), 0.0)}

    def coin_net(self, coin):
        key = str(coin).upper()
        if key in self.coin_nets:
            return self.coin_nets[key]
        return sum(v for (w, c), v in self.sleeve_sizes.items() if c == key)
