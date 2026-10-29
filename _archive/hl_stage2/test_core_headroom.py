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
cr = h.CountingRequests(fake_real, m2, ["https://api.hyperliquid.xyz/info"])
with h.request_lane("poll"):
    cr.post("https://api.hyperliquid.xyz/info", json={"type": "userFillsByTime"})
cr.post("https://other.example/x", json={"type": "meta"})
check("proxy_counts_info_only", m2.info_used("api.hyperliquid.xyz") == 22 and len(calls) == 2 and cr.other == 7, str(m2.info_used("api.hyperliquid.xyz")))
fake_real.post = lambda url, *a, **k: SimpleNamespace(status_code=429, json=lambda: {})
with h.request_lane("back-poll"):
    cr.post("https://api.hyperliquid.xyz/info", json={"type": "meta"})
check("429_is_refusal", any(r["resource"].startswith("info:") for r in m2.refusals))
cr.post = lambda *a, **k: "patched"      # tests patch requests.post on the proxy: must work
check("proxy_patchable", cr.post("u") == "patched")

counts = m2.http_requests_by_minute()
check("request_counts_have_lane_network_endpoint_status", any(
    r.get("endpoint") == "userFillsByTime" and r.get("lane") == "poll"
    and r.get("network") == "mainnet_read" and r.get("status") == "200" and r.get("count") == 1
    for r in counts
) and any(r.get("endpoint") == "meta" and r.get("lane") == "back-poll" and r.get("status") == "429" for r in counts), str(counts))

import requests
import exchange_truth as xt  # noqa: E402
real_send, old_session, old_request = requests.adapters.HTTPAdapter.send, xt._SESSION, requests.Session.request
old_getenv = xt.os.getenv
session = requests.Session()
def fake_send(adapter, request, **_kwargs):
    response = requests.Response()
    response.status_code = 429
    response._content = b"{}"
    response.url = request.url
    response.request = request
    return response
try:
    h.install_session_counter(m2)
    requests.adapters.HTTPAdapter.send = fake_send
    xt._SESSION = session
    session.post("https://api.hyperliquid-testnet.xyz/exchange", json={"action": {"type": "order"}})
    with h.request_lane("catch-up"):
        xt.http_post("https://api.hyperliquid-testnet.xyz/info", {"type": "userFillsByTime"}, 1.0)
    xt._SESSION = None
    xt.os.getenv = lambda name, default=None: "0" if name == "HL_LIVE_HTTP_SESSION" else default
    with h.request_lane("back-poll"):
        xt.http_post("https://api.hyperliquid-testnet.xyz/info", {"type": "clearinghouseState"}, 1.0)
finally:
    requests.adapters.HTTPAdapter.send = real_send
    requests.Session.request = old_request
    xt.os.getenv = old_getenv
    xt._SESSION = old_session
    session.close()
counts = m2.http_requests_by_minute()
check("sdk_session_records_hot_send_status", any(
    r.get("endpoint") == "order" and r.get("lane") == "hot-send"
    and r.get("network") == "testnet_exchange" and r.get("status") == "429"
    for r in counts
), str(counts))
check("shared_http_path_records_lane_once", any(
    r.get("endpoint") == "userFillsByTime" and r.get("lane") == "catch-up"
    and r.get("network") == "testnet_read" and r.get("status") == "429" and r.get("count") == 1
    for r in counts
), str(counts))
check("disabled_session_fallback_is_counted", any(
    r.get("endpoint") == "clearinghouseState" and r.get("lane") == "back-poll"
    and r.get("network") == "testnet_read" and r.get("status") == "429"
    for r in counts
), str(counts))
m2.evaluate()
saved_counts = json.loads((tmp / "b" / "headroom_state.json").read_text()).get("http_requests_by_minute")
check("request_counts_written_to_state", saved_counts == m2.http_requests_by_minute(), str(saved_counts))

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
