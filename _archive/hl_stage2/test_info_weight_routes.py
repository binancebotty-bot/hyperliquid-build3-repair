#!/usr/bin/env python3
"""Every /info read route adds its true HL weight to the shared headroom window EXACTLY once: exchange_truth.http_post,
_post, post_many, the fetcher=None helpers, the keep-alive read, the stub and switch-off branches, and the CountingRequests
wrapper. Fake session only; no network, no keys."""
import os
import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import requests
import headroom
import exchange_truth as xt

FAILED = []


def check(name, cond, detail=""):
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", "" if cond else " | " + str(detail)))
    if not cond:
        FAILED.append(name)


URL = "https://api.hyperliquid-testnet.xyz/info"
HOST = "api.hyperliquid-testnet.xyz"
ADDR = "0x" + "ab" * 20


class Resp:
    def __init__(self, body):
        self.status_code, self._b = 200, body

    def json(self):
        return self._b


class FakeSession:
    def __init__(self):
        self.sent = []

    def post(self, url, json=None, timeout=None):
        self.sent.append(json)
        t = (json or {}).get("type")
        if t == "perpDexs":
            return Resp([None, {"name": "xyz"}])
        if t == "userFillsByTime":
            return Resp([{"coin": "BTC", "tid": i, "oid": i, "time": i} for i in range(40)])
        if t == "clearinghouseState":
            return Resp({"assetPositions": [], "marginSummary": {"accountValue": "0"}})
        return Resp([])


mon = headroom.HeadroomMonitor()
headroom._SESSION_REQUEST_MONITOR = mon
sess = FakeSession()
xt._SESSION = sess


def wsum(m):
    return sum(w for _, w in m._info.get(HOST, ()))


def window():
    return wsum(mon)


def delta(fn):
    before, n = window(), len(sess.sent)
    fn()
    return window() - before, len(sess.sent) - n


W = headroom.info_weight
state = {"type": "clearinghouseState", "user": ADDR}
oo = {"type": "openOrders", "user": ADDR}
mids = {"type": "allMids"}
fills = {"type": "userFillsByTime", "user": ADDR, "startTime": 0}
check("WEIGHT_TABLE_SANITY", W(mids) == 2 and W(state) >= 2 and W(fills, 40) > W(fills, 0) and W(oo) >= 2,
      (W(mids), W(state), W(oo), W(fills, 0), W(fills, 40)))

d, n = delta(lambda: xt.http_post(URL, state, 3.0))
check("DIRECT_HTTP_POST_ONCE", (d, n) == (W(state), 1), (d, n))
d, n = delta(lambda: xt._post(None, oo, URL, 3.0))
check("POST_ONCE", (d, n) == (W(oo), 1), (d, n))
pl = [state, oo, mids, state]
d, n = delta(lambda: xt.post_many(None, pl, URL, 3.0, workers=4))
check("POST_MANY_BATCH_PARALLEL_EACH_ONCE", (d, n) == (sum(W(p) for p in pl), 4), (d, n))
d, n = delta(lambda: xt.post_many(None, pl, URL, 3.0, workers=1))
check("POST_MANY_BATCH_SERIAL_EACH_ONCE", (d, n) == (sum(W(p) for p in pl), 4), (d, n))
d, n = delta(lambda: xt._post(None, fills, URL, 3.0))
check("ROWS_SCALED_WEIGHT_ONCE", (d, n) == (W(fills, 40), 1), (d, n))
# helpers called as production does, fetcher=None
d, n = delta(lambda: xt.master_exposure(ADDR, ["", "xyz"], None, URL, 3.0))
check("HELPER_MASTER_EXPOSURE_FETCHER_NONE", (d, n) == (2 * W(state), 2), (d, n))
d, n = delta(lambda: xt.list_perp_dexes(None, URL, 3.0))
check("HELPER_LIST_PERP_DEXES_FETCHER_NONE", (d, n) == (W({"type": "perpDexs"}), 1), (d, n))
d, n = delta(lambda: xt.rolling_day_pnl(ADDR, None, URL, 3.0))
check("HELPER_ROLLING_DAY_PNL_FETCHER_NONE", n == 1 and d == W({"type": "portfolio", "user": ADDR}), (d, n))
d, n = delta(lambda: xt.master_userfills(ADDR, 0, "", None, URL, 3.0))
check("HELPER_MASTER_USERFILLS_FETCHER_NONE", n == 1 and d == W(fills, 40), (d, n))
d, n = delta(lambda: xt.master_account_net(ADDR, "BTC", None, URL, 3.0))
check("HELPER_MASTER_ACCOUNT_NET_FETCHER_NONE", n == 3 and d == W({"type": "perpDexs"}) + 2 * W(state), (d, n))
# an injected fetcher never touches the network, so it adds no weight
d, n = delta(lambda: xt._post(lambda p: [], oo, URL, 3.0))
check("INJECTED_FETCHER_NO_WEIGHT", (d, n) == (0, 0), (d, n))
d, n = delta(lambda: xt.http_post("https://api.hyperliquid-testnet.xyz/exchange", {"type": "x"}, 3.0))
check("NON_INFO_URL_NO_WEIGHT", d == 0, d)


