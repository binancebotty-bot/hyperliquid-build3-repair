#!/usr/bin/env python3
"""Info reads share one keep-alive connection (a bare requests.post opened a new TCP+TLS connection per read), and an
offline test stub of requests.post is still honoured. Local loopback server only; no exchange, no keys."""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"
R = []


def check(n, c, d=""):
    R.append((n, bool(c)))
    print("RESULT::%s_%s%s" % (n, "PASS" if c else "FAIL", (" | " + d) if (d and not c) else ""))


PORTS = set()


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        PORTS.add(self.client_address[1])
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(n)
        body = json.dumps({"ok": 1}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = "http://127.0.0.1:%d/info" % srv.server_address[1]

import requests
import exchange_truth as xt

for _ in range(6):
    xt.http_post(url, {"type": "allMids"}, 3.0).json()
check("SEQUENTIAL_READS_REUSE_ONE_CONNECTION", len(PORTS) == 1, "connections=%d" % len(PORTS))

PORTS.clear()
ths = [threading.Thread(target=lambda: xt.http_post(url, {"type": "x"}, 3.0)) for _ in range(5)]
[t.start() for t in ths]
[t.join() for t in ths]
for _ in range(5):
    xt.http_post(url, {"type": "x"}, 3.0)
check("PARALLEL_READS_STAY_WITHIN_THE_POOL", 1 <= len(PORTS) <= 5, "connections=%d" % len(PORTS))

PORTS.clear()
os.environ["HL_LIVE_HTTP_SESSION"] = "0"
xt.http_post(url, {"type": "x"}, 3.0)
xt.http_post(url, {"type": "x"}, 3.0)
check("SWITCH_OFF_RESTORES_ONE_CONNECTION_PER_READ", len(PORTS) == 2, "connections=%d" % len(PORTS))
del os.environ["HL_LIVE_HTTP_SESSION"]

real = requests.post
calls = []


def stub(u, json=None, timeout=None, **k):
    calls.append(u)
    raise RuntimeError("offline test stub")
requests.post = stub
try:
    res = xt._post(None, {"type": "x"}, url, 1.0)
finally:
    requests.post = real
check("TEST_STUB_OF_REQUESTS_POST_IS_HONOURED", calls == [url] and not res["ok"], str((calls, res)))
# the Core posts through headroom.CountingRequests: it must still count every read AND ride the shared session
import headroom
noted = []


class Mon:
    def note_info(self, host, payload, rows):
        noted.append(payload)

    def note_refusal(self, *a):
        pass
PORTS.clear()
cr = headroom.CountingRequests(requests, Mon(), [url])
for _ in range(4):
    cr.post(url, json={"type": "allMids"}, timeout=3.0).json()
check("HEADROOM_WRAPPER_STILL_COUNTS_EVERY_READ", len(noted) == 4, str(len(noted)))
check("HEADROOM_WRAPPER_READS_SHARE_ONE_CONNECTION", len(PORTS) == 1, "connections=%d" % len(PORTS))
# a stale pooled connection fails once: retried once on a fresh one; a timeout is not retried
class _Flaky:
    def __init__(self, exc):
        self.n = 0
        self.exc = exc

    def post(self, u, json=None, timeout=None):
        self.n += 1
        if self.n == 1:
            raise self.exc
        return "OK"
real_sess = xt._SESSION
fl = _Flaky(requests.ConnectionError("RemoteDisconnected"))
xt._SESSION = fl
try:
    got = xt.http_post(url, {"type": "x"}, 3.0)
finally:
    xt._SESSION = real_sess
check("STALE_CONNECTION_IS_RETRIED_ONCE", got == "OK" and fl.n == 2, "got=%r n=%d" % (got, fl.n))
fl2 = _Flaky(requests.ReadTimeout("slow"))
xt._SESSION = fl2
try:
    try:
        xt.http_post(url, {"type": "x"}, 3.0)
        raised_t = False
    except requests.Timeout:
        raised_t = True
finally:
    xt._SESSION = real_sess
check("TIMEOUT_IS_NOT_RETRIED", raised_t and fl2.n == 1, "n=%d" % fl2.n)
failed = [n for n, ok in R if not ok]
print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
raise SystemExit(1 if failed else 0)
