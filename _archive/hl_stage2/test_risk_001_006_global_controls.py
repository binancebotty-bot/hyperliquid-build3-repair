#!/usr/bin/env python3
"""RISK-001..006: offline tests for the Global Controls, one block per control ID.

Each control is driven through the REAL engine decision seam: a value is written to
live_config.json (the same file the UI saves), then IntentBuilder.build() / SenderGateway._send_real()
reads it at decision time. Per ID there is a positive (control trips -> block) and a non-vacuous
negative (control set so it MUST allow, or mis-set so it MUST block).

Run:  python test_risk_001_006_global_controls.py     # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="risk16_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_FOLLOWER_DEXES": "xyz"})  # HIP-3 DEX in scope
    import HL_Live_Copy_Service_Core as c
    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient
    ui.LIVE_COPY_CONFIG_FILE = c.LIVE_CONFIG_FILE
    client = TestClient(ui.app)
    c.USER_WALLET = FOLLOWER

    # follower exchange truth (per-DEX clearinghouseState) -- the caps read this, not the local ledger
    book = {"positions": []}

    def fetcher(payload):
        if payload.get("type") == "perpDexs":
            return [{"name": "xyz"}]
        return {"assetPositions": [{"position": p} for p in book["positions"] if p.get("dex", "") == payload.get("dex", "")]}
    c.EXPOSURE_FETCHER = fetcher

    mids = {"BTC": 100.0, "ETH": 400.0}

    def mids_fetcher(payload):
        if payload.get("type") == "perpDexs":
            return []
        return {k: str(v) for k, v in mids.items()}
    c.MIDS_FETCHER = mids_fetcher
    c.LEADER_MIDS_FETCHER = lambda payload: [] if payload.get("type") == "perpDexs" else {"BTC": "100"}

    def set_mid(px):
        mids.clear()
        if px:
            mids["BTC"] = px
        c._FOLLOWER_MIDS.update(px={}, ms=0)

    def config(**gc):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": gc, "wallets": {
            LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000}}})

    seq = [0]

    def fill(side="BUY", coin="BTC"):
        seq[0] += 1
        return c.LeaderFill(f"f{seq[0]}", LEADER, coin, side, 100.0, 1.0, c.utc_now_ms(), "TEST")

    def decide(gc, positions=(), side="BUY", coin="BTC", ledger=None):
        config(**gc)
        book["positions"] = list(positions)
        b = c.IntentBuilder(c.ConfigManager(), ledger or c.ManualLedger(path=tmp / f"p{seq[0]}.json"))
        return b.build(fill(side, coin))

    eth = {"coin": "ETH", "szi": "5", "positionValue": "2000"}
    hip3 = {"coin": "xyz:GOLD", "szi": "1", "positionValue": "700", "dex": "xyz"}
    set_mid(100.0)

    # ---- RISK-001  Max total live exposure ($) ------------------------------------------------
    os.environ["HL_LIVE_CAP_SIZE_DOWN"] = "0"   # pin block-whole for this ID
    d = decide({"max_total_live_exposure_usd": 3500}, [eth, hip3])           # 2700 held + ~1000 entry > 3500
    check("RISK-001_BLOCKS_ABOVE_TOTAL_CAP", d.decision == "SEND_BLOCKED_RISK" and "max total exposure" in d.reason, str(d.reason))
    d = decide({"max_total_live_exposure_usd": 5000}, [eth, hip3])           # NEGATIVE: same book, cap raised -> must allow
    check("RISK-001_NEGATIVE_WITHIN_CAP_ALLOWS", d.decision == "ENTRY_ALLOWED", str(d.reason))
    d = decide({"max_total_live_exposure_usd": 0}, [eth, hip3])              # zero = disabled
    check("RISK-001_ZERO_DISABLES", d.decision == "ENTRY_ALLOWED", str(d.reason))
    os.environ["HL_LIVE_CAP_SIZE_DOWN"] = "1"   # size-down on: the last order fills the remaining allowance
    config(max_total_live_exposure_usd=3500)
    book["positions"] = [eth, hip3]
    b = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "r1.json"))
    i = b.build(fill())
    check("RISK-001_SIZES_LAST_ORDER_TO_ALLOWANCE", i.decision == "ENTRY_ALLOWED" and "CAP_SIZED_DOWN" in i.reason and i.copy_notional < 1000.0,
          f"{i.decision} {i.reason} {i.copy_notional}")
    os.environ["HL_LIVE_CAP_SIZE_DOWN"] = "0"

    # ---- RISK-002  Max per-asset directional exposure ($) -------------------------------------
    d = decide({"max_asset_directional_exposure_usd": 1500}, [{"coin": "BTC", "szi": "6", "positionValue": "600"}])  # 600 + 1000 > 1500
    check("RISK-002_BLOCKS_ASSET_OVER_CAP", d.decision == "SEND_BLOCKED_RISK" and "asset directional" in d.reason, str(d.reason))
    d = decide({"max_asset_directional_exposure_usd": 1500}, [{"coin": "BTC", "szi": "-6", "positionValue": "600"}])  # NEGATIVE: short net, BUY reduces -> allow
    check("RISK-002_NEGATIVE_COUNTS_NET_DIRECTION", d.decision == "ENTRY_ALLOWED", str(d.reason))
    d = decide({"max_asset_directional_exposure_usd": 5000}, [{"coin": "BTC", "szi": "6", "positionValue": "600"}])  # cap above usage -> allow
    check("RISK-002_NEGATIVE_WITHIN_CAP_ALLOWS", d.decision == "ENTRY_ALLOWED", str(d.reason))

    # ---- RISK-003  Max per-wallet exposure ($) ------------------------------------------------
    d = decide({"max_wallet_exposure_usd": 500})                             # 1000 entry > 500
    check("RISK-003_BLOCKS_WALLET_OVER_CAP", d.decision == "SEND_BLOCKED_RISK" and "wallet exposure" in d.reason, str(d.reason))
    d = decide({"max_wallet_exposure_usd": 50000})                           # NEGATIVE: cap raised -> allow
    check("RISK-003_NEGATIVE_WITHIN_CAP_ALLOWS", d.decision == "ENTRY_ALLOWED", str(d.reason))

    # ---- RISK-004  Max per-order notional ($) -------------------------------------------------
    d = decide({"max_order_notional_usd": 500})                              # 1000 entry > 500
    check("RISK-004_BLOCKS_ORDER_OVER_CAP", d.decision == "SEND_BLOCKED_RISK" and "max order notional" in d.reason, str(d.reason))
    d = decide({"max_order_notional_usd": 5000})                             # NEGATIVE: cap raised -> allow
    check("RISK-004_NEGATIVE_WITHIN_CAP_ALLOWS", d.decision == "ENTRY_ALLOWED", str(d.reason))
    ledger = c.ManualLedger(path=tmp / "r4close.json")
    ledger.sleeve(LEADER, "BTC")["signed_size"] = 10.0
    d = decide({"max_order_notional_usd": 1, "max_total_live_exposure_usd": 1, "max_wallet_exposure_usd": 1,
                "max_asset_directional_exposure_usd": 1}, side="SELL", ledger=ledger)
    check("RISK-004_NEVER_BLOCKS_CLOSE", d.decision == "EXIT_ALLOWED", str(d.reason))

    # ---- wire-level harness (fake exchange; no network, no real orders) ------------------------
    class FakeExchange:
        def __init__(self):
            self.calls = []

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"coin": coin, "size": size, "px": px, "reduce_only": reduce_only})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}]}}}
    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def send(gc, side="BUY", mid=93.0, sleeve=0.0):
        config(**gc)
        led = c.ManualLedger(path=tmp / f"s{seq[0]}.json")
        if sleeve:
            led.sleeve(LEADER, "BTC")["signed_size"] = sleeve
        intent = c.IntentBuilder(c.ConfigManager(), led).build(fill(side))
        fake = FakeExchange()
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw._resolve_coin = lambda coin: dict(resolved)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        set_mid(mid)
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        try:
            ok, status, res = gw._send_real(intent)
        finally:
            c.HLAccount, c.HLExchange = saved
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        return status, fake.calls, intent

    # ---- RISK-005  Marketable slippage % ------------------------------------------------------
    status, calls, _ = send({"marketable_bps": 10}, mid=93.0)                # BUY 10 bps over mid
    check("RISK-005_PRICED_FROM_SLIPPAGE", len(calls) == 1 and abs(calls[0]["px"] - round(93.0 * 1.001, 2)) < 1e-9,
          f"{status} {calls}")   # limit = mid*(1+bps); rounded to the symbol's price tick (2 dp here)
    status, calls, _ = send({"marketable_bps": 0}, mid=93.0)                 # NEGATIVE: 0 = exactly at mid
    check("RISK-005_NEGATIVE_ZERO_IS_AT_MID", len(calls) == 1 and abs(calls[0]["px"] - 93.0) < 1e-9, f"{status} {calls}")
    config()
    check("RISK-005_UNSET_DEFAULTS_02PCT", c.ConfigManager().marketable_bps() == 20.0, str(c.ConfigManager().marketable_bps()))
    status, calls, _ = send({"max_order_notional_usd": 1000, "marketable_bps": 50}, mid=100.0)   # slippage counts toward the order value
    check("RISK-005_SLIPPAGE_COUNTS_TOWARD_ORDER_CAP", status.startswith("SEND_BLOCKED_RISK") or status == "SEND_NOT_ATTEMPTED_MAX_ORDER_NOTIONAL", f"{status} {calls}")

    # ---- RISK-006  Adverse close diff % -------------------------------------------------------
    status, calls, _ = send({"marketable_bps": 50, "max_close_adverse_diff_pct": 0.2}, side="SELL", mid=100.0, sleeve=10.0)
    check("RISK-006_BLOCKS_CLOSE_TOO_ADVERSE", status == "SEND_NOT_ATTEMPTED_CLOSE_ADVERSE_DIFF" and not calls, f"{status} {calls}")
    status, calls, _ = send({"marketable_bps": 10, "max_close_adverse_diff_pct": 0.2}, side="SELL", mid=100.0, sleeve=10.0)
    check("RISK-006_NEGATIVE_WITHIN_DIFF_ALLOWS_REDUCE_ONLY", len(calls) == 1 and calls[0]["reduce_only"] is True, f"{status} {calls}")
    status, calls, _ = send({"marketable_bps": 50}, side="SELL", mid=100.0, sleeve=10.0)          # 0/missing = OFF
    check("RISK-006_NEGATIVE_ZERO_IS_OFF", len(calls) == 1, f"{status} {calls}")

    # ---- UI/config chain: the UI save must reach the engine's live_config.json -----------------
    config()
    r = client.post("/api/global-controls", json={"max_total_live_exposure_usd": 4200, "max_asset_directional_exposure_usd": 900,
                                                   "marketable_slippage_pct": 0.05, "max_close_adverse_diff_pct": 0.3,
                                                   "max_order_notional_usd": 777, "max_wallet_exposure_usd": 888})
    cm = c.ConfigManager()
    check("RISK_ALL_UI_SAVE_REACHES_ENGINE_CONFIG", r.status_code == 200 and cm.max_total_exposure() == 4200.0
          and cm.max_asset_directional_exposure() == 900.0 and cm.max_order_notional() == 777.0
          and cm.max_wallet_exposure(LEADER) == 888.0 and cm.marketable_bps() == 5.0
          and cm.max_close_adverse_diff_pct() == 0.3,
          f"{r.status_code} {cm.max_total_exposure()} {cm.max_asset_directional_exposure()} {cm.max_order_notional()} "
          f"{cm.max_wallet_exposure(LEADER)} {cm.marketable_bps()} {cm.max_close_adverse_diff_pct()}")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
