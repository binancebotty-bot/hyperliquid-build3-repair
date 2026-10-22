#!/usr/bin/env python3
"""exchange_truth.http_post (the shared keep-alive /info session used by post_many) must feed the
headroom WEIGHT budget. Today install_session_counter counts the REQUEST but only CountingRequests.post
called note_info, so every read Core makes through post_many was weight HEADROOM never saw -> 420/min
was a floor. No network, no orders.

Run: python test_core_http_post_headroom.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["HL_LIVE_HTTP_SESSION"] = "1"

import requests  # noqa: E402
import headroom as h  # noqa: E402
import exchange_truth as xt  # noqa: E402

RESULTS = []
INFO = "https://api.hyperliquid-testnet.xyz/info"
HOST = "api.hyperliquid-testnet.xyz"


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def fresh(install=True):
    m = h.HeadroomMonitor(alerts_dir=Path(tempfile.mkdtemp(prefix="hr_http_post_")))
    cur = requests.Session.request
    if getattr(cur, "_headroom_counter", False):
        requests.Session.request = getattr(cur, "__wrapped__", cur)
    if install:
        h.install_session_counter(m)
    return m


def with_transport(rows, fn, status=200):
    real_send, old_session = requests.adapters.HTTPAdapter.send, xt._SESSION

    def fake_send(adapter, request, **kwargs):
        r = requests.Response()
        r.status_code = status
        r._content = json.dumps(rows).encode()
        r.url = request.url
        r.request = request
        return r

    try:
        requests.adapters.HTTPAdapter.send = fake_send
        xt._SESSION = None
        return fn()
    finally:
        requests.adapters.HTTPAdapter.send = real_send
        xt._SESSION = old_session


m = fresh()
with_transport([], lambda: xt.post_many(None, [{"type": "clearinghouseState", "user": "0xabc"}],
                                        info_url=INFO, timeout=3.0, workers=1))
check("http_post_counts_cheap_read_weight", m.info_used(HOST) == 2, "info_used=%d" % m.info_used(HOST))

m = fresh()
with_transport([{"oid": i} for i in range(40)],
               lambda: xt.post_many(None, [{"type": "userFillsByTime", "user": "0xabc"}],
                                    info_url=INFO, timeout=3.0, workers=1))
check("http_post_counts_fill_rows", m.info_used(HOST) == 22, "info_used=%d" % m.info_used(HOST))

m = fresh()
counting = h.CountingRequests(requests, m, [INFO])
with_transport([], lambda: counting.post(INFO, json={"type": "clearinghouseState", "user": "0xabc"}, timeout=3.0))
check("shared_path_not_double_counted", m.info_used(HOST) == 2, "info_used=%d" % m.info_used(HOST))

m = fresh(install=False)
with_transport([], lambda: xt.post_many(None, [{"type": "clearinghouseState", "user": "0xabc"}],
                                        info_url=INFO, timeout=3.0, workers=1))
check("no_counter_no_weight", m.info_used(HOST) == 0, "info_used=%d" % m.info_used(HOST))

m = fresh()
with_transport({}, lambda: xt.post_many(None, [{"type": "clearinghouseState", "user": "0xabc"}],
                                        info_url=INFO, timeout=3.0, workers=1), status=429)
check("http_post_429_is_a_refusal", any("refusal" in k for k in m._level), str(dict(m._level)))

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
