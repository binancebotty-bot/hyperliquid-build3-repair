#!/usr/bin/env python3
"""Mutation helper for test_core_c7_close_must_send.py (STUB: the hunk list arrives with STEP 2).

For each hunk it copies this directory's *.py into a scratch dir, REVERTS the hunk in the scratch copy of
HL_Live_Copy_Service_Core.py (replaces `new` back with `old`), runs the named test file there in its own process and
requires the named test to FAIL. A hunk whose revert leaves every named test passing is a dead hunk (nothing proves
it); a revert that fails an unrelated test is reported too. The real tree is never modified.

Usage:
    python c7_close_must_send_mutation.py hunks.json [--test test_core_c7_close_must_send.py]

hunks.json: [ {"name": "H1", "old": "<text before the change>", "new": "<text the change introduced>",
               "expect_fail": ["W1_STALE_REPLAY_ON_FLAT_SLEEVE_IS_A_NAMED_NO_SEND_WITH_ONE_DURABLE_ROW"]}, ... ]
Matching is on the exact text (CRLF-tolerant). Exit code 0 only when every hunk reverted cleanly and every expected
test failed. Offline; testnet; no network.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORE = "HL_Live_Copy_Service_Core.py"
CREATE_NO_WINDOW = 0x08000000


def run_test(scratch, test):
    proc = subprocess.run([sys.executable, str(scratch / test)], cwd=str(scratch), capture_output=True, text=True,
                          timeout=300, creationflags=CREATE_NO_WINDOW)
    out = proc.stdout + "\n" + proc.stderr
    failed = set(re.findall(r"RESULT::(\S+?)_FAIL\b", out))
    total = re.findall(r"TOTAL=\d+ FAILED=\d+", out)
    return failed, (total[-1] if total else "NO_TOTAL")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    hunks = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    test = "test_core_c7_close_must_send.py"
    if "--test" in argv:
        test = argv[argv.index("--test") + 1]
    if not hunks:
        print("NO_HUNKS: nothing to mutate (stub)")
        return 0
    bad = 0
    for h in hunks:
        scratch = Path(tempfile.mkdtemp(prefix="c7_mut_"))
        try:
            for p in HERE.glob("*.py"):
                shutil.copyfile(p, scratch / p.name)
            core_p = scratch / CORE
            raw = core_p.read_bytes().decode("utf-8")
            crlf = "\r\n" in raw
            norm = lambda t: t.replace("\r\n", "\n").replace("\n", "\r\n" if crlf else "\n")   # noqa: E731
            old, new = norm(h["old"]), norm(h["new"])
            if raw.count(new) != 1:
                print("HUNK %s: NOT_APPLICABLE (new text occurs %d times)" % (h["name"], raw.count(new)))
                bad += 1
                continue
            core_p.write_bytes(raw.replace(new, old).encode("utf-8"))
            failed, total = run_test(scratch, test)
            want = set(h.get("expect_fail") or [])
            missing = sorted(want - failed)
            print("HUNK %s: %s failed=%d  expected=%s  not_failing=%s" % (h["name"], total, len(failed), sorted(want), missing))
            if missing or not want:
                bad += 1
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
    print("MUTATION_DEAD_OR_BROKEN_HUNKS=%d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
