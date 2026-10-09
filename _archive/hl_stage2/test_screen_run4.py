#!/usr/bin/env python3
"""Operator-screen fixes after testnet run 4 (the "Live Copy Command Centre", /live-copy).

S1  Sending ON/OFF comes only from the master switch (live_config auto_send_enabled); one label, "Sending".
S2  Health is one calm line: green Healthy / amber Needs a look / red Stopped: <reason>; codes go to a
    collapsed Technical detail. Red only when the engine really cannot send.
S3  Per-wallet closed / open / fees / Net P&L from the engine's own ledger sleeves (no n/a, no amber
    UNKNOWN/NOT_PROVEN); a prominent Net P&L column.
S4  Leaders sharing a coin is normal netting: a grey "shared" tag, never a red "Shared coin" status.
S5  A coin whose exchange net is the sum of the leaders' sleeves is engine-owned, not an orphan; only an
    unexplained position is listed, as "Not opened by the engine — managed by you" (amber, not red).
S6  "restart required" shows only when a websocket feed's wallet set really changed.
S7  Wallet type is Live / Close-only / Off from the wallet mode (no "TRACKED").
S8  The live page is dark edge to edge (no white body margin, no light border).
S9  Polling is normal: "Polling (normal)" in grey, never a red WS DOWN.
S10 One Last Fill and one Last Reject on the screen.
S11 Every fill in the window is counted (userFillsByTime paged past 2000 rows), funding included, and the
    P&L tally adds up: start value -> closed + funding - fees + open = expected; actual; unexplained.
S12 One status banner at the top (account value, sending, health, net P&L since start, open positions,
    resting orders when the engine reports them).

Run: python test_screen_run4.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
WA = "0x" + "a" * 40
WB = "0x" + "b" * 40
WC = "0x" + "e" * 40
WOFF = "0x" + "f" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


# ---- fake follower /info (no network) -----------------------------------------------------------------
NOW_MS = int(time.time() * 1000)
RUN_START_MS = NOW_MS - 6 * 3600 * 1000
N_FILLS = 5314


def make_fills():
    fills = []
    t = RUN_START_MS + 1000
    for i in range(N_FILLS):
        if i % 3 == 0:  # groups of same-millisecond fills (one order hitting several makers)
            t += 3000
        fills.append({"coin": "BTC", "px": "100", "sz": "0.01", "side": "B" if i % 2 else "A", "time": t,
                      "hash": "0xh%05d" % (i // 3), "tid": i, "oid": i, "closedPnl": "0.05" if i % 2 else "-0.02",
                      "fee": "0.01"})
    return fills


FILLS = make_fills()
FUNDING = [{"time": RUN_START_MS + 3600_000 * (k // 3 + 1), "hash": "0x" + "0" * 64,
            "delta": {"type": "funding", "coin": ["BTC", "ETH", "SOL"][k % 3], "usdc": "-0.25", "szi": "1", "fundingRate": "0.0001"}}
           for k in range(15)]
CALLS = {"userFillsByTime": 0, "userFunding": 0}
EXCHANGE = {"positions": [], "unrealized": 0.0}


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(req, timeout=None):
    payload = json.loads(req.data.decode("utf-8"))
    kind = payload.get("type")
    if kind == "userFillsByTime":
        CALLS[kind] += 1
        st, en = payload["startTime"], payload["endTime"]
        rows = [f for f in FILLS if st <= f["time"] <= en][:2000]  # oldest first, at most 2000, like Hyperliquid
        return FakeResp(json.dumps(rows).encode())
    if kind == "userFunding":
        CALLS[kind] += 1
        st, en = payload["startTime"], payload["endTime"]
        rows = [f for f in FUNDING if st <= f["time"] <= en][:4]  # tiny pages so paging is exercised
        return FakeResp(json.dumps(rows).encode())
    if kind == "clearinghouseState":
        aps = [{"position": {"coin": p["coin"], "szi": str(p["szi"]), "positionValue": str(abs(p["szi"]) * p["mark"]),
                             "entryPx": str(p["entry"]), "unrealizedPnl": str(p["upnl"]), "marginUsed": "1"}}
               for p in EXCHANGE["positions"]]
        return FakeResp(json.dumps({"marginSummary": {"accountValue": "1400", "totalRawUsd": "1400", "totalMarginUsed": "1",
                                                      "totalNtlPos": "1"}, "crossMarginSummary": {}, "withdrawable": "1300",
                                    "assetPositions": aps}).encode())
    if kind == "spotClearinghouseState":
        return FakeResp(json.dumps({"balances": [{"coin": "USDC", "total": "1418.0", "hold": "0"}]}).encode())
    raise OSError("offline test: unexpected info call " + str(kind))


def write_csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({k for r in rows for k in r})
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="screen_run4_"))
    env_file = tmp / "stage2.env"
    env_file.write_text(f"HL_LIVE_HL_ACCOUNT_ADDRESS={FOLLOWER}\n", encoding="utf-8")
    for k in ("HL_LIVE_HL_ACCOUNT_ADDRESS", "HL_USER_WALLET", "HL_FOLLOWER_DEXES", "HL_LIVE_AUTO_SEND_ENABLED"):
        os.environ.pop(k, None)
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(env_file)})
    urllib.request.urlopen = fake_urlopen
    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient
    client = TestClient(ui.app)
    ui.ACCOUNT_VALUE_FETCHER = lambda payload: [["day", {"accountValueHistory": [[0, "1449.0"], [1, "1418.0"]],
                                                         "pnlHistory": [[0, "0"], [1, "0"]]}]]
    page = client.get("/live-copy").text
    panel = ui.render_live_copy_control_panel()

    def fresh_state(**over):
        st = {"created_at_ms": int(time.time() * 1000), "last_state_write_ms": int(time.time() * 1000),
              "networks": {"leader": "mainnet", "follower": "testnet"}, "master_real_orders_enabled": True,
              "effective_real_orders_enabled": True, "entry_sends_blocked_reason": "", "sender_key_invalid": "",
              "copy_account_status": "COPY_ACCOUNT_POLLED", "ws_status": "WS_DISABLED"}
        st.update(over)
        return st

    # ---- S1 sending from the master switch only ----------------------------------------------------------
    cfg = {"auto_send_enabled": False, "wallets": {WA: {"mode": "LIVE", "enabled": True, "copy_mode": "fixed"},
                                                   WB: {"mode": "LIVE", "enabled": True}, WC: {"mode": "CLO"},
                                                   WOFF: {"mode": "OFF"}}}
    ui.atomic_write_json(ui.LIVE_COPY_CONFIG_FILE, cfg)
    ui.atomic_write_json(ui.LIVE_COPY_SERVICE_STATE_FILE, fresh_state())  # a stale engine copy saying ON
    ws_off = {"ws_summary": {"ws_status": "WS_DISABLED"}, "wallets": {WA: {}, WB: {}}}
    ui.atomic_write_json(ui.LIVE_COPY_WS_HEALTH_FILE, ws_off)
    top = ui._build_live_top_status(cfg, ws_off, fresh_state(), {"status": "GREEN", "available": True}, [], [], [])
    check("S1_SENDING_OFF_WHEN_SWITCH_OFF", top["sending"] == "OFF" and top["master_real_orders_enabled"] is False, str(top["sending"]))
    top_on = ui._build_live_top_status({**cfg, "auto_send_enabled": True}, ws_off, fresh_state(master_real_orders_enabled=False),
                                       {"status": "GREEN"}, [], [], [])
    check("S1_SENDING_ON_WHEN_SWITCH_ON", top_on["sending"] == "ON", str(top_on["sending"]))
    check("S1_LIVE_WALLET_COUNT_SEPARATE", top["live_wallets"] == 2, str(top["live_wallets"]))
    check("S1_ONE_LABEL_ON_SCREEN", "REAL ORDERS:" not in panel and "lcAutoSend" not in panel and "Real order sending" not in panel
          and "MASTER REAL ORDERS" not in panel and "const armed=lcAudit.master_real_orders_enabled===true" in panel
          and ">Sending<" in panel and "Live wallets: ${liveCount}" in panel)

    # ---- S2 calm health ---------------------------------------------------------------------------------
    H = ui._build_health_summary
    ok = {"status": "GREEN", "available": True, "reasons": []}
    check("S2_GREEN_HEALTHY", H(fresh_state(), ok)["level"] == "green" and H(fresh_state(), ok)["text"] == "Healthy")
    amb = H(fresh_state(), {"status": "RED", "available": True, "reasons": ["hard_copy_invariant_red", "exchange_manual_mismatch"]})
    check("S2_INTEGRITY_CODES_ARE_AMBER_NOT_RED", amb["level"] == "amber" and amb["text"].startswith("Needs a look")
          and any("hard_copy_invariant_red" in t for t in amb["technical"]) and "hard_copy" not in amb["text"], str(amb))
    blk = H(fresh_state(entry_sends_blocked_reason="COPY_POLL_STALE"), ok)
    check("S2_ENTRY_BLOCK_IS_RED_IN_PLAIN_WORDS", blk["level"] == "red" and blk["text"].startswith("Stopped:")
          and "COPY_POLL_STALE" not in blk["text"], blk["text"])
    check("S2_BAD_KEY_IS_RED", H(fresh_state(sender_key_invalid="User does not exist"), ok)["level"] == "red")
    check("S2_WRONG_NETWORK_IS_RED", H(fresh_state(networks={"follower": "mainnet"}), ok)["level"] == "red")
    old = int(time.time() * 1000) - 3600_000
    check("S2_SILENT_ENGINE_IS_RED", H(fresh_state(last_state_write_ms=old, created_at_ms=old), ok)["level"] == "red")
    check("S2_NO_ENGINE_IS_RED", H({}, ok)["level"] == "red")
    check("S2_SENDING_OFF_IS_NOT_A_FAULT", H(fresh_state(master_real_orders_enabled=False), ok)["level"] == "green")
    check("S2_CODES_COLLAPSED_ON_SCREEN", '<details class="lc-tech"' in panel and "Technical detail" in panel
          and "statusCard('LIVE INTEGRITY'" not in panel)

    # ---- S3 / S4 per-wallet P&L from the ledger; shared coin is grey -------------------------------------
    t0 = RUN_START_MS + 10_000
    live_fills = [
        # wallet A: buy 1 BTC @100, sell 0.5 @110 (closed +5), fee 0.1 each
        {"created_at_ms": t0, "created_at": "a1", "copy_fill_id": "f1", "leader_wallet": WA, "coin": "BTC", "side": "BUY",
         "fill_price": 100, "fill_size": 1, "fee": 0.1, "wallet_position_before": 0, "wallet_position_after": 1},
        {"created_at_ms": t0 + 1, "created_at": "a2", "copy_fill_id": "f2", "leader_wallet": WA, "coin": "BTC", "side": "SELL",
         "fill_price": 110, "fill_size": 0.5, "fee": 0.1, "wallet_position_before": 1, "wallet_position_after": 0.5},
        # wallet B: short 0.2 BTC @105 (shares BTC with A), long 2 ETH @10 then sell 2 @9 (closed -2)
        {"created_at_ms": t0 + 2, "created_at": "b1", "copy_fill_id": "f3", "leader_wallet": WB, "coin": "BTC", "side": "SELL",
         "fill_price": 105, "fill_size": 0.2, "fee": 0.05, "wallet_position_before": 0, "wallet_position_after": -0.2},
        {"created_at_ms": t0 + 3, "created_at": "b2", "copy_fill_id": "f4", "leader_wallet": WB, "coin": "ETH", "side": "BUY",
         "fill_price": 10, "fill_size": 2, "fee": 0.02, "wallet_position_before": 0, "wallet_position_after": 2},
        {"created_at_ms": t0 + 4, "created_at": "b3", "copy_fill_id": "f5", "leader_wallet": WB, "coin": "ETH", "side": "SELL",
         "fill_price": 9, "fill_size": 2, "fee": 0.02, "wallet_position_before": 2, "wallet_position_after": 0},
    ]
    write_csv(ui.LIVE_FILLS_CSV, live_fills)
    manual = {"schema": "manual_live_positions.v1.wallet_sleeves", "by_wallet": {
        WA: {"BTC": {"signed_size": 0.5, "avg_entry_px": 100.0, "leader_wallet": WA, "coin": "BTC"}},
        WB: {"BTC": {"signed_size": -0.2, "avg_entry_px": 105.0, "leader_wallet": WB, "coin": "BTC"},
             "ETH": {"signed_size": 0.0, "avg_entry_px": 0.0}}}}
    snap = {"available": True, "updated_at": "now", "positions_by_coin": {
        "BTC": {"coin": "BTC", "signed_size": 0.3, "mark_px": 120.0, "entry_px": 98.0, "unrealized_pnl": 6.6, "position_value": 36.0},
        "SOL": {"coin": "SOL", "signed_size": 3.0, "mark_px": 20.0, "entry_px": 21.0, "unrealized_pnl": -3.0, "position_value": 60.0}}}
    sends = [{"leader_wallet": WA, "status": "ORDER_FILLED", "created_at": "x"}, {"leader_wallet": WB, "status": "ORDER_FILLED", "created_at": "y"}]
    perf = ui._build_live_leader_performance(sends, manual, snap, cfg, [])
    pa, pb = perf[WA.lower()], perf[WB.lower()]
    # A: closed (110-100)*0.5 = 5; open 0.5*(120-100) = 10; fees 0.2 -> net 14.8
    # B: closed (9-10)*2 = -2; open -0.2*(120-105) = -3; fees 0.09 -> net -5.09
    check("S3_WALLET_A_CLOSED_OPEN_NET", abs(pa["live_realized_pnl"] - 5) < 1e-9 and abs(pa["live_unrealized_pnl"] - 10) < 1e-9
          and abs(pa["fees"] - 0.2) < 1e-9 and abs(pa["live_net_pnl"] - 14.8) < 1e-9, str({k: pa[k] for k in ("live_realized_pnl", "live_unrealized_pnl", "fees", "live_net_pnl")}))
    check("S3_WALLET_B_CLOSED_OPEN_NET", abs(pb["live_realized_pnl"] + 2) < 1e-9 and abs(pb["live_unrealized_pnl"] + 3) < 1e-9
          and abs(pb["live_net_pnl"] + 5.09) < 1e-9, str({k: pb[k] for k in ("live_realized_pnl", "live_unrealized_pnl", "fees", "live_net_pnl")}))
    check("S3_DRAWDOWN_KNOWN_FROM_SERIES", pa["drawdown"] is not None and pa["max_drawdown"] is not None, str(pa["drawdown"]))
    rows = ui._build_live_wallet_rows(cfg, [], sends, manual, {}, ws_off, perf, live_fills=live_fills)
    by = {r["wallet"].lower(): r for r in rows}
    check("S3_ROWS_CARRY_NET", abs(by[WA.lower()]["net_pnl"] - 14.8) < 1e-9 and abs(by[WB.lower()]["net_pnl"] + 5.09) < 1e-9)
    nowallet = by[WC.lower()]
    check("S3_UNKNOWN_IS_A_DASH_WITH_REASON", nowallet["net_pnl"] is None and "no trades" in str(nowallet["net_pnl_reason"]), str(nowallet["net_pnl_reason"]))
    check("S3_NET_COLUMN_ON_SCREEN", "<th>Net P&amp;L</th>" in panel and "lc-net" in panel and "UNKNOWN/NOT_PROVEN" not in panel
          and "provenMoneyOrUnknown" not in panel)
    netted = {"schema": "manual_live_positions.v1.wallet_sleeves", "by_wallet": {
        WA: {"BTC": {"signed_size": 0.2, "avg_entry_px": 100.0}}, WB: {"BTC": {"signed_size": -0.2, "avg_entry_px": 105.0}}}}
    flat_snap = {"available": True, "positions_by_coin": {}}  # BTC netted flat on the exchange: no live price
    pflat = ui._build_live_leader_performance(sends, netted, flat_snap, cfg, [])[WA.lower()]
    check("S3_NO_PRICE_MEANS_DASH_NOT_FAKE", pflat["live_net_pnl"] is None and "no live price" in pflat["net_pnl_reason"], pflat["net_pnl_reason"])
    check("S4_SHARED_COIN_IS_A_TAG", pa["shared_coins"] == ["BTC"] and pa["pnl_status"] != "AMBIGUOUS_COIN_SHARED"
          and "'AMBIGUOUS_COIN_SHARED':'lc-red'" not in panel and "shared ${h(c)}" in panel)

    # ---- S5 netted coins are engine-owned, not orphans ----------------------------------------------------
    real = ui._build_real_copy_positions(manual, snap)
    orphans = [r for r in real if r.get("row_type") == "ACCOUNT_LEVEL_ONLY"]
    check("S5_NETTED_COIN_NOT_ORPHAN", [r["coin"] for r in orphans] == ["SOL"], str([(r["coin"], r.get("ledger_vs_exchange")) for r in orphans]))
    reg = ui._build_account_orphan_registry(orphans, tmp / "orphans.json")
    check("S5_REGISTRY_ONLY_UNEXPLAINED", sorted(p["coin"] for p in reg["positions"].values() if p["status"] == "ACTIVE") == ["SOL"])
    snap_res = {"available": True, "positions_by_coin": {"BTC": {"coin": "BTC", "signed_size": 0.4, "mark_px": 120.0, "entry_px": 98.0}}}
    res = [r for r in ui._build_real_copy_positions(manual, snap_res) if r.get("row_type") == "ACCOUNT_LEVEL_ONLY"]
    check("S5_ONLY_THE_UNEXPLAINED_PART_LISTED", len(res) == 1 and abs(res[0]["exchange_signed_size"] - 0.1) < 1e-9, str(res))
    check("S5_PLAIN_AMBER_LABEL", "Not opened by the engine — managed by you" in panel and "engine_can_close=false" not in panel
          and "NOT ENGINE OWNED" not in panel)

    # ---- S6 restart note ---------------------------------------------------------------------------------
    ws_on_same = {"ws_summary": {"ws_status": "WS_OK", "socket_open": True, "thread_alive": True}, "wallets": {WA: {}, WB: {}, WC: {}}}
    ws_on_diff = {"ws_summary": {"ws_status": "WS_OK", "socket_open": True, "thread_alive": True}, "wallets": {WA: {}}}
    st_args = (fresh_state(), {"status": "GREEN"}, [], [], [])
    check("S6_NO_RESTART_NOTE_WHEN_POLLING", ui._build_live_top_status(cfg, ws_off, *st_args)["ws_restart_needed"] is False)
    check("S6_NO_RESTART_NOTE_WHEN_UNCHANGED", ui._build_live_top_status(cfg, ws_on_same, *st_args)["ws_restart_needed"] is False)
    check("S6_RESTART_NOTE_WHEN_CHANGED", ui._build_live_top_status(cfg, ws_on_diff, *st_args)["ws_restart_needed"] is True)
    check("S6_NOTE_HIDDEN_BY_DEFAULT", 'id="lcRestartNote" hidden' in panel and "restart required for WS subscription changes" not in panel)

    # ---- S7 wallet type from mode --------------------------------------------------------------------------
    check("S7_MODE_LABELS", (by[WA.lower()]["mode_label"], by[WC.lower()]["mode_label"], by[WOFF.lower()]["mode_label"]) == ("Live", "Close-only", "Off"))
    check("S7_NO_TRACKED_LABEL", "pill('TRACKED'" not in panel and "LIVE COPY" not in panel)

    # ---- S8 dark edge to edge ------------------------------------------------------------------------------
    check("S8_BODY_HAS_NO_WHITE_MARGIN", re.search(r"html,body\{\{?margin:0;padding:0;background:#070c11", page) is not None, page[:400])
    css = re.search(r"\.live-copy-centre\{[^}]*\}", panel).group(0)
    check("S8_NO_LIGHT_BORDER", "border-top" not in css and "#30363d" not in css and "background:var(--lc-bg)" in css, css)

    # ---- S9 polling is normal ------------------------------------------------------------------------------
    tp = ui._build_live_top_status(cfg, ws_off, *st_args)
    check("S9_POLL_MODE_REPORTED", tp["ws_status"] == "POLLING" and tp["ws_enabled"] is False, str(tp["ws_status"]))
    check("S9_WALLET_FEED_POLLING", by[WA.lower()]["conn_status"] == "POLLING", by[WA.lower()]["conn_status"])
    pill_src = re.search(r"function pill\(text,kind\)\{.*?\n", panel).group(0)
    off_in_red = re.search(r"\[[^\]]*'OFF'[^\]]*\]\.includes\(token\)\?'lc-red'", pill_src)
    check("S9_GREY_POLLING_AND_OFF", "Polling (normal)" in panel and not off_in_red and "'lc-red'" not in pill_src
          and "COPY DISABLED</span>" not in panel)
    reds = [ln for ln in panel.splitlines() if "lc-red" in ln and "--lc-red" not in ln]
    check("S9_RED_ONLY_FOR_STOP_LEVEL", len(reds) == 2 and all(("ENGINE ALERT" in ln or "levelCls" in ln) for ln in reds),
          "\n".join(x[:120] for x in reds))

    # ---- S10 one last fill / last reject -------------------------------------------------------------------
    check("S10_ONE_LAST_FILL_AND_REJECT", panel.count("statusCard('Last fill'") == 1 and panel.count("statusCard('Last reject'") == 1
          and "['Last Fill'" not in panel and "['Last Reject'" not in panel)

    # ---- S11 every fill counted, funding included, tally adds up -------------------------------------------
    CALLS.update({"userFillsByTime": 0, "userFunding": 0})
    got = ui._fetch_user_fills_paged(FOLLOWER, RUN_START_MS, NOW_MS + 1000)
    check("S11_PAGES_PAST_2000", got["ok"] and len(got["rows"]) == N_FILLS and got["complete"] and CALLS["userFillsByTime"] >= 3,
          f"{len(got['rows'])} rows, {CALLS['userFillsByTime']} calls")
    check("S11_NO_FILL_LOST_AT_PAGE_EDGE", len({(r["hash"], r["tid"]) for r in got["rows"]}) == N_FILLS)
    check("S11_SINGLE_CALL_HELPER_ALSO_PAGED", len(ui._fetch_user_fills_by_time(FOLLOWER, RUN_START_MS, NOW_MS + 1000) or []) == N_FILLS)
    fund = ui._fetch_user_funding_paged(FOLLOWER, RUN_START_MS, NOW_MS + 1000)
    check("S11_FUNDING_PAGED_AND_SUMMED", fund["ok"] and len(fund["rows"]) == 15 and abs(fund["funding_sum"] + 3.75) < 1e-9,
          f"{len(fund['rows'])} {fund.get('funding_sum')}")
    # end to end: history at run start 1449, first live fill at run start, account 1418 now
    write_csv(ui.SEND_ATTEMPTS_CSV, [{"status": "ORDER_FILLED", "leader_wallet": WA, "coin": "BTC",
                                      "created_at": ui.datetime.fromtimestamp(RUN_START_MS / 1000, tz=ui.timezone.utc).isoformat()}])
    ui.atomic_write_json(ui.EXCHANGE_ACCOUNT_HISTORY_FILE, [
        {"timestamp": ui.datetime.fromtimestamp((RUN_START_MS - 7200_000) / 1000, tz=ui.timezone.utc).isoformat(), "account_value": 1300, "unified_portfolio_value": 1440.0, "open_position_count": 0},
        {"timestamp": ui.datetime.fromtimestamp((RUN_START_MS - 60_000) / 1000, tz=ui.timezone.utc).isoformat(), "account_value": 1310, "unified_portfolio_value": 1449.0, "open_position_count": 0},
        {"timestamp": ui.datetime.fromtimestamp((RUN_START_MS + 60_000) / 1000, tz=ui.timezone.utc).isoformat(), "account_value": 1320, "unified_portfolio_value": 1447.0, "open_position_count": 1},
    ])
    EXCHANGE["positions"] = [{"coin": "BTC", "szi": 0.3, "mark": 120.0, "entry": 98.0, "upnl": 6.6}]
    ui._ACCOUNT_VALUE_CACHE.clear()
    ui.atomic_write_json(ui.LIVE_COPY_CONFIG_FILE, {**cfg, "auto_send_enabled": True})
    ui.atomic_write_json(ui.LIVE_COPY_SERVICE_STATE_FILE, fresh_state(resting_entry_limits=2))
    ui._AUDIT_SUMMARY_CACHE.clear()
    summary = client.get("/api/live-audit-summary").json()
    tally = summary.get("pnl_tally") or {}
    closed = round(sum(float(f["closedPnl"]) for f in FILLS), 2)
    fees = round(sum(float(f["fee"]) for f in FILLS), 2)
    check("S11_TALLY_STARTS_AT_RUN_START", tally.get("start_value") == 1449.0 and tally.get("start_how") == "at run start"
          and tally.get("now_value") == 1418.0, str({k: tally.get(k) for k in ("start_value", "start_how", "now_value", "value_basis", "reason")}))
    check("S11_TALLY_COUNTS_EVERY_FILL", tally.get("fill_count") == N_FILLS and tally.get("fills_complete") is True, str(tally.get("fill_count")))
    check("S11_TALLY_FUNDING_FEES_CLOSED", abs(tally.get("closed_pnl", 0) - closed) < 0.01 and abs(tally.get("fees", 0) - fees) < 0.01
          and abs(tally.get("funding", 0) + 3.75) < 1e-9, str({k: tally.get(k) for k in ("closed_pnl", "fees", "funding")}))
    exp = round(closed - 3.75 - fees + (6.6 - 0.0), 2)
    check("S11_TALLY_ARITHMETIC", abs(tally.get("expected_change", 0) - exp) < 0.011 and abs(tally.get("actual_change", 0) - (1418.0 - 1449.0)) < 1e-9
          and abs(tally.get("unexplained", 0) - round(tally["actual_change"] - tally["expected_change"], 2)) < 1e-9,
          str({k: tally.get(k) for k in ("expected_change", "actual_change", "unexplained")}) + f" exp={exp}")
    check("S11_TALLY_ON_SCREEN", 'id="lcTally"' in panel and "Unexplained difference" in panel and "Expected change" in panel
          and "Counted ${h(t.fill_count)} exchange fills" in panel)
    pts = (summary.get("live_graph") or {}).get("realized_pnl_points") or []
    check("S11_GRAPH_USES_EVERY_FILL", len(pts) == N_FILLS, str(len(pts)))
    hist = ui.load_json(ui.EXCHANGE_ACCOUNT_HISTORY_FILE, [])
    check("S11_HISTORY_RECORDS_OPEN_PNL_AND_PORTFOLIO", hist and hist[-1].get("portfolio_value") == 1418.0
          and abs((hist[-1].get("unrealized_pnl") or 0) - 6.6) < 1e-9, str(hist[-1:]))

    # ---- S12 status banner ---------------------------------------------------------------------------------
    b = summary.get("status_banner") or {}
    check("S12_BANNER_FACTS", b.get("account_value") == 1418.0 and b.get("sending") == "ON" and b.get("follower_network") == "testnet"
          and (b.get("health") or {}).get("level") == "green" and b.get("net_pnl_since_start") == -31.0
          and b.get("open_positions") == 1 and b.get("resting_orders") == 2, str(b))
    check("S12_BANNER_ON_SCREEN", all(f'id="{i}"' in panel for i in ("lcBanner", "lcBannerAcct", "lcBannerSending", "lcBannerHealth",
                                                                  "lcBannerPnl", "lcBannerOpen", "lcBannerResting")))
    ui.atomic_write_json(ui.LIVE_COPY_SERVICE_STATE_FILE, {k: v for k, v in fresh_state().items()})
    ui._AUDIT_SUMMARY_CACHE.clear()
    b2 = client.get("/api/live-audit-summary").json().get("status_banner") or {}
    check("S12_RESTING_OMITTED_WHEN_NOT_REPORTED", b2.get("resting_orders") is None, str(b2.get("resting_orders")))

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
