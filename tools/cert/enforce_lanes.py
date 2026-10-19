"""Enforce lane discipline: fill every lane to its measured cap, best lanes first.

MAXIMUM CONCURRENCY IS THE JOB. That means every live lane at its cap — not 16 workers piled on one lane while
three sit idle. A lane that has proven completions gets filled first; a lane at its cap gets nothing.

NEVER touches a running card. Moving a running card clears worker_pid and kills the worker mid-job. Only `ready`
cards are assigned, and only into lanes that actually have headroom.

Usage:
    python tools/cert/enforce_lanes.py            # report + assign ready cards
    python tools/cert/enforce_lanes.py --dry-run  # report only
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter

DB = r"C:/Users/wigmore/.hermes/kanban.db"

# Measured caps. Change these numbers, never the mechanism.
CAP = {
    "custom-deepseek-free": 3,
    "openai-codex": 4,
    "gemini": 4,
    "openrouter": 2,
    "nous": 3,
}
MODEL = {
    "custom-deepseek-free": "deepseek-v4-flash-thinking-nosearch",
    "openai-codex": "gpt-6-luna",
    "gemini": "gemini-2.5-flash",
    "openrouter": "nvidia/nemotron-3-ultra-550b-a55b:free",
    "nous": "poolside/laguna-s-2.1:free",
}
TAG = {
    "custom-deepseek-free": "deepseek:v4-flash",
    "openai-codex": "luna",
    "gemini": "gemini:2.5-flash",
    "openrouter": "openrouter",
    "nous": "nous",
}
# Proven success order (routing scoreboard: PASS counts). Fill the proven lanes first.
PRIORITY_ORDER = ["custom-deepseek-free", "openai-codex", "gemini", "openrouter", "nous"]
# Lanes known to be rate-limited right now. Pass as args: --down gemini --down openrouter
DEFAULT_DOWN: set[str] = set()


def main() -> int:
    dry = "--dry-run" in sys.argv
    down = set(DEFAULT_DOWN)
    for i, a in enumerate(sys.argv):
        if a == "--down" and i + 1 < len(sys.argv):
            down.add(sys.argv[i + 1])
    live = [l for l in PRIORITY_ORDER if l not in down]

    c = sqlite3.connect(DB)
    running = Counter(x[0] or "UNSET" for x in c.execute(
        "select provider_override from tasks where status='running'"))

    # 1) workers sitting on lanes beyond their cap: report, never touch
    over = {l: running.get(l, 0) - CAP[l] for l in CAP if running.get(l, 0) > CAP[l]}

    # 2) headroom per live lane
    head = {l: max(0, CAP[l] - running.get(l, 0)) for l in live}
    total_head = sum(head.values())

    print("lane                     cap  running  headroom")
    for l in PRIORITY_ORDER:
        mark = " (DOWN)" if l in down else ""
        print(f"  {l:<22} {CAP[l]:>3}  {running.get(l,0):>7}  {head.get(l,0):>8}{mark}")
    print(f"\n  usable headroom: {total_head}")
    if over:
        print(f"  OVER CAP (leaving alone - never kill a running worker): {over}")

    # 3) assign ready cards into lanes with headroom, best lane first
    ready = [r[0] for r in c.execute("select id from tasks where status='ready' order by priority desc, id")]
    if not ready:
        print("\n  no ready cards to place")
        return 0

    # weight by headroom, so a lane with 4 slots gets ~2x the cards of a lane with 2
    seq: list[str] = []
    for l in live:
        seq += [l] * head.get(l, 0)
    if not seq:
        print("\n  ALL LIVE LANES AT CAP - nothing to assign. Cards wait for a slot.")
        return 0

    changed = 0
    for i, tid in enumerate(ready):
        tgt = seq[i % len(seq)]
        cur = c.execute("select provider_override, title from tasks where id=?", (tid,)).fetchone()
        if cur[0] != tgt:
            title = cur[1] or ""
            rest = title.split("] ", 1)[-1] if title.startswith("[") else title
            if not dry:
                c.execute("update tasks set provider_override=?, model_override=?, title=? where id=?",
                          (tgt, MODEL[tgt], f"[{TAG[tgt]}] {rest}", tid))
            changed += 1
    if not dry:
        c.commit()

    print(f"  ready cards: {len(ready)}  re-assigned: {changed}{'  (dry run)' if dry else ''}")
    after = Counter(x[0] or "UNSET" for x in c.execute(
        "select provider_override from tasks where status='ready'"))
    print(f"  ready by lane now: {dict(after)}")
    print("  running UNCHANGED:", dict(running))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
