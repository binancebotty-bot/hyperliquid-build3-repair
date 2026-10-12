"""A throttled/empty /info answer is retried before a read fails (entries were blocked SCOPE_UNAVAILABLE by one such read).
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_exchange_truth_retry.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["HL_LIVE_INFO_RETRIES"] = "2"
import exchange_truth as e
R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))
calls = []
class Resp:
    def __init__(s, ok): s.ok = ok
    def json(s):
        if not s.ok: raise ValueError("Expecting value")
        return {"assetPositions": []}
def run(seq, fetcher=None):
    calls.clear()
    e.http_post = lambda url, payload, timeout: (calls.append(1), Resp(seq[len(calls) - 1]))[1]
    return e._post(fetcher, {}, "u", 1)
check("RETRY_RECOVERS_AFTER_TWO_BAD_ANSWERS", run([False, False, True])["ok"] and len(calls) == 3)
check("GIVES_UP_AFTER_THREE_TRIES_AND_FAILS_CLOSED", not run([False, False, False])["ok"] and len(calls) == 3)
check("GOOD_FIRST_ANSWER_IS_ONE_CALL", run([True])["ok"] and len(calls) == 1)
n = []
def bad(p): n.append(1); raise ValueError("x")
calls.clear()
check("INJECTED_FETCHER_IS_NEVER_RETRIED", not e._post(bad, {}, "u", 1)["ok"] and len(n) == 1)
class ReadTimeout(Exception): pass
calls.clear()
def slow(url, payload, timeout): calls.append(1); raise ReadTimeout("slow")
e.http_post = slow
check("TIMEOUT_IS_NOT_RETRIED", not e._post(None, {}, "u", 1)["ok"] and len(calls) == 1)
failed = [k for k, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
