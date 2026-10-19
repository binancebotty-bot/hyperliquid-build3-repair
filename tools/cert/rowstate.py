"""Print row states from a NAMED ref, so a card body can never quote the wrong register.

This exists because the same error recurred three times: card bodies were written from the working-tree matrix (the
790-row cert lineage) while workers cloned origin/main (the 832-row register). The card said "4 rows are FAIL" and the
worker found 4 PASS. The worker was right every time.

    python tools/cert/rowstate.py --ref origin/main ORD-001 ORD-002 ...
    python tools/cert/rowstate.py --ref origin/main --prefix ORD-
    python tools/cert/rowstate.py --diff        # compare working tree vs main for a prefix

Default ref is origin/main because that is what a worker clones.
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

WS = Path(r"C:/Users/wigmore/hyperliquid-build3-repair")


def load(ref: str) -> dict:
    if ref == "WORKTREE":
        return json.loads((WS / "certification" / "certification_matrix.json").read_text(encoding="utf-8-sig"))
    out = subprocess.run(["git", "-C", str(WS), "show", ref + ":certification/certification_matrix.json"],
                         capture_output=True, timeout=120)
    if out.returncode != 0:
        raise SystemExit("  cannot read %s" % ref)
    return json.loads(out.stdout.decode("utf-8-sig"))


def main() -> int:
    args = sys.argv[1:]
    ref = "origin/main"
    if "--ref" in args:
        ref = args[args.index("--ref") + 1]
        args = [a for a in args if a not in ("--ref", ref)]
    doc = load(ref)
    by = {str(r.get("id")): r for r in doc["records"]}

    if "--diff" in args:
        wt = {str(r.get("id")): r for r in load("WORKTREE")["records"]}
        prefix = args[args.index("--prefix") + 1] if "--prefix" in args else ""
        diffs = [(i, str(by[i].get("result")), str(wt[i].get("result")))
                 for i in set(by) & set(wt) if i.startswith(prefix) and str(by[i].get("result")) != str(wt[i].get("result"))]
        print("  %s vs WORKTREE: %d differing row(s) under prefix %r" % (ref, len(diffs), prefix))
        for i, a, b in sorted(diffs)[:25]:
            print("   %-14s %-11s -> %s" % (i, a, b))
        return 0

    ids = [a for a in args if not a.startswith("--")]
    if "--prefix" in args:
        pre = args[args.index("--prefix") + 1]
        ids = [i for i in by if i.startswith(pre)]
        ids.sort()

    print("  ref: %s  (%d rows, %s)" % (ref, len(doc["records"]),
                                        dict(Counter(str(r.get("result")) for r in doc["records"]))))
    for i in ids:
        r = by.get(i)
        print("  %-14s %s" % (i, r.get("result") if r else "ABSENT"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
