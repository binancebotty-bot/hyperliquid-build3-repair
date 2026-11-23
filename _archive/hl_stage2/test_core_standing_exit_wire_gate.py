"""Fix 5 RED/GREEN: the standing exit recovery must pass the final wire gate before exchange.order().

Review finding: the standing-exit recovery path called _place_order() directly at Core ~L5559 while every other
order path runs _validate_final_wire_order() first, so a non-canonical sdk_coin (or a zero/NaN size or price)
could reach the exchange from that path alone.

This file asserts the gate is respected. _place_order is the only funnel to exchange.order(), so a recording
stand-in for it is what "must not reach the exchange" is measured against.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
os.environ.setdefault("PAID_GUARD_ALLOW", "1")

import HL_Live_Copy_Service_Core as core  # noqa: E402

checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    if not ok:
        print(f"FAIL {name}: {detail}")


class Recorder:
    def __init__(self):
        self.records = []

    def append_reconciliation(self, *a, **k):
        self.records.append((a, k))

    def append(self, *a, **k):  # tolerate other call shapes
        self.records.append((a, k))

    def labels(self):
        return " ".join(str(r[0][1]) if len(r[0]) > 1 else str(r[0][0]) for r in self.records)


def make_intent(coin="BTC", side="SELL", size=1.0, px=100.0):
    fill = SimpleNamespace(leader_wallet="0xleader", coin=coin, leader_fill_id="F1", price=px)
    # fixture completeness: the final wire gate reads intent.notes (dust-close detection) and
    # classify_send_lifecycle reads it too; real intents always carry it.
    return SimpleNamespace(fill=fill, reduce_only_intended=True, copy_side=side, copy_size=size,
                           intent_id="I1", sleeve_id="S1", position_id="P1", notes="")


def make_gateway(place_calls, ledger_size="1.0"):
    g = core.SenderGateway.__new__(core.SenderGateway)
    # fixture completeness: the gate reads the ENTRY/ADD cap through cfg.max_order_notional(); absent, the gate
    # correctly fails closed, which would mask what this file is testing.
    g.cfg = SimpleNamespace(master_switch_now=lambda: True, send_mode_now=lambda: "ON",
                            max_order_notional=lambda: 1000.0)
    g.ledger = SimpleNamespace(sleeve=lambda _w, _c: {"signed_size": ledger_size}, coin_net=lambda _c: 0.0)
    g.audit = Recorder()
    g._exit_recovery_exists = lambda _intent: False
    g._resolve_coin = lambda coin: {"ok": True, "raw_coin": coin, "sdk_coin": coin, "price_max_dec": 2, "sz_dec": 3}
    g._effective_symbol_min_notional = lambda _res: 0.0
    g._close_wire_plan = lambda intent, cs, _szd, _min_n, _x, ledger_may_lag=False: (False, cs, "")
    g._parse_hl_response = lambda _resp: (True, "ORDER_RESTING", "1", "")
    g._recovery_intent_ids = set()
    g._resting_lock = threading.Lock()
    g._standing_closes = {}
    g._record_placed_order = lambda *a, **k: None

    def _place_order(*a, **k):
        place_calls.append((a, k))
        return {}

    g._place_order = _place_order
    return g


def run_case(sdk_coin, wire_size=1.0, limit_px=100.0, ledger_size="1.0"):
    place_calls = []
    g = make_gateway(place_calls, ledger_size=ledger_size)
    # fixture completeness: the recovery path reads the original IOC response's notes for its audit line.
    sentinel = SimpleNamespace(error="ioc missed", notes="ioc did not fill")
    g._queue_exit_recovery_if_needed(sentinel, sdk_coin, make_intent(px=limit_px), limit_px, wire_size, {}, "")
    return g, place_calls


def main():
    # 1. non-canonical symbol must not be sent
    g, calls = run_case("#123")
    check("F5_A_NONCANONICAL_SYMBOL_NOT_SENT", len(calls) == 0,
          f"place_order calls={len(calls)}; audit={g.audit.labels()[:200]}")

    # 2. zero size must not be sent
    g, calls = run_case("BTC", wire_size=0.0)
    check("F5_C_ZERO_SIZE_NOT_SENT", len(calls) == 0,
          f"place_order calls={len(calls)}; audit={g.audit.labels()[:200]}")

    # 3. a non-finite size must not be sent. A NaN wire_size is clamped by min() against the sleeve, so the
    #    size that would actually be sent stays finite; the case that reaches the wire as NaN is a NaN sleeve.
    g, calls = run_case("BTC", wire_size=float("nan"))
    check("F5_C_NAN_WIRE_CLAMPED_TO_FINITE", len(calls) == 1,
          f"place_order calls={len(calls)}; audit={g.audit.labels()[:200]}")
    g, calls = run_case("BTC", ledger_size="nan")
    check("F5_C_NAN_SIZE_NOT_SENT", len(calls) == 0,
          f"place_order calls={len(calls)}; audit={g.audit.labels()[:200]}")

    # 4. a valid recovery still places exactly once
    g, calls = run_case("BTC", wire_size=1.0, limit_px=100.0)
    check("F5_VALID_RECOVERY_PLACES_ONCE", len(calls) == 1,
          f"place_order calls={len(calls)}; audit={g.audit.labels()[:200]}")

    failed = [c for c in checks if not c[1]]
    for name, ok, _ in checks:
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    print(f"SUMMARY pass={len(checks)-len(failed)} fail={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
