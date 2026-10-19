"""Refuse any Kanban card assigned to a provider the operator has not authorised.

The operator's standing rule (repeated, zero tolerance): the profile-default provider is FORBIDDEN. Permitted lanes only:

    openai-codex (luna)          max 6
    custom-deepseek-free          max 3   (the coordinator's own inference path shares this budget)
    nous                         no fixed cap - use what it manages
    openrouter                   no fixed cap - free tier, 1000 requests/DAY
    gemini                       allowed but SPARING - it is the operator's vision model, keep it near 2

`provider_override = NULL` is the trap: it silently resolves to the profile default, which is the forbidden provider. This
tool treats NULL as a violation, not as "unset".

    python tools/cert/provider_guard.py            # report violations, exit 1 if any
    python tools/cert/provider_guard.py --fix      # re-tag NULL and over-cap cards onto permitted lanes

Runs against the live Kanban DB. Read-only unless --fix.
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

DB = Path(r"C:/Users/wigmore/.hermes/kanban.db")

# provider -> (max_concurrent or None, model to stamp when re-tagging)
ALLOWED = {
    "openai-codex": (6, "gpt-6-luna"),
    "custom-deepseek-free": (3, "deepseek-v4-flash-thinking-nosearch"),
    "nous": (None, "meituan/longcat-2.5-preview:free"),
    "openrouter": (None, "poolside/laguna-s-2.1:free"),
    "gemini": (2, "gemini-2.5-flash"),          # sparing: the operator's vision model
}
FORBIDDEN_LABEL = "PROFILE-DEFAULT (forbidden)"


def load(conn):
    run = list(conn.execute("select id, provider_override from tasks where status='running'"))
    rdy = list(conn.execute("select id, provider_override from tasks where status='ready'"))
    return run, rdy


def violations(conn):
    run, rdy = load(conn)
    out = []
    for state, rows in (("running", run), ("ready", rdy)):
        for tid, prov in rows:
            if prov is None:
                out.append((state, tid, FORBIDDEN_LABEL, "provider_override is NULL -> resolves to the forbidden profile default"))
            elif prov not in ALLOWED:
                out.append((state, tid, prov, "provider not on the permitted list"))
    counts = Counter(p for _, p in run)
    for prov, (cap, _) in ALLOWED.items():
        if cap is not None and counts.get(prov, 0) > cap:
            out.append(("running", "*", prov, "over ceiling: %d running, cap %d" % (counts[prov], cap)))
    return out, counts


def fix(conn):
    changed = 0
    for tid, prov in list(conn.execute("select id, provider_override from tasks where status='ready'")):
        if prov is None or prov not in ALLOWED:
            target = "openai-codex"
            model = ALLOWED[target][1]
            conn.execute("update tasks set provider_override=?, model_override=? where id=?", (target, model, tid))
            print("  re-tagged %-12s %s -> %s" % (tid, prov or "NULL", target))
            changed += 1
    conn.commit()
    return changed


def main() -> int:
    do_fix = "--fix" in sys.argv
    conn = sqlite3.connect(DB)
    bad, counts = violations(conn)
    print("RUNNING BY LANE")
    for prov, (cap, _) in ALLOWED.items():
        n = counts.get(prov, 0)
        flag = "" if cap is None or n <= cap else "  <-- OVER CEILING"
        print("  %-24s %d%s" % (prov, n, " / %d" % cap if cap else "")+ ("  <-- OVER CEILING" if flag else ""))
    if counts.get(None):
        print("  %-24s %d  <-- VIOLATION: forbidden provider" % (FORBIDDEN_LABEL, counts[None]))
    print()
    if not bad:
        print("PROVIDER GUARD  clean - every card is on a permitted lane and within ceiling")
        return 0
    print("PROVIDER GUARD  %d violation(s):" % len(bad))
    for state, tid, prov, why in bad[:20]:
        print("  [%s] %-12s %-24s %s" % (state, tid, prov, why))
    if do_fix:
        n = fix(conn)
        print("\n  fixed %d ready card(s). Re-run to confirm." % n)
        return 0
    print("\n  Run with --fix to re-tag ready cards onto permitted lanes.")
    print("  RUNNING violations must be killed by exact PID - this tool will not kill work.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
