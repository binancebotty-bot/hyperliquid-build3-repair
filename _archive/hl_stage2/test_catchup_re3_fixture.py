#!/usr/bin/env python3
"""J3 - RE3 outage fixture through catchup_plan vs per-fill replay (doc + test only, no Core change).

`catchup_plan.plan_catchup` is a pure prototype imported by nothing. This test replays the RE3 outage fixture
(reproduced from test_core_outage_replay.py: 300 leader fills / 20 coins / 0-120 s old / alternating Open Long
(BUY) and Close Long (SELL) / size 0.1 @ 100.0 / the first 5 coins carry an owned sleeve of 5.0) through the
planner and asserts the planner's end position EQUALS honest per-fill replay, per (wallet, coin) and in aggregate.

  Variant A - exactly as RE3 builds it (no startPosition): per-fill fallback, nothing netted, nothing skipped.
  Variant B - the same fills with a coherent startPosition on every fill: 20/20 groups net, one order per group.
  Four fixture-shaped windows force CLOSE-only and flip (CLOSE then ENTRY) and are position-preserved too.
  Mutation controls: the comparison is re-run with two deliberate mutations and MUST detect each (proves the test
  can fail), plus the R1 relative-target observation from the review, pinned as a check.

Position preservation is the property the review depends on:
    held_before + sum(emitted step deltas) == held_before + sum(raw signed fill sizes)
Step deltas: FILL/ENTRY/CLOSE contribute signed(side,size); SKIP contributes nothing.

Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_catchup_re3_fixture.py
Prints RESULT:: markers, TOTAL=/FAILED=, exit 0/1. No network, no engine, no orders, no keys.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from catchup_plan import plan_catchup  # noqa: E402

RESULTS = []
LEADER = "0x" + "a" * 40
N_FILLS, N_COINS, SEEDED_COINS, SEED_SIZE, FILL_SIZE, PX = 300, 20, 5, 5.0, 0.1, 100.0
AGE_MIN_MS, AGE_MAX_MS = 400, 120_000


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def signed(side, size):
    return abs(float(size)) if str(side).upper() == "BUY" else -abs(float(size))


def re3_fixture(now, with_start=False):
    """The RE3 outage fixture, verbatim in values (see test_core_outage_replay.py L117-124)."""
    coins = ["BN%02d" % i for i in range(N_COINS)]
    span = AGE_MAX_MS - AGE_MIN_MS
    fills = []
    for i in range(N_FILLS):
        coin = coins[i % N_COINS]
        side = "BUY" if (i // N_COINS) % 2 == 0 else "SELL"
        ts = now - AGE_MAX_MS + int(span * i / max(1, N_FILLS - 1))
        f = {"id": "E3-%03d" % i, "coin": coin, "side": side, "size": FILL_SIZE, "price": PX, "ts": ts,
             "wallet": LEADER, "dir": ("Open Long %d" % i) if side == "BUY" else ("Close Long %d" % i)}
        if with_start:
            f["startPosition"] = 0.0   # filled in below as a coherent chain
        fills.append(f)
    if with_start:
        # a coherent chain per coin: no coin ever returns to flat (the RE3 shape has no in-window round trip),
        # so the planner nets instead of skipping. Seeded coins stand at +5.0, the rest at +1.0 (leader-only).
        run = {}
        for f in fills:
            start = run.get(f["coin"], SEED_SIZE if coins.index(f["coin"]) < SEEDED_COINS else 1.0)
            f["startPosition"] = start
            run[f["coin"]] = start + signed(f["side"], f["size"])
    return fills


def raw_truth(fills, held):
    """Honest per-fill replay: held + the signed sum of every fill, per coin."""
    out = defaultdict(lambda: 0.0)
    for f in fills:
        out[f["coin"]] += signed(f["side"], f["size"])
    return {c: held.get(c, 0.0) + d for c, d in out.items()}


def planner_position(plan, held, skip_contributes=False, ignore_close=False):
    """held + the plan's emitted deltas. FILL/ENTRY/CLOSE are real orders; SKIP is not (unless mutated)."""
    delta = 0.0
    for s in plan["steps"]:
        act = s["action"]
        if act in ("FILL", "ENTRY"):
            delta += signed(s["side"], s["size"])
        elif act == "CLOSE":
            if not ignore_close:
                delta += signed(s["side"], s["size"])
        elif act == "SKIP" and skip_contributes:
            delta += signed(s["side"], s["size"])
    return held + delta


