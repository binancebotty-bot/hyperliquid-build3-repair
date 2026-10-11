#!/usr/bin/env python3
"""
convergence_shadow.py  —  SHADOW / OFFLINE ONLY.  Sends no orders. Imports no Core.

Pure, deterministic "desired-state convergence" planner for the HL copy engine, plus a
self-test that proves it on known disaster cases. This file is sealed: it has NO exchange
client, NO network, NO Core import, and NO ledger writes. It cannot place an order. Its only
job is to compute, from (desired_net, actual_net), the single safe next order — so the result
can be diffed against the live engine in shadow before any live wiring is approved.

Run:  python convergence_shadow.py            # prints PASS/FAIL + RESULT:: markers, exit 0/1

Model (per coin, evaluated each reconcile tick):
    DESIRED_NET = sum of copied-wallet target exposures (your intent truth; signed: long +, short -)
    ACTUAL_NET  = fresh exchange net position for the coin (the only real truth; signed)
    ORDER       = the minimal next step that moves ACTUAL_NET toward DESIRED_NET, where:
                    * reduce_only is decided from the NET (|DESIRED| < |ACTUAL|), never from a sleeve
                    * a sign flip is split into two legs: reduce-only flatten THIS tick,
                      open deferred until ACTUAL is confirmed flat next tick
                    * size is the delta, never the full sleeve -> idempotent / convergent:
                      once ACTUAL == DESIRED the order is NONE, so duplicate leader events
                      produce zero extra orders.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Optional, Tuple

EPS = 1e-9


@dataclass(frozen=True)
class ConvergenceOrder:
    coin: str
    side: str               # "BUY" | "SELL" | ""  ("" when action == NONE)
    size: float             # absolute quantity, >= 0
    reduce_only: bool
    action: str             # NONE | OPEN | ADD | REDUCE | FLATTEN | FLATTEN_THEN_OPEN
    reason: str
    # For a sign flip, the open leg is deferred until ACTUAL is confirmed flat:
    pending_open: Optional[Tuple[str, float]] = None   # (side, size) or None

    def short(self) -> str:
        if self.action == "NONE":
            return f"NONE ({self.reason})"
        ro = "reduce_only" if self.reduce_only else "open"
        tail = ""
        if self.pending_open:
            tail = f"  +deferred OPEN {self.pending_open[0]} {self.pending_open[1]:g}"
        return f"{self.side} {self.size:g} [{ro}] {self.action}{tail}"


def _none(coin: str, reason: str) -> ConvergenceOrder:
    return ConvergenceOrder(coin, "", 0.0, False, "NONE", reason)


def compute_convergence_order(
    coin: str,
    desired_net: float,
    actual_net: float,
    *,
    leader_known: bool = True,
    in_flight: bool = False,
    mark_px: float = 0.0,
    min_notional: float = 0.0,
    dust_qty: float = 0.0,
) -> ConvergenceOrder:
    """Return the single safe next order to move ACTUAL_NET toward DESIRED_NET.

    Hard gates (return NONE, never trade) come first:
      * in_flight        -> an order for this coin is unacknowledged; never stack (burst guard).
      * not leader_known -> leader position is unknown (stale/no data). UNKNOWN != FLAT;
                            never close on missing data.
    Then the convergence math. Invariants this guarantees:
      * a reduce_only order can never increase |position| and never flip the sign;
      * a sign flip never crosses zero in one order (two legs);
      * size is the delta, so repeated identical (desired, actual) inputs after a fill
        produce NONE (idempotent).
    """
    if in_flight:
        return _none(coin, "IN_FLIGHT_HOLD")
    if not leader_known:
        return _none(coin, "LEADER_UNKNOWN_HOLD")

    d = float(desired_net)
    a = float(actual_net)

    # --- Sign flip: opposite signs, both materially non-zero -> two legs. ---
    if (a > EPS and d < -EPS) or (a < -EPS and d > EPS):
        flat_side = "BUY" if a < 0 else "SELL"          # buy to cover a short, sell to shed a long
        open_side = "BUY" if d > 0 else "SELL"
        return ConvergenceOrder(
            coin, flat_side, abs(a), reduce_only=True,
            action="FLATTEN_THEN_OPEN", reason="SIGN_FLIP_LEG1_FLATTEN",
            pending_open=(open_side, abs(d)),
        )

    delta = d - a
    # --- Converged / dust: nothing material to do. ---
    if abs(delta) <= max(dust_qty, EPS):
        return _none(coin, "CONVERGED" if abs(delta) <= EPS else "BELOW_DUST_HOLD")

    side = "BUY" if delta > 0 else "SELL"
    reducing = abs(d) < abs(a) - EPS          # moving toward flat on the same side (incl. d == 0)

    if reducing:
        action = "FLATTEN" if abs(d) <= EPS else "REDUCE"
        # Reduces toward flat are always permitted (we must be able to shed exposure),
        # even below the open min-notional.
        return ConvergenceOrder(coin, side, abs(delta), reduce_only=True, action=action,
                                reason=action)

    # Opening or adding (reduce_only=False). Gate sub-minimal opens so we never chase dust.
    if mark_px > 0 and min_notional > 0 and abs(delta) * mark_px < min_notional - EPS:
        return _none(coin, "BELOW_MIN_NOTIONAL_HOLD")
    action = "OPEN" if abs(a) <= EPS else "ADD"
    return ConvergenceOrder(coin, side, abs(delta), reduce_only=False, action=action, reason=action)


# ----------------------------------------------------------------------------------------------
# Self-test: disaster cases + real incident + safety invariants. No network, no orders.
# ----------------------------------------------------------------------------------------------
_fails = 0
_passes = 0


def _check(name: str, cond: bool, detail: str = "") -> None:
    global _fails, _passes
    status = "PASS" if cond else "FAIL"
    if cond:
        _passes += 1
    else:
        _fails += 1
    print(f"  {status}: {name}" + (f"  ::  {detail}" if detail else ""))


def _expect(name: str, order: ConvergenceOrder, side: str, size: float,
            reduce_only: bool, pending: Optional[Tuple[str, float]] = None) -> None:
    ok = (order.side == side
          and abs(order.size - size) < 1e-6
          and order.reduce_only is reduce_only
          and ((pending is None and order.pending_open is None)
               or (pending is not None and order.pending_open is not None
                   and order.pending_open[0] == pending[0]
                   and abs(order.pending_open[1] - pending[1]) < 1e-6)))
    _check(name, ok, f"got: {order.short()}")


def run_self_test() -> None:
    print("=== Disaster cases (your spec) ===")

    # 1) Massive accidental open: desired HYPE 0.5, actual 13.8 -> SELL reduce-only 13.3, NOT open more.
    o = compute_convergence_order("HYPE", desired_net=0.5, actual_net=13.8)
    _expect("1) massive over-long -> reduce-only sell 13.3 (not open)", o, "SELL", 13.3, True)

    # 2) Missed close: desired SOL 0, actual 0.28 -> reduce-only SELL 0.28.
    o = compute_convergence_order("SOL", desired_net=0.0, actual_net=0.28)
    _expect("2) missed close -> reduce-only sell 0.28", o, "SELL", 0.28, True)

    # 3) Opposing wallet sleeves: A wants BTC +0.001, B wants BTC -0.0007 => desired +0.0003;
    #    actual +0.001 -> reduce-only SELL 0.0007.
    desired_btc = 0.001 + (-0.0007)
    o = compute_convergence_order("BTC", desired_net=desired_btc, actual_net=0.001)
    _expect("3) opposing sleeves net -> reduce-only sell 0.0007", o, "SELL", 0.0007, True)

    # 4) Sign flip: desired AAVE +0.2, actual -0.6 -> leg1 BUY reduce-only 0.6 to flat;
    #    deferred OPEN BUY 0.2. Then after flat confirmed, leg2 = BUY open 0.2.
    o = compute_convergence_order("AAVE", desired_net=0.2, actual_net=-0.6)
    _expect("4) sign flip leg1 -> reduce-only buy 0.6 to flat (+deferred open 0.2)",
            o, "BUY", 0.6, True, pending=("BUY", 0.2))
    o2 = compute_convergence_order("AAVE", desired_net=0.2, actual_net=0.0)  # after flat confirmed
    _expect("4) sign flip leg2 (after flat) -> open buy 0.2", o2, "BUY", 0.2, False)

    # 5) Duplicate close burst: desired already == exchange flat after first close -> zero further orders.
    a = 0.28
    first = compute_convergence_order("ENA", desired_net=0.0, actual_net=a)
    _expect("5) burst: first close -> reduce-only sell 0.28", first, "SELL", 0.28, True)
    a = a - first.size  # simulate confirmed fill -> flat
    again = compute_convergence_order("ENA", desired_net=0.0, actual_net=a)
    _check("5) burst: after fill, second/third events -> NONE (idempotent)",
           again.action == "NONE", again.short())
    inflight = compute_convergence_order("ENA", desired_net=0.0, actual_net=0.28, in_flight=True)
    _check("5) burst: while first close in-flight -> HOLD (no stacked full-size order)",
           inflight.action == "NONE" and inflight.reason == "IN_FLIGHT_HOLD", inflight.short())

    print("\n=== Real incident replay: NEAR short fully exited by leader ===")
    # Pre-patch this flipped -2598 short into +6963 long. Convergence must close to flat and STOP.
    near_a = -2598.0
    leg = compute_convergence_order("NEAR", desired_net=0.0, actual_net=near_a)
    _expect("NEAR: close short -> reduce-only BUY 2598 (cannot flip)", leg, "BUY", 2598.0, True)
    near_a = near_a + leg.size  # confirmed fill -> 0
    orders_after = [compute_convergence_order("NEAR", 0.0, near_a) for _ in range(3)]
    _check("NEAR: after flat, 3 more leader close events -> 0 orders (no +6963 blowup)",
           all(x.action == "NONE" for x in orders_after),
           ", ".join(x.short() for x in orders_after))

    print("\n=== Guard cases ===")
    o = compute_convergence_order("SOL", desired_net=0.0, actual_net=0.28, leader_known=False)
    _check("leader UNKNOWN != flat -> HOLD (never close on missing data)",
           o.action == "NONE" and o.reason == "LEADER_UNKNOWN_HOLD", o.short())
    o = compute_convergence_order("WIF", desired_net=5.0, actual_net=0.0, mark_px=0.001, min_notional=10.0)
    _check("sub-min-notional OPEN -> HOLD (don't chase dust opens)",
           o.action == "NONE" and o.reason == "BELOW_MIN_NOTIONAL_HOLD", o.short())
    o = compute_convergence_order("WIF", desired_net=0.0, actual_net=0.005, mark_px=0.001, min_notional=10.0)
    _check("but a tiny CLOSE below min-notional is still allowed (must be able to flatten)",
           o.action == "FLATTEN" and o.reduce_only is True, o.short())

    print("\n=== Safety invariant sweep (the proof a reduce-only order can never flip/increase) ===")
    bad = []
    steps = [round(x * 0.1 - 2.0, 4) for x in range(41)]   # -2.0 .. +2.0
    checked = 0
    for a in steps:
        for d in steps:
            o = compute_convergence_order("X", desired_net=d, actual_net=a)
            checked += 1
            if o.action == "NONE":
                continue
            signed = o.size if o.side == "BUY" else -o.size
            new_a = a + signed
            if o.reduce_only:
                # reduce-only: magnitude must not grow, and sign must not flip (may reach 0).
                if abs(new_a) > abs(a) + 1e-6:
                    bad.append((a, d, o.short(), f"increased |pos| {a}->{new_a}"))
                if a > EPS and new_a < -1e-6:
                    bad.append((a, d, o.short(), f"flipped long->short {a}->{new_a}"))
                if a < -EPS and new_a > 1e-6:
                    bad.append((a, d, o.short(), f"flipped short->long {a}->{new_a}"))
            else:
                # open/add: must move toward desired, never overshoot past d into the opposite side.
                if (d > EPS and new_a > d + 1e-6) or (d < -EPS and new_a < d - 1e-6):
                    bad.append((a, d, o.short(), f"overshoot past desired {new_a} vs {d}"))
    _check(f"reduce-only never increases |pos| and never flips sign (swept {checked} (actual,desired) pairs)",
           not bad, (f"{len(bad)} violations e.g. {bad[0]}" if bad else "0 violations"))

    print("\n=== Result ===")
    print(f"  checks: {_passes} passed, {_fails} failed")
    if _fails == 0:
        print("RESULT::CONVERGENCE_DISASTER_CASES_PASS")
        print("RESULT::CONVERGENCE_REDUCE_ONLY_NEVER_FLIPS_INVARIANT_PASS")
        print("RESULT::CONVERGENCE_IDEMPOTENT_NO_DUPLICATE_ORDERS_PASS")
        print("RESULT::CONVERGENCE_SHADOW_SELFTEST_PASS")
        print("RESULT::NO_ORDER_MUTATION (pure planner; no exchange client, no Core import)")
    else:
        print("RESULT::CONVERGENCE_SHADOW_SELFTEST_FAIL")


if __name__ == "__main__":
    run_self_test()
    sys.exit(1 if _fails else 0)
