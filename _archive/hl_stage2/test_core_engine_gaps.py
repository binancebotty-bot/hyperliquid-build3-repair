#!/usr/bin/env python3
"""Core engine gaps: one order site, daily loss limit, real leader equity, wallet stream limit.

O: every order (IOC or missed-entry limit, IOC retry, missed-entry limit after no match, rate-limit
   recovery, exit recovery) goes through one physical exchange.order() call in SenderGateway._place_order,
   and every cancel through one exchange.cancel() call in SenderGateway._cancel_order.
D: Global Controls max_daily_loss_usd stops entries once the follower account lost that much over
   the exchange's rolling 24 h window; 0 = off; unreadable PnL fails closed; exits keep flowing.
E: proportional copies scale by the leader's REAL account value on the leader network (every perp
   DEX); the old leader_equity_base setting (UI default 10,000) is ignored; no equity = no size.
W: more LIVE/CLO wallets than the leader stream follows is refused at start and blocks entries on
   reload; OFF wallets never take a live wallet's slot.

Run: python test_core_engine_gaps.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
M_INFO = "https://api.hyperliquid.xyz/info"


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def wallets(n_live: int, n_off: int = 0) -> dict:
    out = {"0x%040x" % (0xA000 + i): {"enabled": True, "mode": "OFF"} for i in range(n_off)}
    out.update({"0x%040x" % (0xB000 + i): {"enabled": True, "mode": "LIVE", "copy_mode": "fixed"} for i in range(n_live)})
    return out


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="coregaps_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env")})
    import requests
    import HL_Live_Copy_Service_Core as c
    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient
    ui.LIVE_COPY_CONFIG_FILE = c.LIVE_CONFIG_FILE
    c.USER_WALLET = FOLLOWER

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.MIDS_FETCHER = lambda payload: [] if payload.get("type") == "perpDexs" else {"BTC": "100"}   # follower mids

    def config(gc=None, wallet_cfg=None, all_wallets=None, auto=False):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": auto, "global_controls": gc or {},
                                                 "wallets": all_wallets or {LEADER: wallet_cfg or {
                                                     "enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000}}})

    seq = [0]

    def fill(side="BUY", price=100.0, size=1.0):
        seq[0] += 1
        return c.LeaderFill(f"g{seq[0]}", LEADER, "BTC", side, price, size, c.utc_now_ms(), "TEST")

    # ---- O: one physical order site -------------------------------------------------------
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    calls = re.findall(r"exchange\.order\((?!\))", src)
    body = src.split("def _place_order(", 1)[1].split("\n    def ", 1)[0]
    check("O1_EXACTLY_ONE_EXCHANGE_ORDER_CALL", len(calls) == 1 and "exchange.order(" in body, str(len(calls)))
    # six sites: IOC/GTC, entry IOC retry, missed-entry limit, netting close resend, exit recovery, rate-limit recovery
    check("O1_ALL_SIX_ORDER_SITES_USE_IT", src.count("self._place_order(") == 6, str(src.count("self._place_order(")))
    cancel_body = src.split("def _cancel_order(", 1)[1].split("\n    def ", 1)[0]
    check("O1_EXACTLY_ONE_EXCHANGE_CANCEL_CALL", len(re.findall(r"exchange\.cancel\(", src)) == 1
          and "exchange.cancel(" in cancel_body and "_exchange_order_lock" in cancel_body)

    class FakeExchange:
        def __init__(self):
            self.calls = []

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"size": size, "px": px, "tif": tif["limit"]["tif"], "reduce_only": reduce_only})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 7}}]}}}

    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "rec.json"))
    gw.ledger.sleeve(LEADER, "BTC")["signed_size"] = 2.0
    used = []
    real_place = gw._place_order
    gw._place_order = lambda *a, **k: used.append(a[5]) or real_place(*a, **k)
    config()
    intent = c.IntentBuilder(c.ConfigManager(), gw.ledger).build(fill("SELL"))
    fake = FakeExchange()
    os.environ["HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS"] = "0"
    gw._queue_exit_recovery_if_needed(fake, "BTC", intent, 99.0, 2.0, {}, "could not immediately match")
    check("O2_EXIT_RECOVERY_GOES_THROUGH_THE_ONE_SITE",
          used == ["Gtc"] and fake.calls == [{"size": 2.0, "px": 99.0, "tif": "Gtc", "reduce_only": True}], f"{used} {fake.calls}")

    # ---- D: daily loss limit --------------------------------------------------------------
    pnl = {"rows": None, "reads": 0}

    def fetcher(payload):
        if payload.get("type") == "portfolio":
            pnl["reads"] += 1
            if pnl["rows"] is None:
                raise RuntimeError("portfolio unavailable")
            return [["day", {"accountValueHistory": [], "pnlHistory": pnl["rows"]}], ["week", {"pnlHistory": [[0, "0"], [1, "-999"]]}]]
        return {"assetPositions": []}
    c.EXPOSURE_FETCHER = fetcher

    class Stub:
        pass

    def gate(gc, rows):
        config(gc)
        pnl["rows"] = rows
        st = Stub()
        st.cfg = c.ConfigManager()
        return c.LiveCopyCore._daily_loss_block(st)

    check("D1_ZERO_IS_OFF_AND_READS_NOTHING", gate({}, None) == "" and pnl["reads"] == 0, str(pnl["reads"]))
    check("D2_LOSS_AT_LIMIT_STOPS_ENTRIES",
          gate({"max_daily_loss_usd": 50}, [[0, "10"], [1, "-45"]]) == "DAILY_LOSS_LIMIT_REACHED")
    check("D3_LOSS_UNDER_LIMIT_ALLOWED", gate({"max_daily_loss_usd": 50}, [[0, "0"], [1, "-49"]]) == "")
    check("D3_ONLY_THE_DAY_WINDOW_COUNTS", gate({"max_daily_loss_usd": 500}, [[0, "0"], [1, "20"]]) == "")
    check("D4_UNREADABLE_PNL_FAILS_CLOSED", gate({"max_daily_loss_usd": 50}, None) == "DAILY_LOSS_UNREADABLE")
    config({"max_daily_loss_usd": 50}, auto=True)
    pnl["rows"] = [[0, "0"]]
    sgw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    entry = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "d5.json")).build(fill())
    sent, status = sgw.send_if_allowed(entry, "DAILY_LOSS_LIMIT_REACHED")
    check("D5_ENTRY_REFUSED_WITH_VISIBLE_REASON", not sent and status == "ENTRY_BLOCKED_DAILY_LOSS_LIMIT_REACHED", status)
    client = TestClient(ui.app)
    r = client.post("/api/global-controls", json={"max_daily_loss_usd": 250})
    g = client.get("/api/global-controls").json().get("global_controls", {})
    check("D6_UI_SAVE_REACHES_CORE", r.status_code == 200 and c.ConfigManager().max_daily_loss() == 250.0
          and g.get("max_daily_loss_usd") == 250.0, f"{r.status_code} {g}")
    page = ui.render_live_copy_control_panel()
    check("D6_UI_HAS_DAILY_LOSS_FIELD", 'id="gcMaxDailyLoss"' in page and "max_daily_loss_usd:g('gcMaxDailyLoss')" in page)

    # ---- E: real leader equity ------------------------------------------------------------
    leader_book = {"down": False, "urls": [], "whole": "45000"}

    class Resp:
        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    def leader_post(url, json=None, timeout=None):
        leader_book["urls"].append(url)
        if leader_book["down"]:
            raise RuntimeError("leader read failed")
        if json.get("type") == "perpDexs":
            return Resp([{"name": "xyz"}])
        if json.get("type") == "portfolio":   # whole-account value (unified: spot collateral included)
            return Resp([["day", {"accountValueHistory": [[0, "40000"], [1, leader_book["whole"]]], "pnlHistory": [[0, "0"]]}]])
        acct = {"": "30000", "xyz": "20000"}[json.get("dex", "")]
        return Resp({"assetPositions": [], "marginSummary": {"accountValue": acct}})
    requests.post = leader_post
    prop = {"enabled": True, "mode": "LIVE", "copy_mode": "proportional", "norm_base": 100, "leader_equity_base": 10000}
    config(wallet_cfg=prop)
    b = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "e1.json"))
    i = b.build(fill(price=100.0, size=1000.0))   # leader notional 100,000; equity 50,000 over two DEXes
    check("E1_SIZES_FROM_REAL_LEADER_EQUITY_ALL_DEXES", abs(i.copy_notional - 200.0) < 1e-6 and i.decision == "ENTRY_ALLOWED",
          f"{i.copy_notional} {i.decision} {i.reason}")
    check("E1_EQUITY_READ_FROM_LEADER_NETWORK", leader_book["urls"] and set(leader_book["urls"]) == {M_INFO}, str(leader_book["urls"]))
    leader_book["whole"] = "100000"     # unified account: most collateral in spot -> whole value wins
    i = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "e1u.json")).build(fill(price=100.0, size=1000.0))
    check("E1_UNIFIED_ACCOUNT_SPOT_COLLATERAL_COUNTED", abs(i.copy_notional - 100.0) < 1e-6, str(i.copy_notional))
    leader_book["whole"] = None
    i = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "e1n.json")).build(fill(price=100.0, size=1000.0))
    check("E1_NO_WHOLE_ACCOUNT_VALUE_NO_SIZE", i.copy_notional == 0.0 and "leader equity unavailable" in i.reason, i.reason)
    leader_book["whole"] = "45000"
    n = len(leader_book["urls"])
    b.build(fill(price=100.0, size=1000.0))
    check("E1_EQUITY_CACHED_BETWEEN_FILLS", len(leader_book["urls"]) == n)
    leader_book["down"] = True
    i = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "e2.json")).build(fill(price=100.0, size=1000.0))
    check("E2_NO_EQUITY_NO_SIZE_NO_10000_FALLBACK", i.copy_notional == 0.0 and i.decision == "MANUAL_REVIEW"
          and "leader equity unavailable" in i.reason, f"{i.copy_notional} {i.decision} {i.reason}")
    led = c.ManualLedger(path=tmp / "e3.json")
    led.sleeve(LEADER, "BTC")["signed_size"] = 3.0
    i = c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", price=100.0, size=1000.0))
    check("E3_FULL_CLOSE_STILL_ALLOWED_WITHOUT_EQUITY", i.decision == "EXIT_ALLOWED" and abs(i.copy_size - 3.0) < 1e-9,
          f"{i.decision} {i.copy_size}")
    requests.post = offline

    # ---- W: wallet stream limit -----------------------------------------------------------
    config(all_wallets=wallets(10, n_off=2))
    cm = c.ConfigManager()
    stream = cm.stream_wallets()
    check("W1_OFF_WALLETS_NEVER_TAKE_A_LIVE_SLOT", len(stream) == 10 and set(cm.active_wallets()) <= set(stream), str(len(stream)))
    run_dir = Path(tempfile.mkdtemp(prefix="w2_"))
    c.atomic_write_json(run_dir / "live_config.json", {"auto_send_enabled": False, "wallets": wallets(11)})
    env = {k: v for k, v in os.environ.items() if not k.startswith("HL_")}
    env.update({"HL_LIVE_AUDIT_DIR": str(run_dir), "HL_LIVE_ENV_FILE": str(run_dir / "none.env")})
    r = subprocess.run([sys.executable, "HL_Live_Copy_Service_Core.py", "--once"], cwd=str(HERE), env=env,
                       capture_output=True, text=True, timeout=180)
    check("W2_ELEVEN_ACTIVE_WALLETS_REFUSED_AT_START", r.returncode != 0 and "TOO_MANY_ACTIVE_WALLETS" in r.stderr, r.stderr[-300:])
    config(all_wallets=wallets(11))
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.run_cycle(use_source_csv=False)
    check("W3_RELOAD_OVER_LIMIT_BLOCKS_ENTRIES", core._entry_sends_blocked_reason == "TOO_MANY_ACTIVE_WALLETS",
          core._entry_sends_blocked_reason)
    config(gc={"max_daily_loss_usd": 50}, all_wallets=wallets(1))
    pnl["rows"] = [[0, "0"], [1, "-60"]]
    core._daily_pnl = None
    core.run_cycle(use_source_csv=False)
    check("D7_CYCLE_PUBLISHES_DAILY_LOSS_BLOCK", core._entry_sends_blocked_reason == "DAILY_LOSS_LIMIT_REACHED",
          core._entry_sends_blocked_reason)

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
