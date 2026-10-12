"""Every fill merged into one copy gets its own row naming the head; the classifier resolves it (outage test Q7: 152 'missing' ids).
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_merged_rows.py"""
import os, sys, tempfile, threading
from pathlib import Path
from types import SimpleNamespace
tmp = Path(tempfile.mkdtemp(prefix="mrg_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c
import outage_classify as oc

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

rows = []
class Audit:
    def append_reconciliation(self, *a, **k): rows.append((a, k))
def me(accepted, deferred=()):
    return SimpleNamespace(audit=Audit(), _idem_lock=threading.Lock(), _idem_accepted=set(accepted), _deferred=set(deferred),
                           _guard_key=c.LiveCopyCore._guard_key)
fill = SimpleNamespace(leader_wallet="0xw", coin="BTC", leader_fill_id="H", raw={"merged_fill_ids": ["S1", "S2"]})
f = c.LiveCopyCore._rows_for_merged_siblings

rows.clear(); f(me({"H", "S1", "S2"}), fill, (False, "DEDUPED", None))
check("EACH_SIBLING_GETS_A_ROW", sorted(k["leader_fill_id"] for _a, k in rows) == ["S1", "S2"] and all(k["terminal_state"] == "MERGED_INTO_HEAD_COPY" and "merged_into=H" in k["notes"] for _a, k in rows))
rows.clear(); f(me({"H"}), fill, (False, "DEDUPED", None))
check("NO_ROW_IF_SIBLINGS_NOT_ACCEPTED", not rows)
rows.clear(); f(me({"H", "S1", "S2"}), fill, (False, "REPLAY_DEFERRED_TRUTH_UNREADABLE", None))
check("NO_ROW_WHILE_HEAD_IS_HELD", not rows)
rows.clear(); f(me({"H", "S1", "S2"}), fill, (False, "DUPLICATE_BLOCKED", None))
check("NO_ROW_FOR_DUPLICATE_HEAD", not rows)
rows.clear(); f(me({"H", "S1", "S2"}), fill, (True, "REAL_SENT", None))
check("NORMAL_PATH_WRITES_NOTHING_EXTRA", not rows)
rows.clear(); f(me({"H"}), SimpleNamespace(leader_wallet="w", coin="B", leader_fill_id="H", raw={}), (True, "X", None))
check("NO_SIBLINGS_NO_ROWS", not rows)

# classifier: sibling row names the head -> MERGED_SENT / MERGED_BLOCKED
ad = tmp / "ap"; ad.mkdir()
import csv
def w(name, header, data):
    with (ad / name).open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=header); wr.writeheader(); [wr.writerow(r) for r in data]
w("order_intents.csv", ["leader_fill_id", "notes"], [])
w("send_attempts.csv", ["leader_fill_id", "status", "exchange_status"], [{"leader_fill_id": "H", "status": "ORDER_FILLED", "exchange_status": ""}])
w("reconciliation.csv", ["leader_fill_id", "terminal_state", "notes"], [
    {"leader_fill_id": "S1", "terminal_state": "MERGED_INTO_HEAD_COPY", "notes": "merged_into=H; head_outcome=X"},
    {"leader_fill_id": "S2", "terminal_state": "MERGED_INTO_HEAD_COPY", "notes": "merged_into=NOPE; head_outcome=X"}])
out = oc.classify(ad, ["H", "S1", "S2"])
check("CLASSIFIER_RESOLVES_SIBLING_TO_HEAD", out["S1"] == "MERGED_SENT" and out["S2"] == "MERGED_NO_OUTCOME" and out["H"] == "SENT", str(out))
rows.clear(); c.LiveCopyCore._rows_for_held_siblings(me(set()), fill, "REPLAY_DEFERRED_TRUTH_UNREADABLE")
check("HELD_HEAD_GIVES_SIBLINGS_A_DEFERRED_ROW", sorted(k["leader_fill_id"] for _a, k in rows) == ["S1", "S2"] and all(k["terminal_state"] == "REPLAY_DEFERRED_TRUTH_UNREADABLE" for _a, k in rows))
w("reconciliation.csv", ["leader_fill_id", "terminal_state", "notes"], [{"leader_fill_id": "S1", "terminal_state": "REPLAY_DEFERRED_TRUTH_UNREADABLE", "notes": "merged_into=H"}])
check("CLASSIFIER_HELD_SIBLING_TAKES_DECIDED_HEAD", oc.classify(ad, ["S1"])["S1"] == "MERGED_SENT")  # H was sent (send_attempts)
w("send_attempts.csv", ["leader_fill_id", "status", "exchange_status"], [])
check("CLASSIFIER_CALLS_HELD_SIBLING_DEFERRED_OPEN", oc.classify(ad, ["S1"])["S1"] == "DEFERRED_OPEN")  # head undecided: still open
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
