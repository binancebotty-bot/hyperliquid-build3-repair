"""A leader subscription HL refused (per-IP quota full) is asked for again on the open socket, so freed quota is picked up without a restart.
Run (from _archive/hl_stage2): HL_LIVE_ENV_FILE=/nonexistent python -u test_core_ws_resubscribe.py"""
import json, os, sys, tempfile
from pathlib import Path
from types import SimpleNamespace
tmp = Path(tempfile.mkdtemp(prefix="wsr_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_WS_RESUBSCRIBE_SEC": "1"})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

R = []
def check(n, ok, d=""):
    R.append((n, bool(ok))); print(("PASS" if ok else "FAIL"), n, d); print("RESULT::%s_%s" % (n, "PASS" if ok else "FAIL"))

W = ["0x" + str(i) * 40 for i in range(1, 6)]
sent = []
ws = object.__new__(c.WSManager)
ws._wallet_source = W; ws.wallets = list(W)
ws._socket_open = True; ws._socket_opened_at_ms = c.utc_now_ms() - 60000
ws._subscribed = set(W[:3]); ws._app = SimpleNamespace(send=lambda m: sent.append(json.loads(m)))
ws._last_subscribe_ms = 0
f = c.WSManager._resubscribe_missing
f(ws)
check("ASKS_ONLY_THE_MISSING_WALLETS", sorted(m["subscription"]["user"] for m in sent) == sorted(W[3:]) and all(m["method"] == "subscribe" for m in sent), str(sent))
n = len(sent); f(ws)
check("THROTTLED", len(sent) == n)
ws._subscribed = set(W); ws.__dict__["_last_resub_ms"] = 0
f(ws)
check("NOTHING_WHEN_ALL_ACKED", len(sent) == n)
ws._subscribed = set(W[:4]); ws.__dict__["_last_resub_ms"] = 0; ws._socket_opened_at_ms = c.utc_now_ms()
f(ws)
check("WAITS_FOR_A_FRESH_SOCKET", len(sent) == n)
ws._socket_opened_at_ms = c.utc_now_ms() - 60000; ws._socket_open = False
f(ws)
check("NOTHING_WHEN_SOCKET_CLOSED", len(sent) == n)
fails = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(fails)))
sys.exit(1 if fails else 0)
