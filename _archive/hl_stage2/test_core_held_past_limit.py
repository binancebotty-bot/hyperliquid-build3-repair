"""A fill held past the defer limit gets one visible ALERT row (still unresolved for the classifier). Run (from _archive/hl_stage2):
HL_LIVE_ENV_FILE=/nonexistent python -u test_core_held_past_limit.py"""
import os, sys, tempfile, threading
from pathlib import Path
from types import SimpleNamespace
tmp = Path(tempfile.mkdtemp(prefix="hpl_"))
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
now = c.utc_now_ms()
def fl(i): return SimpleNamespace(leader_wallet="0xw", coin="BTC", leader_fill_id=i)
core = SimpleNamespace(audit=Audit(), _deferred_lock=threading.Lock(),
                       _deferred={"old": (fl("OLD"), 0.0), "new": (fl("NEW"), 0.0)},
                       _defer_first_ms={"old": now - 400_000, "new": now - 10_000})
f = c.LiveCopyCore._alert_held_past_limit
f(core)
check("ONE_ALERT_FOR_THE_OLD_FILL_ONLY", [k["leader_fill_id"] for _a, k in rows] == ["OLD"] and rows[0][1]["terminal_state"].startswith("REPLAY_DEFERRED"), str(rows))
f(core)
check("NO_SECOND_ALERT", len(rows) == 1)
core._defer_first_ms["new"] = now - 361_000
f(core)
check("ALERT_AFTER_LIMIT_PLUS_GRACE", sorted(k["leader_fill_id"] for _a, k in rows) == ["NEW", "OLD"])
# the classifier must keep counting an alerted fill as still open
import csv
ad = tmp / "ap"; ad.mkdir()
with (ad / "order_intents.csv").open("w", newline="") as fh: fh.write("leader_fill_id,notes\n")
with (ad / "reconciliation.csv").open("w", newline="") as fh: fh.write("leader_fill_id,terminal_state,notes\nOLD,REPLAY_DEFERRED_PAST_LIMIT_ALERT,x\n")
check("CLASSIFIER_STILL_OPEN", oc.classify(ad, ["OLD"])["OLD"] == "DEFERRED_OPEN")

# A zero configured limit uses the bounded default; once that age is reached the entry falls through
# with a visible operator alert instead of remaining deferred forever.
os.environ["HL_LIVE_DEFER_MAX_SEC"] = "0"
expired_fill = SimpleNamespace(leader_wallet="0xw", coin="BTC", leader_fill_id="EXPIRED",
                               side="BUY", timestamp_ms=now - 400_000, size=1.0, price=100.0)
expired_intent = SimpleNamespace(decision="SEND_BLOCKED_RISK", reason="follower positions unavailable",
                                 notes="lifecycle=ENTRY")
expiry_rows = []
expiry_core = SimpleNamespace(audit=Audit(), _guard_key=c.LiveCopyCore._guard_key,
                              _TRUTH_UNREADABLE_MARKERS=c.LiveCopyCore._TRUTH_UNREADABLE_MARKERS,
                              _defer_first_ms={"EXPIRED": now - 400_000}, _defer_alerted=set())
expiry_core.audit.append_reconciliation = lambda *a, **k: expiry_rows.append((a, k))
expired = c.LiveCopyCore._defer_unreadable_truth(expiry_core, expired_fill, expired_intent, [])
check("ZERO_LIMIT_EVENTUALLY_RELEASES", not expired)
check("EXPIRY_WRITES_MANUAL_ALERT", len(expiry_rows) == 1
      and expiry_rows[0][0][1] == "REPLAY_DEFERRED_PAST_LIMIT_ALERT"
      and expiry_rows[0][1].get("action") == "MANUAL_REVIEW_UNREADABLE_TRUTH", str(expiry_rows))
fails = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(fails)))
sys.exit(1 if fails else 0)
