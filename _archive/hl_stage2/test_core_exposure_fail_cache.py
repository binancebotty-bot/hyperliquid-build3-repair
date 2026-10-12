"""A failed follower-exposure read is remembered for a moment: workers behind it get 'unavailable' at once instead of each
repeating the slow failing read (startup backlog: ~9 s per fill). Fail-closed is unchanged. Run (from _archive/hl_stage2):
HL_LIVE_ENV_FILE=/nonexistent python -u test_core_exposure_fail_cache.py"""
import os, sys, tempfile, threading, time
from pathlib import Path
tmp = Path(tempfile.mkdtemp(prefix="efc_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_EXPOSURE_FAIL_TTL_SEC": "0.5"})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

c.USER_WALLET = "0x" + "1" * 40
c.follower_dex_scope = lambda: [""]
calls = {"n": 0, "ok": False}
def fake(*a, **k):
    calls["n"] += 1
    if calls["ok"]:
        return {"ok": True, "status": "OK", "total_usd": 0.0, "by_coin": {}, "equity_usd": 1.0}
    return {"ok": False, "status": "SCOPE_UNAVAILABLE", "dex": "io", "detail": "non-JSON"}
c._XNET.master_exposure = fake
b = object.__new__(c.IntentBuilder)
b._exposure = None; b._exposure_ms = 0; b._exposure_prefetched = None; b._exposure_gen = 0; b._exposure_pending = []
b._exposure_prefetch_lock = threading.Lock()

r1 = b.follower_exposure()
check("FIRST_FAILURE_IS_UNAVAILABLE", not r1["ok"] and r1["dex"] == "io" and "SCOPE_UNAVAILABLE" in r1["status"], str(r1))
n1 = calls["n"]
for _ in range(5):
    r = b.follower_exposure()
    b._prefetch_exposure()
check("NO_REPEAT_READS_WITHIN_WINDOW", calls["n"] == n1 and not r["ok"] and r["dex"] == "io", f"calls={calls['n']}")
time.sleep(0.6)
calls["ok"] = True
r2 = b.follower_exposure()
check("READS_AGAIN_AFTER_WINDOW_AND_RECOVERS", calls["n"] == n1 + 1 and r2["ok"], str(r2))
calls["ok"] = False
b._exposure = None; b._exposure_prefetched = None
time.sleep(0.01)
b._exposure_fail = None
b._prefetch_exposure(); n2 = calls["n"]
b._prefetch_exposure()
check("PREFETCH_ALSO_REMEMBERS_FAILURE", calls["n"] == n2 and n2 > n1 + 1)
fails = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(fails)))
sys.exit(1 if fails else 0)
