#!/usr/bin/env python3
"""Readiness 1: an ambiguous order send (timeout / no definitive exchange reply) must NEVER blind-resend.

The engine must first resolve whether the ORIGINAL order landed, by its client order id (cloid):
  - order status by cloid  -> open / filled / cancelled / unknown
  - fills for that cloid   -> the fill that proves it landed
Only a definitive "not on the exchange" answer allows the single recovery retry; a landed order is
reported as-is; an unreadable/ambiguous resolution HOLDS and ALERTS (no resend).

Run: HL_LIVE_ENV_FILE=/nonexistent python -u test_readiness1_ambiguous_timeout_no_blind_resend.py
Offline: fake exchange, injected read fixtures, no network, no orders, no keys.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="readiness1_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_RATE_LIMIT_COOLDOWN_MS": "0",
                       "HL_LIVE_AMBIGUOUS_SEND_RECHECK_ATTEMPTS": "3",
                       "HL_LIVE_AMBIGUOUS_SEND_RECHECK_INTERVAL_SEC": "0.01"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    mid = {"f": 100.0, "l": 100.0}
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else ({"BTC": str(mid["f"])} if mid["f"] else {})
    c.LEADER_MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else ({"BTC": str(mid["l"])} if mid["l"] else {})

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    class FakeExchange:
        """First `fail_times` physical calls raise a timeout (the ambiguous outcome); later calls fill."""

        def __init__(self, fail_times: int = 1):
            self.calls, self.fail_times = [], fail_times

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"coin": coin, "px": px, "tif": tif["limit"]["tif"], "buy": is_buy, "size": size,
                               "reduce_only": reduce_only, "cloid": (str(cloid) if cloid is not None else None)})
            if len(self.calls) <= self.fail_times:
                raise TimeoutError("read timed out")
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 99}}]}}}

    gateways = []

    def gateway(fake, ledger=None):
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
        gw._resolve_coin = lambda coin: dict(resolved)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        gateways.append(gw)
        return gw

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {"marketable_bps": 20},
                                             "wallets": {LEADER: {"enabled": True, "mode": "ON",
                                                                  "copy_mode": "fixed", "fixed_notional": 1000}}})
    seq = [0]

    def fill(side="BUY", price=100.0, size=1.0):
        seq[0] += 1
        return c.LeaderFill(f"t{seq[0]}", LEADER, "BTC", side, price, size, c.utc_now_ms() + seq[0], "TEST", 0, {})

    def send(fake, follower=100.0, order_status=None, fill_cloid=False, fills=None, unreadable=False,
             side="BUY", seeded_position=0.0):
        """One ambiguous send. order_status is the orderStatus `response.data` (or None to leave it unreadable).
        fill_cloid=True adds a fill carrying THIS send's cloid (the proof it landed)."""
        mid["f"] = follower
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)
        led = c.ManualLedger(path=tmp / f"l{seq[0]}.json")
        if seeded_position:
            sleeve = led.sleeve(LEADER, "BTC")
            sleeve.update({"direction": "LONG", "signed_size": seeded_position, "avg_entry_px": 100.0,
                           "position_id": "test-position", "opened_by_intent_id": "test-open"})
            led._recompute_net(led.data)
            led.save(touched_sleeves=[(LEADER, "BTC")])
        intent = c.IntentBuilder(c.ConfigManager(), led).build(fill(side=side))
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64   # placeholder; the fake exchange never signs
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object

        def order_status_fetcher(payload):
            if unreadable:
                raise RuntimeError("orderStatus unreadable")
            if isinstance(order_status, list):
                row = order_status[min(order_status_idx[0], len(order_status) - 1)]
                order_status_idx[0] += 1
                return row
            return order_status if order_status is not None else {"order": {"order": {}, "status": "unknown"}}

        fill_rows = list(fills or [])
        if fill_cloid:
            fill_rows.append({"coin": "BTC", "cloid": c.generate_cloid(intent.intent_id), "oid": 777, "sz": "1",
                              "px": "100", "time": c.utc_now_ms(), "hash": "0xabc", "tid": 1})

        saved_of, saved_cf = c.OPEN_ORDERS_FETCHER, c.COPY_FILLS_FETCHER
        order_status_idx = [0]
        c.OPEN_ORDERS_FETCHER = order_status_fetcher
        c.COPY_FILLS_FETCHER = lambda payload: list(fill_rows)
        try:
            gw = gateway(fake, led)
            ok, status, res = gw._send_real(intent)
            gw._append_real_attempt(intent, status, res)
            gw.signal_ambiguous_send_attempt_written(res.get("timing", {}))
            thread = gw._ambiguous_send_recheck_thread
            if thread is not None:
                thread.join(timeout=2.0)
        finally:
            c.HLAccount, c.HLExchange = saved
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
            c.OPEN_ORDERS_FETCHER, c.COPY_FILLS_FETCHER = saved_of, saved_cf
        return ok, status, res, intent

    cloid_of = lambda intent: c.generate_cloid(intent.intent_id)

    # ---- B1: the original order is still OPEN -> no resend, reported resting -----------------------
    fake = FakeExchange()
    cl = None
    ok, status, res, intent = send(fake, order_status={"order": {"order": {"oid": 4242, "limitPx": "100"},
                                                              "status": "open"}})
    cl = cloid_of(intent)
    check("B1_OPEN_NO_BLIND_RESEND", len(fake.calls) == 1, f"order calls={len(fake.calls)}")
    check("B2_OPEN_REPORTED_RESTING", ok and status == "ORDER_RESTING" and str(res.get("oid")) == "4242",
          f"{ok} {status} {res.get('oid')}")
    check("B3_OPEN_RESULT_NAMES_AMBIGUOUS_SEND", "AMBIGUOUS_SEND" in str(res.get("terminal_state", "")),
          str(res.get("terminal_state")))
    check("B4_OPEN_RESOLVED_BY_THIS_CLOID", fake.calls and fake.calls[0]["cloid"] == cl, str(fake.calls))

    # ---- B5: a fill carries the original cloid -> no resend, reported filled ----------------------
    fake = FakeExchange()
    ok, status, res, intent = send(fake, order_status={"order": {"order": {}, "status": "unknown"}}, fill_cloid=True)
    check("B5_FILL_MATCH_NO_BLIND_RESEND", len(fake.calls) == 1, f"order calls={len(fake.calls)}")
    check("B6_FILL_MATCH_REPORTED_FILLED", ok and status == "ORDER_FILLED", f"{ok} {status}")

    # ---- B7: orderStatus says filled -> no resend -----------------------------------------------
    fake = FakeExchange()
    ok, status, res, intent = send(fake, order_status={"order": {"order": {"oid": 555}, "status": "filled"}})
    check("B7_STATUS_FILLED_NO_BLIND_RESEND", len(fake.calls) == 1 and ok and status == "ORDER_FILLED",
          f"order calls={len(fake.calls)} {ok} {status}")

    # ---- B8: the order is definitively CANCELLED -> the one recovery retry may run ----------------
    fake = FakeExchange()
    ok, status, res, intent = send(fake, order_status={"order": {"order": {}, "status": "canceled"}})
    check("B8_CANCELLED_ALLOWS_ONE_RETRY", len(fake.calls) == 2
          and fake.calls[0]["cloid"] == fake.calls[1]["cloid"] == cloid_of(intent),
          f"order calls={len(fake.calls)} cloids={[r['cloid'] for r in fake.calls]}")

    # ---- B9: an unreadable resolution -> hold + alert, no resend ---------------------------------
    fake = FakeExchange()
    ok, status, res, intent = send(fake, unreadable=True)
    check("B9_UNREADABLE_HOLDS_NO_RESEND", len(fake.calls) == 1, f"order calls={len(fake.calls)}")
    check("B10_UNREADABLE_ALERTS", str(res.get("terminal_state")) == "SEND_OUTCOME_UNKNOWN_HOLD",
          str(res.get("terminal_state")))
    hold_rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
                 if r.get("event") == "AMBIGUOUS_SEND" and r.get("terminal_state") == "SEND_OUTCOME_UNKNOWN_HOLD"]
    check("B11_UNREADABLE_ALERT_ROW_WRITTEN", len(hold_rows) == 1
          and "MANUAL_REVIEW_CHECK_ORDER_BY_CLOID" in str(hold_rows[0].get("operator_action") or hold_rows[0].get("action")),
          str(hold_rows)[:300])
    manual_alerts = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
                     if r.get("status") == "SEND_OUTCOME_UNKNOWN_MANUAL_ALERT"]
    latest_b9_attempt = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV) if r.get("intent_id") == intent.intent_id][-1]
    check("B16_UNKNOWN_OUTCOME_GETS_BOUNDED_RECHECK_ALERT", len(manual_alerts) == 1
          and "3 deferred CLOID rechecks" in str(manual_alerts[0].get("notes"))
          and latest_b9_attempt.get("status") == "ORDER_UNKNOWN"
          and latest_b9_attempt.get("terminal_state") == "SEND_OUTCOME_UNKNOWN_MANUAL_ALERT",
          f"alerts={len(manual_alerts)} latest={latest_b9_attempt}")

    # ---- B12: order status "unknown" (not a definitive answer) -> hold, no resend -----------------
    fake = FakeExchange()
    ok, status, res, intent = send(fake, order_status={"order": {"order": {}, "status": "unknown"}})
    check("B12_UNKNOWN_STATUS_HOLDS_NO_RESEND", len(fake.calls) == 1
          and str(res.get("terminal_state")) == "SEND_OUTCOME_UNKNOWN_HOLD",
          f"order calls={len(fake.calls)} {res.get('terminal_state')}")

    # ---- B13: a deferred read resolves an exit as open and tracks the standing close ------------
    fake = FakeExchange()
    ok, status, res, exit_intent = send(
        fake, side="SELL", seeded_position=1.0,
        order_status=[{"order": {"order": {}, "status": "unknown"}},
                      {"order": {"order": {"oid": 8181, "limitPx": "99"}, "status": "open"}}])
    exit_gw = gateways[-1]
    standing = exit_gw._standing_closes.get(exit_intent.sleeve_id, {})
    check("B13_DEFERRED_EXIT_OPEN_TRACKED_AS_STANDING_CLOSE", len(fake.calls) == 1
          and str(standing.get("oid")) == "8181"
          and bool(standing.get("reduce_only")) == bool(res.get("reduce_only_sent")), str(standing))
    check("B14_EXIT_NOT_REGISTERED_AS_RESTING_ENTRY", not exit_gw._resting_entries, str(exit_gw._resting_entries))

    # ---- B15: a zero pending-exit TTL falls back to the bounded default -------------------------
    os.environ["HL_LIVE_PENDING_EXIT_GUARD_TTL_MS"] = "0"
    exit_gw._pending_exit_guard[exit_intent.sleeve_id] = {
        "ts_ms": c.utc_now_ms() - 31000, "position_abs_before": 1.0, "intent_id": "prior-exit"}
    with exit_gw._pending_exit_lock:
        blocked, _reason = exit_gw._pending_exit_blocked(exit_intent)
    check("B15_ZERO_TTL_DOES_NOT_BLOCK_INDEFINITELY", not blocked
          and exit_intent.sleeve_id not in exit_gw._pending_exit_guard)

    failed = [n for n, ok in RESULTS if not ok]
    for gw in gateways:
        gw.stop_ambiguous_send_rechecks()
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
