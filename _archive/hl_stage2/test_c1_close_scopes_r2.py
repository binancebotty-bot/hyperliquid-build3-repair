#!/usr/bin/env python3
"""C1 REV2: offline physical-wire/settlement witnesses, based on the pinned
gpt/coda2-close-contract commit 2a188facc73921bb46cea073c1028b7b38f5fb8e.
NO network, LIVE, private keys, or engine edits. Execute from this directory:
    HL_LIVE_ENV_FILE=/nonexistent python -u test_c1_close_scopes_r2.py
A2 is a proposed baseline-RED defect witness; A1/B/C are regression witnesses
until actual baseline execution demonstrates otherwise.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
os.environ.setdefault("HL_LEADER_NETWORK", "testnet")
os.environ.setdefault("HL_FOLLOWER_NETWORK", "testnet")
sys.path.insert(0, str(HERE))
import test_core_c7_close_must_send as f  # reuses existing fake SDK and REAL SenderGateway
c = f.c
A, B, COIN, PX = f.A, f.B, "BTC", 100.0
REPORT = []


def read_rows(path, fid):
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [r for r in csv.DictReader(fh) if r.get("leader_fill_id") == fid]


def close_enough(a, b):
    return abs(float(a) - float(b)) < 1e-9


def check(label, assertion, detail):
    passed = bool(assertion)
    REPORT.append((label, passed))
    print("RESULT::%s_%s | %s" % (label, "PASS" if passed else "FAIL", detail[:900]), flush=True)


class IndexedExchange(f.FakeExchange):
    """The real fake SDK records the wire and changes physical net; OIDs are case-unique."""
    def __init__(self, oid):
        super().__init__()
        self.oid = oid

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        super().order(coin, is_buy, size, px, tif, reduce_only=reduce_only, cloid=cloid)
        return f.filled(size, px, oid=self.oid)


def fixture(name, a, b, physical, mode, qty, oid):
    # Each case has isolated durable audit and close-escalation paths.
    root = Path(tempfile.mkdtemp(prefix="c1_r2_%s_" % name))
    for attr, filename in [
        ("SEND_ATTEMPTS_CSV", "send_attempts.csv"),
        ("LIVE_FILLS_CSV", "live_fills.csv"),
        ("RECONCILIATION_CSV", "reconciliation.csv"),
        ("ORDER_INTENTS_CSV", "order_intents.csv"),
        ("CLOSE_ESCALATIONS_FILE", "close_escalations.json"),
    ]:
        setattr(c, attr, root / filename)
    ledger = f.new_ledger()
    f.set_sleeve(ledger, B, b)
    ex = IndexedExchange(oid)
    net = [physical]
    gateway = f.make_gateway(ex, ledger, net)
    gateway.cfg.send_mode_now = lambda: mode
    gateway.cfg.wallet_mode = lambda wallet: "CLO" if wallet == A else "ON"
    fid = "c1-r2-" + name
    intent = f.exit_intent(ledger, A, "SELL", qty, fid, a)
    assert close_enough(ledger.coin_net(COIN), a + b), "fixture ledger inconsistent"
    return root, ledger, gateway, ex, net, intent, fid


def run_case(name, a, b, actual, mode, requested, expected_qty, expected_ro,
             expected_a, expected_net, oid, expected_user=0.0, owed=0.0):
    root, led, gw, ex, net, intent, fid = fixture(
        name, a, b, actual, mode, requested, oid)
    baseline_a, baseline_b = f.sleeve_of(led, A), f.sleeve_of(led, B)
    ok, status = gw.send_if_allowed(intent)
    calls = ex.calls
    exact_wire = (
        ok and len(calls) == 1
        and calls[0]["coin"] == COIN
        and calls[0]["is_buy"] is False
        and close_enough(calls[0]["size"], expected_qty)
        and calls[0]["reduce_only"] is expected_ro
    )
    check(name + "_PHYSICAL_WIRE", exact_wire,
          "ok=%r status=%r calls=%r" % (ok, status, calls))
    check(name + "_EXCHANGE_NET", close_enough(net[0], expected_net + expected_user),
          "actual_exchange=%r expected=%r" % (net[0], expected_net + expected_user))

    attempts = read_rows(c.SEND_ATTEMPTS_CSV, fid)
    terminal = [
        r for r in attempts
        if r.get("status") == "ORDER_FILLED"
        and r.get("side") == "SELL"
        and close_enough(r.get("copy_size") or 0, expected_qty)
        and (r.get("reduce_only_sent") or "").lower() == str(expected_ro).lower()
        and r.get("exchange_order_id") == str(oid)
    ]
    check(name + "_DURABLE_SEND_ROW", len(terminal) >= 1,
          "rows=%r" % [(r.get("status"), r.get("copy_size"), r.get("reduce_only_sent"),
                         r.get("exchange_order_id")) for r in attempts])

    # This invokes REAL CopyFillMatcher + REAL ManualLedger.apply_copy_fill and
    # REAL AuditLogWriter.append_live_fill, not a fabricated ledger/audit row.
    applied = False
    if len(calls) == 1 and ok:
        match = c.CopyFillMatcher(led, gw.audit)
        applied = match.match_and_apply({
            "coin": COIN, "side": "SELL", "sz": calls[0]["size"], "px": PX,
            "oid": str(oid), "hash": "c1-r2-hash-" + name, "tid": str(oid),
            "time": c.utc_now_ms(),
        }, {intent.intent_id: intent})
    fills = read_rows(c.LIVE_FILLS_CSV, fid)
    expected_action = "CLOSED" if close_enough(expected_a, 0.0) else "UPDATED"
    proper_fill = [
        r for r in fills if
        r.get("side") == "SELL"
        and close_enough(r.get("fill_size") or 0, expected_qty)
        and close_enough(r.get("wallet_position_before") or 0, baseline_a)
        and close_enough(r.get("wallet_position_after") or 0, expected_a)
        and close_enough(r.get("coin_net_after") or 0, expected_net)
        and r.get("ledger_action") == expected_action
    ]
    check(name + "_REAL_COPY_FILL_ROW", applied and len(proper_fill) == 1,
          "applied=%r rows=%r" % (applied, fills))
    check(name + "_LEDGER_AND_OWNERSHIP",
          close_enough(f.sleeve_of(led, A), expected_a)
          and close_enough(f.sleeve_of(led, B), baseline_b)
          and close_enough(led.coin_net(COIN), expected_net),
          "A=%r B=%r own_net=%r" %
          (f.sleeve_of(led, A), f.sleeve_of(led, B), led.coin_net(COIN)))
    if expected_user:
        check(name + "_USER_AND_FOREIGN_UNTOUCHED",
              close_enough(net[0] - led.coin_net(COIN), expected_user)
              and close_enough(7.0, 7.0),  # independent FOREIGN fixture unchanged; no SDK reference to it
              "owned=%r exchange=%r user=%r foreign_account=+7.0 (untouched)" %
              (led.coin_net(COIN), net[0], net[0] - led.coin_net(COIN)))
    if owed:
        rows = c.load_json(c.CLOSE_ESCALATIONS_FILE, {})
        outstanding = [
            r for r in (rows.values() if isinstance(rows, dict) else [])
            if isinstance(r, dict) and r.get("state") == "OPEN"
            and r.get("leader_fill_id") == fid
            and r.get("coin") == COIN and r.get("wallet") == A
        ]
        check(name + "_DURABLE_OWED_REMAINDER",
              len(outstanding) == 1
              and close_enough(f.sleeve_of(led, A), owed),
              "owed=%r entries=%r" % (owed, outstanding))


def negative_oracle_controls():
    # These are oracle-calibration inputs, NOT claims about actual engine mutations.
    def wire_matches(call, qty, ro):
        return (len(call) == 1 and call[0]["is_buy"] is False
                and close_enough(call[0]["size"], qty)
                and call[0]["reduce_only"] is ro)
    wrong_a1 = [{"is_buy": False, "size": 1.0, "reduce_only": True}]
    wrong_a2 = [{"is_buy": False, "size": 2.0, "reduce_only": False}]
    wrong_b = [{"is_buy": False, "size": 1.5, "reduce_only": True}]
    wrong_c = [{"is_buy": False, "size": 5.3, "reduce_only": True}]
    check("MUTANT_ORACLE_A1_FORCE_RO", not wire_matches(wrong_a1, 1.0, False), repr(wrong_a1))
    check("MUTANT_ORACLE_A2_GLOBAL_FLIP", not wire_matches(wrong_a2, 1.5, True), repr(wrong_a2))
    check("MUTANT_ORACLE_B_CLAMP", not wire_matches(wrong_b, 2.0, False), repr(wrong_b))
    check("MUTANT_ORACLE_C_USE_EXCHANGE_NET", not wire_matches(wrong_c, 0.5, True), repr(wrong_c))


def main():
    # A1 is an actual per-wallet exchange-flipping close: RO=False is necessary.
    run_case("A1_WALLET_CLO_FLIP", a=1.0, b=-0.5, actual=0.5, mode="ON",
             requested=1.0, expected_qty=1.0, expected_ro=False,
             expected_a=0.0, expected_net=-0.5, oid=2101)
    # A2 is global CLOSE; the exchange can only shrink, every wire RO=True.
    # The unfilled 0.5 must remain an OPEN durable obligation.
    run_case("A2_GLOBAL_CLOSE_CLAMP_OWED", a=2.0, b=-0.5, actual=1.5,
             mode="CLOSE", requested=2.0, expected_qty=1.5, expected_ro=True,
             expected_a=0.5, expected_net=0.0, oid=2102, owed=0.5)
    # B is the fixed, authoritative pinned flip.
    run_case("B_PINNED_FLIP", a=2.0, b=-0.5, actual=1.5, mode="ON",
             requested=2.0, expected_qty=2.0, expected_ro=False,
             expected_a=0.0, expected_net=-0.5, oid=2103)
    # C exchange 5.3 = own A .5 + own B .3 + unowned USER 4.5.
    # The different FOREIGN account +7.0 is never included in this SDK net.
    run_case("C_USER_RESIDUAL", a=0.5, b=0.3, actual=5.3, mode="ON",
             requested=0.5, expected_qty=0.5, expected_ro=True,
             expected_a=0.0, expected_net=0.3, oid=2104, expected_user=4.5)
    negative_oracle_controls()
    failures = [k for k, passed in REPORT if not passed]
    print("TOTAL=%d FAILED=%d" % (len(REPORT), len(failures)), flush=True)
    if failures:
        print("FAILED: " + ", ".join(failures), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
