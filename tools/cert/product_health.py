"""Does the PRODUCT pass its own tests? Credit-free, local, no model.

board_health.py answers "is work flowing". This answers "is the thing correct" - the gap that let a send-affecting
regression sit on main behind a green merge while every board metric looked healthy.

It checks out origin/main into a scratch worktree, runs every shipped test under _archive/hl_stage2 with Python 3.11,
parses RESULT:: lines, and reports failures as BLOCKING.

    python tools/cert/product_health.py
    python tools/cert/product_health.py --json
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(r"C:/Users/wigmore/hyperliquid-build3-repair")
WORK = Path(r"C:/Users/wigmore/.hermes/cache/scratch/product_health")
PY311 = r"C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe"
TEST_GLOB = "test_*.py"
RESULT_RE = re.compile(r"^RESULT::(.+?)::(PASS|FAIL)$|^RESULT::(.+?)_(PASS|FAIL)$", re.M)


def sync_main() -> str:
    """Fetch origin/main into a clean scratch checkout. Returns the commit."""
    if not (WORK / ".git").exists():
        WORK.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--filter=blob:none", "-q",
                        "https://github.com/binancebotty-bot/hyperliquid-build3-repair", str(WORK)],
                       capture_output=True, timeout=600)
    subprocess.run(["git", "-C", str(WORK), "fetch", "-q", "origin", "main"], timeout=300)
    subprocess.run(["git", "-C", str(WORK), "checkout", "-q", "-f", "origin/main"], timeout=300)
    return subprocess.run(["git", "-C", str(WORK), "rev-parse", "--short", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    as_json = "--json" in sys.argv
    commit = sync_main()
    stage2 = WORK / "_archive" / "hl_stage2"
    tests = sorted(stage2.glob(TEST_GLOB)) if stage2.is_dir() else []

    results, failures = [], []
    for t in tests:
        try:
            r = subprocess.run([PY311, str(t)], capture_output=True, timeout=240, cwd=str(stage2))
        except subprocess.TimeoutExpired:
            results.append((t.name, "TIMEOUT", []))
            failures.append((t.name, "TIMEOUT", []))
            continue
        out = (r.stdout or b"").decode("utf-8", errors="replace") + (r.stderr or b"").decode("utf-8", errors="replace")
        checks = []
        for m in RESULT_RE.finditer(out):
            if m.group(1):
                checks.append((m.group(1), m.group(2)))
            else:
                checks.append((m.group(3), m.group(4)))
        bad = [c for c in checks if c[1] == "FAIL"]
        ok = r.returncode == 0 and not bad
        results.append((t.name, "PASS" if ok else "FAIL", bad))
        if not ok:
            failures.append((t.name, "FAIL" if checks or r.returncode else "NO-ASSERTIONS", bad or
                             [(f"exit_{r.returncode}", "FAIL")]))

    out_lines = []
    out_lines.append("PRODUCT   origin/main @ %s  |  %d shipped test(s) under _archive/hl_stage2" % (commit, len(tests)))
    for name, verdict, bad in results:
        mark = "OK  " if verdict == "PASS" else "FAIL"
        out_lines.append("          %-52s %s" % (name[:52], mark))
        for cname, cv in bad[:4]:
            out_lines.append("              %s -> %s" % (cname, cv))

    out_lines.append("")
    if failures:
        out_lines.append("PRODUCT PUNCH (BLOCKING) — %d shipped test suite(s) failing on origin/main:" % len(failures))
        for name, verdict, bad in failures:
            detail = ", ".join("%s=%s" % (c, v) for c, v in bad[:4]) or verdict
            out_lines.append("  - %s — %s" % (name, detail))
        out_lines.append("")
        out_lines.append("A merge that carries a failing test is the false-green class: the test existed before the merge")
        out_lines.append("and was red. Do not treat the board as healthy while this line is present.")
    else:
        out_lines.append("PRODUCT PUNCH  empty — every shipped test passes on origin/main")

    if as_json:
        print(json.dumps({"commit": commit, "tests": len(tests),
                          "failures": [{"test": n, "detail": d} for n, _, d in failures]}))
    else:
        print("\n".join(out_lines))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
