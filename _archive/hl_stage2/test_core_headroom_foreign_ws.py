#!/usr/bin/env python3
"""Headroom: other local processes holding connections to the feed host are reported (WARN; CRITICAL when our own subscriptions were
refused). The Wallet Finder's connections took the whole per-IP WebSocket quota in Q14/Q15 and nothing said so.

Run: python test_core_headroom_foreign_ws.py   # No network, no orders.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import headroom as h  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


class Clock:
    def __init__(self): self.t = 1000.0
    def __call__(self): return self.t


def events(d):
    p = Path(d) / "headroom_events.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def settle(m, ck):
    for _ in range(100):
        if not m._foreign_busy:
            return
        time.sleep(0.02)


tmp = Path(tempfile.mkdtemp(prefix="hrfw_"))
ck = Clock()
m = h.HeadroomMonitor(alerts_dir=tmp, clock=ck)
state = {"foreign": 0, "refused": False, "calls": 0}


def scanner():
    state["calls"] += 1
    return {"ok": True, "foreign": state["foreign"], "pids": {"30984": {"connections": state["foreign"], "name": "python.exe"}} if state["foreign"] else {}}


m.ws_provider = lambda: {"acked": 4, "wanted": 10, "refused": state["refused"], "last_refusal": ""}
m.foreign_ws_scanner = scanner

m.evaluate(); settle(m, ck); st = m.evaluate()
check("F1_NONE_IS_OK_NO_EVENT", st["ws_foreign"]["level"] == "OK" and not [e for e in events(tmp) if e["resource"] == "ws_foreign"], str(st.get("ws_foreign")))

state["foreign"] = 11
ck.t += 31
m.evaluate(); settle(m, ck); st = m.evaluate()
check("F2_FOREIGN_IS_WARN_WITH_PID", st["ws_foreign"]["level"] == "WARN" and "30984" in st["ws_foreign"]["pids"], str(st.get("ws_foreign")))
ev = [e for e in events(tmp) if e["resource"] == "ws_foreign"]
check("F3_EVENT_NAMES_THE_PROCESS_AND_ACTION", ev and "pid 30984" in ev[-1]["detail"] and ev[-1]["suggested_actions"], str(ev[-1:]))

state["refused"] = True
ck.t += 31
m.evaluate(); settle(m, ck); st = m.evaluate()
check("F4_FOREIGN_PLUS_REFUSAL_IS_CRITICAL", st["ws_foreign"]["level"] == "CRITICAL" and st["worst"] == "CRITICAL", str(st.get("ws_foreign")))

n = state["calls"]
for _ in range(5):
    m.evaluate()
check("F5_SCAN_RATE_LIMITED", state["calls"] == n, "%d -> %d" % (n, state["calls"]))

m2 = h.HeadroomMonitor(alerts_dir=None, clock=ck)
m2.foreign_ws_scanner = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
m2.evaluate(); settle(m2, ck); st = m2.evaluate()
check("F6_SCAN_ERROR_NEVER_RAISES", st.get("ws_foreign_scan", {}).get("ok") is False, str(st))

m3 = h.HeadroomMonitor(alerts_dir=None, clock=ck)
st = m3.evaluate()
check("F7_NO_SCANNER_NO_KEY", "ws_foreign" not in st and "ws_foreign_scan" not in st)

r = h.scan_foreign_ws("wss://invalid.invalid/ws")
check("F8_UNRESOLVABLE_HOST_NOT_OK_NO_RAISE", r.get("ok") is False and r.get("foreign") == 0, str(r))

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
