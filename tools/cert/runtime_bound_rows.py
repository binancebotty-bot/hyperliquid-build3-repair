"""Group the runtime-bound NOT_TESTED rows by area, so the controller can point Codex at the evidence each group needs.

These rows cannot be closed by a worker card: their proof requires executed/live/testnet evidence. Grouping them is the
deliverable; nothing here certifies anything.
"""
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

OUT = Path(r"C:/Users/wigmore/hyperliquid-build3-repair/EVIDENCE/RUNTIME_BOUND_ROWS.md")
PAT = re.compile(r"testnet|exchange parity|executed|runtime|live capture|two-instance", re.I)


def main():
    raw = subprocess.run(
        ["git", "-C", r"C:/Users/wigmore/hyperliquid-build3-repair",
         "show", "origin/main:certification/certification_matrix.json"],
        capture_output=True, timeout=180).stdout
    d = json.loads(raw)
    recs = d["records"]

    nt = [r for r in recs if r.get("result") == "NOT_TESTED"]

    # The three buckets OVERLAP: a row can need runtime evidence AND be blocked by an open decision. Report a strict
    # partition so the counts add up, and name the overlap explicitly rather than quoting three numbers that do not sum.
    decision = [r for r in nt if r.get("open_decisions")]
    runtime_any = [r for r in nt if PAT.search(str(r.get("execution_proof") or "") + str(r.get("independent_oracle") or ""))]
    both = [r for r in runtime_any if r.get("open_decisions")]
    runtime = [r for r in runtime_any if not r.get("open_decisions")]
    static = [r for r in nt if r not in runtime_any and not r.get("open_decisions")]

    groups = defaultdict(list)
    for r in runtime:
        groups[(r.get("area") or "UNKNOWN").upper()].append(r)

    lines = []
    lines.append("# The runtime-bound rows: %d that need only evidence, plus %d that also need a ruling" % (len(runtime), len(both)))
    lines.append("")
    lines.append("Generated from `origin/main` (832 rows, the register of record). These rows are **NOT_TESTED** and")
    lines.append("**cannot be closed by a worker card**: their `execution_proof` or `independent_oracle` requires executed,")
    lines.append("live or testnet evidence. Codex's soak and verifier outputs are the evidence source for them.")
    lines.append("")
    lines.append("The other two buckets, for contrast: rows blocked by an **open decision** (221) wait on a ruling; rows")
    lines.append("settleable by **static analysis** (414) are being worked by worker cards.")
    lines.append("")
    lines.append("## The strict partition (the counts must add up)")
    lines.append("")
    lines.append("| bucket | rows |")
    lines.append("|---|---:|")
    lines.append("| blocked by an **open decision** (some also need runtime evidence) | %d |" % len(decision))
    lines.append("| needs **runtime evidence**, no decision blocking it | %d |" % len(runtime))
    lines.append("| settlable by **static analysis** | %d |" % len(static))
    lines.append("| **total NOT_TESTED** | **%d** |" % len(nt))
    lines.append("")
    lines.append("Of the %d decision-blocked rows, **%d also need runtime evidence** — so they need the ruling *and* the "
                 "soak output before they can move. An earlier message quoted 231/221/414 as if they summed to 826; they "
                 "do not, because they overlap by these %d. This file uses a strict partition." %
                 (len(decision), len(both), len(both)))
    lines.append("")
    lines.append("`runtime_any` (patterns match, decision or not) = **%d**. That is the group Codex's soak/verifier "
                 "outputs feed; the %d with a decision outstanding also need the ruling first." % (len(runtime_any), len(both)))
    lines.append("")

    lines.append("| area | rows |")
    lines.append("|---|---:|")
    for area in sorted(groups, key=lambda a: -len(groups[a])):
        lines.append("| %s | %d |" % (area, len(groups[area])))
    lines.append("| **total** | **%d** |" % len(runtime))
    lines.append("")

    for area in sorted(groups, key=lambda a: -len(groups[a])):
        rows = groups[area]
        lines.append("## %s — %d rows" % (area, len(rows)))
        lines.append("")
        proofs = defaultdict(list)
        for r in rows:
            key = re.sub(r"\s+", " ", str(r.get("execution_proof") or ""))[:150]
            proofs[key].append(r["id"])
        lines.append("| rows | what the proof requires |")
        lines.append("|---|---|")
        for proof, ids in sorted(proofs.items(), key=lambda kv: -len(kv[1])):
            lines.append("| %s | %s |" % (", ".join(ids[:14]) + (" …" if len(ids) > 14 else ""),
                                          proof.replace("|", "/")))
        lines.append("")

    lines.append("## Note for whoever supplies the evidence")
    lines.append("")
    lines.append("A row is only earned by evidence bound to **that row's** proof. A soak or verifier run that exercises")
    lines.append("the engine generally is not row-bound evidence; the artifact must let a reader answer \"did *this* row's")
    lines.append("assertion hold\" without re-running the whole thing. Where an aggregate run does cover a row, cite the")
    lines.append("specific check inside it.")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("  wrote:", OUT)
    print("  runtime-bound rows:", len(runtime))
    print("  groups:", {a: len(g) for a, g in sorted(groups.items(), key=lambda kv: -len(kv[1]))})


if __name__ == "__main__":
    main()
