"""Provider guard: fail loudly on a forbidden lane, an over-ceiling lane, OR an under-used permitted lane.

Three violation classes, because "not misallocating" is not the same as "using everything permitted":

  1. FORBIDDEN   - provider_override is NULL (resolves to the profile default the operator forbids) or not whitelisted
  2. OVER        - a lane above its measured ceiling
  3. UNDER-USED  - a permitted lane idle while ready cards queue on other lanes

Class 3 is what kept biting: the deepseek proxy sat at 0/3 while 19 cards queued on luna, for no reason at all. Nothing
crashed, so nothing flagged it. Now it fails the check.

    python tools/cert/provider_guard.py            # report, exit 1 on any violation
    python tools/cert/provider_guard.py --fix      # re-tag NULL/forbidden/under-used ready cards

Permitted lanes (operator, repeated):
    openai-codex (luna)   6
    custom-deepseek-free  3      (shared with the coordinator's own inference path)
    nous                  no cap
    openrouter            no cap (free tier, 1000 requests/DAY)
    gemini                2      allowed but sparing - the operator's vision model
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

DB = Path(r"C:/Users/wigmore/.hermes/kanban.db")
ALLOWED = {
    "openai-codex": (6, "gpt-6-luna"),
    "custom-deepseek-free": (3, "deepseek-v4-flash-thinking-nosearch"),
    "nous": (None, "meituan/longcat-2.5-preview:free"),
    "openrouter": (None, "poolside/laguna-s-2.1:free"),
    "gemini": (2, "gemini-2.5-flash"),
}
UNDERUSE_QUEUE_THRESHOLD = 3


def main() -> int:
    do_fix = "--fix" in sys.argv
    conn = sqlite3.connect(DB)
    run = Counter(p for (p,) in conn.execute("select provider_override from tasks where status='running'"))
    ready = Counter(p for (p,) in conn.execute("select provider_override from tasks where status='ready'"))
    ready_rows = list(conn.execute("select id, provider_override from tasks where status='ready'"))

    problems = []

    for lane, n in list(run.items()) + list(ready.items()):
        if lane is None:
            problems.append(("FORBIDDEN", "NULL provider_override -> resolves to the forbidden profile default", n))
        elif lane not in ALLOWED:
            problems.append(("FORBIDDEN", "provider not on the permitted list: %s" % lane, n))

    for lane, (cap, _) in ALLOWED.items():
        if cap is not None and run.get(lane, 0) > cap:
            problems.append(("OVER", "%s over ceiling: %d running, cap %d" % (lane, run[lane], cap), run[lane]))

    elsewhere = sum(v for k, v in ready.items() if k in ALLOWED)
    total_running = sum(run.values())
    # Board cap dominates per-lane headroom: with max_in_progress=7 and 6 running there is ONE slot, so a lane showing
    # five "free" slots is not starved. Read the cap rather than assuming lane capacity is usable.
    try:
        import re as _re
        _cfg = Path(r"C:/Users/wigmore/.hermes/config.yaml").read_text(encoding="utf-8", errors="ignore")
        _m = _re.search(r"\n  max_in_progress:\s*(\d+)", _cfg)
        board_cap = int(_m.group(1)) if _m else 18
    except Exception:
        board_cap = 18
    board_free = board_cap - total_running
    for lane, (cap, _) in ALLOWED.items():
        if lane == "gemini":
            continue
        if cap is None:
            if run.get(lane, 0) == 0 and ready.get(lane, 0) == 0 and elsewhere >= UNDERUSE_QUEUE_THRESHOLD:
                problems.append(("UNDER-USED", "%s uncapped but nothing running or queued while %d cards queue elsewhere"
                                 % (lane, elsewhere), 0))
            continue
        free = cap - run.get(lane, 0)
        # A lane with free slots AND a real backlog is starved only if the BOARD still has room to place a worker.
        if free > 0 and ready.get(lane, 0) >= 3 and board_free >= 2:
            problems.append(("STARVED", "%s has %d free slot(s) and %d card(s) queued on it but only %d running "
                             "(board has %d free of %d)" % (lane, free, ready.get(lane, 0), run.get(lane, 0),
                                                            board_free, board_cap), free))
        elif free > 0 and ready.get(lane, 0) == 0 and elsewhere >= UNDERUSE_QUEUE_THRESHOLD and board_free >= 2:
            problems.append(("UNDER-USED", "%s has %d free slot(s), no card assigned, %d queued elsewhere"
                             % (lane, free, elsewhere), free))

    print("RUNNING BY LANE")
    for lane, (cap, _) in ALLOWED.items():
        n = run.get(lane, 0)
        mark = ""
        if cap is not None and n > cap:
            mark = "  <-- OVER"
        elif lane != "gemini" and cap is not None and n < cap and ready.get(lane, 0) == 0 \
                and elsewhere >= UNDERUSE_QUEUE_THRESHOLD:
            mark = "  <-- IDLE"
        print("  %-22s %d%s%s" % (lane, n, " / %d" % cap if cap else "", mark))
    if run.get(None):
        print("  %-22s %d  <-- FORBIDDEN" % ("PROFILE-DEFAULT", run[None]))
    print("  ready queue: %s" % dict(ready))
    print("")

    if not problems:
        print("PROVIDER GUARD  clean - permitted lanes used, within ceilings, no forbidden provider")
        return 0

    print("PROVIDER GUARD  %d violation(s):" % len(problems))
    for kind, why, n in problems:
        print("  [%-10s] %s" % (kind, why))

    if do_fix:
        changed = 0
        # Cover every non-terminal card, not just ready: a NULL provider on a gated (todo) card becomes a
        # forbidden lane the moment its parent finishes, which is how seven workers landed on the profile
        # default before. Assign by least-loaded permitted lane so the fix also balances.
        live = list(conn.execute(
            "select id from tasks where status in ('ready','todo') "
            "and (provider_override is null or provider_override='' or provider_override not in (%s))"
            % ",".join("?" * len(ALLOWED)), tuple(ALLOWED)))
        for (tid,) in live:
            load = {}
            for lane, (cap, _model) in ALLOWED.items():
                if lane == "gemini":          # operator's vision model - never auto-assign
                    continue
                n = conn.execute("select count(*) from tasks where provider_override=? and status in ('ready','running')",
                                 (lane,)).fetchone()[0]
                load[lane] = (n, cap)
            lane = min(load, key=lambda L: (load[L][0] >= (load[L][1] or 99), load[L][0]))
            conn.execute("update tasks set provider_override=?, model_override=? where id=?",
                         (lane, ALLOWED[lane][1], tid))
            changed += 1
        conn.commit()
        print("\n  re-tagged %d forbidden/NULL ready card(s). Re-run to confirm." % changed)
        return 0

    print("\n  --fix re-tags forbidden/NULL ready cards. Lane balancing is a dispatch-order decision.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
