"""The DEFAULT hold: with no HL_LIVE_DEFER_MAX_SEC set, unreadable entry truth stays held with NO time
limit, and exactly one alert fires past the 300 s default boundary (never a second).

Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_defer_default_hold.py
Offline: fakes only, no network, no orders, no keys.
"""
import os, sys, tempfile, threading
from pathlib import Path
from types import SimpleNamespace

tmp = Path(tempfile.mkdtemp(prefix="dhold_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent"})
os.environ.pop("HL_LIVE_DEFER_MAX_SEC", None)          # the DEFAULT, not an override
os.environ.pop("HL_LIVE_DEFER_ALERT_GRACE_SEC", None)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

check("DEFAULT_HOLD_LIMIT_IS_UNBOUNDED", c.deferred_truth_max_seconds() == 0.0, str(c.deferred_truth_max_seconds()))

now = c.utc_now_ms()
class Running:
    def is_alive(self): return True
fill = SimpleNamespace(leader_wallet="0xw", coin="BTC", leader_fill_id="HELD",
                       side="BUY", timestamp_ms=now - 400_000, size=1.0, price=100.0, raw={})
intent = SimpleNamespace(decision="SEND_BLOCKED_RISK", reason="follower positions unavailable",
                         notes="lifecycle=ENTRY")

# --- a fill held 400 s under the DEFAULT setting is still held, not aged out ---------------------
rows = []
core = SimpleNamespace(audit=SimpleNamespace(append_reconciliation=lambda *a, **k: rows.append((a, k))),
                       _guard_key=c.LiveCopyCore._guard_key,
                       _TRUTH_UNREADABLE_MARKERS=c.LiveCopyCore._TRUTH_UNREADABLE_MARKERS,
                       _defer_first_ms={"HELD": now - 400_000}, _defer_alerted=set(),
                       _idem_lock=threading.Lock(), _idem_accepted={"HELD"},
                       dedupe=SimpleNamespace(_lock=threading.Lock(), processed={"HELD"}),
                       _deferred_lock=threading.Lock(), _deferred={}, _deferred_thread=Running(),
                       _rows_for_held_siblings=lambda *_a, **_k: None)
held = c.LiveCopyCore._defer_unreadable_truth(core, fill, intent, [])
check("DEFAULT_HOLDS_PAST_LIMIT_NO_EXPIRY", held is True and "HELD" in core._deferred and "HELD" in core._defer_first_ms,
      "held=%r deferred=%r" % (held, list(core._deferred)))
check("DEFAULT_HOLD_WRITES_NO_EXPIRY_ALERT",
      [k for _a, k in rows if k.get("terminal_state") == "REPLAY_DEFERRED_PAST_LIMIT_ALERT"] == [], str(rows)[:300])

# --- one alert just past the 300 s default boundary, and never a second --------------------------
hrows = []
acore = SimpleNamespace(audit=SimpleNamespace(append_reconciliation=lambda *a, **k: hrows.append((a, k))),
                        _deferred_lock=threading.Lock(), _deferred={"HELD": (fill, 0.0)},
                        _defer_first_ms={"HELD": now - 301_000})
c.LiveCopyCore._alert_held_past_limit(acore)
alerts = [k for a, k in hrows if len(a) > 1 and a[1] == "REPLAY_DEFERRED_PAST_LIMIT_ALERT"]
check("ONE_ALERT_JUST_PAST_300S", len(alerts) == 1, str(hrows)[:300])
check("ALERT_NAMES_THE_300S_DEFAULT", bool(alerts) and "limit 300s" in str(alerts[0].get("notes", "")),
      str(alerts[:1]))
c.LiveCopyCore._alert_held_past_limit(acore)
check("NO_SECOND_ALERT", len(hrows) == 1, "rows=%d" % len(hrows))

fails = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(fails)))
sys.exit(1 if fails else 0)