def held_by_coin():
    coins = ["BN%02d" % i for i in range(N_COINS)]
    return {c: (SEED_SIZE if i < SEEDED_COINS else 0.0) for i, c in enumerate(coins)}


def main():
    now = 1_800_000_000_000
    held = held_by_coin()
    fx_a = re3_fixture(now, with_start=False)
    fx_b = re3_fixture(now, with_start=True)

    # ---- fixture sanity ---------------------------------------------------------------------------------
    check("FIXTURE_IS_300_FILLS_OVER_20_COINS", len(fx_a) == N_FILLS and len({f["coin"] for f in fx_a}) == N_COINS)
    check("FIXTURE_FILLS_ARE_0_TO_120S_OLD",
          min(f["ts"] for f in fx_a) >= now - AGE_MAX_MS and max(f["ts"] for f in fx_a) <= now - AGE_MIN_MS)
    check("FIXTURE_HAS_BOTH_OPEN_AND_CLOSE_FILLS",
          {f["side"] for f in fx_a} == {"BUY", "SELL"} and 5 == len([c for c in held if held[c] == SEED_SIZE]))

    # ---- Variant A: no startPosition -> per-fill fallback, positions preserved ---------------------------
    groups_a = defaultdict(list)
    for f in fx_a:
        groups_a[f["coin"]].append(f)
    truth_a = raw_truth(fx_a, held)
    plans_a = {c: plan_catchup(g, held[c]) for c, g in groups_a.items()}
    check("A_NETTING_IS_FALSE", all(p["netting"] is False for p in plans_a.values()))
    check("A_EVERY_FILL_EMITTED_AS_A_FILL_STEP",
          sum(1 for p in plans_a.values() for s in p["steps"] if s["action"] == "FILL") == N_FILLS)
    check("A_NO_SKIP_AND_NO_NET_ORDER",
          not any(s["action"] in ("SKIP", "ENTRY", "CLOSE") for p in plans_a.values() for s in p["steps"]))
    a_pos = {c: planner_position(plans_a[c], held[c]) for c in groups_a}
    check("A_EVERY_GROUP_POSITION_EQUALS_PER_FILL_REPLAY",
          all(abs(a_pos[c] - truth_a[c]) <= 1e-9 for c in groups_a),
          str([(c, a_pos[c], truth_a[c]) for c in groups_a if abs(a_pos[c] - truth_a[c]) > 1e-9][:4]))
    check("A_AGGREGATE_POSITION_EQUALS_PER_FILL_REPLAY",
          abs(sum(a_pos.values()) - sum(truth_a.values())) <= 1e-9)

    # ---- Variant B: startPosition present -> nets, one order per group, positions preserved --------------
    groups_b = defaultdict(list)
    for f in fx_b:
        groups_b[f["coin"]].append(f)
    truth_b = raw_truth(fx_b, held)
    plans_b = {c: plan_catchup(g, held[c]) for c, g in groups_b.items()}
    check("B_NETTING_IS_TRUE_FOR_EVERY_GROUP", all(p["netting"] is True for p in plans_b.values()),
          str([c for c, p in plans_b.items() if p["netting"] is not True][:4]))
    check("B_ONE_NET_ORDER_PER_GROUP__20_ORDERS_FOR_300_FILLS",
          sum(1 for p in plans_b.values() for s in p["steps"] if s["action"] in ("ENTRY", "CLOSE")) == N_COINS
          and N_COINS == 20)
    check("B_NO_SKIP_STEPS", not any(s["action"] == "SKIP" for p in plans_b.values() for s in p["steps"]))
    b_pos = {c: planner_position(plans_b[c], held[c]) for c in groups_b}
    check("B_EVERY_GROUP_POSITION_EQUALS_PER_FILL_REPLAY",
          all(abs(b_pos[c] - truth_b[c]) <= 1e-9 for c in groups_b),
          str([(c, b_pos[c], truth_b[c]) for c in groups_b if abs(b_pos[c] - truth_b[c]) > 1e-9][:4]))
    check("B_AGGREGATE_POSITION_EQUALS_PER_FILL_REPLAY",
          abs(sum(b_pos.values()) - sum(truth_b.values())) <= 1e-9)
    check("B_NETTING_MATCHES_THE_RAW_WINDOW_NET",
          all(abs(p["net"] - sum(signed(f["side"], f["size"]) for f in groups_b[c])) <= 1e-9
              for c, p in plans_b.items()))

    # ---- fixture-shaped branches the RE3 shape cannot reach: CLOSE-only and flip -------------------------
    # a chain that closes the engine's +5.0 sleeve exactly: SELL 1.0 x5 from +5.0
    close_win = [{"id": "C%d" % k, "coin": "ZZ", "side": "SELL", "size": 1.0, "price": 100.0 + k, "ts": now + k,
                  "startPosition": 5.0 - k} for k in range(5)]
    pc = plan_catchup(close_win, 5.0)
    check("CLOSE_ONLY_EMITS_EXACTLY_ONE_CLOSE", [s["action"] for s in pc["steps"]] == ["CLOSE"],
          str([s["action"] for s in pc["steps"]]))
    check("CLOSE_ONLY_CLOSES_THE_ENGINE_SLEEVE", pc["steps"] and abs(pc["steps"][0]["size"] - 5.0) <= 1e-9)
    check("CLOSE_ONLY_POSITION_PRESERVED", abs(planner_position(pc, 5.0) - (5.0 - 5.0)) <= 1e-9)

    # a flip: SELL 1.0 x8 from +5.0 -> -3.0 (CLOSE 5.0, then ENTRY 3.0 SELL)
    flip_win = [{"id": "F%d" % k, "coin": "ZZ", "side": "SELL", "size": 1.0, "price": 100.0 + k, "ts": now + k,
                 "startPosition": 5.0 - k} for k in range(8)]
    pf = plan_catchup(flip_win, 5.0)
    check("FLIP_EMITS_CLOSE_THEN_ENTRY", [s["action"] for s in pf["steps"]] == ["CLOSE", "ENTRY"],
          str([s["action"] for s in pf["steps"]]))
    check("FLIP_CLOSE_IS_THE_WHOLE_SLEEVE_AND_ENTRY_IS_THE_REMAINDER",
          abs(pf["steps"][0]["size"] - 5.0) <= 1e-9 and abs(pf["steps"][1]["size"] - 3.0) <= 1e-9
          and pf["steps"][1]["side"] == "SELL")
    check("FLIP_POSITION_PRESERVED", abs(planner_position(pf, 5.0) - (-3.0)) <= 1e-9)

    # a partial reduce (no flip): the window nets -2.0 against a +5.0 sleeve -> one ENTRY, same side as the net
    red_win = [{"id": "R%d" % k, "coin": "ZZ", "side": "SELL", "size": 1.0, "price": 100.0, "ts": now + k,
                "startPosition": 5.0 - k} for k in range(2)]
    pr = plan_catchup(red_win, 5.0)
    check("PARTIAL_REDUCE_EMITS_ONE_ENTRY_STEP", [s["action"] for s in pr["steps"]] == ["ENTRY"],
          str([s["action"] for s in pr["steps"]]))
    check("PARTIAL_REDUCE_POSITION_PRESERVED", abs(planner_position(pr, 5.0) - 3.0) <= 1e-9)

    # a window the leader flattens inside: open then close -> both skipped, held 0 -> position preserved
    skip_win = [{"id": "S0", "coin": "ZZ", "side": "BUY", "size": 1.0, "price": 100.0, "ts": now,
                 "startPosition": 0.0},
                {"id": "S1", "coin": "ZZ", "side": "SELL", "size": 1.0, "price": 101.0, "ts": now + 1000,
                 "startPosition": 1.0}]
    ps = plan_catchup(skip_win, 0.0)
    check("SKIPPED_WINDOW_EMITS_NO_ORDER", not any(s["action"] in ("ENTRY", "CLOSE") for s in ps["steps"]))
    check("SKIPPED_WINDOW_POSITION_PRESERVED", abs(planner_position(ps, 0.0) - 0.0) <= 1e-9)

    # ---- mutation controls: the comparison MUST detect a wrong aggregation ------------------------------
    # NOTE (instrument): a SKIP-counting mutation is only DETECTABLE on a window whose skipped subset does not
    # net to zero. On the flat-return window above (ps) the skips sum to zero by construction, so counting them
    # is a no-op and a control there can never fail - it would be a control that proves nothing. The window
    # below returns to flat EARLY and then leaves flat again, so the skipped "open" (+2) is unbalanced.
    ps_mut_win = [{"id": "M0", "coin": "ZZ", "side": "BUY", "size": 2.0, "price": 100.0, "ts": now,
                   "startPosition": 0.0},
                  {"id": "M1", "coin": "ZZ", "side": "SELL", "size": 2.0, "price": 100.0, "ts": now + 1,
                   "startPosition": 2.0},
                  {"id": "M2", "coin": "ZZ", "side": "BUY", "size": 3.0, "price": 100.0, "ts": now + 2,
                   "startPosition": 0.0},
                  {"id": "M3", "coin": "ZZ", "side": "SELL", "size": 1.0, "price": 100.0, "ts": now + 3,
                   "startPosition": 3.0}]
    pm = plan_catchup(ps_mut_win, 0.0)
    check("SKIP_PLUS_ORDER_WINDOW_IS_POSITION_PRESERVED",
          [s["action"] for s in pm["steps"]] == ["SKIP", "ENTRY"]
          and abs(planner_position(pm, 0.0) - 2.0) <= 1e-9,
          "steps=%s pos=%s" % ([s["action"] for s in pm["steps"]], planner_position(pm, 0.0)))
    mut_close = abs(planner_position(pc, 5.0, ignore_close=True) - 0.0) <= 1e-9
    check("MUTATION_IGNORING_THE_CLOSE_STEP_IS_DETECTED", mut_close is False,
          "ignoring CLOSE still looked position-preserving: the comparison cannot fail")
    mut_skip = abs(planner_position(pm, 0.0, skip_contributes=True) - 2.0) <= 1e-9
    check("MUTATION_LETTING_SKIPS_CONTRIBUTE_IS_DETECTED", mut_skip is False,
          "counting SKIP sizes still looked position-preserving: the comparison cannot fail")
    mut_sign = abs(planner_position(pf, 5.0, ignore_close=True) - (-3.0)) <= 1e-9
    check("MUTATION_WRONG_FLIP_SIGN_IS_DETECTED", mut_sign is False)

    # ---- R1 from the review, pinned: the plan is relative and reproduces a mis-tracked sleeve ------------
    r1_win = [{"id": "r0", "coin": "ZZ", "side": "BUY", "size": 3.0, "price": 100.0, "ts": now, "startPosition": 0.0},
              {"id": "r1", "coin": "ZZ", "side": "BUY", "size": 2.0, "price": 100.0, "ts": now + 1, "startPosition": 3.0}]
    r1 = [plan_catchup(r1_win, h)["leader_after"] for h in (0.0, 5.0, -2.0)]
    check("R1_PLAN_IS_RELATIVE_AND_FOLLOWS_HELD_BEFORE", [round(x, 6) for x in r1] == [5.0, 10.0, 3.0],
          "leader_after=%s (the review claims 5/10/3 for held 0/5/-2)" % r1)

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    for n in failed:
        print("FINDING::%s failed" % n)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
