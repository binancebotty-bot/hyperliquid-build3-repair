#!/usr/bin/env python3
"""WS startup grace: right after the socket thread is launched, a feed that is not up yet is STARTING, not DEGRADED,
so the entry gate (WS_FEED_STALE) does not mark a burst of entries blocked for good (Q17: 34 rows in 6 s after a restart).
A refusal, or a feed that is still down after the grace, stays DEGRADED.

Run: python test_core_ws_startup_grace.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
W = ["0x%040x" % i for i in range(1, 4)]


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="wsgrace_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_HOT_SEND_WORKERS": "2"})
    os.environ.pop("HL_LIVE_WS_START_GRACE_MS", None)
    import HL_Live_Copy_Service_Core as c

    ws = c.WSManager(W, c.LeaderFillIngestor())
    ws.enabled = True
    now = c.utc_now_ms()
    grade = lambda: ws.write_health()["ws_summary"]["worst_health_grade"]

    ws._started_ms = now - 10_000          # launched 10 s ago, socket not open yet
    ws._socket_open = False
    check("starting_socket_not_open", grade() == "STARTING", grade())
    ws._thread = threading.current_thread()
    ws._socket_open = True                 # open, no ack yet, inside grace
    check("starting_open_no_ack", grade() == "STARTING", grade())

    ws._started_ms = now - 120_000         # grace over, still nothing acked
    ws._socket_opened_at_ms = now - 100_000
    check("degraded_after_grace_no_ack", grade() == "DEGRADED", grade())
    ws._socket_open = False
    check("degraded_after_grace_socket_down", grade() == "DEGRADED", grade())

    ws._started_ms = now - 10_000          # inside grace, but HL refused a subscription
    ws._socket_open = True
    ws._subscribed = {W[0]}
    ws._on_message(json.dumps({"channel": "error", "data": "Cannot track more than 15 total users"}))
    check("refusal_degrades_inside_grace", grade() == "DEGRADED", grade())

    ws2 = c.WSManager(W, c.LeaderFillIngestor())
    ws2.enabled = True
    ws2._started_ms = now - 10_000
    ws2._thread = threading.current_thread()   # write_health needs a live thread for socket_open
    ws2._socket_open = True
    ws2._socket_opened_at_ms = now - 5_000
    ws2._subscribed = set(W)
    ws2.last_msg_ms = {w: now for w in W}
    check("acked_feed_is_ok", ws2.write_health()["ws_summary"]["worst_health_grade"] == "OK")

    ws3 = c.WSManager(W, c.LeaderFillIngestor())   # never started (tests, polling-only): old behaviour kept
    ws3.enabled = True
    ws3._socket_open = False
    check("never_started_stays_degraded", ws3.write_health()["ws_summary"]["worst_health_grade"] == "DEGRADED")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
