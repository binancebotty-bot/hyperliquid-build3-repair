#!/usr/bin/env python3
"""Testnet run 5 fixes (2026-10-10): no leader exit is lost, dust can be closed, busy leaders cost fewer orders.

C  convergence: while armed, an engine sleeve whose leader is now flat or on the other side (leader network, read
   twice over the confirm window) is closed through the normal leader-close path; never while sending is off, never
   on an unreadable leader, never twice inside the retry window (run 5: 2,523 exits dropped while sending was off;
   20 sleeves on leaders that had left).
D  dust: a reduce-only close of an owned sleeve below the $10 minimum reaches the exchange (it can never add
   exposure); entries below the minimum stay blocked; HL_LIVE_DUST_CLOSE_ATTEMPT=0 restores the old block.
P  queue: leader exits and convergence closes go before waiting entries; a convergence close still waiting is
   never queued again (run 5: closes waited ~7.7 min behind entries and were re-queued every few minutes).
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
    # C10: a queued close that no longer closes its sleeve (the leader closed and reopened the other way first) is
    # dropped, never sent as an ADD; C11: it does not stamp the leader's side with the local clock
    core.sender.send_if_allowed = lambda intent, block="": sent.append(intent) or (False, "TEST_NO_SEND")
    stale = c.LeaderFill("converge:x", A, "ETH", "SELL", 100.0, 1.0, c.utc_now_ms(), "CONVERGE", 0,
                         {"dir": "Close Long", "position_id": "old-position", "sleeve_size": 1.0})
    core.ledger.sleeve(A, "ETH")["signed_size"] = -1.0   # now a short sleeve: a SELL would ADD to it
    core.ledger.sleeve(A, "ETH")["position_id"] = "new-short"
    core.ledger._recompute_net(core.ledger.data)
    n2 = len(sent)
    ok, status, _i = core._process_leader_fill(stale, None, "")
    check("C10_STALE_CONVERGE_CLOSE_NEVER_ADDS", not ok and status == "CONVERGE_CLOSE_DROPPED_SLEEVE_CHANGED"
          and len(sent) == n2, status)
    check("C11_CONVERGE_CLOSE_DOES_NOT_STAMP_THE_LEADER_SIDE",
          not any(k[0] == c.normalise_wallet(A) for k in core.sender._leader_side_seen_ms),
          str(core.sender._leader_side_seen_ms))
    tries_key = next(iter(core._converge_tries), None)
    check("C12_REPEATED_FAILED_CLOSES_COUNTED", tries_key is not None and core._converge_tries[tries_key] >= 1)
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
    c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": 0.05}}})
    ok_exit, blk_exit = g._validate_final_wire_order(intent("EXIT", True), resolved, "BTC", 0.05, 100.0, {})
    c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": 0.5}}})
    ok_sliver, _ = g._validate_final_wire_order(intent("EXIT", True), resolved, "BTC", 0.05, 100.0, {})
    check("D4_SLIVER_OF_A_LARGER_ACCOUNT_POSITION_STAYS_BLOCKED", not ok_sliver)
    c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": 0.05}}})
    ok_entry, blk_entry = g._validate_final_wire_order(intent("ENTRY", False), resolved, "BTC", 0.05, 100.0, {})
    check("D1_WHOLE_POSITION_DUST_CLOSE_REACHES_THE_EXCHANGE", ok_exit, str(blk_exit))
    check("D1_DUST_ENTRY_STILL_BLOCKED", not ok_entry and blk_entry.get("terminal_state") == "DUST_BELOW_MIN_NOTIONAL")
    os.environ["HL_LIVE_DUST_CLOSE_ATTEMPT"] = "0"
    ok_off, _ = g._validate_final_wire_order(intent("EXIT", True), resolved, "BTC", 0.05, 100.0, {})
    os.environ.pop("HL_LIVE_DUST_CLOSE_ATTEMPT", None)
    check("D2_SWITCH_RESTORES_THE_OLD_BLOCK", not ok_off)
    # D3: a close the netting rule would send WITHOUT reduce-only is not exempt from the minimum
    g._reduce_only_on_wire = lambda intent, size: False
    ok_net, _ = g._validate_final_wire_order(intent("EXIT", True), resolved, "BTC", 0.05, 100.0, {})
    check("D3_NON_REDUCE_ONLY_CLOSE_KEEPS_THE_MINIMUM", not ok_net)

    # P: closes jump the entry queue (run 5: convergence closes waited ~7.7 min behind entries and were re-queued)
    import queue as _queue
    import threading as _t
    import time as _time
    config(send=True)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    core._hot_stop_event.clear()
    core.async_dispatch = True
    core.cfg.master_switch_now = lambda: True
    core.ledger.sleeve(B, "DOGE")["signed_size"] = 2.0
    core.ledger.sleeve(B, "DOGE")["position_id"] = "pd"
    core.ledger._recompute_net(core.ledger.data)
    leader_pos[B]["DOGE"] = 0.0
    leader_pos[A] = {}
    got = []
    first_entry_started = _t.Event()
    release = _t.Event()

    def slow_process(f, s=None, b=""):
        got.append((f.source, f.coin))
        if f.source == "TEST":
            first_entry_started.set()
            release.wait(2)
        return False, "T", None
    core._process_leader_fill = slow_process
    t0 = c.utc_now_ms()
    shard = core._shard(c.LeaderFill("x", B, "DOGE", "SELL", 1, 1, t0, "TEST", 0, {}))
    entries = [c.LeaderFill(f"e{i}", B if i % 2 else A, "DOGE", "BUY", 100.0, 0.1, t0 + i, "TEST", 0,
                            {"oid": str(100 + i), "dir": "Open Long"}) for i in range(6)]
    for e in entries:
        core._hot_queues[shard].put(e)
    th = _t.Thread(target=core._hot_send_loop, args=(shard,), daemon=True)
    th.start()
    first_entry_started.wait(2)
    os.environ["HL_LIVE_CONVERGE_CONFIRM_SEC"] = "0"
    os.environ["HL_LIVE_CONVERGE_RETRY_SEC"] = "0"
    r1 = core.converge_once()   # queued while the worker is busy with the entry batch
    r2 = core.converge_once()   # still waiting: never queued twice
    check("P2_A_WAITING_CONVERGE_CLOSE_IS_NEVER_QUEUED_TWICE",
          r1.get("queued") == 1 and r2.get("queued") == 0 and r2.get("still_queued") == 1, f"{r1} {r2}")
    release.set()
    deadline = _time.time() + 5
    while len(got) < 3 and _time.time() < deadline:
        _time.sleep(0.02)
    core._hot_stop_event.set()
    th.join(timeout=2)
    pos = [i for i, g in enumerate(got) if g[0] == "CONVERGE"]
    check("P1_CONVERGE_CLOSE_SENT_BEFORE_THE_REST_OF_THE_ENTRY_BATCH", pos == [1] and len(got) == 3, str(got))  # entries merge per leader: 2 sends
    check("P3_SENT_CLOSE_RELEASES_ITS_SLEEVE", not core._converge_queued, str(core._converge_queued))
    xfill = c.LeaderFill("x2", B, "DOGE", "SELL", 100.0, 1.0, t0 + 50, "WS_CAPTURED", 0, {"oid": "999", "dir": "Close Long"})
    core._dispatch_fill(xfill)
    check("P4_LEADER_EXIT_GOES_TO_THE_PRIORITY_LANE",
          core._prio_queues[shard].qsize() == 1 and core._hot_queues[shard].qsize() == 0)
    os.environ.pop("HL_LIVE_CONVERGE_CONFIRM_SEC", None)
    os.environ.pop("HL_LIVE_CONVERGE_RETRY_SEC", None)
    core.stop()

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
