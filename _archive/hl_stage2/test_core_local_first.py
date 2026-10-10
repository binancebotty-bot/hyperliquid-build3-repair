#!/usr/bin/env python3
"""PR 1 step B: a fill that will end in a local block makes ZERO info reads (no prewarm); a fill that can reach the
exchange still prewarms (follower mid + exposure + leader mid cross-network) side by side.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_local_first.py"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="localfirst_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_WS_ENABLED": "0",
                   "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                   "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_PREWARM_SYMBOL_META": "0",
                   "HL_LIVE_PREWARM_SDK_CLIENT": "0", "HL_LIVE_HOT_SEND_WORKERS": "2"})
import requests  # noqa: E402
import HL_Live_Copy_Service_Core as c  # noqa: E402

requests.post = requests.get = c.requests.post = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline"))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


LEADER, FOLLOWER = "0x" + "a" * 40, "0x" + "c" * 40
c.USER_WALLET = FOLLOWER
CALLS, LOCK, DELAY = [], threading.Lock(), 0.3


def slow(name, fn):
    def fetch(payload):
        with LOCK:
            CALLS.append((name, time.monotonic()))
        time.sleep(DELAY)
        return fn(payload)
    return fetch


MIDS = {"BTC": 100.0, "ETH": 100.0}
EXP = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}
c.MIDS_FETCHER = slow("mids", lambda _p: dict(MIDS))
c.LEADER_MIDS_FETCHER = slow("leader_mids", lambda _p: dict(MIDS))
c.EXPOSURE_FETCHER = slow("exposure", lambda p: [] if p.get("type") == "perpDexs" else dict(EXP))
c.LEADER_FETCHER = slow("leader", lambda p: [] if p.get("type") == "perpDexs" else dict(EXP))

c.atomic_write_json(c.LIVE_CONFIG_FILE, {
    "auto_send_enabled": True,
    "global_controls": {"symbol_blocklist": ["ETH"], "min_notional": 1},
    "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100}},
})
core = c.LiveCopyCore(source_csv=tmp / "none.csv")
b = core.intent_builder

now = c.utc_now_ms()
btc = c.LeaderFill("t-btc", LEADER, "BTC", "BUY", 100.0, 1.0, now, "WS_CAPTURED")
eth = c.LeaderFill("t-eth", LEADER, "ETH", "BUY", 100.0, 1.0, now, "WS_CAPTURED")
close_flat = c.LeaderFill("t-close", LEADER, "BTC", "SELL", 100.0, 1.0, now, "WS_CAPTURED", raw={"dir": "Close Long"})

check("L1_BLOCKLISTED_ENTRY_IS_LOCAL", b.blocked_locally(eth) is True)
check("L2_SENDABLE_ENTRY_IS_NOT_LOCAL", b.blocked_locally(btc) is False)
check("L3_ENTRY_BLOCK_REASON_IS_LOCAL", b.blocked_locally(btc, "paused") is True)
check("L4_CLOSE_WITHOUT_SLEEVE_IS_LOCAL", b.blocked_locally(close_flat) is True)

CALLS.clear()
core._process_leader_fill(eth, None, "")
check("L5_LOCAL_BLOCK_MAKES_ZERO_READS", not [x for x in CALLS if x[0] in ("mids", "leader_mids", "exposure", "leader")],
      str(CALLS))
CALLS.clear()
t0 = time.monotonic()
b.prewarm(btc)
took = time.monotonic() - t0
names = sorted({n for n, _t in CALLS})
check("L6_SENDABLE_PREWARMS_MIDS_AND_EXPOSURE", "exposure" in names and ("mids" in names), str(names))
check("L7_PREWARM_READS_RUN_SIDE_BY_SIDE", took < DELAY * 2.2, "took=%.2fs for %d reads" % (took, len(CALLS)))
core.stop()

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
