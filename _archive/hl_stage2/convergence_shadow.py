#!/usr/bin/env python3
"""
convergence_shadow.py  —  THE LIVE ENTRY-SIZING AUTHORITY for the HL copy engine.

This module GATES live copy entries. HL_Live_Copy_Service.convergence_notional_for_fill() calls
compute_convergence_order() for every active fill, and the size/reason it returns is what the service
sizes, sends and records in the ledger -- including the OD-09 below-minimum decision (round the copy up
to the minimum, or refuse it by name).

It stays exchange-free on purpose: no exchange client, no network, no Core import, no ledger write, so
every decision can be replayed and diffed offline. That is what "shadow" means here -- how it is PROVED,
not that it is inert. It cannot place an order itself; it decides the order the service may place.

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

import math
import os
import sys
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Any, Optional, Tuple

EPS = 1e-9

# OD-09: ONE vocabulary for the below-minimum decision, and ONE classification of its outcome. The
# planner decides and classifies here; the service records the reason verbatim and counts the outcome in
# ONE counter. No second envelope, no second refusal name, no second counter anywhere.
MIN_NOTIONAL_REFUSAL = "BELOW_MIN_NOTIONAL_REFUSED"
NON_FINITE_REFUSAL = "NON_FINITE_INPUT_REFUSED"
MIN_NOTIONAL_EVENT_UPLIFTED = "uplifted"
MIN_NOTIONAL_EVENT_REFUSED = "refused"

# OD-09 default round-up envelope (same bounds the live sender applies for its own lot rounding).
# These are DEFAULTS only: the live values are read from the environment on every call (uplift_envelope),
# so the planner can never freeze an envelope at import and disagree with the sender about a notional.
UPLIFT_MAX_RATIO = 1.25
UPLIFT_MAX_ABS_USD = 3.0
UPLIFT_RATIO_ENV = "HL_LIVE_MAX_ENTRY_UPLIFT_RATIO"
UPLIFT_ABS_ENV = "HL_LIVE_MAX_ENTRY_UPLIFT_ABS_USD"


def _finite(*values: Any) -> bool:
    try:
        return all(math.isfinite(float(v)) for v in values)
    except (TypeError, ValueError):
        return False


def _env_float(name: str, default: float, floor: float) -> float:
    """Read a float knob at CALL time; anything missing, unparsable, non-finite or below `floor`
    falls back to `default` (NaN/inf in the env is not an envelope)."""
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) and value >= floor else default


def uplift_envelope() -> Tuple[float, float]:
    """OD-09: (max_ratio, max_abs_usd) for the round-up, read live from the SAME env knobs the sender
    reads, on every call -- a planner that froze these at import could refuse a copy the sender uplifts."""
    return (_env_float(UPLIFT_RATIO_ENV, UPLIFT_MAX_RATIO, 1.0),
            _env_float(UPLIFT_ABS_ENV, UPLIFT_MAX_ABS_USD, 0.0))


def ceil_to_sz_decimals(size: float, sz_decimals: int) -> float:
    """CEILING-quantise a size to the symbol's lot increment (szDecimals), so the sender's own floor
    cannot drop it back below the minimum. Float dust is absorbed by ceil, never by luck."""
    step = Decimal("1").scaleb(-max(0, int(sz_decimals)))
    return float(Decimal(repr(float(size))).quantize(step, rounding=ROUND_CEILING))


def min_notional_uplift_size(delta_qty: float, mark_px: float, min_notional: float,
                             *, max_ratio: Optional[float] = None,
                             max_abs_usd: Optional[float] = None,
                             sz_decimals: Optional[int] = None) -> Optional[float]:
    """OD-09: the WIRE-VALID size that clears `min_notional`, or None when that is not a rounding.

    The $10 threshold is NOT negotiable: a copy below the exchange minimum is still owed to the leader's
    event, so it is rounded UP to the minimum when the increase stays inside the uplift envelope
    (<= max_ratio of the copy, or <= max_abs_usd above it). The size is then ceiling-quantised to the
    symbol's szDecimals and re-asserted against the minimum -- the sender floors to szDecimals, so an
    unquantised uplift would land BELOW the minimum on the wire. Outside that envelope, or unreachable
    after quantisation, the caller must refuse by name -- never drop the copy silently.
    """
    if not _finite(delta_qty, mark_px, min_notional) or delta_qty == 0 or mark_px <= 0 or min_notional <= 0:
        return None
    ratio = max_ratio if max_ratio is not None else uplift_envelope()[0]
    abs_usd = max_abs_usd if max_abs_usd is not None else uplift_envelope()[1]
    if not (_finite(ratio, abs_usd) and ratio >= 1.0 and abs_usd >= 0.0):
        return None
    intended = abs(delta_qty) * mark_px
    if intended >= min_notional - EPS:
        return abs(delta_qty)  # nothing to round up
    target = min_notional / mark_px
    if sz_decimals is not None:
        target = ceil_to_sz_decimals(target, sz_decimals)
    if not _finite(target) or target <= 0 or target * mark_px < min_notional - EPS:
        return None                       # unreachable at this lot increment: refuse by name
    max_target = max(intended * ratio, intended + abs_usd)
    if target * mark_px > max_target + EPS:
        return None                       # rounding up is no longer a rounding
    return target


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
    # OD-09: the planner classifies its own min-notional outcome ("" | "uplifted" | "refused"); the
    # service records THAT in its one counter, so nothing downstream re-derives the rule.
    min_notional_event: str = ""

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
    sz_decimals: Optional[int] = None,
) -> ConvergenceOrder:
    """Return the single safe next order to move ACTUAL_NET toward DESIRED_NET.

    Hard gates (return NONE, never trade) come first:
      * in_flight        -> an order for this coin is unacknowledged; never stack (burst guard).
      * not leader_known -> leader position is unknown (stale/no data). UNKNOWN != FLAT;
                            never close on missing data.
      * non-finite input -> NaN/inf in any quantity is a broken measurement, not a market: refuse.
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

    try:
        d = float(desired_net)
        a = float(actual_net)
    except (TypeError, ValueError):
        return _none(coin, NON_FINITE_REFUSAL)

    # OD-09: NaN/inf poisons every comparison below (NaN compares False, so it would slip through the
    # minimum and be sent as an order). Reject it BEFORE any arithmetic or division.
    if not _finite(d, a, mark_px, min_notional, dust_qty):
        return _none(coin, NON_FINITE_REFUSAL)

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

    # Opening or adding (reduce_only=False). OD-09: a copy that rounds below the minimum is still owed to
    # the leader's event, so round the SIZE UP to the minimum -- ceiling-quantised to szDecimals so the
    # sender cannot floor it back under the minimum -- and send it; refuse BY NAME (and classify it) when
    # rounding up would not be a rounding any more. Either way it never becomes a silent no-copy.
    if mark_px > 0 and min_notional > 0 and abs(delta) * mark_px < min_notional - EPS:
        uplift = min_notional_uplift_size(abs(delta), mark_px, min_notional, sz_decimals=sz_decimals)
        action = "OPEN" if abs(a) <= EPS else "ADD"
        if uplift is None:
            return ConvergenceOrder(coin, "", 0.0, False, "NONE", MIN_NOTIONAL_REFUSAL,
                                    min_notional_event=MIN_NOTIONAL_EVENT_REFUSED)
        return ConvergenceOrder(coin, side, uplift, reduce_only=False, action=action,
                                reason=f"{action}_ROUNDED_UP_TO_MIN_NOTIONAL",
                                min_notional_event=MIN_NOTIONAL_EVENT_UPLIFTED)
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
    # OD-09: a copy too small for the minimum to be a rounding is refused BY NAME (and classified), and a copy
    # just under the minimum is rounded UP to the minimum and still sent.
    o = compute_convergence_order("WIF", desired_net=5.0, actual_net=0.0, mark_px=0.001, min_notional=10.0)
    _check("unroundable sub-min-notional OPEN -> NAMED refusal + classification (never a silent drop)",
           o.action == "NONE" and o.reason == MIN_NOTIONAL_REFUSAL
           and o.min_notional_event == MIN_NOTIONAL_EVENT_REFUSED, o.short())
    o = compute_convergence_order("SOL", desired_net=9.6, actual_net=0.0, mark_px=1.0, min_notional=10.0)
    _check("sub-min-notional OPEN inside the uplift envelope -> rounded UP to the $10 minimum and sent",
           o.action == "OPEN" and o.reduce_only is False and abs(o.size - 10.0) < 1e-9
           and o.min_notional_event == MIN_NOTIONAL_EVENT_UPLIFTED, o.short())
    o = compute_convergence_order("WIF", desired_net=0.0, actual_net=0.005, mark_px=0.001, min_notional=10.0)
    _check("but a tiny CLOSE below min-notional is still allowed (must be able to flatten)",
           o.action == "FLATTEN" and o.reduce_only is True, o.short())

    print("\n=== OD-09: wire-valid uplift (szDecimals ceiling) + non-finite + live envelope ===")
    # The sender floors every size to szDecimals. An uplift that is not ceiling-quantised lands BELOW the
    # minimum on the wire (XRP szD=0 @1.40 -> 7 units = $9.80; BTC szD=5 @61000 -> $9.76; DOGE @0.1234 -> $9.9954).
    for coin, px, sz_d in (("XRP", 1.40, 0), ("BTC", 61000.0, 5), ("DOGE", 0.1234, 0)):
        o = compute_convergence_order(coin, desired_net=8.0 / px, actual_net=0.0, mark_px=px,
                                      min_notional=10.0, sz_decimals=sz_d)
        if o.action == "NONE":
            ok = o.reason == MIN_NOTIONAL_REFUSAL
            detail = f"refused by name: {o.short()}"
        else:
            wire = ceil_to_sz_decimals(o.size, sz_d)
            ok = abs(wire - o.size) < 1e-12 and wire * px >= 10.0 - 1e-9
            detail = f"{o.short()} wire={wire * px:.4f} szD={sz_d}"
        _check(f"{coin} @{px:g} szD={sz_d}: copied order is wire-valid at szDecimals (>= $10 or named refusal)",
               ok, detail)

    # NaN/inf is a broken measurement, never an order: pre-fix NaN fell through the minimum and opened 2.5.
    for label, kwargs in (("NaN delta", dict(desired_net=float("nan"), actual_net=0.0)),
                          ("inf delta", dict(desired_net=float("inf"), actual_net=0.0)),
                          ("NaN mark", dict(desired_net=2.5, actual_net=0.0, mark_px=float("nan"),
                                            min_notional=10.0)),
                          ("NaN min", dict(desired_net=2.5, actual_net=0.0, mark_px=1.0,
                                           min_notional=float("nan")))):
        o = compute_convergence_order("HYPE", **kwargs)
        _check(f"{label} -> NAMED non-finite refusal, zero size",
               o.action == "NONE" and o.size == 0.0 and o.reason == NON_FINITE_REFUSAL, o.short())

    # The envelope is read at CALL time: the same $7.50 copy flips verdict when the env changes.
    _saved = {k: os.environ.get(k) for k in (UPLIFT_RATIO_ENV, UPLIFT_ABS_ENV)}
    try:
        os.environ[UPLIFT_RATIO_ENV], os.environ[UPLIFT_ABS_ENV] = "1.1", "0.5"
        tight = compute_convergence_order("XRP", desired_net=7.5 / 1.40, actual_net=0.0,
                                          mark_px=1.40, min_notional=10.0, sz_decimals=0)
        os.environ[UPLIFT_RATIO_ENV], os.environ[UPLIFT_ABS_ENV] = "2.0", "0.5"
        wide = compute_convergence_order("XRP", desired_net=7.5 / 1.40, actual_net=0.0,
                                         mark_px=1.40, min_notional=10.0, sz_decimals=0)
    finally:
        for k, v in _saved.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
    _check("same $7.50 copy: env envelope tight -> refusal, env envelope wide -> wire-valid uplift",
           tight.reason == MIN_NOTIONAL_REFUSAL and wide.action == "OPEN"
           and wide.size * 1.40 >= 10.0 - 1e-9, f"tight={tight.short()} wide={wide.short()}")

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
