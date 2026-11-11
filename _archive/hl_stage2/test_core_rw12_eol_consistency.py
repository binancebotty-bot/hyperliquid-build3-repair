#!/usr/bin/env python3
"""rw12 item 4: every line this stack added/modified in HL_Live_Copy_Service_Core.py ends like its unchanged neighbours.

The file has mixed CRLF/LF endings in the base, so unchanged lines are never touched; only changed lines are compared with the
nearest unchanged previous/next lines. Skips (passes with a SKIP line) when git or the base commit 29af865 is unavailable.
Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw12_eol_consistency.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "29af865"
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    f = "HL_Live_Copy_Service_Core.py"
    try:
        diff = subprocess.run(["git", "diff", "-U0", BASE, "--", f], cwd=HERE, capture_output=True, check=True).stdout
    except Exception as exc:  # no git / no base commit: nothing to compare
        print("SKIP: %r" % (exc,))
        check("E1_EOL_CONSISTENCY_SKIPPED_NO_BASE", True)
        sys.exit(0)
    added = set()
    for m in re.finditer(rb"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff, re.M):
        start, n = int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1
        added.update(range(start, start + n))
    lines = (HERE / f).read_bytes().split(b"\n")
    total = len(lines) - 1 if lines[-1] == b"" else len(lines)
    crlf = lambda i: lines[i - 1].endswith(b"\r")
    bad = []
    for i in sorted(added):
        if i > total:
            continue
        p, q = i - 1, i + 1
        while p >= 1 and p in added:
            p -= 1
        while q <= total and q in added:
            q += 1
        neighbours = [crlf(x) for x in (p, q) if 1 <= x <= total]
        if neighbours and (crlf(i) not in neighbours or (len(neighbours) == 2 and neighbours[0] == neighbours[1] != crlf(i))):
            bad.append(i)
    check("E1_CHANGED_LINES_MATCH_NEIGHBOUR_ENDINGS", not bad, "%d mismatches, first lines %s" % (len(bad), bad[:10]))
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