real_event = threading.Event


class _EvFactory:
    """Returns a real Event whose first wait() elapses at once and whose second reports stop."""
    first = True

    def __call__(self):
        ev = real_event()
        if not self.first:  # Thread.__init__ builds its own Event: only the keep-alive's stop event is faked
            return ev
        self.first = False
        calls = [0]
        orig_wait = ev.wait

        def wait(t=None):
            calls[0] += 1
            return calls[0] > 1
        ev.wait = wait
        return ev


xt._KEEPALIVE["thread"] = None
before = window()
threading.Event = _EvFactory()
try:
    xt.start_keepalive([URL], 5.0)
    xt._KEEPALIVE["thread"].join(5)
finally:
    threading.Event = real_event
    xt._KEEPALIVE["thread"] = None
check("KEEPALIVE_ALLMIDS_ONCE", window() - before == W(mids), window() - before)

# wrapper route: CountingRequests -> shared http_post; counted once, into the WRAPPER's monitor, not also the process one
mon2 = headroom.CountingRequests  # noqa: F841 (name reuse guard)
mon2 = headroom.HeadroomMonitor()
cr = headroom.CountingRequests(requests, mon2, [URL])
b1 = window()
cr.post(URL, json=oo, timeout=3.0)
check("WRAPPER_ROUTE_ONCE_IN_WRAPPER_MONITOR", wsum(mon2) == W(oo), wsum(mon2))
check("WRAPPER_ROUTE_NOT_DOUBLE_COUNTED_ELSEWHERE", window() == b1, window() - b1)

# stub branch (offline stub of requests.post): http_post counts it; the wrapper counts it itself (not requests.api)
real = requests.post
requests.post = lambda u, json=None, timeout=None, **k: Resp([])
try:
    d, _ = delta(lambda: xt._post(None, oo, URL, 3.0))
    check("STUB_BRANCH_ONCE", d == W(oo), d)
    mon3 = headroom.HeadroomMonitor()
    headroom.CountingRequests(requests, mon3, [URL]).post(URL, json=oo, timeout=3.0)
    check("WRAPPER_STUB_ROUTE_ONCE", wsum(mon3) == W(oo), wsum(mon3))
finally:
    requests.post = real

# switch-off branch (HL_LIVE_HTTP_SESSION=0 with the real-looking requests.post)
os.environ["HL_LIVE_HTTP_SESSION"] = "0"


def fake_post(u, json=None, timeout=None, **k):
    return Resp([])


