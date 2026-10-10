#!/usr/bin/env python3
"""Run 5 (2026-10-10 08:11Z): the exchange liquidated an isolated HYPE short of 0.45; the fill has no engine order,
stayed unmatched, and the ledger kept -0.45 against an exchange 0, so every later HYPE close was refused.

L1 the run 5 fill: the short sleeve is reduced, the longs are untouched, ledger net = exchange net (0)
L2 audited (LIQUIDATION_APPLIED, a live_fills row per sleeve); applied once only
L3 shared over several sleeves on the liquidated side by size
L4 refused (ledger unchanged, LIQUIDATION_NOT_APPLIED) when the ledger did not match the exchange before it

Run: python test_core_liquidation.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
W = {k: "0x" + k * 40 for k in "abcde"}


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="liq_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0"})
    import HL_Live_Copy_Service_Core as c

    def setup(name, sleeves):
        led = c.ManualLedger(path=tmp / f"{name}.json")
        for w, sz in sleeves.items():
            led.sleeve(W[w], "HYPE")["signed_size"] = sz
        led._recompute_net(led.data)
        return led, c.CopyFillMatcher(led, c.AuditLogWriter())

    liq = {"coin": "HYPE", "time": 1791619912462, "oid": 62327156007, "side": "B", "sz": "0.45", "px": "49.5935",
           "tid": 132292667646358, "hash": "0xf90232bb", "dir": "Liquidated Isolated Short", "startPosition": "-0.45"}
    led, m = setup("run5", {"a": 0.24, "b": 0.22, "c": 0.22, "d": -1.13})
    ok = m.match_and_apply(dict(liq), {})
    net = led.coin_net("HYPE")
    check("L1_RUN5_LIQUIDATION_BRINGS_LEDGER_TO_EXCHANGE", ok and abs(net) < 1e-9
          and abs(led.wallet_coin_position(W["d"], "HYPE") + 0.68) < 1e-9
          and abs(led.wallet_coin_position(W["a"], "HYPE") - 0.24) < 1e-9, f"ok={ok} net={net}")
    rows = c.read_csv_rows(c.RECONCILIATION_CSV)
    fills = [r for r in c.read_csv_rows(c.LIVE_FILLS_CSV) if r.get("source") == "EXCHANGE_LIQUIDATION"]
    check("L2_AUDITED", any(r.get("status") == "LIQUIDATION_APPLIED" for r in rows) and len(fills) == 1, str(len(fills)))
    again = m.match_and_apply(dict(liq), {})
    check("L2_APPLIED_ONCE", not again and abs(led.coin_net("HYPE")) < 1e-9)

    led, m = setup("two", {"a": -0.3, "b": -0.1, "c": 0.5})
    ok = m.match_and_apply(dict(liq, hash="0x2", tid=2, sz="0.2", startPosition="0.1", side="B",
                                dir="Liquidated Cross Short", oid=2), {})
    check("L4_LEDGER_DISAGREES_REFUSED", not ok and abs(led.coin_net("HYPE") - 0.1) < 1e-9)
    ok = m.match_and_apply(dict(liq, hash="0x3", tid=3, sz="0.2", startPosition="-0.4", oid=3), {})
    check("L4_LEDGER_DISAGREES_REFUSED_WHEN_SHORTER", not ok, "")
    led, m = setup("three", {"a": -0.3, "b": -0.1})
    ok = m.match_and_apply(dict(liq, hash="0x4", tid=4, sz="0.2", startPosition="-0.4", oid=4), {})
    check("L3_SHARED_BY_SIZE", ok and abs(led.wallet_coin_position(W["a"], "HYPE") + 0.15) < 1e-9
          and abs(led.wallet_coin_position(W["b"], "HYPE") + 0.05) < 1e-9,
          f"{led.wallet_coin_position(W['a'], 'HYPE')} {led.wallet_coin_position(W['b'], 'HYPE')}")
    check("L4_NOT_APPLIED_ROW_WRITTEN", any(r.get("status") == "LIQUIDATION_NOT_APPLIED"
                                           for r in c.read_csv_rows(c.RECONCILIATION_CSV)))
    # L6: our own order filling against SOMEONE ELSE's liquidation is our fill, never a liquidation of ours
    other = {"coin": "HYPE", "side": "B", "sz": "0.1", "px": "50", "oid": 777, "hash": "0x7", "tid": 7,
             "dir": "Close Short", "startPosition": "-0.1", "liquidation": {"liquidatedUser": "0x" + "9" * 40}}
    check("L6_COUNTERPARTY_OF_A_LIQUIDATION_IS_NOT_OURS", not c.CopyFillMatcher._is_liquidation_fill(other))
    c.USER_WALLET = "0x" + "8" * 40
    check("L6_OUR_OWN_LIQUIDATION_FIELD_RECOGNISED",
          c.CopyFillMatcher._is_liquidation_fill(dict(other, liquidation={"liquidatedUser": "0x" + "8" * 40})))
    failed = sum(1 for _n, ok in RESULTS if not ok)
    print(f"TOTAL={len(RESULTS)} FAILED={failed}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
