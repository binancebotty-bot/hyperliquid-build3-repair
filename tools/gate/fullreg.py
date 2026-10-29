"""Parallel full regression, manifest-based (CC-1 R33 / CH-4, CH-9, VERIFY-001/003).

Usage:
    fullreg.py <worktree_dir_or_sha> [-j N] [--base a1acc28] [--timeout 300] [--manifest PATH]

WHY THIS REPLACES THE OLD RUNNER
The previous runner enumerated with `glob(d + r"\\test_core_*.py")` - a FILENAME-PREFIX glob,
not a manifest. At a1acc28 that admitted 124 of 167 test files: 43 files (26%) were silently
never run, and 5 of those 43 were red. Every "REGRESSIONS (0)" it printed was therefore true
of 74% of the suite.

THE FOUR RULES THIS ENFORCES (controller ruling, R33)
1. ENUMERATION: never a prefix glob. Use the pinned manifest if one is given, otherwise every
   `test_*.py`. A file that exists and is not run is a defect, not a saving.
2. NO `TOTAL=` LINE IS A GATE FAILURE: a file that produces no TOTAL= verdict is NOT_RUN and
   counts against the gate. It is never a pass.
3. CRASH IS NOT AN ASSERTION FAILURE: process death (non-zero exit with no TOTAL=) is reported
   separately from a test that ran and reported failures.
4. HEADLINE NUMBER: "N files run, A assertion failures, C crashes, M files with no TOTAL=".

VERDICTS
    PASS            ran, printed TOTAL=, FAILED=0
    ASSERTION_FAIL  ran, printed TOTAL=, FAILED>0
    CRASH           exited non-zero WITHOUT printing TOTAL=  (died before it could report)
    NOT_RUN         exited 0 WITHOUT printing TOTAL=         (ran, produced no verdict)
    TIMEOUT         exceeded the per-file timeout
Offline: no env files, testnet only, each file in its own process and its own TEMP dir.
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

OUT = r"C:\tmp\oc_results"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MANIFEST = os.path.join(HERE, "manifest_pinned.txt")


def wt(x):
    return x if os.path.isdir(x) else rf"C:\tmp\oc_wt_{x}"


def classify(rc, txt):
    """Return (verdict, total, failed, failing_cases). Rules 2 and 3 live here."""
    m = re.findall(r"TOTAL=(\d+)\s+FAILED=(\d+)", txt)
    total, failed = (m[-1] if m else (None, None))
    cases = sorted(set(re.findall(r"RESULT::(\S+?)_FAIL\b", txt)))
    if rc == "TIMEOUT":
        return "TIMEOUT", total, failed, cases
    if total is None:
        # No verdict was ever printed. Non-zero exit = died; zero exit = ran and said nothing.
        return ("CRASH" if rc != 0 else "NOT_RUN"), None, None, cases
    if int(failed) > 0 or rc != 0:
        return "ASSERTION_FAIL", total, failed, cases
    return "PASS", total, failed, cases


def run_one(d, t, sha, to):
    p = os.path.join(d, t)
    tmp = tempfile.mkdtemp(prefix="reg_", dir=r"C:\tmp")
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "TEMP": tmp,
        "TMP": tmp,
        "HL_LIVE_ENV_FILE": "/nonexistent/none.env",
        "HL_LEADER_NETWORK": "testnet",
        "HL_FOLLOWER_NETWORK": "testnet",
    }
    cmd = [sys.executable, "-m", "pytest", "-q", p] if t == "test_core_c7w_close_dust.py" else [sys.executable, p]
    t0 = time.time()
    try:
        o = subprocess.run(
            cmd, cwd=d, capture_output=True, text=True, timeout=to,
            creationflags=0x08000000, env=env,
        )
        rc, txt = o.returncode, o.stdout + "\n--STDERR--\n" + o.stderr
    except subprocess.TimeoutExpired:
        rc, txt = "TIMEOUT", "timeout"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(OUT + r"\full", exist_ok=True)
    open(rf"{OUT}\full\{sha}_{t[:-3]}.txt", "w", encoding="utf-8").write(f"exit={rc}\n{txt}")
    verdict, total, failed, cases = classify(rc, txt)
    last = [ln for ln in txt.strip().splitlines() if ln.strip()]
    return t, dict(
        rc=rc, verdict=verdict, tot=f"TOTAL={total} FAILED={failed}" if total else "",
        fails=cases, sec=round(time.time() - t0), tail=(last[-1][:100] if last else ""),
    )


def enumerate_files(d, manifest):
    """Rule 1: manifest, else every test_*.py. Never a prefix glob on its own."""
    if manifest and os.path.exists(manifest):
        names = []
        with open(manifest, encoding="utf-8") as fh:
            for line in fh:
                line = line.split("#", 1)[0].strip()
                if line:
                    names.append(line)
        present = [n for n in names if os.path.exists(os.path.join(d, n))]
        missing = [n for n in names if n not in present]
        return sorted(present), missing, "manifest"
    files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(d, "test_*.py")))
    return files, [], "test_*.py glob"


def run_sha(w, j, to, manifest=None):
    d = os.path.join(wt(w), "_archive", "hl_stage2")
    sha = os.path.basename(wt(w)).replace("oc_wt_", "")
    files, missing, source = enumerate_files(d, manifest)
    with ThreadPoolExecutor(j) as ex:
        res = dict(ex.map(lambda t: run_one(d, t, sha, to), files))
    for m in missing:  # a pinned file that is absent is itself a finding
        res[m] = dict(rc="ABSENT", verdict="MISSING", tot="", fails=[], sec=0, tail="pinned but not present")
    json.dump(res, open(rf"{OUT}\reg_{sha}.json", "w"), indent=1)
    return sha, res, source


def headline(sha, res, elapsed):
    counts = {}
    for v in res.values():
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    no_total = sum(1 for v in res.values() if not v["tot"] and v["verdict"] in ("NOT_RUN", "CRASH", "TIMEOUT"))
    return (
        f"SHA {sha}  files={len(res)} run  "
        f"A={counts.get('ASSERTION_FAIL', 0)} assertion failures  "
        f"C={counts.get('CRASH', 0)} crashes  "
        f"M={no_total} files with no TOTAL=  "
        f"P={counts.get('PASS', 0)} pass  "
        f"X={counts.get('MISSING', 0)} missing  "
        f"T={counts.get('TIMEOUT', 0)} timeout  elapsed={elapsed}s"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cand")
    ap.add_argument("-j", type=int, default=6)
    ap.add_argument("--base", default="a1acc28")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--no-base", action="store_true", help="baseline only; do not diff against --base")
    a = ap.parse_args()
    t0 = time.time()
    sha, res, source = run_sha(a.cand, a.j, a.timeout, a.manifest)
    elapsed = round(time.time() - t0)
    print(headline(sha, res, elapsed))
    print(f"enumeration: {source}  ({len(res)} files)")

    if a.no_base:
        return

    bp = rf"{OUT}\reg_{a.base}.json"
    if os.path.exists(bp):
        base = json.load(open(bp))
    else:
        _, base, _ = run_sha(a.base, a.j, a.timeout, a.manifest)

    L = [f"| test | {a.base} | {sha} | verdict | failing checks |", "|---|---|---|---|---|"]
    reg, fix = [], []
    rank = {"PASS": 0, "NOT_RUN": 1, "ASSERTION_FAIL": 2, "CRASH": 3, "TIMEOUT": 4, "MISSING": 5}
    for t in sorted(set(base) | set(res)):
        x, y = base.get(t), res.get(t)
        f = lambda z: "absent" if z is None else f"{z['verdict']} {z['tot']}".strip()
        L.append(f"| {t} | {f(x)} | {f(y)} | {y['verdict'] if y else '-'} | {', '.join(y['fails']) if y else ''} |")
        if x and y and rank.get(y["verdict"], 9) > rank.get(x["verdict"], 9):
            reg.append(t)
        if x and y and rank.get(y["verdict"], 9) < rank.get(x["verdict"], 9):
            fix.append(t)
    L += [
        "",
        headline(sha, res, elapsed),
        f"enumeration source: {source}",
        f"REGRESSIONS ({len(reg)}): {reg!r}",
        f"FIXED: {', '.join(fix)}",
        "",
        "NOTE: a REGRESSION is any worsening, including PASS -> NOT_RUN (a file that stopped",
        "reporting a verdict). The old runner scored only exit codes, so a test that went from",
        "green to silent scored as a pass.",
    ]
    open(rf"{OUT}\diff_{a.base}_vs_{sha}.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L[-8:]))


if __name__ == "__main__":
    main()
