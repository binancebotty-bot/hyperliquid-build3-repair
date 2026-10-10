#!/usr/bin/env python3
"""Run 5 (2026-10-10): two HYPE auto-deleveraging (ADL) fills left the ledger at -0.68 against an exchange 0.
The exchange closed the follower's short itself, so the fills carry no engine order; dir is "Auto-Deleveraging"
and there is no liquidation object. The repair (and the live matcher) refused them, exactly as it once refused a
liquidation, so the ledger kept a phantom short.

T3 treats an "Auto-Deleveraging" fill as a liquidation of the follower: it reduces the sleeves pro-rata, under the
same guard as PR #21 (only applied while the ledger net equals the fill's own startPosition), and the ledger
catch-up repair accepts it.

A1 the ADL fill is recognised as a liquidation; an ordinary close is not
A2 replaying the two HYPE ADL fills (B 0.46 and B 0.22 @ 49.6805) brings the ledger to the exchange net (0)
A3 pro-rata: every short sleeve on that side is reduced, proportional to its size, and accounted (LIQUIDATION_APPLIED)
A4 applied once only (a duplicate does not reduce again)
A5 refused (ledger unchanged, LIQUIDATION_NOT_APPLIED) when the ledger did not match the startPosition before it
A6 the ledger catch-up repair accepts the two ADL fills and ends flat against the exchange
A7 the repair leaves a refused coin's ledger untouched

Run: python test_core_adl.py   # RESULT:: markers, exit 0/1. No network, no orders.
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
W = {k: "0x" + k * 40 for k in "abcde"}
FOLLOWER = "0x" + "c" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


# The two run 5 HYPE ADL fills: a 0.68 short closed by B 0.46 then B 0.22 @ 49.6805. Different oid/hash/tid each.
ADL1 = {"coin": "HYPE", "time": 1791655835000, "oid": 62332571712, "side": "B", "sz": "0.46", "px": "49.6805",
        "tid": 132292667646400, "hash": "0xadl1cafe", "dir": "Auto-Deleveraging", "startPosition": "-0.68",
        "fee": "0.01", "closedPnl": "0"}
ADL2 = dict(ADL1, oid=62332571713, sz="0.22", tid=132292667646401, hash="0xadl2cafe", startPosition="-0.22",
            time=ADL1["time"] + 1)


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="adl_"))
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

    # ---- A1: recognition -----------------------------------------------------------------------------------
    check("A1_ADL_FILL_IS_A_LIQUIDATION", c.CopyFillMatcher._is_liquidation_fill(dict(ADL1)))
    check("A1_ORDINARY_CLOSE_IS_NOT", not c.CopyFillMatcher._is_liquidation_fill(
        dict(ADL1, dir="Close Short", hash="0xn", tid=9, oid=9)))

    def setup(name, sleeves):
        led = c.ManualLedger(path=tmp / f"{name}.json")
        for w, sz in sleeves.items():
            led.sleeve(W[w], "HYPE")["signed_size"] = sz
        led._recompute_net(led.data)
        return led, c.CopyFillMatcher(led, c.AuditLogWriter())

    # ---- A2/A3/A4: replay the two ADL fills -----------------------------------------------------------------
    led, m = setup("adl", {"a": -0.46, "b": -0.22})
    ok1 = m.match_and_apply(dict(ADL1), {})
    ok2 = m.match_and_apply(dict(ADL2), {})
    net = led.coin_net("HYPE")
    check("A2_ADL_FILLS_BRING_LEDGER_TO_EXCHANGE", ok1 and ok2 and abs(net) < 1e-9, f"ok1={ok1} ok2={ok2} net={net}")
    check("A3_PRO_RATA_SLEEVES_REDUCED",
          abs(led.wallet_coin_position(W["a"], "HYPE")) < 1e-9 and abs(led.wallet_coin_position(W["b"], "HYPE")) < 1e-9,
          f"{led.wallet_coin_position(W['a'], 'HYPE')} {led.wallet_coin_position(W['b'], 'HYPE')}")
    rows = c.read_csv_rows(c.RECONCILIATION_CSV)
    fills = [r for r in c.read_csv_rows(c.LIVE_FILLS_CSV) if r.get("source") == "EXCHANGE_LIQUIDATION"]
    # one live_fills row per sleeve per fill (2 sleeves x 2 fills), one LIQUIDATION_APPLIED audit row per fill
    check("A3_AUDITED_LIQUIDATION_APPLIED",
          len([r for r in rows if r.get("status") == "LIQUIDATION_APPLIED"]) == 2 and len(fills) == 4, str(len(fills)))
    again = m.match_and_apply(dict(ADL1), {})
    check("A4_APPLIED_ONCE", not again and abs(led.coin_net("HYPE")) < 1e-9)

    # ---- A5: the PR #21 guard still holds -------------------------------------------------------------------
    led, m = setup("guard", {"a": -0.40, "b": -0.10})  # ledger net -0.50, the fill says startPosition -0.68
    ok = m.match_and_apply(dict(ADL1, hash="0xguard", tid=77, oid=77), {})
    check("A5_LEDGER_DISAGREES_REFUSED", not ok and abs(led.coin_net("HYPE") + 0.50) < 1e-9
          and any(r.get("status") == "LIQUIDATION_NOT_APPLIED" for r in c.read_csv_rows(c.RECONCILIATION_CSV)),
          f"ok={ok} net={led.coin_net('HYPE')}")

    # ---- A6/A7: the ledger catch-up repair accepts ADL fills ------------------------------------------------
    led = c.ManualLedger()
    for w, sz in ((W["a"], -0.46), (W["b"], -0.22)):
        s = led.sleeve(w, "HYPE")
        s.update(signed_size=sz, direction="SHORT", avg_entry_px=49.6805, last_copy_fill_id="x")
    led._recompute_net(led.data)
    led.save()
    audit = c.AuditLogWriter()
    for path, fields in ((c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS), (c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS)):
        c.ensure_csv_header(path, fields)

    # A repair runs in a fresh process where these ADL ids were never owned: use distinct exchange hash/tid so the
    # live_fills rows the matcher section above wrote to the shared audit dir do not pre-own them.
    fills = [dict(ADL1, time=t0 + 1000, hash="0xadlrepair1", tid=9001),
             dict(ADL2, time=t0 + 1001, hash="0xadlrepair2", tid=9002)]

    def fill_pages(payload):
        return [x for x in fills if payload["startTime"] <= x["time"] <= payload["endTime"]]
    c.COPY_FILLS_FETCHER = fill_pages
    exchange = {}   # HYPE flat on the exchange

    def positions(payload):
        if payload.get("type") != "clearinghouseState":
            return []
        if payload.get("dex"):
            return {"assetPositions": [], "marginSummary": {"accountValue": "0"}}
        return {"assetPositions": [{"position": {"coin": k, "szi": str(v), "positionValue": str(abs(v) * 10)}}
                                   for k, v in exchange.items()], "marginSummary": {"accountValue": "1000"}}
    c.EXPOSURE_FETCHER = positions

    dry = c.repair_ledger_catch_up(t0 - 1000, dry_run=True)
    check("A6_DRY_RUN_REPAIRS_HYPE", [r["coin"] for r in dry["repairs"]] == ["HYPE"] and dry["refused"] == [],
          json.dumps(dry, default=str)[:400])
    before = c.load_json(c.MANUAL_LIVE_POSITIONS_FILE, {}).get("by_wallet")
    c.repair_ledger_catch_up(t0 - 1000, dry_run=True)
    check("A6_DRY_RUN_CHANGES_NOTHING",
          c.load_json(c.MANUAL_LIVE_POSITIONS_FILE, {}).get("by_wallet") == before)
    res = c.repair_ledger_catch_up(t0 - 1000, dry_run=False)
    led2 = c.ManualLedger()
    check("A6_REPAIR_APPLIES_ADL_LEDGER_FLAT",
          res["repairs"] and res["repairs"][0].get("verified") and abs(led2.coin_net("HYPE")) < 1e-9
          and abs(led2.wallet_coin_position(W["a"], "HYPE")) < 1e-9 and abs(led2.wallet_coin_position(W["b"], "HYPE")) < 1e-9,
          f"{led2.coin_net('HYPE')} {res['repairs']}")

    # refused coin: the exchange holds 0.5 HYPE the ledger cannot explain, so it must be left untouched
    led3 = c.ManualLedger()
    led3.sleeve(W["a"], "HYPE").update(signed_size=-0.4, direction="SHORT", avg_entry_px=49.6805, last_copy_fill_id="x")
    led3._recompute_net(led3.data)
    led3.save()
    c.COPY_FILLS_FETCHER = lambda p: []           # no fills explain the gap
    exchange = {"HYPE": 0.5}
    c.repair_ledger_catch_up(t0 - 1000, dry_run=False)
    led4 = c.ManualLedger()
    check("A7_REFUSED_COIN_UNTOUCHED", abs(led4.wallet_coin_position(W["a"], "HYPE") + 0.4) < 1e-9,
          str(led4.wallet_coin_position(W["a"], "HYPE")))

    failed = sum(1 for _n, ok in RESULTS if not ok)
    print(f"TOTAL={len(RESULTS)} FAILED={failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
