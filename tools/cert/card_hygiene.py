#!/usr/bin/env python
"""card_hygiene.py - enforce the two card properties whose absence keeps costing worker runs.

Both failure modes are card-creation defects, not worker defects, and both have killed real cards on this project:

  1. NO PROVIDER.  A card with provider_override NULL resolves to the profile default, which is the FORBIDDEN lane. It
     also silently spawns on the wrong model. Cards created BY A WORKER (a reviewer raising a REDO) never inherit a
     provider, so this recurs no matter how many times the existing cards are fixed.

  2. NO CLONE URL.  A card that says "clone into your own workspace" without the URL makes a worker with a stale local
     repo (one sits at 76dfaa26) block on "the exact required commit is absent". Two gate cards died on this one line.

Run before every dispatch. --fix repairs both; without --fix it reports and exits non-zero.

    python tools/cert/card_hygiene.py
    python tools/cert/card_hygiene.py --fix
"""
import sqlite3
import sys
from collections import Counter
from pathlib import Path

DB = Path(r"C:/Users/wigmore/.hermes/kanban.db")
CLONE_URL = "https://github.com/binancebotty-bot/hyperliquid-build3-repair"
LIVE = ("ready", "todo", "running")

# lane -> (cap, model). gemini excluded from auto-assignment: it is the operator's vision model.
LANES = {
    "openai-codex": (6, "gpt-6-luna"),
    "custom-deepseek-free": (3, "deepseek-v4-flash-thinking-nosearch"),
    "nous": (3, "meituan/longcat-2.5-preview:free"),
    "openrouter": (2, "poolside/laguna-s-2.1:free"),
}

CLONE_BLOCK = """## CLONE - do this first (anonymous clone works; no credential needed)

    rm -rf repo                       # a previous run may have left one; this is not a failure
    git -c credential.helper= clone %s repo
    cd repo && git fetch origin && git checkout -B work origin/main
    git rev-parse --short HEAD        # record this; it is your tested_commit

The repository is public. If a clone prompts for credentials the host helper is interfering - the
`-c credential.helper=` above disables it for that one command. Do NOT reuse a shared checkout on this
host (`b3_clean`, `merge_*`, `verify_*`, `hl-build3-main-*`): several are stale and others dirty.

If `repo` already exists from an earlier attempt, `rm -rf` it and clone fresh - do not block on a
non-empty directory, and do not inspect or reuse its contents.

""" % CLONE_URL


def pick_lane(conn) -> str:
    load = {}
    for lane, (cap, _m) in LANES.items():
        n = conn.execute(
            "select count(*) from tasks where provider_override=? and status in ('ready','running')",
            (lane,)).fetchone()[0]
        load[lane] = (n, cap)
    return min(load, key=lambda L: (load[L][0] >= (load[L][1] or 99), load[L][0]))


def main() -> int:
    fix = "--fix" in sys.argv
    conn = sqlite3.connect(DB)
    rows = list(conn.execute(
        "select id, status, coalesce(provider_override,''), coalesce(body,'') "
        "from tasks where status in (%s)" % ",".join("?" * len(LIVE)), LIVE))

    no_provider = [(i, s) for i, s, p, _b in rows if not p.strip()]
    no_clone = [(i, s) for i, s, _p, b in rows if CLONE_URL not in b]

    print("CARD_HYGIENE  %d live card(s)" % len(rows))
    print("  missing provider : %d %s" % (len(no_provider), [i for i, _ in no_provider][:8]))
    print("  missing clone URL: %d %s" % (len(no_clone), [i for i, _ in no_clone][:8]))

    if not no_provider and not no_clone:
        print("  clean")
        return 0

    if not fix:
        print("\n  run with --fix to repair")
        return 1

    for tid, _s in no_provider:
        lane = pick_lane(conn)
        conn.execute("update tasks set provider_override=?, model_override=? where id=?",
                     (lane, LANES[lane][1], tid))
    for tid, _s in no_clone:
        body = conn.execute("select coalesce(body,'') from tasks where id=?", (tid,)).fetchone()[0]
        conn.execute("update tasks set body=? where id=?", (CLONE_BLOCK + body, tid))
    conn.commit()

    after = list(conn.execute(
        "select coalesce(provider_override,''), coalesce(body,'') from tasks where status in (%s)"
        % ",".join("?" * len(LIVE)), LIVE))
    remaining = sum(1 for p, b in after if not p.strip() or CLONE_URL not in b)
    print("\n  fixed %d provider, %d clone block(s); remaining defects: %d"
          % (len(no_provider), len(no_clone), remaining))
    print("  lanes now: %s" % dict(Counter(p for p, _ in after)))
    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
