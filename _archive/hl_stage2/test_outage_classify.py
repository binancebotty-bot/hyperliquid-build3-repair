#!/usr/bin/env python3
"""The outage classifier gives every fill one outcome and fails (MISSING) on a silent loss. Offline, temp files only."""
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import outage_classify as oc

R = []


def check(n, c, d=""):
    R.append((n, bool(c)))
    print("RESULT::%s_%s%s" % (n, "PASS" if c else "FAIL", (" | " + d) if (d and not c) else ""))


def w(path, rows):
    keys = sorted({k for r in rows for k in r})
    with path.open("w", newline="") as f:
        d = csv.DictWriter(f, fieldnames=keys)
        d.writeheader()
        d.writerows(rows)


tmp = Path(tempfile.mkdtemp(prefix="classify_"))
w(tmp / "order_intents.csv", [
    {"leader_fill_id": "a1", "notes": "x;merged_leader_fills=3:a2,a3"},
    {"leader_fill_id": "b1", "notes": "merged_leader_fills=2:b2"},
])
w(tmp / "send_attempts.csv", [{"leader_fill_id": "a1", "status": "ORDER_FILLED"}])
w(tmp / "reconciliation.csv", [
    {"leader_fill_id": "b1", "terminal_state": "SEND_BLOCKED_RISK"},
    {"leader_fill_id": "c1", "terminal_state": "MISSED_ENTRY_LEADER_ALREADY_CLOSED"},
    {"leader_fill_id": "d1", "terminal_state": "REPLAY_DEFERRED_TRUTH_UNREADABLE"},
])
res = oc.classify(tmp, ["a1", "a2", "a3", "b1", "b2", "c1", "d1", "zz"])
check("CLASSIFY_SENT", res["a1"] == "SENT", str(res))
check("CLASSIFY_MERGED_SIBLINGS_FOLLOW_THE_HEAD", res["a2"] == res["a3"] == "MERGED_SENT", str(res))
check("CLASSIFY_BLOCKED_HEAD_AND_SIBLING", res["b1"] == "BLOCKED_SEND_BLOCKED_RISK" and res["b2"].startswith("MERGED_BLOCKED"), str(res))
check("CLASSIFY_SKIPPED_FLAT", res["c1"] == "SKIPPED_FLAT", str(res))
check("CLASSIFY_DEFERRED_IS_OPEN_NOT_LOST", res["d1"] == "DEFERRED_OPEN", str(res))
check("CLASSIFY_UNKNOWN_FILL_IS_MISSING", res["zz"] == "MISSING", str(res))
w(tmp / "errors.csv", [{"leader_fill_id": "mm", "note": "x"}])
det = oc.missing_detail(tmp, ["mm", "nn"])
check("MISSING_DETAIL_SPLITS_INGESTED_FROM_NEVER_SEEN", "NEVER_IN_ANY_FILE=1" in det[0] and "errors.csv" in det[1] and "files={}" in det[2], str(det))
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
