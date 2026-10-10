#!/usr/bin/env python3
"""E2 tests for the pure catch-up net planner (catchup_plan.plan_catchup). Not wired into the engine.

Covers: open+close in an outage (skip both), open-add-add (one net entry), open then partial reduce (net),
flip long to short (close then entry), reduce-only close of an owned sleeve, unknown startPosition (per-fill
fallback), and the invariant that a late entry never becomes a position the leader no longer holds.
Run: HL_LIVE_ENV_FILE=/nonexistent python -u test_catchup_plan.py   (RESULT:: markers, exit 0/1)
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from catchup_plan import plan_catchup  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def f(i, side, size, price, ts, start):
    return {"id": i, "side": side, "size": size, "price": price, "ts": ts, "startPosition": start}


def acts(plan):
    return [s["action"] for s in plan["steps"]]


def main():
    # 1) open + close inside an outage: the leader is flat again -> skip BOTH (engine never held it)
    p = plan_catchup([f("a", "BUY", 1.0, 100.0, 1000, 0.0), f("b", "SELL", 1.0, 101.0, 2000, 1.0)], 0.0)
    check("OUTAGE_OPEN_CLOSE_SKIPS_BOTH", acts(p) == ["SKIP", "SKIP"] and abs(p["net"]) < 1e-9,
          "steps=%s net=%s" % (acts(p), p["net"]))
    check("OUTAGE_OPEN_CLOSE_NO_ORDER", not any(s["action"] in ("ENTRY", "CLOSE") for s in p["steps"]))

    # 2) open-add-add -> ONE net entry, size = sum, oldest entry price carried
    p = plan_catchup([f("a", "BUY", 1.0, 100.0, 1000, 0.0), f("b", "BUY", 2.0, 102.0, 2000, 1.0),
                      f("c", "BUY", 1.0, 101.0, 3000, 3.0)], 0.0)
    e = [s for s in p["steps"] if s["action"] == "ENTRY"]
    check("OPEN_ADD_ADD_ONE_NET_ENTRY", len(e) == 1 and e[0]["side"] == "BUY" and abs(e[0]["size"] - 4.0) < 1e-9,
          "steps=%s" % acts(p))
    check("OPEN_ADD_ADD_CARRIES_OLDEST_AND_NEWEST_PRICE", abs(e[0]["oldest_entry_price"] - 100.0) < 1e-9
          and abs(e[0]["newest_price"] - 101.0) < 1e-9, str(e[0]))

    # 3) open then partial reduce -> net entry of the remainder
    p = plan_catchup([f("a", "BUY", 2.0, 100.0, 1000, 0.0), f("b", "SELL", 1.0, 101.0, 2000, 2.0)], 0.0)
    e = [s for s in p["steps"] if s["action"] == "ENTRY"]
    check("OPEN_THEN_PARTIAL_REDUCE_NETS", len(e) == 1 and e[0]["side"] == "BUY" and abs(e[0]["size"] - 1.0) < 1e-9,
          "steps=%s" % acts(p))

    # 4) flip long -> short: CLOSE the sleeve FIRST, then the entry remainder
    p = plan_catchup([f("a", "SELL", 5.0, 200.0, 1000, 3.0)], 3.0)
    check("FLIP_CLOSES_THEN_ENTERS", acts(p) == ["CLOSE", "ENTRY"], "steps=%s" % acts(p))
    check("FLIP_CLOSE_FULL_SLEEVE_THEN_REMAINDER",
          abs(p["steps"][0]["size"] - 3.0) < 1e-9 and p["steps"][0]["side"] == "SELL"
          and abs(p["steps"][1]["size"] - 2.0) < 1e-9 and p["steps"][1]["side"] == "SELL", str(p["steps"]))

    # 5) reduce-only full close of an owned sleeve: CLOSE only, no entry
    p = plan_catchup([f("a", "SELL", 2.0, 300.0, 1000, 2.0)], 2.0)
    check("OWNED_SLEEVE_FULL_CLOSE_ONLY", acts(p) == ["CLOSE"] and abs(p["steps"][0]["size"] - 2.0) < 1e-9,
          "steps=%s" % acts(p))
    check("OWNED_SLEEVE_CLOSE_IS_REDUCE_SIDE", p["steps"][0]["side"] == "SELL")

    # 6) unknown startPosition -> per-fill fallback, no netting, nothing skipped
    p = plan_catchup([f("a", "BUY", 1.0, 100.0, 1000, None), f("b", "SELL", 1.0, 101.0, 2000, None)], 0.0)
    check("UNKNOWN_START_FALLS_BACK_PER_FILL", acts(p) == ["FILL", "FILL"] and p["netting"] is False,
          "steps=%s netting=%s" % (acts(p), p["netting"]))

    # invariant: a late entry never becomes a position the leader no longer holds
    bad = []
    for held, fills in [
        (0.0, [f("a", "BUY", 1.0, 10.0, 1, 0.0), f("b", "SELL", 1.0, 11.0, 2, 1.0)]),
        (0.0, [f("a", "BUY", 2.0, 10.0, 1, 0.0), f("b", "SELL", 2.0, 11.0, 2, 2.0)]),
        (1.0, [f("a", "BUY", 1.0, 10.0, 1, 1.0), f("b", "SELL", 1.0, 11.0, 2, 2.0)]),
    ]:
        pl = plan_catchup(fills, held)
        for s in pl["steps"]:
            if s["action"] == "ENTRY" and abs(pl["leader_after"]) < 1e-9:
                bad.append((held, s))
    check("NEVER_OPENS_A_POSITION_THE_LEADER_NO_LONGER_HOLDS", not bad, str(bad))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
