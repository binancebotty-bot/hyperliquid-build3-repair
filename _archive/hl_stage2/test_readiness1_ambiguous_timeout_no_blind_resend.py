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
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_RATE_LIMIT_COOLDOWN_MS": "0"})
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

    def gateway(fake):
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw._resolve_coin = lambda coin: dict(resolved)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        return gw

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {"marketable_bps": 20},
                                             "wallets": {LEADER: {"enabled": True, "mode": "ON",
                                                                  "copy_mode": "fixed", "fixed_notional": 1000}}})
    seq = [0]

    def fill(side="BUY", price=100.0, size=1.0):
        seq[0] += 1
        return c.LeaderFill(f"t{seq[0]}", LEADER, "BTC", side, price, size, c.utc_now_ms() + seq[0], "TEST", 0, {})

    def send(fake, follower=100.0, order_status=None, fill_cloid=False, fills=None, unreadable=False):
        """One ambiguous send. order_status is the orderStatus `response.data` (or None to leave it unreadable).
        fill_cloid=True adds a fill carrying THIS send's cloid (the proof it landed)."""
        mid["f"] = follower
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)
        led = c.ManualLedger(path=tmp / f"l{seq[0]}.json")
        intent = c.IntentBuilder(c.ConfigManager(), led).build(fill())
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64   # placeholder; the fake exchange never signs
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object

        def order_status_fetcher(payload):
            if unreadable:
                raise RuntimeError("orderStatus unreadable")
            return order_status if order_status is not None else {"order": {"order": {}, "status": "unknown"}}

        fill_rows = list(fills or [])
        if fill_cloid:
            fill_rows.append({"coin": "BTC", "cloid": c.generate_cloid(intent.intent_id), "oid": 777, "sz": "1",
                              "px": "100", "time": c.utc_now_ms(), "hash": "0xabc", "tid": 1})

        saved_of, saved_cf = c.OPEN_ORDERS_FETCHER, c.COPY_FILLS_FETCHER
        c.OPEN_ORDERS_FETCHER = order_status_fetcher
        c.COPY_FILLS_FETCHER = lambda payload: list(fill_rows)
        try:
            ok, status, res = gateway(fake)._send_real(intent)
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
    check("B8_CANCELLED_ALLOWS_ONE_RETRY", len(fake.calls) == 2, f"order calls={len(fake.calls)}")

    # ---- B9: an unreadable resolution -> hold + alert, no resend ---------------------------------
    fake = FakeExchange()
    ok, status, res, intent = send(fake, unreadable=True)
    check("B9_UNREADABLE_HOLDS_NO_RESEND", len(fake.calls) == 1, f"order calls={len(fake.calls)}")
    check("B10_UNREADABLE_ALERTS", str(res.get("terminal_state")) == "SEND_OUTCOME_UNKNOWN_HOLD",
          str(res.get("terminal_state")))
    hold_rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
                 if r.get("terminal_state") == "SEND_OUTCOME_UNKNOWN_HOLD"]
    check("B11_UNREADABLE_ALERT_ROW_WRITTEN", len(hold_rows) == 1
          and "MANUAL_REVIEW_CHECK_ORDER_BY_CLOID" in str(hold_rows[0].get("operator_action") or hold_rows[0].get("action")),
          str(hold_rows)[:300])

    # ---- B12: order status "unknown" (not a definitive answer) -> hold, no resend -----------------
    fake = FakeExchange()
    ok, status, res, intent = send(fake, order_status={"order": {"order": {}, "status": "unknown"}})
    check("B12_UNKNOWN_STATUS_HOLDS_NO_RESEND", len(fake.calls) == 1
          and str(res.get("terminal_state")) == "SEND_OUTCOME_UNKNOWN_HOLD",
          f"order calls={len(fake.calls)} {res.get('terminal_state')}")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
