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
r = classify(d, ["H", "S", "T", "Z", "Q"])
assert r["H"] == "BLOCKED_ENTRY_BLOCKED_RISK", r
assert r["S"] == "MERGED_BLOCKED_ENTRY_BLOCKED_RISK", r
assert r["T"] == "DEFERRED_OPEN" and r["Z"] == "DEFERRED_OPEN", r
assert r["Q"] == "MISSING", r
(d / "ids.txt").write_text("H S")
assert subprocess.run([sys.executable, "outage_classify.py", str(d), str(d / "ids.txt")], capture_output=True).returncode == 0
(d / "ids.txt").write_text("H S T")
assert subprocess.run([sys.executable, "outage_classify.py", str(d), str(d / "ids.txt")], capture_output=True).returncode == 1
print("PASS test_outage_classify_deferred")
