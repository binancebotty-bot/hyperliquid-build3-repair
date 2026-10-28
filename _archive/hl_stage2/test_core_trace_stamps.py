#!/usr/bin/env python3
"""Fill trace stage stamps: ws_received_ms and send_real_started_ms on the proc_end/stage rows.

Test (1) a fill parsed from a websocket message carries ws_received_ms; a polled fill and a synthetic catch-up net fill do not (None)
Test (2) a real send stamps send_real_started_ms (just before exchange.order); a blocked send does not

Run: python test_core_trace_stamps.py   # RESULT:: markers, exit 0/1. Offline: fake exchange, no network, no orders.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from collections import deque
from pathlib import Path
from test_offline_send_fixture import arm_offline_send, SleeveLedgerStub

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
LEADER = "0x" + "d" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


tmp = Path(tempfile.mkdtemp(prefix="tracestamps_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                   "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_HL_PRIVATE_KEY": "0x" + "1" * 64,
                   "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_WS_ENABLED": "0"})
import requests  # noqa: E402


def offline(*a, **k):
    raise RuntimeError("offline test: no network")


requests.post = offline
import HL_Live_Copy_Service_Core as c  # noqa: E402

c.requests.post = offline
c.USER_WALLET = "0x" + "c" * 40
c.HLAccount, c.HLExchange = object, object  # non-None so _send_real proceeds to the stubbed client
c.follower_mid = lambda coin: 100.0
c.leader_mid = lambda coin, use_cached=False: 100.0
c.follower_position_mark = lambda coin: 100.0

core = object.__new__(c.LiveCopyCore)
core._fill_trace_condition = threading.Condition()
core._fill_trace_buffer = deque()
core._fill_trace_dropped = 0


def stages(fill):
    core._fill_trace_buffer.clear()
    core._fill_trace("proc_end", fill)
    return json.loads(core._fill_trace_buffer[-1])["stage_stamps"]


# (1) websocket fill vs polled fill vs synthetic catch-up fill
ws = c.WSManager.__new__(c.WSManager)
ws.ingestor = c.LeaderFillIngestor()
ws.hot_fill_handler = None
ws.queue = __import__("queue").Queue()
ws.last_msg_ms = {}
ws._message_errors = 0
c.utc_now_ms = lambda: 1_234_567
msg = {"channel": "user", "data": {"user": LEADER, "fills": [
    {"coin": "BTC", "side": "B", "px": "100", "sz": "1", "time": 1_234_000, "oid": 7, "tid": 70, "dir": "Open Long",
     "startPosition": "0"}]}}
ws._on_message(json.dumps(msg))
ws_fill = ws.queue.get_nowait()
polled = c.LeaderFillIngestor.parse_fill(LEADER, {"coin": "ETH", "side": "B", "px": "100", "sz": "1", "time": 1_000_000,
                                                  "oid": 8, "tid": 80, "dir": "Open Long", "startPosition": "0"}, "POLL")
synthetic = c.LeaderFill("syn", LEADER, "SOL", "BUY", 100.0, 1.0, 1_000, "POLL", 0, {"catchup_net": True})
check("ws_fill_carries_ws_received_ms", stages(ws_fill).get("ws_received_ms") == 1_234_567, str(stages(ws_fill)))
check("polled_fill_has_no_ws_received_ms", "ws_received_ms" in stages(polled) and stages(polled)["ws_received_ms"] is None,
      str(stages(polled)))
check("synthetic_catchup_fill_has_no_ws_received_ms", "ws_received_ms" in stages(synthetic) and stages(synthetic)["ws_received_ms"] is None, str(stages(synthetic)))

# (2) real send vs blocked send
class FakeExchange:
    def __init__(self):
        self.calls = 0

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        self.calls += 1
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
            {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}]}}}


RESOLVED = {"ok": True, "sdk_coin": "ZRO", "sz_decimals": 2, "price_max_decimals": 4, "perp_dexs": [""],
            "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}


def send(tag, block):
    fake = FakeExchange()
    gw = c.SenderGateway(arm_offline_send(c, [LEADER]), c.AuditLogWriter())
    gw._resolve_coin = lambda coin: dict(RESOLVED)
    gw._get_exchange_client = lambda *a, **k: fake
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._validate_final_wire_order = (lambda *a, **k: (False, {"status": "WIRE_BLOCKED", "error": "", "exchange_response": {},
                                                              "oid": "", "exchange_called": False, "timing": a[-1]})
                                     if block else (True, {}))
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._ensure_margin_mode = lambda *a, **k: None
    gw._fresh_exchange_net = lambda coin: 0.0
    gw.ledger = SleeveLedgerStub()
    i = object.__new__(c.Intent)
    i.intent_id = "i-" + tag
    i.fill = c.LeaderFill("fid-" + tag, LEADER, "ZRO", "BUY", 100.0, 10.0, 1, "WS_CAPTURED", 1_234_567, {})
    i.copy_side, i.copy_size, i.copy_notional = "BUY", 2.0, 200.0
    i.copy_mode, i.wallet_mode, i.decision, i.reason = "fixed", "ON", "ENTRY_ALLOWED", "ENTRY"
    i.sleeve_id, i.position_id, i.position_direction_before = "s-" + tag, "p-" + tag, "FLAT"
    i.wallet_position_before = i.coin_net_before = 0.0
    i.reduce_only_intended = i.reduce_only_sent_planned = False
    i.created_at_ms, i.notes = 1, "lifecycle=ENTRY"
    ok, status, result = gw._send_real(i)
    gw._append_real_attempt(i, status, result)
    return fake, i, status


fake, intent, status = send("real", False)
sr = stages(intent.fill)
check("real_send_called_exchange", fake.calls == 1, status)
check("real_send_stamps_send_real_started_ms", isinstance(sr.get("send_real_started_ms"), int) and sr["send_real_started_ms"] > 0, str(sr))
fake, intent, status = send("blocked", True)
sb = stages(intent.fill)
check("blocked_send_did_not_call_exchange", fake.calls == 0, status)
check("blocked_send_has_no_send_real_started_ms", "send_real_started_ms" in sb and sb["send_real_started_ms"] is None, str(sb))

failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
