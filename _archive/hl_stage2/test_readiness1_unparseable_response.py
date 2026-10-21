"""An UNPARSEABLE order reply (no exception, a body the parser cannot read) must reach the bounded
CLOID recheck and end in a manual alert. The existing B16 covers the unreadable-READ path only.

STATUS ON 97120af: RED by design (U2/U3/U4 fail) - the routing guard does not exist; see GAP_unparseable_reply_no_recheck.md. Kept out of any green suite.

Run: HL_LIVE_ENV_FILE=/nonexistent python -u test_readiness1_unparseable_response.py
Offline: fake exchange, injected fixtures, no network, no orders, no keys.
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


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="unparseable_"))
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

    class UnparseableExchange:
        """200 with a body the order parser cannot read: no statuses, no error."""
        def __init__(self):
            self.calls = []

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"coin": coin, "px": px, "size": size})
            return {"status": "ok", "response": {"type": "order", "data": {}}}

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {"marketable_bps": 20},
                                             "wallets": {LEADER: {"enabled": True, "mode": "ON",
                                                                  "copy_mode": "fixed", "fixed_notional": 1000}}})
    led = c.ManualLedger(path=tmp / "l1.json")
    fill = c.LeaderFill("t1", LEADER, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms() + 1, "TEST", 0, {})
    intent = c.IntentBuilder(c.ConfigManager(), led).build(fill)
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
    c.atomic_write_json(c.STANDING_CLOSES_FILE, {})
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64  # placeholder; the fake exchange never signs

    def unreadable_order_status(payload):   # the read side never resolves the cloid either
        raise RuntimeError("orderStatus unreadable")
    saved_of, saved_cf = c.OPEN_ORDERS_FETCHER, c.COPY_FILLS_FETCHER
    c.OPEN_ORDERS_FETCHER = unreadable_order_status
    c.COPY_FILLS_FETCHER = lambda payload: []

    fake = UnparseableExchange()
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), led)
    gw._resolve_coin = lambda coin: dict(resolved)
    gw._get_exchange_client = lambda *a, **k: fake
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._validate_final_wire_order = lambda *a, **k: (True, {})
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._exchange_client_for_coin = lambda coin: (fake, "BTC")

    saved = c.HLAccount, c.HLExchange
    c.HLAccount, c.HLExchange = object, object
    try:
        ok, status, res = gw._send_real(intent)
        gw._append_real_attempt(intent, status, res)
        gw.signal_ambiguous_send_attempt_written(res.get("timing", {}))
        thread = gw._ambiguous_send_recheck_thread
        if thread is not None:
            thread.join(timeout=5.0)
    finally:
        c.HLAccount, c.HLExchange = saved
        os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        c.OPEN_ORDERS_FETCHER, c.COPY_FILLS_FETCHER = saved_of, saved_cf

    attempts = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV) if r.get("intent_id") == intent.intent_id]
    latest = attempts[-1] if attempts else {}
    manual_alerts = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
                     if r.get("status") == "SEND_OUTCOME_UNKNOWN_MANUAL_ALERT"
                     and r.get("intent_id") == intent.intent_id]

    check("U1_UNPARSEABLE_REPLY_IS_ORDER_UNKNOWN", latest.get("status") == "ORDER_UNKNOWN", str(latest)[:400])
    check("U2_UNPARSEABLE_REPLY_ENTERS_BOUNDED_RECHECK", thread is not None, "recheck thread=%r" % (thread,))
    check("U3_UNPARSEABLE_REPLY_ENDS_IN_MANUAL_ALERT", len(manual_alerts) == 1
          and "deferred CLOID rechecks" in str(manual_alerts[0].get("notes")), str(manual_alerts)[:300])
    check("U4_UNPARSEABLE_REPLY_ATTEMPT_MARKED_MANUAL_ALERT",
          latest.get("terminal_state") == "SEND_OUTCOME_UNKNOWN_MANUAL_ALERT", str(latest)[:400])
    check("U5_NO_BLIND_RESEND", len(fake.calls) == 1, "order calls=%d" % len(fake.calls))

    gw.stop_ambiguous_send_rechecks()
    failed = [n for n, okk in RESULTS if not okk]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
