#!/usr/bin/env python3
"""T2 (issue #3): operator-approved per-oid adoption in the ledger repair tool.

PENGU exchange -1,427 / ledger 0 (fill ~09:30:35Z, oid 62330275636, no send row): a resting missed-entry
limit that filled while the engine was down, so the copy poll never owned it. `--adopt-oid <oid>` (repeatable)
lets the operator rule on it: the tool reads the follower's OWN fills and refuses unless the fill EXISTS for
this follower, is in NO ledger/send row, and exactly ONE recorded (unowned) order intent matches coin+side+size
(that intent names the sleeve). It then books the fill to that sleeve through the normal ledger fill path and
writes an audit row. Ledger and audit files only: no exchange order, no cancel, reads only. Without the flag it
refuses and changes nothing.

P  the PENGU fill is adopted: booked to A's PENGU sleeve (-1,427), live_fills + audit rows written.
D  a dry run reports the same and changes nothing; a second run finds it already owned (idempotent).
F  refused unchanged: an oid with no exchange fill; an oid already in a send row; a fill already in the ledger;
   a fill with no matching recorded intent; and the base catch-up repair refuses the orphan without the flag.
N  the adoption path has no exchange write; the CLI flag is wired.

Run: python test_core_adopt_oid.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import json
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
PENGU_OID = "62330275636"


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def finish() -> None:
    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    sys.exit(1 if failed else 0)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="adoptoid_"))
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
    adopt = getattr(c, "repair_adopt_oids", None)
    check("T2_ADOPTION_FUNCTION_EXISTS", adopt is not None,
          "repair_adopt_oids missing (this test fails on main, where --adopt-oid does not exist)")
    if adopt is None:
        finish()  # cannot exercise the rest without the feature; the FAIL above is the finding
    assert adopt is not None
    t0 = c.utc_now_ms() - 3_600_000

    ledger = c.ManualLedger()
    for w, coin, size in ((A, "BTC", 2.0), (A, "ETH", 1.0)):
        s = ledger.sleeve(w, coin)
        s.update(signed_size=size, direction="LONG", avg_entry_px=10.0, last_copy_fill_id="x")
    ledger._recompute_net(ledger.data)
    ledger.save()  # a normal BTC sleeve that must stay untouched; PENGU has no sleeve at all
    audit = c.AuditLogWriter()
    for path, fields in ((c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS), (c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS),
                         (c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS), (c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS)):
        c.ensure_csv_header(path, fields)

    # ---- the recorded intent the engine wrote BEFORE placing the PENGU resting limit (its send row was lost) ----
    pengu_intent = c.Intent(
        intent_id="i-pengu", fill=c.LeaderFill("lf-pengu", A, "PENGU", "SELL", 0.008, 1427.0, t0, "TEST", 0, {}),
        copy_side="SELL", copy_size=1427.0, copy_notional=1427.0 * 0.008, wallet_mode="LIVE", copy_mode="fixed",
        decision="ENTRY_ALLOWED", reason="MISSED_ENTRY", sleeve_id=c.ManualLedger.sleeve_id(A, "PENGU"), position_id="",
        position_direction_before="", wallet_position_before=0.0, coin_net_before=0.0, reduce_only_intended=False,
        reduce_only_sent_planned=False, created_at_ms=t0, notes="lifecycle=ENTRY;missed entry resting limit (GTC)")
    audit.append_order_intent(pengu_intent)
    # SOL oid 777: an order the engine DID place (send row) -> never re-booked
    audit.append_send_attempt({"created_at_ms": t0, "intent_id": "i-sol", "leader_fill_id": "lf-sol", "leader_wallet": A,
                               "coin": "SOL", "side": "SELL", "copy_size": 1.0, "limit_price": 10.0,
                               "status": "ORDER_FILLED", "exchange_order_id": "777", "reduce_only_sent": "True",
                               "wallet_position_before": 1.0, "terminal_state": "FILLED_AWAITING_COPY_POLL",
                               "notes": "lifecycle=EXIT"})
    # ETH oid 555: already owned in the ledger (live_fills)
    audit.append_live_fill({"created_at_ms": t0, "copy_fill_id": "0xeth:1", "intent_id": "i-eth", "leader_wallet": A,
                            "coin": "ETH", "side": "BUY", "fill_size": 1.0, "exchange_hash": "0xeth",
                            "exchange_order_id": "555"})

    def f(coin, side, sz, oid, h, tid, dt=0, extra=None):
        row = {"coin": coin, "side": side, "sz": str(sz), "px": "10", "oid": oid, "hash": h, "tid": tid,
               "time": t0 + 1000 + dt, "dir": "Close", "fee": "0.01", "closedPnl": "0"}
        if extra:
            row.update(extra)
        return row
    fills = [
        # the PENGU fill: exchange -1,427, oid 62330275636, no send row  (dir Open Short from flat)
        f("PENGU", "A", 1427, PENGU_OID, "0xpengu", 91, 0, {"px": "0.008", "dir": "Open Short", "startPosition": "0"}),
        f("SOL", "A", 1.0, 777, "0xsol", 92, 10),
        f("LTC", "B", 5.0, 888, "0xltc", 93, 20),          # no recorded intent -> refuse
        f("ETH", "B", 1.0, 555, "0xeth2", 94, 30),          # already in the ledger -> refuse
    ]
    reads = []

    def fill_pages(payload):
        reads.append(payload)
        return [x for x in fills if payload["startTime"] <= x["time"] <= payload["endTime"]]
    c.COPY_FILLS_FETCHER = fill_pages

    def positions(payload):
        if payload.get("type") != "clearinghouseState":
            return []
        if payload.get("dex"):
            return {"assetPositions": [], "marginSummary": {"accountValue": "0"}}
        ex = {"PENGU": -1427.0}  # exchange -1,427 while the ledger shows 0: the orphan the base repair refuses
        return {"assetPositions": [{"position": {"coin": k, "szi": str(v), "positionValue": str(abs(v) * 0.008)}}
                                   for k, v in ex.items()], "marginSummary": {"accountValue": "1000"}}
    c.EXPOSURE_FETCHER = positions

    # ---- refuses without the flag, and the base repair refuses the orphan without it ---------------------------------
    no_flag = adopt([], dry_run=False)
    check("F5_ADOPTION_REFUSES_WITHOUT_THE_FLAG", no_flag["status"] == "REFUSED" and "adopt-oid" in no_flag["reason"]
          and c.ManualLedger().coin_net("PENGU") == 0.0, json.dumps(no_flag, default=str)[:300])
    base = c.repair_ledger_catch_up(dry_run=True)
    check("F6_BASE_CATCH_UP_REFUSES_THE_ORPHAN_WITHOUT_THE_FLAG",
          {r["coin"] for r in base["repairs"]}.isdisjoint({"PENGU"})
          and "not from an order this engine placed" in next((r["reason"] for r in base["refused"] if r["coin"] == "PENGU"), ""),
          json.dumps(base["refused"], default=str)[:400])

    # ---- dry run reports the PENGU fill and changes nothing ----------------------------------------------------------
    before = c.load_json(c.MANUAL_LIVE_POSITIONS_FILE, {})
    live_before = len(c.read_csv_rows(c.LIVE_FILLS_CSV))
    dry = adopt([PENGU_OID], dry_run=True)
    check("D1_DRY_RUN_REPORTS_THE_PENGU_FILL", dry["status"] == "DRY_RUN" and dry["adopted_count"] == 1
          and dry["adopted"][0]["sleeves"] == [c.ManualLedger.sleeve_id(A, "PENGU")]
          and dry["adopted"][0]["fills"][0]["size"] == 1427.0, json.dumps(dry, default=str)[:400])
    check("D2_DRY_RUN_CHANGES_NOTHING", c.load_json(c.MANUAL_LIVE_POSITIONS_FILE, {}).get("by_wallet") == before.get("by_wallet")
          and len(c.read_csv_rows(c.LIVE_FILLS_CSV)) == live_before)

    # ---- apply: the fill is booked to the sleeve, with a live_fills row and an audit row -----------------------------
    res = adopt([PENGU_OID], dry_run=False)
    led2 = c.ManualLedger()
    check("P1_PENGU_FILL_BOOKED_TO_THE_SLEEVE", res["status"] == "APPLIED" and res["adopted_count"] == 1
          and abs(led2.wallet_coin_position(A, "PENGU") + 1427.0) < 1e-9 and abs(led2.coin_net("PENGU") + 1427.0) < 1e-9,
          f"{led2.wallet_coin_position(A, 'PENGU')} {led2.coin_net('PENGU')}")
    check("P2_BTC_UNTOUCHED", led2.wallet_coin_position(A, "BTC") == 2.0 and led2.wallet_coin_position(A, "ETH") == 1.0
          and led2.wallet_coin_position(B, "PENGU") == 0.0)
    lf = [r for r in c.read_csv_rows(c.LIVE_FILLS_CSV) if r.get("source") == c.OPERATOR_ADOPT_SOURCE]
    check("P3_LIVE_FILL_ROW_WRITTEN", len(lf) == 1 and c.CopyFillMatcher._normalize_oid(lf[0]["exchange_order_id"]) == PENGU_OID
          and lf[0]["coin"] == "PENGU" and lf[0]["side"] == "SELL" and abs(float(lf[0]["fill_size"]) - 1427.0) < 1e-9
          and lf[0]["sleeve_id"] == c.ManualLedger.sleeve_id(A, "PENGU"), json.dumps(lf, default=str)[:400])
    rec = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("status") == c.OPERATOR_ADOPT_AUDIT_STATUS]
    check("P4_AUDIT_ROW_WRITTEN", len(rec) == 1 and rec[0]["event"] == "LEDGER_REPAIR"
          and c.CopyFillMatcher._normalize_oid(rec[0]["exchange_order_id"]) == PENGU_OID and rec[0]["coin"] == "PENGU"
          and "no exchange order placed" in rec[0]["notes"], json.dumps(rec, default=str)[:400])

    # ---- refusals change nothing --------------------------------------------------------------------------------------
    r_missing = adopt(["999999"], dry_run=False)
    check("F1_NO_EXCHANGE_FILL_REFUSED", r_missing["refused_count"] == 1
          and "no fill with this order id exists" in r_missing["refused"][0]["reason"], json.dumps(r_missing, default=str)[:300])
    r_send = adopt(["777"], dry_run=False)
    check("F2_ALREADY_IN_A_SEND_ROW_REFUSED", r_send["refused_count"] == 1
          and "already in a send row" in r_send["refused"][0]["reason"], json.dumps(r_send, default=str)[:300])
    r_led = adopt(["555"], dry_run=False)
    check("F3_ALREADY_IN_THE_LEDGER_REFUSED", r_led["refused_count"] == 1
          and "already in the ledger" in r_led["refused"][0]["reason"], json.dumps(r_led, default=str)[:300])
    r_no_intent = adopt(["888"], dry_run=False)
    check("F4_NO_MATCHING_INTENT_REFUSED", r_no_intent["refused_count"] == 1
          and "no recorded intent matches" in r_no_intent["refused"][0]["reason"], json.dumps(r_no_intent, default=str)[:300])
    led3 = c.ManualLedger()
    check("F7_REFUSED_OIDS_UNTOUCHED", led3.coin_net("SOL") == 0.0 and led3.coin_net("LTC") == 0.0
          and led3.coin_net("ETH") == 1.0)

    # ---- idempotent: a second run finds the fill already owned ---------------------------------------------------------
    again = adopt([PENGU_OID], dry_run=False)
    led4 = c.ManualLedger()
    check("D3_SECOND_RUN_FINDS_IT_ALREADY_OWNED", again["adopted_count"] == 0 and again["refused_count"] == 1
          and "already in the ledger" in again["refused"][0]["reason"] and abs(led4.coin_net("PENGU") + 1427.0) < 1e-9,
          json.dumps(again, default=str)[:300])

    # ---- N: no exchange write in the adoption path; the CLI flag is wired ---------------------------------------------
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    body = src.split("def repair_adopt_oids", 1)[1].split("\ndef _INSTANCE_LOCK", 1)[0]
    check("N1_ADOPTION_HAS_NO_EXCHANGE_WRITE", not any(s in body for s in
          ("_place_order", "_cancel_order", "exchange.order", "exchange.cancel", "HL_EXCHANGE_URL")))
    main_body = src.split("def main()", 1)[1]
    check("N2_CLI_FLAG_WIRED", 'add_argument("--adopt-oid"' in main_body and "if args.adopt_oid:" in main_body
          and "repair_adopt_oids(args.adopt_oid" in main_body)
    check("N3_ADOPT_RAN_OFFLINE", len(reads) >= 1)  # every exchange read went through the stubbed fetcher; requests.post raised

    finish()


if __name__ == "__main__":
    main()
