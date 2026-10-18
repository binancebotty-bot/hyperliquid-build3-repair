"""Derive the routing scoreboard from what actually happened.

Answers the question the card titles are supposed to make answerable: which lane delivers, which fails, and why.
Reads completed cards only - a claim about capability must come from outcomes, not from a health check.

Usage: python tools/cert/routing_scoreboard.py [--write]
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

DB = Path(r"C:/Users/wigmore/.hermes/kanban.db")
OUT = Path(r"C:/Users/wigmore/hyperliquid-build3-repair/EVIDENCE/ROUTING_SCOREBOARD.md")

# map the tag in the title to a lane name
LANE_TAG = re.compile(r"^\[([^\]]+)\]")


def classify(summary: str) -> str:
    s = (summary or "").lower()
    if s.startswith("fail") or "verdict is fail" in s or "review verdict: fail" in s or "returned fail" in s:
        return "FAIL"
    if "not_test" in s:
        return "NOT_TESTED"
    if re.search(r"\bpass(ed)?\b", s) and "not_test" not in s:
        return "PASS"
    if "blocked" in s:
        return "BLOCKED"
    return "OTHER"


def main() -> int:
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    # provider actually used, per done card
    done = {}
    for r in c.execute("select id, title, provider_override, model_override from tasks where status='done'"):
        done[r["id"]] = (r["title"] or "", r["provider_override"] or "?", r["model_override"] or "")

    outcomes = defaultdict(Counter)
    for tid, payload in c.execute("select task_id, payload from task_events where kind='completed'"):
        if tid not in done:
            continue
        try:
            s = json.loads(payload).get("summary") or ""
        except Exception:
            continue
        _, prov, _ = done[tid]
        outcomes[prov][classify(s)] += 1

    # live state per lane
    run = Counter(r[0] or "?" for r in c.execute(
        "select provider_override from tasks where status='running'"))
    ready = Counter(r[0] or "?" for r in c.execute(
        "select provider_override from tasks where status='ready'"))

    CAP = {"custom-deepseek-free": 3, "openai-codex": 4, "gemini": 4, "openrouter": 2, "nous": 3}

    L = []
    L.append("# Routing scoreboard\n")
    L.append(f"**Derived:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} — regenerate with "
             f"`python tools/cert/routing_scoreboard.py --write`\n")
    L.append("Ranked by **proven completions**, not by health. A lane that is 'up' has proven nothing.\n")
    L.append("---\n")
    L.append("## Outcomes by lane (completed cards)\n")
    L.append("| lane | PASS | FAIL | NOT_TESTED | other | total | pass rate |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    rows = []
    for lane, cnt in outcomes.items():
        tot = sum(cnt.values())
        p = cnt.get("PASS", 0)
        rows.append((lane, cnt, tot, p))
    for lane, cnt, tot, p in sorted(rows, key=lambda x: (-x[3], -x[2])):
        rate = f"{100*p/tot:.0f}%" if tot else "-"
        L.append(f"| `{lane}` | {cnt.get('PASS',0)} | {cnt.get('FAIL',0)} | "
                 f"{cnt.get('NOT_TESTED',0)} | {cnt.get('OTHER',0)+cnt.get('BLOCKED',0)} | {tot} | {rate} |")
    L.append("")
    L.append("## Live state\n")
    L.append("| lane | running | ready | ceiling |")
    L.append("|---|---:|---:|---:|")
    for lane in CAP:
        L.append(f"| `{lane}` | {run.get(lane,0)} | {ready.get(lane,0)} | {CAP[lane]} |")
    L.append("")
    L.append("## How to read this\n")
    L.append("- **PASS rate is per lane, not per model.** The provider a card ran on is the lane setting at completion; "
             "it is not a controlled experiment.\n")
    L.append("- **NOT_TESTED is not a lane failure.** It usually means the evidence did not exist, not that the worker "
             "could not do the job. Judge lanes on FAIL and on whether they finished at all.\n")
    L.append("- **A high PASS count with a low pass *rate*** means the lane took a lot of work and returned little.\n")
    L.append("- **Never rank on health checks.** 'It responded' and 'it delivered' are different claims.\n")

    text = "\n".join(L)
    if "--write" in sys.argv:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT} ({len(text)} chars)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
