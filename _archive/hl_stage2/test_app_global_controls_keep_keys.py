#!/usr/bin/env python3
"""Command Centre: saving Global Controls or a wallet must not drop the keys the form does not own.

Before: _normalise_global_controls kept only the nine form keys, so every UI save (global controls, set-mode,
set-wallet) rewrote live_config.json without send_mode / follower_leverage / liq_parity. Sending then fell back to
the legacy root auto_send_enabled flag (false = OFF) and the leverage reset.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_app_global_controls_keep_keys.py   # RESULT:: markers, exit 0/1.
"""
from __future__ import annotations

import asyncio
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


class FakeReq:
    def __init__(self, body):
        self._b = body

    async def json(self):
        return self._b


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="gckeep_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env")})
    import HL_Copy_App_SSOT as app

    cfg = {"auto_send_enabled": False, "wallets": {},
           "global_controls": {"send_mode": "ON", "follower_leverage": 5, "liq_parity": False, "max_wallet_exposure_usd": 600}}
    app.LIVE_COPY_CONFIG_FILE.write_text(json.dumps(cfg), encoding="utf-8")

    loaded = app._load_live_copy_config()["global_controls"]
    check("LOAD_KEEPS_SEND_MODE", loaded.get("send_mode") == "ON", str(loaded))
    check("LOAD_KEEPS_LEVERAGE_AND_PARITY", loaded.get("follower_leverage") == 5 and loaded.get("liq_parity") is False, str(loaded))

    # a form save that does not mention send_mode keeps it, and updates the keys it does own
    asyncio.run(app.set_global_controls(FakeReq({"max_wallet_exposure_usd": 2000, "max_order_notional_usd": 500})))
    saved = json.loads(app.LIVE_COPY_CONFIG_FILE.read_text(encoding="utf-8"))["global_controls"]
    check("FORM_SAVE_KEEPS_SEND_MODE", saved.get("send_mode") == "ON", str(saved))
    check("FORM_SAVE_KEEPS_LEVERAGE", saved.get("follower_leverage") == 5, str(saved))
    check("FORM_SAVE_UPDATES_ITS_KEYS", saved.get("max_wallet_exposure_usd") == 2000 and saved.get("max_order_notional_usd") == 500, str(saved))

    # a wallet-style rewrite (load, change, save) keeps it too
    c = app._load_live_copy_config()
    app._save_live_copy_config(c)
    again = json.loads(app.LIVE_COPY_CONFIG_FILE.read_text(encoding="utf-8"))["global_controls"]
    check("LOAD_SAVE_ROUND_TRIP_KEEPS_SEND_MODE", again.get("send_mode") == "ON", str(again))

    # an explicit send_mode in the body is read and normalised; a bad value is dropped, not stored
    asyncio.run(app.set_global_controls(FakeReq({"send_mode": "close only"})))
    sm = json.loads(app.LIVE_COPY_CONFIG_FILE.read_text(encoding="utf-8"))["global_controls"].get("send_mode")
    check("BODY_SEND_MODE_NORMALISED", sm == "CLOSE", str(sm))
    asyncio.run(app.set_global_controls(FakeReq({"send_mode": "banana"})))
    gc = json.loads(app.LIVE_COPY_CONFIG_FILE.read_text(encoding="utf-8"))["global_controls"]
    check("BAD_SEND_MODE_NOT_STORED", "send_mode" not in gc or gc.get("send_mode") in {"ON", "OFF", "CLOSE"}, str(gc))

    bad = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
