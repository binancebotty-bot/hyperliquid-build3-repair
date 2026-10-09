#!/usr/bin/env python3
"""Follower DEX scope (testnet run 1, blocker B1) and truthful front page (findings U1-U5).

S: follower prices, symbol meta and exposure are read only for the follower DEX scope: the default
   DEX, every HIP-3 DEX a leader trades or the follower holds (learned), and HL_FOLLOWER_DEXES; reads
   run concurrently, so a refresh fits the 5 s age budget even with all 10 mainnet DEXes in scope,
   and testnet's hundreds of unused DEXes are never read on the price path. A slow full sweep reads
   every other DEX, adds any the follower holds, and entries wait until a sweep has succeeded.
U: the front page shows the real follower account value (U1), the wallets the engine follows (U2)
   and the engine's sizing (U3); the UI reads the account address from the engine's env file (U4);
   per-wallet settings the engine never reads are not offered or saved (U5).

Run: python test_core_dex_scope_and_ui_truth.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
TESTNET_DEXES = [{"name": f"dex{i:03d}"} for i in range(267)]   # + the default DEX = 268, as on testnet


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="corescope_"))
    env_file = tmp / "stage2.env"
    env_file.write_text(f"HL_LIVE_HL_ACCOUNT_ADDRESS={FOLLOWER}\nHL_FOLLOWER_DEXES=xyz\n", encoding="utf-8")
    os.environ.pop("HL_FOLLOWER_DEXES", None)
    os.environ.pop("HL_LIVE_HL_ACCOUNT_ADDRESS", None)
    os.environ.pop("HL_USER_WALLET", None)
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(env_file), "HL_LIVE_SCOPE_SWEEP_THREAD": "0"})
    import requests
    import exchange_truth as X
    import HL_Live_Copy_Service_Core as c
    import HL_Copy_App_SSOT as ui
    ui.LIVE_COPY_CONFIG_FILE = c.LIVE_CONFIG_FILE
    c.USER_WALLET = FOLLOWER
    os.environ.pop("HL_FOLLOWER_DEXES", None)   # the engine loads its env file; each test sets the scope itself

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline

    # ---- S1: the scope ------------------------------------------------------------------------
    check("S1_DEFAULT_SCOPE_IS_DEFAULT_DEX_ONLY", c.follower_dex_scope() == [""], str(c.follower_dex_scope()))
    os.environ["HL_FOLLOWER_DEXES"] = " XYZ, abc ,,xyz"
    check("S1_NAMED_DEXES_ADDED_ONCE_LOWERCASE", c.follower_dex_scope() == ["", "abc", "xyz"], str(c.follower_dex_scope()))

    # ---- S2: prices read only inside the scope, never by walking every listed DEX ---------------
    seen = []
    lock = threading.Lock()

    def mids(payload):
        with lock:
            seen.append(payload)
        if payload.get("type") == "perpDexs":
            return TESTNET_DEXES
        return {"xyz:GOLD": "2500"} if payload.get("dex") == "xyz" else ({} if payload.get("dex") else {"BTC": "100"})
    c.MIDS_FETCHER = mids
    os.environ["HL_FOLLOWER_DEXES"] = "xyz"
    c._FOLLOWER_MIDS.update(px={}, ms=0)
    ok = c.follower_mid("BTC") == 100.0 and c.follower_mid("xyz:GOLD") == 2500.0
    check("S2_MIDS_READ_ONLY_FOR_SCOPE", ok and sorted(p.get("dex", "") for p in seen) == ["", "xyz"], str(seen))
    check("S2_NO_DEX_ENUMERATION_ON_PRICE_PATH", not any(p.get("type") == "perpDexs" for p in seen))
    check("S2_UNTRADED_DEX_NOT_READ", c.follower_mid("dex200:FOO") == 0.0 and not any(p.get("dex") == "dex200" for p in seen))
    os.environ.pop("HL_FOLLOWER_DEXES")
    c._LEARNED_DEXES.clear()
    c._FOLLOWER_MIDS.update(px={}, ms=0)
    seen.clear()
    check("S2_NOTHING_NAMED_NO_HIP3_READ", c.follower_mid("BTC") == 100.0 and [p.get("dex", "") for p in seen] == [""], str(seen))
    seen.clear()
    c.LeaderFill("lf1", LEADER, "xyz:GOLD", "BUY", 2400.0, 1.0, c.utc_now_ms(), "TEST")
    check("S2_LEADER_TRADE_ADDS_ITS_MARKET", c.follower_dex_scope() == ["", "xyz"], str(c.follower_dex_scope()))
    check("S2_NEW_MARKET_PRICED_AT_ONCE_NOT_AFTER_TTL", c.follower_mid("xyz:GOLD") == 2500.0
          and sorted(p.get("dex", "") for p in seen) == ["", "xyz"], str(seen))
    c._LEARNED_DEXES.clear()

    # ---- S3: 5 s price-age budget, mainnet case (all 10 mainnet DEXes named, 0.5 s per read) ----
    os.environ["HL_FOLLOWER_DEXES"] = ",".join(f"m{i}" for i in range(9))   # default + 9 = all 10 mainnet DEXes

    def slow_mids(payload):
        time.sleep(0.5)
        return {"BTC": "100"} if not payload.get("dex") else {}
    c.MIDS_FETCHER = slow_mids
    c._FOLLOWER_MIDS.update(px={}, ms=0)
    t0 = time.monotonic()
    px = c.follower_mid("BTC")
    took = time.monotonic() - t0
    check("S3_TEN_DEX_REFRESH_INSIDE_TTL", px == 100.0 and took < 2.0, f"px={px} took={took:.2f}s")
    check("S3_REFRESH_TIME_RECORDED", 0 < c._FOLLOWER_MIDS.get("refresh_ms", 0) < 2000, str(c._FOLLOWER_MIDS.get("refresh_ms")))
    os.environ["HL_LIVE_READ_CONCURRENCY"] = "1"
    c._FOLLOWER_MIDS.update(px={}, ms=0)
    t0 = time.monotonic()
    c.follower_mid("BTC")
    check("S3_SEQUENTIAL_READS_WOULD_MISS_BUDGET", time.monotonic() - t0 >= 4.5)   # why concurrency is needed
    os.environ.pop("HL_LIVE_READ_CONCURRENCY")
    t0 = time.monotonic()
    res = X.post_many(lambda p: time.sleep(0.05) or {"i": p["i"]}, [{"i": i} for i in range(40)], timeout=1)
    check("S3_POST_MANY_KEEPS_ORDER_AND_RUNS_CONCURRENTLY",
          [r["data"]["i"] for r in res] == list(range(40)) and time.monotonic() - t0 < 1.0, f"{time.monotonic() - t0:.2f}s")

    # ---- S4: exposure read only inside the scope -------------------------------------------------
    os.environ["HL_FOLLOWER_DEXES"] = "xyz"
    reads = []

    def account(payload):
        with lock:
            reads.append(payload)
        if payload.get("type") == "perpDexs":
            return TESTNET_DEXES
        return {"assetPositions": [], "marginSummary": {"accountValue": "0"}}
    c.EXPOSURE_FETCHER = account
    ib = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "pos.json"))
    exp = ib.follower_exposure()
    check("S4_EXPOSURE_READ_ONLY_FOR_SCOPE",
          exp.get("ok") and sorted(p.get("dex", "") for p in reads) == ["", "xyz"], str(reads)[:300])

    # ---- S5: symbol meta loaded only inside the scope --------------------------------------------
    metas = []

    class Resp:
        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    def fake_post(url, json=None, timeout=None):
        metas.append(json)
        if json.get("type") == "perpDexs":
            return Resp(TESTNET_DEXES)
        return Resp({"universe": [{"name": "BTC" if not json.get("dex") else f"{json['dex']}:GOLD", "szDecimals": 3}]})
    c.requests.post = fake_post
    sender = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "pos2.json"))
    sender.warm_symbol_cache()
    sender._meta_fetched = False
    sender._builder_meta_fetched.pop("*", None)
    sender._fetch_meta()
    check("S5_META_ONLY_FOR_SCOPE", {(m.get("type"), m.get("dex", "")) for m in metas} == {("meta", ""), ("meta", "xyz")}, str(metas)[:300])
    check("S5_SCOPE_COIN_RESOLVES", "XYZ:GOLD" in sender._meta_cache, str(list(sender._meta_cache)[:5]))
    metas.clear()
    c.LeaderFill("lf2", LEADER, "abc:GOLD", "BUY", 10.0, 1.0, c.utc_now_ms(), "TEST")   # leader opens a new market
    r = sender._resolve_coin("abc:GOLD")
    check("S5_NEW_LEADER_MARKET_RESOLVES_ON_FIRST_TRADE", r.get("ok") and metas == [{"type": "meta", "dex": "abc"}], f"{r} {metas}")
    metas.clear()
    r2 = sender._resolve_coin("qqq:GOLD")
    check("S5_UNTRADED_MARKET_NOT_FETCHED_ON_SEND_PATH", not r2.get("ok") and metas == [], f"{r2} {metas}")
    c._LEARNED_DEXES.clear()
    c.requests.post = offline

    # ---- S6: the slow full sweep and its entry gate ----------------------------------------------
    book = {"held": {}, "enum_down": False}
    sweep_reads = []

    def sweep_fetch(payload):
        if payload.get("type") == "perpDexs":
            if book["enum_down"]:
                raise RuntimeError("enumeration down")
            return TESTNET_DEXES + [{"name": "xyz"}]
        with lock:
            sweep_reads.append(payload.get("dex", ""))
        held = book["held"].get(payload.get("dex", ""))
        return {"assetPositions": [{"position": held}] if held else [], "marginSummary": {"accountValue": "0"}}
    c.EXPOSURE_FETCHER = sweep_fetch
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {}, "wallets": {
        LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 12}}})
    os.environ.pop("HL_LIVE_MOCK_SEND", None)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    try:
        core.cfg = c.ConfigManager()
        check("S6_NO_SWEEP_YET_BLOCKS_ENTRIES", core._scope_sweep_block().startswith("SCOPE_SWEEP_PENDING"), core._scope_sweep_block())
        t0 = time.monotonic()
        res = core.run_scope_sweep()
        took = time.monotonic() - t0
        check("S6_SWEEP_READS_EVERY_DEX_OUTSIDE_SCOPE",
              res.get("ok") and sorted(sweep_reads) == sorted(d["name"] for d in TESTNET_DEXES), f"{len(sweep_reads)} reads")
        check("S6_SWEEP_SKIPS_SCOPE_DEXES", "" not in sweep_reads and "xyz" not in sweep_reads)
        check("S6_SWEEP_OF_268_DEXES_IS_FAST_OFFLINE", took < 5.0, f"{took:.2f}s")
        check("S6_CLEAN_SWEEP_ALLOWS_ENTRIES", core._scope_sweep_block() == "", core._scope_sweep_block())
        book["held"] = {"dex200": {"coin": "dex200:FOO", "szi": "3", "positionValue": "30"}}
        core.run_scope_sweep()
        check("S6_HELD_DEX_JOINS_SCOPE", "dex200" in c.follower_dex_scope(), str(c.follower_dex_scope()))
        core.intent_builder._exposure = None
        sweep_reads.clear()
        exp = core.intent_builder.follower_exposure()
        check("S6_HELD_DEX_NOW_IN_EXPOSURE_CAPS", exp.get("ok") and "DEX200:FOO" in exp.get("by_coin", {})
              and "dex200" in sweep_reads, str(exp)[:200])
        sweep_reads.clear()
        core.run_scope_sweep()
        check("S6_NEXT_SWEEP_SKIPS_IT", "dex200" not in sweep_reads and core._scope_sweep_block() == "")
        book["enum_down"] = True
        core._scope_sweep_ok = None
        core.run_scope_sweep()
        check("S6_UNREADABLE_SWEEP_FAILS_CLOSED", core._scope_sweep_block().startswith("SCOPE_SWEEP_PENDING: DEX_ENUM"),
              core._scope_sweep_block())
        book["enum_down"] = False
        core.run_scope_sweep()
        core._scope_sweep_ok["ms"] -= 901_000
        check("S6_STALE_SWEEP_FAILS_CLOSED", core._scope_sweep_block().startswith("SCOPE_SWEEP_PENDING"), core._scope_sweep_block())
        core.run_cycle(use_source_csv=False)
        check("S7_CYCLE_PUBLISHES_SCOPE_BLOCK", core._entry_sends_blocked_reason.startswith("SCOPE_SWEEP_PENDING"),
              core._entry_sends_blocked_reason)
        core.run_scope_sweep()
        core.run_cycle(use_source_csv=False)
        check("S7_CYCLE_CLEARS_AFTER_SWEEP", core._entry_sends_blocked_reason == "", core._entry_sends_blocked_reason)
        os.environ["HL_LIVE_MOCK_SEND"] = "1"
        check("S6_NOT_ARMED_NOT_GATED", core._scope_sweep_block() == "")
        os.environ.pop("HL_LIVE_MOCK_SEND")
    finally:
        core.stop()

    # ---- U: the front page tells the truth ---------------------------------------------------------
    check("U4_ACCOUNT_ADDRESS_READ_FROM_ENGINE_ENV_FILE", ui._public_account_address() == FOLLOWER, ui._public_account_address())
    portfolio = {"down": False}

    def pf(payload):
        if portfolio["down"]:
            raise RuntimeError("portfolio down")
        return [["day", {"accountValueHistory": [[0, "1450.0"], [1, "1450.12"]], "pnlHistory": [[0, "0"], [1, "0"]]}]]
    ui.ACCOUNT_VALUE_FETCHER = pf
    lines = "".join(ui._account_card_lines())
    check("U1_ACCOUNT_CARD_SHOWS_REAL_EXCHANGE_VALUE", "$1,450.12" in lines and "TESTNET" in lines, lines)
    portfolio["down"] = True
    ui._ACCOUNT_VALUE_CACHE.clear()
    lines = "".join(ui._account_card_lines())
    check("U1_UNREADABLE_ACCOUNT_SAYS_UNAVAILABLE", "UNAVAILABLE" in lines and "$" not in lines, lines)
    portfolio["down"] = False
    ui._ACCOUNT_VALUE_CACHE.clear()
    four = {f"0x{i:040x}": {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 12} for i in range(1, 4)}
    four["0x" + "e" * 40] = {"enabled": True, "mode": "LIVE", "fixed_notional": 12}   # no copy_mode: engine default
    four["0x" + "f" * 40] = {"enabled": False, "mode": "OFF"}
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": four})
    check("U2_U3_ENGINE_WALLETS_AND_SIZING", ui._engine_wallet_summary() == (4, 0, "4 FIXED"), str(ui._engine_wallet_summary()))
    ui.get_model_state_cached = lambda max_age_sec=5.0: {}
    page = ui.render_home({})
    check("U1_FRONT_PAGE_HAS_ACCOUNT_CARD", "ACCOUNT (EXCHANGE)" in page and "$1,450.12" in page)
    check("U2_FRONT_PAGE_COUNTS_FOLLOWED_WALLETS", "TRACKED WALLETS (4 followed: 4 LIVE, 0 close-only; 0 with copy history)" in page)
    check("U3_FRONT_PAGE_SHOWS_ENGINE_SIZING", "Engine sizing: 4 FIXED" in page and "Current: PROPORTIONAL" not in page)
    out = ui._normalise_live_wallet_payload({"mode": "LIVE", "leader_equity_base": 5, "max_diff_pct": 1, "daily_loss_limit": 9},
                                            {"mode": "LIVE", "leader_equity_base": 10000, "max_diff_pct": 0.1, "daily_loss_limit": 0,
                                             "max_wallet_exposure_usd": 40})
    check("U5_IGNORED_WALLET_KEYS_NOT_SAVED", not any(k in out for k in ui.ENGINE_IGNORED_WALLET_KEYS)
          and out.get("max_wallet_exposure_usd") == 40, str(out))
    check("U5_UNSET_COPY_MODE_IS_FIXED_LIKE_ENGINE", ui._normalise_live_wallet_payload({"mode": "LIVE"})["copy_mode"] == "fixed"
          and c.ConfigManager().copy_mode("0x" + "e" * 40) == "fixed")
    panel = ui.render_live_copy_control_panel()
    check("U5_PANEL_OFFERS_NO_IGNORED_FIELD", not any(f'name="{k}"' in panel or f"[name={k}]" in panel
                                                     for k in ui.ENGINE_IGNORED_WALLET_KEYS))
    from fastapi.testclient import TestClient
    nets = TestClient(ui.app).get("/api/global-controls").json()["networks"]
    check("S8_UI_SHOWS_MARKETS_TRADED", nets.get("follower_dexes") == ["default", "xyz"], str(nets))

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
