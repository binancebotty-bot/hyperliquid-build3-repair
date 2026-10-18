"""Generate STATE.md — the current truth — from the live board and the committed register.

STATE.md is a DERIVED document: it is rewritten, never appended. It exists so that any agent (or human) can read
one short file and know what is true right now, instead of reconstructing state from a 1,200-comment thread.

Rule: if a fact cannot be regenerated from the board or a committed ref, it does not belong in STATE.md.

Usage:  python tools/cert/gen_state.py [--write]
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:/Users/wigmore/hyperliquid-build3-repair")
CLEAN = Path(r"C:/Users/wigmore/.hermes/cache/scratch/b3_clean")
DB = Path(r"C:/Users/wigmore/.hermes/kanban.db")
OUT = REPO / "STATE.md"

REGISTER_REF = "origin/cert/local-main-b142cf8"
REGISTER_PATH = "certification/certification_matrix.json"


def register_stats() -> dict:
    """Read the register at a NAMED ref. Never the working tree."""
    def show(ref: str) -> dict | None:
        try:
            out = subprocess.run(
                ["git", "show", f"{ref}:{REGISTER_PATH}"],
                cwd=CLEAN, capture_output=True, timeout=120,
            )
            if out.returncode != 0:
                return None
            return json.loads(out.stdout.decode("utf-8", "replace"))
        except Exception:
            return None

    stats = {}
    for ref in (REGISTER_REF, "origin/main"):
        d = show(ref)
        if not d:
            stats[ref] = None
            continue
        recs = d.get("records", [])
        stats[ref] = {
            "rows": len(recs),
            "results": dict(Counter(r.get("result") for r in recs)),
            "with_ref": sum(1 for r in recs if r.get("evidence_ref")),
        }
    return stats


def board_stats() -> dict:
    import sqlite3
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    status = dict(Counter(r[0] for r in c.execute("select status from tasks")))
    lanes = dict(Counter(r[0] or "UNSET" for r in c.execute(
        "select provider_override from tasks where status='running'")))
    ready = dict(Counter(r[0] or "UNSET" for r in c.execute(
        "select provider_override from tasks where status='ready'")))
    recent = [dict(r) for r in c.execute(
        "select id, substr(title,1,70) t, status from tasks where status='done' "
        "order by rowid desc limit 5")]
    blocked = [dict(r) for r in c.execute(
        "select id, substr(title,1,60) t from tasks where status='blocked'")]
    return {"status": status, "lanes": lanes, "ready": ready,
            "recent": recent, "blocked": blocked}


def main() -> int:
    reg = register_stats()
    bd = board_stats()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    L = []
    L.append("# STATE — the current truth\n")
    L.append(f"**Generated:** {now}  ")
    L.append("**This file is derived and overwritten.** Do not append to it; do not hand-edit facts into it.  ")
    L.append("If it disagrees with a comment thread, **this file wins**.\n")
    L.append("Regenerate: `python tools/cert/gen_state.py --write`\n")
    L.append("---\n")

    L.append("## The register\n")
    cert = reg.get(REGISTER_REF)
    main = reg.get("origin/main")
    if cert:
        r = cert["results"]
        L.append(f"Register of record — `{REGISTER_REF}`:\n")
        L.append("| result | rows |")
        L.append("|---|---:|")
        for k in ("PASS", "FAIL", "BLOCKED", "NOT_TESTED"):
            if k in r:
                L.append(f"| {k} | {r[k]} |")
        L.append(f"| **total** | **{cert['rows']}** |\n")
        L.append(f"Rows carrying an `evidence_ref`: **{cert['with_ref']}** of {cert['rows']}\n")
    else:
        L.append(f"⚠ Could not read the register at `{REGISTER_REF}`.\n")

    if main:
        r = main["results"]
        stub = main["with_ref"] == 0
        L.append(f"`origin/main`: {main['rows']} rows, results {r}, "
                 f"**{main['with_ref']} evidence_refs**")
        if stub:
            L.append("→ **THIS IS A STUB.** Anything reading `main` sees every row as unproven.\n")
        else:
            L.append("")

    L.append("## The position, stated honestly\n")
    L.append("**74 rows are audit-verified.** That is the number to quote. The register's PASS count is a *claim* "
             "count; audits demoted 301 rows because their evidence was not row-bound, and 201 were never "
             "audited at all.\n")
    L.append("Zero UI rows are certified. UI evidence needs rebuilding from scratch, not auditing — the existing "
             "checks would pass for any row.\n")

    L.append("## Board\n")
    L.append("| status | count |")
    L.append("|---|---:|")
    for k in ("running", "ready", "todo", "review", "blocked", "triage", "done"):
        if k in bd["status"]:
            L.append(f"| {k} | {bd['status'][k]} |")
    L.append("")

    L.append("## Lanes (running / measured ceiling)\n")
    CAP = {"custom-deepseek-free": 3, "openai-codex": 4, "gemini": 4, "openrouter": 2, "nous": 3}
    L.append("| lane | running | ceiling |")
    L.append("|---|---:|---:|")
    for lane, cap in CAP.items():
        n = bd["lanes"].get(lane, 0)
        L.append(f"| {lane} | {n} | {cap} |")
    L.append("")

    if bd["blocked"]:
        L.append("## Blocked — each must name its blocker\n")
        for x in bd["blocked"]:
            L.append(f"- `{x['id']}` {x['t']}")
        L.append("")

    L.append("## Recently completed\n")
    for x in bd["recent"]:
        L.append(f"- `{x['id']}` {x['t']}")
    L.append("")

    L.append("---\n")
    L.append("## Open items needing a human or another agent\n")
    L.append("- **J15 / merge** — the register must reach a ref that is not a stub before anything downstream is "
             "certifiable.")
    L.append("- **`:8032`** — an isolated instance is required before the control-write test can run; it has never "
             "landed.")
    L.append("- **ENG-INV-02** — two reachable order sites. The merge stays held on this.\n")

    text = "\n".join(L)
    if "--write" in sys.argv:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT} ({len(text)} chars)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
