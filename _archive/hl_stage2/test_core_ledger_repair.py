#!/usr/bin/env python3
"""Run 4 ledger catch-up repair (2026-10-09): `--repair-ledger-catch-up`.

After run 4 the ledger showed positions on ~24 coins the exchange had closed: the standing recovery closes'
fills were never owned. The repair adopts follower fills of the engine's OWN orders that the ledger missed, only
where that makes the ledger equal the exchange exactly, through the normal fill path, with audit rows. Ledger and
audit files only: no order is placed or cancelled. Any coin it cannot prove is refused and reported.

E  explained: a recovery close (order id only in reconciliation, as in run 4) and a recorded close whose fills
   were missed are adopted; the ledger then equals the exchange; live_fills + reconciliation rows written.
F  refused: a fill of an order the engine did not place; a replay that does not reach the exchange's net; an
   exchange position the ledger cannot explain; nothing is changed for them.
D  dry run changes nothing; a second run finds nothing left; a second tranche of one exchange transaction
   (same hash, new tid) is a real fill, not a duplicate.
X  exchange positions report: explained by the engine's own order ids or not.
T  run 4's live_fills rows carry a doubled tid (hash:tid:tid): those fills are owned, not replayed again; an
   engine row missing its side is refused before anything is applied; the 10,000-fill history limit refuses.
N  no exchange write anywhere in the repair; apply refuses while the engine holds the state folder.

Run: python test_core_ledger_repair.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import json
import os
import subprocess
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
    tmp = Path(tempfile.mkdtemp(prefix="ledgerrepair_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.ensure_dirs()
    t0 = c.utc_now_ms() - 3_600_000

    # ---- state as run 4 left it ----------------------------------------------------------------------------
    led = c.ManualLedger()
    for w, coin, size in ((A, "BTC", 2.0), (A, "AVAX", -5.0), (B, "ETH", 1.0), (A, "SOL", 1.0), (A, "DOGE", 3.0),
                          (A, "TIA", 3.0), (A, "KAS", 2.0), (A, "HYPE", 0.2), (B, "HYPE", -0.65)):
        s = led.sleeve(w, coin)
        s.update(signed_size=size, direction="LONG" if size > 0 else "SHORT", avg_entry_px=10.0, last_copy_fill_id="x")
    led._recompute_net(led.data)
    led.save()
    audit = c.AuditLogWriter()
    for path, fields in ((c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS), (c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS),
                         (c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS), (c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS)):
        c.ensure_csv_header(path, fields)

    # BTC: the IOC close found no match, a standing recovery close rested (oid 501, only in reconciliation as in
    # run 4) and filled in two tranches of one exchange transaction; the ledger owned neither
    exit_intent = c.Intent(
        intent_id="i-btc-exit", fill=c.LeaderFill("lf1", A, "BTC", "SELL", 10.0, 2.0, t0, "TEST", 0, {}),
        copy_side="SELL", copy_size=2.0, copy_notional=20.0, wallet_mode="ON", copy_mode="fixed",
        decision="EXIT_ALLOWED", reason="EXIT", sleeve_id=c.ManualLedger.sleeve_id(A, "BTC"), position_id="p1",
        position_direction_before="LONG", wallet_position_before=2.0, coin_net_before=2.0,
        reduce_only_intended=True, reduce_only_sent_planned=True, created_at_ms=t0, notes="lifecycle=EXIT")
    audit.append_order_intent(exit_intent)
    audit.append_reconciliation("EXIT_RECOVERY", "EXIT_RECOVERY_QUEUED", leader_wallet=A, intent_id="i-btc-exit",
                                coin="BTC", exchange_order_id="501", action="REDUCE_ONLY_STANDING_LIMIT_CLOSE",
                                terminal_state="EXIT_RECOVERY_ACTIVE", notes="run 4 shape")
    # AVAX: a recorded close (send_attempts, oid 601) whose fill the ledger missed
    audit.append_send_attempt({"created_at_ms": t0, "intent_id": "i-avax-exit", "leader_fill_id": "lf2",
                               "leader_wallet": A, "coin": "AVAX", "side": "BUY", "copy_size": 5.0, "limit_price": 10.0,
                               "status": "ORDER_FILLED", "exchange_order_id": "601", "reduce_only_sent": "True",
                               "wallet_position_before": -5.0, "terminal_state": "FILLED_AWAITING_COPY_POLL",
                               "notes": "lifecycle=EXIT"})
    # SOL: closed on the exchange by an order the engine never placed (oid 999)
    # DOGE: an engine order (oid 701) closed only 2 of the ledger's 3
    audit.append_send_attempt({"created_at_ms": t0, "intent_id": "i-doge-exit", "leader_fill_id": "lf3",
                               "leader_wallet": A, "coin": "DOGE", "side": "SELL", "copy_size": 2.0, "limit_price": 1.0,
                               "status": "ORDER_FILLED", "exchange_order_id": "701", "reduce_only_sent": "True",
                               "wallet_position_before": 3.0, "terminal_state": "FILLED_AWAITING_COPY_POLL",
                               "notes": "lifecycle=EXIT"})
    # ETH: the engine's own order (oid 801) opened it and the ledger owns it
    audit.append_send_attempt({"created_at_ms": t0, "intent_id": "i-eth", "leader_fill_id": "lf4", "leader_wallet": B,
                               "coin": "ETH", "side": "BUY", "copy_size": 1.0, "limit_price": 2000.0, "status": "ORDER_FILLED",
                               "exchange_order_id": "801", "terminal_state": "FILLED_AWAITING_COPY_POLL",
                               "notes": "lifecycle=ENTRY"})
    audit.append_live_fill({"created_at_ms": t0, "copy_fill_id": "0xeth:1", "intent_id": "i-eth", "leader_wallet": B,
                            "coin": "ETH", "side": "BUY", "fill_size": 1.0, "exchange_hash": "0xeth", "exchange_order_id": "801"})

    # TIA: the entry fill (oid 901) was recorded the way run 4 wrote it, hash:tid:tid; its close (oid 902) was missed
    audit.append_send_attempt({"created_at_ms": t0, "intent_id": "i-tia", "leader_fill_id": "lf5", "leader_wallet": A,
                               "coin": "TIA", "side": "BUY", "copy_size": 3.0, "limit_price": 5.0, "status": "ORDER_FILLED",
                               "exchange_order_id": "901", "terminal_state": "FILLED_AWAITING_COPY_POLL",
                               "notes": "lifecycle=ENTRY"})
    audit.append_live_fill({"created_at_ms": t0, "copy_fill_id": "0xtia:61:61", "intent_id": "i-tia", "leader_wallet": A,
                            "coin": "TIA", "side": "BUY", "fill_size": 3.0, "exchange_hash": "0xtia", "exchange_order_id": "901"})
    audit.append_send_attempt({"created_at_ms": t0, "intent_id": "i-tia-exit", "leader_fill_id": "lf6", "leader_wallet": A,
                               "coin": "TIA", "side": "SELL", "copy_size": 3.0, "limit_price": 5.0, "status": "ORDER_FILLED",
                               "exchange_order_id": "902", "reduce_only_sent": "True", "wallet_position_before": 3.0,
                               "terminal_state": "FILLED_AWAITING_COPY_POLL", "notes": "lifecycle=EXIT"})
    # KAS: the engine's close row (oid 911) lacks its side, so its fill cannot be recorded faithfully
    audit.append_send_attempt({"created_at_ms": t0, "intent_id": "i-kas-exit", "leader_fill_id": "lf7", "leader_wallet": A,
                               "coin": "KAS", "side": "", "copy_size": 2.0, "limit_price": 1.0, "status": "ORDER_FILLED",
                               "exchange_order_id": "911", "reduce_only_sent": "True", "wallet_position_before": 2.0,
                               "terminal_state": "FILLED_AWAITING_COPY_POLL", "notes": "lifecycle=EXIT"})

    def f(coin, side, sz, oid, h, tid, dt=0):
        return {"coin": coin, "side": side, "sz": str(sz), "px": "10", "oid": oid, "hash": h, "tid": tid,
                "time": t0 + 1000 + dt, "dir": "Close", "fee": "0.01", "closedPnl": "0"}
    fills = [
        f("ETH", "B", 1.0, 801, "0xeth", 1),
        f("BTC", "A", 1.2, 501, "0xbtc", 11, 10), f("BTC", "A", 0.8, 501, "0xbtc", 12, 10),   # two tranches, one hash
        f("AVAX", "B", 5.0, 601, "0xavax", 21, 20),
        f("SOL", "A", 1.0, 999, "0xsol", 31, 30),
        f("DOGE", "A", 2.0, 701, "0xdoge", 41, 40),
        f("LINK", "B", 5.0, 998, "0xlink", 51, 50),
        f("TIA", "B", 3.0, 901, "0xtia", 61, 60), f("TIA", "A", 3.0, 902, "0xtiax", 62, 61),
        f("KAS", "A", 2.0, 911, "0xkas", 71, 70),
        # run 5: the exchange liquidated the account's HYPE short (no engine order)
        dict(f("HYPE", "B", 0.45, 1001, "0xhype", 81, 80), dir="Liquidated Isolated Short", startPosition="-0.45"),
    ]
    reads = []

    def fill_pages(payload):
        reads.append(payload)
        return [x for x in fills if payload["startTime"] <= x["time"] <= payload["endTime"]]
    c.COPY_FILLS_FETCHER = fill_pages
    exchange = {"ETH": 1.0, "LINK": 5.0}   # BTC, AVAX, SOL, DOGE flat on the exchange

    def positions(payload):
        if payload.get("type") != "clearinghouseState":
            return []
        if payload.get("dex"):
            return {"assetPositions": [], "marginSummary": {"accountValue": "0"}}
        return {"assetPositions": [{"position": {"coin": k, "szi": str(v), "positionValue": str(abs(v) * 10)}}
                                   for k, v in exchange.items()], "marginSummary": {"accountValue": "1000"}}
    c.EXPOSURE_FETCHER = positions

    before = c.load_json(c.MANUAL_LIVE_POSITIONS_FILE, {})
    live_before = len(c.read_csv_rows(c.LIVE_FILLS_CSV))
    dry = c.repair_ledger_catch_up(dry_run=True)
    fixed = {r["coin"] for r in dry["repairs"]}
    refused = {r["coin"]: r["reason"] for r in dry["refused"]}
    check("D1_DRY_RUN_FINDS_THE_EXPLAINED_COINS", fixed == {"BTC", "AVAX", "TIA", "HYPE"}, json.dumps(dry, default=str)[:500])
    check("D1_DRY_RUN_CHANGES_NOTHING", c.load_json(c.MANUAL_LIVE_POSITIONS_FILE, {}).get("by_wallet") == before.get("by_wallet")
          and len(c.read_csv_rows(c.LIVE_FILLS_CSV)) == live_before)
    check("F1_FILL_OF_AN_ORDER_THE_ENGINE_DID_NOT_PLACE_REFUSED", "not from an order this engine placed" in refused.get("SOL", ""),
          str(refused))
    check("F2_REPLAY_SHORT_OF_THE_EXCHANGE_NET_REFUSED", "gives ledger net 1.0" in refused.get("DOGE", ""), str(refused))
    check("F3_UNEXPLAINED_EXCHANGE_POSITION_REFUSED", "LINK" in refused, str(refused))
    check("T1_DOUBLED_TID_ROW_OWNS_ITS_FILL_ONLY_THE_MISSED_CLOSE_REPLAYED",
          [[x["copy_fill_id"] for x in r["fills"]] for r in dry["repairs"] if r["coin"] == "TIA"] == [["0xtiax:62"]],
          str([r for r in dry["repairs"] if r["coin"] == "TIA"]))
    check("T2_ENGINE_ROW_WITHOUT_SIDE_REFUSED_BEFORE_APPLYING", "lacks the side" in refused.get("KAS", ""), str(refused))
    check("T3_POLL_PRESET_ID_NOT_DOUBLED", c.CopyAccountIngestor.copy_fill_id({"copy_fill_id": "0xh:7", "hash": "0xh", "tid": 7}) == "0xh:7"
          and c.CopyAccountIngestor.copy_fill_id({"hash": "0xh", "tid": 7}) == "0xh:7")
    check("D1_BTC_DRY_RUN_SHOWS_BOTH_TRANCHES", [len(r["fills"]) for r in dry["repairs"] if r["coin"] == "BTC"] == [2])

    res = c.repair_ledger_catch_up(dry_run=False)
    led2 = c.ManualLedger()
    check("E1_RECOVERY_CLOSE_FILLS_ADOPTED_LEDGER_FLAT",
          abs(led2.wallet_coin_position(A, "BTC")) < 1e-12 and abs(led2.coin_net("BTC")) < 1e-12, str(led2.sleeve(A, "BTC")))
    check("E2_RECORDED_CLOSE_FILL_ADOPTED_LEDGER_FLAT", abs(led2.wallet_coin_position(A, "AVAX")) < 1e-12)
    check("E3_EVERY_REPAIR_VERIFIED", res["repairs"] and all(r.get("verified") for r in res["repairs"]), str(res["repairs"])[:300])
    check("F4_REFUSED_COINS_UNTOUCHED", led2.wallet_coin_position(A, "SOL") == 1.0 and led2.wallet_coin_position(A, "DOGE") == 3.0
          and led2.wallet_coin_position(B, "ETH") == 1.0)
    lf = [r for r in c.read_csv_rows(c.LIVE_FILLS_CSV) if r.get("source") == "ledger_catch_up_repair"]
    check("E4_EACH_ADOPTED_FILL_WRITTEN_TO_LIVE_FILLS", sorted(r["copy_fill_id"] for r in lf) == ["0xavax:21", "0xbtc:11", "0xbtc:12", "0xtiax:62"],
          str([r["copy_fill_id"] for r in lf]))
    rec = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("status") == "LEDGER_CATCH_UP_REPAIR"]
    check("E5_AUDIT_ROW_PER_REPAIRED_COIN_SAYS_NO_ORDER", sorted(r["coin"] for r in rec) == ["AVAX", "BTC", "HYPE", "TIA"]
          and all("no exchange order placed" in r["notes"] for r in rec))
    again = c.repair_ledger_catch_up(dry_run=True)
    check("D2_SECOND_RUN_FINDS_NOTHING_LEFT_TO_REPAIR", not again["repairs"] and {r["coin"] for r in again["refused"]} == {"SOL", "DOGE", "LINK", "KAS"},
          json.dumps(again["repairs"], default=str)[:300])

    check("L5_REPAIR_ADOPTS_THE_EXCHANGE_LIQUIDATION", abs(led2.coin_net("HYPE")) < 1e-9
          and abs(led2.wallet_coin_position(A, "HYPE") - 0.2) < 1e-9 and abs(led2.wallet_coin_position(B, "HYPE") + 0.2) < 1e-9,
          f"{led2.wallet_coin_position(A, 'HYPE')} {led2.wallet_coin_position(B, 'HYPE')}")
    check("T4_TIA_FLAT_AND_KAS_UNTOUCHED", abs(led2.wallet_coin_position(A, "TIA")) < 1e-12 and led2.wallet_coin_position(A, "KAS") == 2.0)
    check("T5_REFUSED_COIN_CREATES_NO_EMPTY_SLEEVE",
          all("LINK" not in (wm or {}) for wm in (c.load_json(c.MANUAL_LIVE_POSITIONS_FILE, {}).get("by_wallet") or {}).values()))
    m0 = c.CopyFillMatcher(c.ManualLedger(), c.AuditLogWriter())
    check("T6_RESTARTED_ENGINE_TREATS_DOUBLED_ID_AS_OWNED", "0xtia:61" in m0.matched_copy_fill_ids)
    c.claim_copy_fill_process_marker("0xold:9:9")  # a marker as run 4 named it
    check("T8_OLD_DOUBLED_MARKER_STILL_CLAIMS_THE_FILL", c.claim_copy_fill_process_marker("0xold:9") is False
          and c.claim_copy_fill_process_marker("0xnew:5") is True)
    pos = {p["coin"]: p for p in res["exchange_positions"]}
    check("X1_ENGINE_OWNED_POSITION_EXPLAINED", pos["ETH"]["explained_by_engine_orders"] and pos["ETH"]["ledger_matches_exchange"])
    check("X1_FOREIGN_POSITION_NOT_EXPLAINED", not pos["LINK"]["explained_by_engine_orders"] and not res["exchange_positions_all_explained"])

    # a second tranche of one exchange transaction is a real fill (the old hash-only guard dropped it on restart)
    m = c.CopyFillMatcher(c.ManualLedger(), c.AuditLogWriter())
    check("D3_HASH_GUARD_ONLY_FOR_PRE_PATCH_ROWS", "0xbtc" not in m.matched_exchange_hashes and "0xeth" not in m.matched_exchange_hashes)

    # unreadable truth: refuse, change nothing
    c.EXPOSURE_FETCHER = lambda p: (_ for _ in ()).throw(RuntimeError("down"))
    check("F5_UNREADABLE_EXCHANGE_REFUSES", c.repair_ledger_catch_up(dry_run=False)["status"] == "REFUSED")
    c.EXPOSURE_FETCHER = positions
    big = [dict(f("XRP", "A", 1, 1, "0xx", i), time=t0 + 5) for i in range(2000)]
    c.COPY_FILLS_FETCHER = lambda p: big
    check("F6_FILL_HISTORY_THAT_CANNOT_BE_READ_IN_FULL_REFUSES", c.repair_ledger_catch_up(dry_run=True)["status"] == "REFUSED")
    c.COPY_FILLS_FETCHER = fill_pages
    huge = [dict(f("ADA", "B", 1, 5, f"0xh{i}", i), time=t0 + 100 + i) for i in range(10_500)]
    c.COPY_FILLS_FETCHER = lambda p: [x for x in huge if p["startTime"] <= x["time"] <= p["endTime"]][:2000]
    got10, st10 = c._read_all_copy_fills(t0, t0 + 100_000)
    check("T7_10K_HISTORY_LIMIT_REFUSES", st10.startswith("FILLS_INCOMPLETE") and "10,000" in st10, st10)
    c.COPY_FILLS_FETCHER = fill_pages

    # paging restarts at the last fill's millisecond, so fills sharing it across a page edge are not lost
    many = [dict(f("ADA", "B", 1, 5, f"0xa{i}", i), time=t0 + 100 + i // 3) for i in range(2500)]
    seen_pages = []

    def paged(p):
        seen_pages.append(p["startTime"])
        rows = [x for x in many if p["startTime"] <= x["time"] <= p["endTime"]]
        return rows[:2000]
    c.COPY_FILLS_FETCHER = paged
    got, st = c._read_all_copy_fills(t0, t0 + 10_000)
    check("D4_PAGING_READS_EVERY_FILL", st == "FILLS_COMPLETE" and len(got) == 2500, f"{st} {len(got)}")
    c.COPY_FILLS_FETCHER = fill_pages

    # ---- N: no exchange write; apply refuses while the engine holds the folder ----------------------------
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    body = src.split("def repair_ledger_catch_up", 1)[1].split("\n_INSTANCE_LOCK", 1)[0]
    reader = src.split("def _read_all_copy_fills", 1)[1].split("\ndef repair_ledger_catch_up", 1)[0]
    check("N1_REPAIR_HAS_NO_EXCHANGE_WRITE", not any(s in body + reader for s in
                                                     ("_place_order", "_cancel_order", "exchange.order", "exchange.cancel", "HL_EXCHANGE_URL")))
    main_body = src.split("def main()", 1)[1]
    check("N2_APPLY_TAKES_THE_ENGINE_INSTANCE_LOCK",
          "if args.repair_ledger_catch_up:\n        if not args.dry_run:\n            acquire_instance_lock(AUDIT_DIR)" in main_body.replace("\r\n", "\n"))
    holder = subprocess.Popen([sys.executable, "-c", (
        "import sys,time;sys.path.insert(0,%r);import HL_Live_Copy_Service_Core as c;"
        "c.acquire_instance_lock(c.AUDIT_DIR);print('held',flush=True);time.sleep(30)") % str(HERE)],
        stdout=subprocess.PIPE, text=True, env=dict(os.environ))
    try:
        holder.stdout.readline()
        out = subprocess.run([sys.executable, str(HERE / "HL_Live_Copy_Service_Core.py"), "--repair-ledger-catch-up"],
                             capture_output=True, text=True, env=dict(os.environ), timeout=60)
        check("N3_APPLY_REFUSED_WHILE_THE_ENGINE_RUNS", "INSTANCE_ALREADY_RUNNING" in (out.stdout + out.stderr),
              (out.stdout + out.stderr)[-300:])
    finally:
        holder.kill()

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
