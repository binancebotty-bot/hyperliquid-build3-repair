#!/usr/bin/env python3
"""A fill decided by its head's final row must not get a late FILL_PENDING_QUEUED row (the batch releases its queue keys only when
every fill of the batch is done), and a merged sibling that has one anyway is decided by its head in the outage classifier
instead of staying DEFERRED_OPEN for ever (Q33: 793 siblings, 0 younger than 10 min)."""
import os, sys, tempfile, threading, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
R = []
def check(n, c_, d=""):
    R.append((n, bool(c_))); print("RESULT::%s_%s%s" % (n, "PASS" if c_ else "FAIL", (" | " + d) if (d and not c_) else ""))

tmp = Path(tempfile.mkdtemp(prefix="pendingdone_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_PENDING_SWEEP_SEC": "0.2",
                   "HL_LIVE_PENDING_ROW_SEC": "0.05", "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_WS_ENABLED": "0"})
import HL_Live_Copy_Service_Core as c
import outage_classify as oc

W = "0x" + "a" * 40
H, S1, S2 = "0xhead1", "0xsib1", "0xsib2"
# --- classifier: siblings with a late pending row are decided by their head
c.append_csv(c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS, {"leader_fill_id": H, "notes": f"lifecycle=ENTRY;merged_leader_fills=3:{H},{S1},{S2}"})
for s in (S1, S2):
    c.append_csv(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS, {"event": "FILL_MERGED", "status": "LEADER_FILL_MERGED_INTO_ORDER", "leader_fill_id": s,
        "notes": f"merged with leader fill {H} into one copy order (intent x)"})
    c.append_csv(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS, {"event": "FILL_PENDING", "status": "FILL_PENDING_QUEUED", "terminal_state": "FILL_PENDING_QUEUED", "leader_fill_id": s,
        "notes": "waited 63s for a worker"})
c.append_csv(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS, {"event": "SEND_TERMINAL", "status": "LIQ_PARITY_BLOCKED", "terminal_state": "LIQ_PARITY_BLOCKED", "leader_fill_id": H})
res = oc.classify(c.RECONCILIATION_CSV.parent, [H, S1, S2])
check("SIBLING_WITH_LATE_PENDING_ROW_DECIDED_BY_HEAD", res[S1] == "MERGED_BLOCKED_LIQ_PARITY_BLOCKED" and res[S2] == res[S1], str(res))
# a sibling whose head is itself still open stays open
c.append_csv(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS, {"event": "FILL_PENDING", "status": "FILL_PENDING_QUEUED", "terminal_state": "FILL_PENDING_QUEUED", "leader_fill_id": "0xopen"})
check("UNDECIDED_FILL_STAYS_DEFERRED_OPEN", oc.classify(c.RECONCILIATION_CSV.parent, ["0xopen"])["0xopen"] == "DEFERRED_OPEN")

# --- sweeper: no pending row for a fill already decided; still one for a fill really waiting
core = c.LiveCopyCore(source_csv=tmp / "none.csv")
now = c.utc_now_ms() - 120000
with core._queued_lock:
    for key, fid in (("k-done", "0xdone"), ("k-wait", "0xwait")):
        core._queued_keys.add(key); core._pending_seen[key] = (now, W, "BTC", fid)
core._handled_ids = {"0xdone": True}
time.sleep(1.2)
core.stop()
rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("terminal_state") == "FILL_PENDING_QUEUED"]
ids = {r["leader_fill_id"] for r in rows}
check("NO_PENDING_ROW_FOR_A_DECIDED_FILL", "0xdone" not in ids, str(ids))
check("PENDING_ROW_STILL_WRITTEN_FOR_A_WAITING_FILL", "0xwait" in ids, str(ids))
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
sys.exit(1 if failed else 0)
