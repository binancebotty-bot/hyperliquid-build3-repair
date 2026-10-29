"""Held sibling rows resolve through their head; a still-open head stays DEFERRED_OPEN and fails the run."""
import subprocess, sys, tempfile
from pathlib import Path
from outage_classify import classify

d = Path(tempfile.mkdtemp())
(d / "order_intents.csv").write_text("leader_fill_id,notes\n")
(d / "reconciliation.csv").write_text(
    "leader_fill_id,terminal_state,notes\n"
    "H,REPLAY_DEFERRED_X,\nS,REPLAY_DEFERRED_X,merged_into=H; held\nH,ENTRY_BLOCKED_RISK,r\n"
    "T,REPLAY_DEFERRED_X,merged_into=Z; held\nZ,REPLAY_DEFERRED_X,\n")
FAIL = []
CASES = []


def check(name, cond, detail=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' :: ' + detail) if detail and not cond else ''))
    CASES.append(name)
    if not cond:
        FAIL.append(name)


r = classify(d, ["H", "S", "T", "Z", "Q"])
check('a held sibling resolves through its blocked head', r["H"] == "BLOCKED_ENTRY_BLOCKED_RISK", repr(r))
check('a held sibling is reported as merged onto that head', r["S"] == "MERGED_BLOCKED_ENTRY_BLOCKED_RISK", repr(r))
check('a still-open head and its sibling stay DEFERRED_OPEN',
      r["T"] == "DEFERRED_OPEN" and r["Z"] == "DEFERRED_OPEN", repr(r))
check('an id with no row is MISSING', r["Q"] == "MISSING", repr(r))
(d / "ids.txt").write_text("H S")
check('a fully resolved id set exits 0',
      subprocess.run([sys.executable, "outage_classify.py", str(d), str(d / "ids.txt")],
                     capture_output=True).returncode == 0)
(d / "ids.txt").write_text("H S T")
check('an id set with a deferred open head exits 1',
      subprocess.run([sys.executable, "outage_classify.py", str(d), str(d / "ids.txt")],
                     capture_output=True).returncode == 1)
print(f"TOTAL={len(CASES)} FAILED={len(FAIL)}")
sys.exit(0 if not FAIL else 1)
