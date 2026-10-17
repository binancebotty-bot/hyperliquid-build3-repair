"""OFFLINE probe: how many TCP connections does ONE sdk exchange.order() open?

Localhost HTTP/1.1 server answers /info with minimal metadata and /exchange with a
synthetic ack, and records the client source port of every request (a new source
port == a new TCP connection). The real hyperliquid SDK is pointed at it.
No live network, no live keys, no orders to any exchange.
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import sys
sys.path.insert(0, r"C:\\Users\\wigmore\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages")

META = {"universe": [{"name": "BTC", "szDecimals": 5, "maxLeverage": 50}]}
SPOT_META = {"universe": [], "tokens": []}

REQS = []
PHASE = {"name": "init"}
LOCK = threading.Lock()


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n)
        with LOCK:
            REQS.append((PHASE["name"], self.path, self.client_address[1], time.monotonic()))
        try:
            payload = json.loads(body or b"{}")
        except Exception:
            payload = {}
        if self.path == "/info":
            t = payload.get("type")
            if t == "meta":
                data = META
            elif t == "spotMeta":
                data = SPOT_META
            elif t == "perpDexs":
                data = [{"name": "test"}]
            elif t == "allMids":
                data = {"BTC": "100000"}
            else:
                data = {}
        else:
            data = {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 1}}]}}}
        raw = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % port

    from eth_account import Account
    from hyperliquid.exchange import Exchange

    acct = Account.from_key("0x" + "11" * 32)

    PHASE["name"] = "construct"
    t0 = time.monotonic()
    ex = Exchange(acct, base_url=base, account_address=acct.address)
    construct_ms = int((time.monotonic() - t0) * 1000)

    PHASE["name"] = "order"
    t1 = time.monotonic()
    resp = ex.order("BTC", True, 0.001, 100000.0, {"limit": {"tif": "Ioc"}})
    order_ms = int((time.monotonic() - t1) * 1000)

    with LOCK:
        reqs = list(REQS)
    init_reqs = [r for r in reqs if r[0] != "order"]
    order_reqs = [r for r in reqs if r[0] == "order"]

    print("SERVER:", base)
    print("CONSTRUCT_MS:", construct_ms, "construct_requests:", [(r[1], r[2]) for r in init_reqs])
    print("ORDER_MS:", order_ms)
    print("ORDER_REQUESTS:", [(r[1], r[2]) for r in order_reqs])
    print("ORDER_DISTINCT_CONN:", len({r[2] for r in order_reqs}))
    print("ALL_DISTINCT_CONN:", len({r[2] for r in reqs}))
    print("RESPONSE:", resp)

    PHASE["name"] = "order2"
    t3 = time.monotonic()
    ex.order("BTC", True, 0.001, 100000.0, {"limit": {"tif": "Ioc"}})
    order2_ms = int((time.monotonic() - t3) * 1000)
    with LOCK:
        o2 = [r for r in REQS if r[0] == "order2"]
    print("ORDER2_MS:", order2_ms, "ORDER2_REQUESTS:", [(r[1], r[2]) for r in o2],
          "ORDER2_DISTINCT_CONN:", len({r[2] for r in o2}))

    from hyperliquid.utils.signing import sign_l1_action
    action = {"type": "order", "orders": [{"a": 0, "b": True, "p": "100000.0", "s": "0.001",
                                           "r": False, "t": {"limit": {"tif": "Ioc"}}}]}
    samples = []
    for _ in range(30):
        s = time.monotonic()
        sign_l1_action(acct, action, None, int(time.time() * 1000), None, False)
        samples.append((time.monotonic() - s) * 1000.0)
    samples.sort()
    print("SIGN_MS p50=%.2f min=%.2f max=%.2f n=%d" % (samples[len(samples) // 2], samples[0], samples[-1], len(samples)))

    print("SESSION_REUSED_ACROSS_ORDERS:", {r[2] for r in order_reqs} == {r[2] for r in o2})


if __name__ == "__main__":
    main()
