"""Accepted exchange results survive post-acceptance bookkeeping errors, with the failure injected
UNDER _queue_exit_recovery_if_needed (B20 replaces the whole method, so neither the
EXIT_RECOVERY_QUEUE_FAILED row nor the accepted-result guard is ever exercised).

A: raise inside the recovery bookkeeping's own try -> EXIT_RECOVERY_QUEUE_FAILED row, result survives.
B: raise after acceptance, before that try -> outer guard returns the accepted result and writes
   POST_SEND_BOOKKEEPING_FAILED. No retry is ever issued.

Run: HL_LIVE_ENV_FILE=/nonexistent python -u test_readiness1_bookkeeping_survival.py
Offline: fake exchange, injected fixtures, no network, no orders, no keys.
"""
import os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="bksurv_"))
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

    class HalfFillExchange:
        """Half-fills the close, so the remaining half drives the post-acceptance recovery bookkeeping."""
        def __init__(self):
            self.calls = []

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"coin": coin, "px": px, "size": size, "reduce_only": reduce_only})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size * 0.5), "avgPx": str(px), "oid": 99}}]}}}

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {"marketable_bps": 20},
                                             "wallets": {LEADER: {"enabled": True, "mode": "ON",
                                                                  "copy_mode": "fixed", "fixed_notional": 1000}}})
    seq = [0]

    def send(on_gateway):
        seq[0] += 1
        mid["f"] = 100.0
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)
        led = c.ManualLedger(path=tmp / ("l%d.json" % seq[0]))
        sleeve = led.sleeve(LEADER, "BTC")
        sleeve.update({"direction": "LONG", "signed_size": 1.0, "avg_entry_px": 100.0,
                       "position_id": "test-position", "opened_by_intent_id": "test-open"})
        led._recompute_net(led.data)
        led.save(touched_sleeves=[(LEADER, "BTC")])
        fill = c.LeaderFill("t%d" % seq[0], LEADER, "BTC", "SELL", 100.0, 1.0,
                            c.utc_now_ms() + seq[0], "TEST", 0, {})
        intent = c.IntentBuilder(c.ConfigManager(), led).build(fill)
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
        c.atomic_write_json(c.STANDING_CLOSES_FILE, {})
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
        fake = HalfFillExchange()
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), led)
        gw._resolve_coin = lambda coin: dict(resolved)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        on_gateway(gw)
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        try:
            ok, status, res = gw._send_real(intent)
            gw._append_real_attempt(intent, status, res)
        finally:
            c.HLAccount, c.HLExchange = saved
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        return ok, status, res, intent, fake

    def rows(status, intent_id):
        return [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
                if r.get("status") == status and r.get("intent_id") == intent_id]

    # A: raise INSIDE _queue_exit_recovery_if_needed's own try (line 5417's _close_wire_plan call).
    #    _close_wire_plan is also called pre-send (line 6666, outside any try), so fail only the 2nd call.
    def fail_close_plan(gw):
        real = gw._close_wire_plan
        calls = [0]
        def raiser(*a, **k):
            calls[0] += 1
            if calls[0] >= 2:
                raise RuntimeError("injected exit-recovery bookkeeping failure")
            return real(*a, **k)
        gw._close_wire_plan = raiser
    ok, status, res, intent, fake = send(fail_close_plan)
    qf = rows("EXIT_RECOVERY_QUEUE_FAILED", intent.intent_id)
    check("A1_RECOVERY_BOOKKEEPING_FAILURE_ROW_WRITTEN", len(qf) == 1
          and "injected exit-recovery bookkeeping failure" in str(qf[0].get("notes")), str(qf)[:300])
    check("A2_ACCEPTED_FILL_SURVIVES_BOOKKEEPING_FAILURE",
          ok and status == "ORDER_FILLED" and str(res.get("oid")) == "99",
          "ok=%r status=%r oid=%r" % (ok, status, res.get("oid")))
    check("A3_NO_RETRY_AFTER_BOOKKEEPING_FAILURE", len(fake.calls) == 1, "calls=%d" % len(fake.calls))

    # B: raise after acceptance, escaping to the outer guard
    def fail_after_accept(gw):
        def raiser(*_a, **_k):
            raise RuntimeError("injected post-acceptance bookkeeping failure")
        gw._filled_size = raiser
    ok, status, res, intent, fake = send(fail_after_accept)
    pa = rows("POST_SEND_BOOKKEEPING_FAILED", intent.intent_id)
    check("B1_ESCAPED_BOOKKEEPING_FAILURE_ALERTED", len(pa) == 1
          and str(pa[0].get("exchange_order_id")) == "99"
          and pa[0].get("terminal_state") == "ORDER_FILLED", str(pa)[:300])
    check("B2_ACCEPTED_RESULT_STILL_RETURNED",
          ok and status == "ORDER_FILLED" and str(res.get("oid")) == "99"
          and "exchange outcome preserved" in str(res.get("notes", "")),
          "ok=%r status=%r oid=%r notes=%r" % (ok, status, res.get("oid"), res.get("notes")))
    check("B3_NO_RETRY_AFTER_ESCAPED_FAILURE", len(fake.calls) == 1, "calls=%d" % len(fake.calls))

    failed = [n for n, okk in RESULTS if not okk]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
