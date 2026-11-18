#!/usr/bin/env python3
"""Stale-fixture runner: runs named suites with the venv interpreter.

Usage: python _run.py <suite.py> [<suite.py> ...]   (paths relative to _archive/hl_stage2)
Full stdout of each suite is written to <scratch>/logs/<suite>.log;
the console shows only failures, totals and tracebacks.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "_archive" / "hl_stage2"
PY = r"C:/Users/wigmore/.hermes/hermes-agent/.venv/Scripts/python.exe"
SCRATCH = Path(r"C:/Users/wigmore/.hermes/cache/scratch/stale5")
LOGS = SCRATCH / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

env = dict(os.environ)
env["HL_LIVE_ENV_FILE"] = "/nonexistent"
env["TMPDIR"] = str(SCRATCH)
env["PYTHONIOENCODING"] = "utf-8"

KEEP = ("TOTAL=", "FAILED_LABELS=", "FAILED:", "MEASURED::", "STARTUP::", "Traceback",
        "AssertionError", "RESULT::")


def run(name, timeout=300):
    p = STAGE / name
    if not p.exists():
        print("MISSING %s" % p, flush=True)
        return 2
    try:
        r = subprocess.run([PY, "-u", str(p)], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        out, rc = (r.stdout or "") + (r.stderr or ""), r.returncode
    except subprocess.TimeoutExpired as exc:
        out = "TIMEOUT after %ss\n%s" % (timeout, (exc.stdout or b"").decode("utf-8", "replace")
                                         if isinstance(exc.stdout, bytes) else (exc.stdout or ""))
        rc = 124
    log = LOGS / (name + ".log")
    log.write_text(out, encoding="utf-8", errors="replace")
    print("=" * 70)
    print("SUITE %s EXIT=%d  (full log: %s)" % (name, rc, log))
    for line in out.splitlines():
        if line.startswith(KEEP):
            if line.startswith("RESULT::") and "_PASS" in line:
                continue
            print(line.rstrip()[:600])
    npass = sum(1 for l in out.splitlines() if l.startswith("RESULT::") and "_PASS" in l)
    print("RESULT_PASS_LINES=%d" % npass)
    print("=" * 70, flush=True)
    return r.returncode


def tally(name, rc):
    """One row for the report: exit code plus whatever count line the suite prints."""
    text = (LOGS / (name + ".log")).read_text(encoding="utf-8", errors="replace")
    total = ""
    for line in text.splitlines():
        if line.startswith("TOTAL=") or "/" in line and line.strip().endswith("passed"):
            total = line.strip()
            break
    npass = sum(1 for l in text.splitlines() if l.startswith("RESULT::") and "_PASS" in l)
    nfail = sum(1 for l in text.splitlines() if l.startswith("RESULT::") and "_FAIL" in l)
    return "%-42s %-4s %-16s pass=%-3d fail=%-3d %s" % (
        name, "GREEN" if rc == 0 else ("RED" if rc != 124 else "TIMEOUT"),
        total or "-", npass, nfail, "" if rc == 0 else "")


def main(argv):
    names = argv[1:]
    if not names:
        print("usage: _run.py <suite.py> ...")
        return 2
    codes = {n: run(n) for n in names}
    print("\nSUMMARY")
    for n, rc in codes.items():
        print("  " + tally(n, rc))
    return 0 if all(c == 0 for c in codes.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
