#!/usr/bin/env python3
"""Headroom monitor: weight math, levels with hysteresis, immediate hard refusals, event file schema, request counting.

Run: python test_core_headroom.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

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


tmp = Path(tempfile.mkdtemp(prefix="headroom_"))
ck = Clock()
m = h.HeadroomMonitor(alerts_dir=tmp, clock=ck)

check("weights", h.info_weight({"type": "allMids"}) == 2 and h.info_weight({"type": "userFillsByTime"}, 2000) == 120
      and h.info_weight({"type": "userRole"}) == 60 and h.info_weight({"type": "meta"}) == 20)

for _ in range(30):                       # 30 x 20 = 600 of 1200 = 50 %
    m.note_info("api.x", {"type": "userFillsByTime"})
st = m.evaluate()
check("ok_at_50pct", st["info_weight:api.x"]["level"] == "OK" and not events(tmp), str(st))
for _ in range(8):                        # 760 = 63 %
    m.note_info("api.x", {"type": "userFillsByTime"})
for _ in range(5):                        # 860 = 71.6 % -> WARN
    m.note_info("api.x", {"type": "userFillsByTime"})
st = m.evaluate()
check("warn_at_70pct", st["info_weight:api.x"]["level"] == "WARN", str(st["info_weight:api.x"]))
for _ in range(11):                       # 1080 = 90 %
    m.note_info("api.x", {"type": "userFillsByTime"})
st = m.evaluate()
check("critical_at_90pct", st["info_weight:api.x"]["level"] == "CRITICAL" and st["worst"] == "CRITICAL", str(st["info_weight:api.x"]))
ev = events(tmp)
req = {"ts_ms", "resource", "level", "used", "limit", "pct", "detail", "suggested_actions", "engine_run_id"}
check("event_schema", ev and all(req <= set(e) for e in ev) and ev[-1]["suggested_actions"], str(ev[-1:]))

ck.t += 61                                 # window empties -> reads OK, but hysteresis holds the level for 60 s
st = m.evaluate()
check("hysteresis_holds", st["info_weight:api.x"]["level"] == "CRITICAL")
ck.t += 61
st = m.evaluate()
check("drops_after_60s", st["info_weight:api.x"]["level"] == "OK" and events(tmp)[-1]["level"] == "OK")

n = len(events(tmp))
m.note_refusal("ws_users", "Cannot track more than 15 total users")
e = events(tmp)
check("refusal_is_immediate_critical", len(e) == n + 1 and e[-1]["level"] == "CRITICAL" and "15 total users" in e[-1]["detail"], str(e[-1:]))
check("refusal_actions", "PAUSE_NEW_ENTRIES" in e[-1]["suggested_actions"])

m.ws_provider = lambda: {"acked": 14, "wanted": 20, "refused": True, "last_refusal": "x"}
st = m.evaluate()
check("ws_users_graded", st["ws_users"]["level"] == "CRITICAL" and st["ws_users"]["wanted"] == 20, str(st.get("ws_users")))
state = json.loads((tmp / "headroom_state.json").read_text())
check("state_file", state.get("worst") == "CRITICAL" and "levels" in state)

# request counting proxy
calls = []
fake_real = SimpleNamespace(post=lambda url, *a, **k: calls.append(url) or SimpleNamespace(status_code=200, json=lambda: [1] * 45), other=7)
m2 = h.HeadroomMonitor(alerts_dir=tmp / "b", clock=ck)
cr = h.CountingRequests(fake_real, m2, ["https://api.hl/info"])
cr.post("https://api.hl/info", json={"type": "userFillsByTime"})
cr.post("https://other.example/x", json={"type": "meta"})
check("proxy_counts_info_only", m2.info_used("api.hl") == 22 and len(calls) == 2 and cr.other == 7, str(m2.info_used("api.hl")))
fake_real.post = lambda url, *a, **k: SimpleNamespace(status_code=429, json=lambda: {})
cr.post("https://api.hl/info", json={"type": "meta"})
check("429_is_refusal", any(r["resource"].startswith("info:") for r in m2.refusals))
cr.post = lambda *a, **k: "patched"      # tests patch requests.post on the proxy: must work
check("proxy_patchable", cr.post("u") == "patched")

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
