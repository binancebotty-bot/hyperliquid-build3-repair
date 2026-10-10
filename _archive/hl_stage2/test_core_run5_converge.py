#!/usr/bin/env python3
"""Testnet run 5 fixes (2026-10-10): no leader exit is lost, dust can be closed, busy leaders cost fewer orders.

C  convergence: while armed, an engine sleeve whose leader is now flat or on the other side (leader network, read
   twice over the confirm window) is closed through the normal leader-close path; never while sending is off, never
   on an unreadable leader, never twice inside the retry window (run 5: 2,523 exits dropped while sending was off;
   20 sleeves on leaders that had left).
D  dust: a reduce-only close of an owned sleeve below the $10 minimum reaches the exchange (it can never add
   exposure); entries below the minimum stay blocked; HL_LIVE_DUST_CLOSE_ATTEMPT=0 restores the old block.
F  fixed sizing: a leader's run of fills in one coin is one order carrying the fixed amount per fill.

Run: python test_core_run5_converge.py   # RESULT:: markers, exit 0/1. No network, no orders.
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
A = "0x" + "a" * 40
B = "0x" + "b" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="run5conv_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    for k in ("HL_LIVE_CONVERGE_CONFIRM_SEC", "HL_LIVE_CONVERGE_RETRY_SEC", "HL_LIVE_DUST_CLOSE_ATTEMPT"):
        os.environ.pop(k, None)
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100", "DOGE": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    leader_pos = {A: {"BTC": 0.0, "ETH": 2.0}, B: {"DOGE": -3.0}}
    unreadable = set()

    def leader_fetcher(payload):
        user = payload.get("user")
        if payload.get("type") != "clearinghouseState" or user in unreadable:
            raise RuntimeError("unreadable")
        return {"marginSummary": {"accountValue": "1000"}, "assetPositions": [
            {"position": {"coin": k, "szi": str(v), "positionValue": str(abs(v) * 100)}}
            for k, v in leader_pos.get(user, {}).items() if v]}
    c.LEADER_FETCHER = leader_fetcher

    def config(send=True, **gc):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": send, "global_controls": gc, "wallets": {
            w: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12} for w in (A, B)}})

    config(send=True)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.cfg.master_switch_now = lambda: switch["on"]
    switch = {"on": True}
    for w, coin, size in ((A, "BTC", 1.5), (A, "ETH", 1.0), (B, "DOGE", 2.0)):
        core.ledger.sleeve(w, coin)["signed_size"] = size
        core.ledger.sleeve(w, coin)["position_id"] = f"{w}::{coin}::LONG::t"
    core.ledger._recompute_net(core.ledger.data)
    sent = []
    core.sender.send_if_allowed = lambda intent, block="": sent.append(intent) or (False, "TEST_NO_SEND")

    # C1: sending off -> nothing read, nothing queued
    switch["on"] = False
    r = core.converge_once()
    check("C1_SENDING_OFF_NEVER_CLOSES", r.get("status") == "SENDING_OFF" and not sent and not core._converge_seen, str(r))
    switch["on"] = True

    # C2: first read only records; confirmed after the window
    r = core.converge_once()
    check("C2_FIRST_READ_ONLY_RECORDS", r["candidates"] == 2 and r["queued"] == 0 and not sent, str(r))
    os.environ["HL_LIVE_CONVERGE_CONFIRM_SEC"] = "0"
    r = core.converge_once()
    by = {(i.fill.leader_wallet, i.fill.coin): i for i in sent}
    check("C2_LEADER_FLAT_AND_OPPOSITE_SIDE_SLEEVES_CLOSED", set(by) == {(A, "BTC"), (B, "DOGE")} and r["queued"] == 2,
          f"{set(by)} {r}")
    btc = by.get((A, "BTC"))
    check("C3_CLOSE_IS_A_FULL_REDUCE_ONLY_EXIT",
          btc is not None and btc.copy_side == "SELL" and abs(btc.copy_size - 1.5) < 1e-9 and btc.reduce_only_intended
          and "lifecycle=EXIT" in btc.notes, str(btc and (btc.copy_side, btc.copy_size, btc.notes)))
    check("C4_LEADER_STILL_HOLDING_IS_LEFT_ALONE", (A, "ETH") not in by)
    rows = c.read_csv_rows(c.RECONCILIATION_CSV)
    check("C5_EACH_CLOSE_IS_AUDITED_WITH_ITS_REASON",
          {r.get("status") for r in rows if r.get("event") == "CONVERGE_CLOSE"} == {"CONVERGE_LEADER_FLAT",
                                                                                  "CONVERGE_LEADER_OPPOSITE_SIDE"})
    n = len(sent)
    core.converge_once()
    check("C6_NOT_RESENT_INSIDE_THE_RETRY_WINDOW", len(sent) == n, str(len(sent) - n))
    os.environ["HL_LIVE_CONVERGE_RETRY_SEC"] = "0"
    unreadable.add(A)
    r = core.converge_once()
    check("C7_UNREADABLE_LEADER_IS_NEVER_ACTED_ON",
          r["unreadable"] == 1 and all(i.fill.leader_wallet != A for i in sent[n:]), str(r))
    unreadable.clear()
    leader_pos[B]["DOGE"] = 4.0   # the leader is back on our side: the candidate is dropped
    core.converge_once()
    check("C8_LEADER_BACK_ON_OUR_SIDE_CLEARS_THE_CANDIDATE",
          not any(k[0] == B for k in core._converge_seen), str(core._converge_seen))
    os.environ.pop("HL_LIVE_CONVERGE_CONFIRM_SEC", None)
    os.environ.pop("HL_LIVE_CONVERGE_RETRY_SEC", None)
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8")
    check("C9_THREAD_STARTED_IN_LOOP_MODE", 'core.start_convergence_thread(' in src and "HL_LIVE_CONVERGE_THREAD" in src)
    core.stop()

    # D: dust closes reach the exchange; dust entries do not
    g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), None)
    resolved = {"ok": True, "sdk_coin": "BTC", "raw_coin": "BTC", "sz_decimals": 3, "min_order_value_usd": 10.0}
    fill = c.LeaderFill("d1", A, "BTC", "SELL", 100.0, 0.05, c.utc_now_ms(), "TEST", 0, {})

    def intent(lifecycle, ro):
        return c.Intent("i-" + lifecycle, fill, "SELL", 0.05, 5.0, "ON", "fixed", "EXIT_ALLOWED", "", "s", "p", "LONG",
                        0.05, 0.05, ro, ro, notes=f"lifecycle={lifecycle}")
    ok_exit, blk_exit = g._validate_final_wire_order(intent("EXIT", True), resolved, "BTC", 0.05, 100.0, {})
    ok_entry, blk_entry = g._validate_final_wire_order(intent("ENTRY", False), resolved, "BTC", 0.05, 100.0, {})
    check("D1_DUST_CLOSE_REACHES_THE_EXCHANGE", ok_exit, str(blk_exit))
    check("D1_DUST_ENTRY_STILL_BLOCKED", not ok_entry and blk_entry.get("terminal_state") == "DUST_BELOW_MIN_NOTIONAL")
    os.environ["HL_LIVE_DUST_CLOSE_ATTEMPT"] = "0"
    ok_off, _ = g._validate_final_wire_order(intent("EXIT", True), resolved, "BTC", 0.05, 100.0, {})
    os.environ.pop("HL_LIVE_DUST_CLOSE_ATTEMPT", None)
    check("D2_SWITCH_RESTORES_THE_OLD_BLOCK", not ok_off)

    # F: fixed sizing merges a leader's run into fewer orders carrying the same amount
    config(send=False, max_order_notional_usd=50)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    t0 = c.utc_now_ms() - 100000
    run = [c.LeaderFill(f"r{i}", A, "BTC", "BUY", 100.0, 0.5, t0 + i, "TEST", 0, {"oid": "9", "dir": "Open Long"})
           for i in range(7)]
    plan = core._plan_batch(run)
    amounts = [core.intent_builder._copy_notional(A, p) for p in plan]
    check("F1_FIXED_RUN_SENT_AS_FEWER_ORDERS_SAME_AMOUNT",
          len(plan) == 3 and abs(sum(amounts) - 7 * 12.0) < 1e-9 and max(amounts) <= 50, f"{len(plan)} {amounts}")
    core.stop()

    failed = sum(1 for _n, ok in RESULTS if not ok)
    print(f"TOTAL={len(RESULTS)} FAILED={failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
