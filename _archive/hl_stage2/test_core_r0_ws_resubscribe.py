#!/usr/bin/env python3
"""R0: WS re-subscribe after restart - offline tests with a fake socket.

Proves the three R0 properties without any network or engine run:
  1. a subscribe message is sent, on open, for EVERY enabled wallet;
  2. after a reconnect the subscribe messages are re-sent, and they reflect a wallet
     enabled after the manager was built (no frozen snapshot);
  3. a userFills message reaches the hot-send handler;
  4. ws_status is NOT OK while no wallet has been acked or has delivered a message
     within the bound, and becomes OK once a subscription ack arrives.

Run: python test_core_r0_ws_resubscribe.py   # RESULT:: markers, exit 0/1.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def wait_for(pred, timeout: float = 6.0, step: float = 0.02) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(step)
    return bool(pred())


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="r0ws_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
        "HL_LIVE_WS_ENABLED": "1",
        "HL_LIVE_WS_HEARTBEAT_SEC": "3600",
        "HL_LIVE_WS_SUBSCRIBE_GRACE_MS": "150",
    })
    import HL_Live_Copy_Service_Core as c

    A = "0x" + "a" * 40
    B = "0x" + "b" * 40
    C = "0x" + "c" * 40
    enabled = [A, B]

    class FakeApp:
        def __init__(self, url, on_open=None, on_message=None, on_error=None, on_close=None):
            self.on_open = on_open
            self.on_message = on_message
            self.on_error = on_error
            self.on_close = on_close
            self.sent = []
            self._closed = threading.Event()

        def send(self, data: str) -> None:
            self.sent.append(json.loads(data))

        def run_forever(self, **kw: object) -> None:
            if self.on_open:
                self.on_open(self)
            self._closed.wait(10.0)

        def close(self) -> None:
            self._closed.set()

    class FakeWS:
        def __init__(self) -> None:
            self.apps = []

        def WebSocketApp(self, url, **kw):
            app = FakeApp(url, **kw)
            self.apps.append(app)
            return app

    def subs_of(app):
        return sorted(m["subscription"]["user"] for m in app.sent if m.get("method") == "subscribe")

    hot = []
    mgr = c.WSManager(lambda: list(enabled), c.LeaderFillIngestor(), lambda f: (hot.append(f) or True))
    mgr.enabled = True
    saved = c.websocket
    fake = FakeWS()
    c.websocket = fake
    try:
        mgr.start()
        # 1) subscribe on open, for every enabled wallet
        wait_for(lambda: len(fake.apps) >= 1 and len(fake.apps[0].sent) >= 2)
        check("R0_SUBSCRIBE_ALL_ENABLED_ON_OPEN",
              subs_of(fake.apps[0]) == sorted([c.normalise_wallet(A), c.normalise_wallet(B)]),
              "subs=%s" % (subs_of(fake.apps[0]),))

        # 3) a fill message reaches the hot-send handler
        msg = json.dumps({"channel": "userFills", "data": {
            "user": A, "fills": [{"coin": "BTC", "side": "B", "px": "100", "sz": "1",
                                  "time": c.utc_now_ms(), "tid": 1}]}})
        fake.apps[0].on_message(fake.apps[0], msg)
        check("R0_FILL_REACHES_HOT_HANDLER",
              len(hot) == 1 and hot[0].leader_wallet == c.normalise_wallet(A), "hot=%s" % (hot,))

        # 2) reconnect re-subscribes, and includes a wallet enabled in between
        enabled.append(C)
        fake.apps[0].close()
        got_new = wait_for(lambda: len(fake.apps) >= 2 and c.normalise_wallet(C) in subs_of(fake.apps[1]))
        check("R0_RESUBSCRIBE_AFTER_RECONNECT_INCLUDES_NEW_WALLET",
              got_new and subs_of(fake.apps[1]) == sorted(c.normalise_wallet(x) for x in enabled),
              "subs=%s" % (subs_of(fake.apps[1]) if len(fake.apps) >= 2 else None,))
    finally:
        mgr.stop()
        c.websocket = saved

    # 4) health: an open socket with nothing acked/delivered inside the bound is NOT OK
    h = c.WSManager([A], c.LeaderFillIngestor())
    h.enabled = True
    h._socket_open = True
    h._thread = type("T", (), {"is_alive": lambda self: True})()
    h._socket_opened_at_ms = c.utc_now_ms() - 10_000
    st = h.write_health()["ws_summary"]
    check("R0_STATUS_NOT_OK_WHEN_SILENT_OPEN_SOCKET",
          st["ws_status"] != "WS_OK" and st["subscribe_pending"] is True, str(st))

    h._on_message(json.dumps({"channel": "subscriptionResponse",
                              "data": {"subscription": {"type": "userFills", "user": A}}}))
    st2 = h.write_health()["ws_summary"]
    check("R0_STATUS_OK_AFTER_SUBSCRIPTION_ACK",
          st2["ws_status"] == "WS_OK" and st2["subscribe_acked"] == 1, str(st2))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
