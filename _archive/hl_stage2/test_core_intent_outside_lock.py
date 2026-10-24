#!/usr/bin/env python3
"""Replay throughput (run 6f): the intent audit row is written outside the send lock; every allowed intent ends in a row.

Test (1) append_order_intent runs with the send lock NOT held; (2) the row is written before send_if_allowed runs
Test (3) send_if_allowed raising leaves a BLOCKED_SEND_EXCEPTION terminal row and returns SEND_EXCEPTION
Test (4) another worker can take the send lock while a slow audit append is in progress

Run: python test_core_intent_outside_lock.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="outlock_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                   "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MOCK_SEND": "1"})
import HL_Live_Copy_Service_Core as c

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


LEADER, FOLLOWER = "0x" + "a" * 40, "0x" + "c" * 40
c.USER_WALLET = FOLLOWER
c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": 100.0}
c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
EXP = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}
c.EXPOSURE_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP)
c.LEADER_FETCHER = c.EXPOSURE_FETCHER
c.atomic_write_json(c.LIVE_CONFIG_FILE, {
    "auto_send_enabled": False, "global_controls": {"min_notional": 1},
    "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100}}})
core = c.LiveCopyCore(source_csv=tmp / "none.csv")
core._hot_stop_event.set()
for t in core._hot_threads:
    t.join(timeout=2)

order = []
held_during_append = []
real_append = core.audit.append_order_intent
other_got_lock = []


def slow_append(intent):
    held_during_append.append(core._send_lock.locked())
    order.append("append")

    def other():
        got = core._send_lock.acquire(blocking=False)
        other_got_lock.append(got)
        if got:
            core._send_lock.release()
    th = threading.Thread(target=other)
    th.start()
    th.join()
    time.sleep(0.05)
    return real_append(intent)


core.audit.append_order_intent = slow_append
real_send = core.sender.send_if_allowed
core.sender.send_if_allowed = lambda i, r="": (order.append("send"), real_send(i, r))[1]

now = c.utc_now_ms()
f1 = c.LeaderFill("ol-1", LEADER, "BTC", "BUY", 100.0, 1.0, now, "WS_CAPTURED", 0, {"oid": "9", "dir": "Open Long"})
core._process_leader_fill(f1, None, "")
check("append_runs_without_send_lock", held_during_append == [False], str(held_during_append))
check("row_written_before_send", order[:2] == ["append", "send"], str(order))
check("other_worker_can_take_lock_during_append", other_got_lock == [True], str(other_got_lock))

# a send that raises still ends in a terminal row
def boom(intent, reason=""):
    raise RuntimeError("boom in send")


core.sender.send_if_allowed = boom
f2 = c.LeaderFill("ol-2", LEADER, "BTC", "BUY", 100.0, 1.0, now + 1, "WS_CAPTURED", 0, {"oid": "10", "dir": "Open Long"})
ok, status, intent = core._process_leader_fill(f2, None, "")
rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("leader_fill_id") == "ol-2"] if hasattr(c, "RECONCILIATION_CSV") else []
check("exception_returns_send_exception", (not ok) and status == "SEND_EXCEPTION", status)
check("exception_leaves_terminal_row", any("BLOCKED_SEND_EXCEPTION" in str(r) for r in rows), str(rows)[:300])

# A known exchange result must survive an exception in later audit bookkeeping.
core.sender.send_if_allowed = real_send
core.cfg.master_switch_now = lambda: True
core.cfg.liq_parity_enabled = lambda: False
core.sender.sender_key_invalid = False
core.sender._pre_send_ownership_gate = lambda _intent: (True, {})
core.sender.signal_ambiguous_send_attempt_written = lambda _timing: None
os.environ["HL_LIVE_MOCK_SEND"] = "0"
real_build = core.intent_builder.build


def allowed_build(fill):
    intent = real_build(fill)
    intent.decision = "ENTRY_ALLOWED"
    return intent


core.intent_builder.build = allowed_build
core.sender._send_real = lambda intent, timing: (True, "ORDER_FILLED", {
    "exchange_called": True, "exchange_response": {"status": "ok"}, "oid": "safe-test-oid",
    "timing": timing, "wire_size": intent.copy_size, "limit_px": intent.fill.price,
})


def fail_attempt_append(*_args, **_kwargs):
    raise RuntimeError("injected audit bookkeeping failure")


core.sender._append_real_attempt = fail_attempt_append
f3 = c.LeaderFill("ol-3", LEADER, "BTC", "BUY", 100.0, 1.0, now + 2, "WS_CAPTURED", 0,
                   {"oid": "11", "dir": "Open Long"})
ok, status, _intent = core._process_leader_fill(f3, None, "")
rows3 = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("leader_fill_id") == "ol-3"]
check("accepted_result_survives_bookkeeping_error", ok and status == "ORDER_FILLED",
      status + ": " + str(rows3[-1].get("notes", "") if rows3 else "no audit row"))
check("bookkeeping_error_alert_identifies_order", any(
    r.get("status") == "POST_SEND_BOOKKEEPING_FAILED" and r.get("exchange_order_id") == "safe-test-oid"
    for r in rows3), str(rows3)[:300])
check("accepted_result_not_mislabeled_blocked", not any(
    r.get("status") == "BLOCKED_SEND_EXCEPTION" for r in rows3), str(rows3)[:300])

# A fallback GTC accepted after an IOC miss must remain visible if its bookkeeping raises.
gw = core.sender
gw._send_real = c.SenderGateway._send_real.__get__(gw, c.SenderGateway)
gw._resolve_coin = lambda _coin: {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3,
                                 "price_max_decimals": 2, "min_size": 0, "perp_dexs": None}
gw.cfg.marketable_bps = lambda: 20
gw.cfg.max_close_adverse_diff_pct = lambda: 0
gw.cfg.min_notional = lambda: 10
gw.cfg.max_order_notional = lambda: 1000
gw._get_exchange_client = lambda *_a, **_k: object()
gw._exchange_client_has_symbol = lambda *_a, **_k: True
gw._pre_exchange_asset_safety = lambda *_a, **_k: (True, {})
gw._validate_final_wire_order = lambda *_a, **_k: (True, {})
gw._begin_pending_send = lambda *_a, **_k: None
gw._ensure_margin_mode = lambda *_a, **_k: None
gw._already_resting_block = lambda *_a, **_k: None
gw.resting_entry_for = lambda *_a, **_k: None
gw._resting_entry_result = lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("injected GTC bookkeeping failure"))
responses = [
    {"status": "ok", "response": {"data": {"statuses": [{"error": "could not immediately match"}]}}},
    {"status": "ok", "response": {"data": {"statuses": [{"resting": {"oid": "safe-test-gtc-oid"}}]}}},
]
sent_tifs = []
def fake_place(*args, **_kwargs):
    sent_tifs.append(args[5])
    return responses.pop(0)
gw._place_order = fake_place
old_missed = c.missed_entry_decision
c.missed_entry_decision = lambda *_a, **_k: {"ok": True, "take": True, "desired_px": 100.0, "cap_px": 101.0}
os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64  # test placeholder; no signer or network client is used
os.environ["HL_LIVE_ENTRY_IOC_RETRY_BPS"] = "20"
c.HLAccount, c.HLExchange = object, object
f4 = c.LeaderFill("ol-4", LEADER, "BTC", "BUY", 100.0, 1.0, now + 3, "WS_CAPTURED", 0,
                   {"oid": "12", "dir": "Open Long"})
gtc_intent = real_build(f4)
gtc_intent.decision = "ENTRY_ALLOWED"
gtc_intent.copy_side, gtc_intent.copy_size, gtc_intent.copy_notional = "BUY", 1.0, 100.0
gtc_ok, gtc_status, gtc_result = gw._send_real(gtc_intent, {"send_cloid": "safe-test-gtc-cloid",
                                                            "send_attempt_id": "safe-test-gtc-attempt"})
c.missed_entry_decision = old_missed
check("accepted_fallback_gtc_survives_bookkeeping_error",
      sent_tifs == ["Ioc", "Gtc"] and gtc_ok and gtc_status == "ORDER_RESTING"
      and gtc_result.get("oid") == "safe-test-gtc-oid",
      f"tifs={sent_tifs} status={gtc_status} result={gtc_result}")
check("accepted_fallback_gtc_has_manual_reconciliation", any(
    r.get("status") == "POST_SEND_BOOKKEEPING_FAILED" and r.get("exchange_order_id") == "safe-test-gtc-oid"
    for r in c.read_csv_rows(c.RECONCILIATION_CSV)), "no GTC bookkeeping alert")

core.stop()
failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