fake_post.__module__ = "requests.api"
requests.post = fake_post
try:
    d, _ = delta(lambda: xt._post(None, oo, URL, 3.0))
    check("SWITCH_OFF_BRANCH_ONCE", d == W(oo), d)
    mon4 = headroom.HeadroomMonitor()
    headroom.CountingRequests(requests, mon4, [URL]).post(URL, json=oo, timeout=3.0)
    check("WRAPPER_SWITCH_OFF_ONCE", wsum(mon4) == W(oo), wsum(mon4))
finally:
    requests.post = real
    os.environ.pop("HL_LIVE_HTTP_SESSION", None)


# a timed-out live read still spent weight: counted once
class Boom(FakeSession):
    def post(self, *a, **k):
        raise requests.ReadTimeout("slow")


xt._SESSION = Boom()
b = window()
try:
    xt.http_post(URL, oo, 3.0)
except requests.ReadTimeout:
    pass
check("TIMEOUT_COUNTED_ONCE", window() - b == W(oo), window() - b)

# --- SDK-session /info posts (HL SDK Info client) are counted by weight by the session counter, once ---
from requests.adapters import BaseAdapter


class FakeAdapter(BaseAdapter):
    def __init__(self, fail_first=False):
        super().__init__()
        self.sent, self.fail_first = [], fail_first

    def send(self, request, **kw):
        import json as _j
        self.sent.append(_j.loads(request.body) if request.body else None)
        if self.fail_first and len(self.sent) == 1:
            raise requests.ConnectionError("RemoteDisconnected")
        r = requests.Response()
        r.status_code = 200
        r._content = b"[]"
        r.url = request.url
        return r

    def close(self):
        pass


headroom.install_session_counter(mon)   # patches requests.Session.request; mon is now the active session monitor
ad = FakeAdapter()
sdk = requests.Session()
sdk.mount("https://", ad)
b = window()
sdk.post("https://api.hyperliquid-testnet.xyz/info", json={"type": "spotMeta"}, timeout=3)
sdk.post("https://api.hyperliquid-testnet.xyz/info", json={"type": "meta"}, timeout=3)
check("SDK_SESSION_INFO_WEIGHT_ONCE", window() - b == W({"type": "spotMeta"}) + W({"type": "meta"}) and len(ad.sent) == 2,
      (window() - b, len(ad.sent)))
b = window()
sdk.post("https://api.hyperliquid-testnet.xyz/exchange", json={"action": {"type": "order"}}, timeout=3)
check("SDK_SESSION_EXCHANGE_NO_WEIGHT", window() == b, window() - b)
b = window()
sdk.get("https://api.hyperliquid-testnet.xyz/info", timeout=3)
check("SDK_SESSION_NON_POST_NO_WEIGHT", window() == b, window() - b)
# http_post riding a REAL Session (counter patched in): the counter and http_post must not both count
real_sess2 = requests.Session()
xt._SESSION = real_sess2
ad2 = FakeAdapter()
real_sess2.mount("https://", ad2)
b = window()
xt.http_post(URL, oo, 3.0)
check("HTTP_POST_ON_COUNTED_SESSION_ONCE", window() - b == W(oo) and len(ad2.sent) == 1, (window() - b, len(ad2.sent)))
b = window()
xt._post(None, state, URL, 3.0)
check("POST_ON_COUNTED_SESSION_ONCE", window() - b == W(state), window() - b)
# conservative retry accounting: a ConnectionError first attempt is counted too (2 dispatched attempts = 2x weight)
ad3 = FakeAdapter(fail_first=True)
real_sess3 = requests.Session()
xt._SESSION = real_sess3
real_sess3.mount("https://", ad3)
b = window()
xt.http_post(URL, oo, 3.0)
check("RETRY_COUNTS_EVERY_DISPATCHED_ATTEMPT", len(ad3.sent) == 2 and window() - b == 2 * W(oo), (len(ad3.sent), window() - b))
print("TOTAL=%d FAILED=%d" % (27, len(FAILED)))
sys.exit(1 if FAILED else 0)
