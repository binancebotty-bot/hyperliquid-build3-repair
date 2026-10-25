#!/usr/bin/env python3
"""PART 2 (rev) tests: a refused ENTRY/ADD is routed THROUGH the normal path.

Order at the point of refusal: _ensure_margin_mode -> follower_mid(force=True) ->
missed_entry_decision(bps) -> IOC within tolerance, else GTC at the leader price. No fresh mid or a
refused margin setup means NO order: a named diff plus an OPEN incident for the convergence path.

R1 stale mid then fresh mid within tolerance -> IOC.
R2 stale mid then fresh mid beyond tolerance -> GTC at the leader price, the real follower price used.
R3 no mid at all -> no order, named diff, OPEN incident.
R4 margin setup fails -> no order, named diff, OPEN incident.
R5 margin setup succeeds -> the order goes.
R6 ORD-010 with HL_LIVE_MISSED_ENTRY_RULE=0: an old ENTRY takes the rule, a fresh one does not.

Run: python test_core_deferred_entry_refusal.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
EXP = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}
RESOLVED = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
            "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="refusal_"))
    os.environ.update({"HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                       "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
                       "HL_LIVE_MM_WAIT_SEC": "2"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    mids = {"follower": 100.0, "leader": 100.0}
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else ({"BTC": str(mids["follower"])} if mids["follower"] else {})
    c.LEADER_MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else ({"BTC": str(mids["leader"])} if mids["leader"] else {})
    c.EXPOSURE_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP)
    c.LEADER_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP)
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {"marketable_bps": 20},
                                             "wallets": {LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed",
                                                                  "fixed_notional": 1000}}})
    seq = [0]

    def set_mids(follower=None, leader=None, cache=True):
        if follower is not None:
            mids["follower"] = follower
        if leader is not None:
            mids["leader"] = leader
        if cache:
            c._FOLLOWER_MIDS.update(px={}, ms=0)
            c._LEADER_MIDS.update(px={}, ms=0)

    def fill(price=100.0, age_ms=0):
        seq[0] += 1
        return c.LeaderFill("r%d" % seq[0], LEADER, "BTC", "BUY", price, 1.0,
                            c.utc_now_ms() - int(age_ms) + seq[0], "TEST", 0, {})

    class FakeExchange:
        def __init__(self, margin_ok=True):
            self.calls, self.cancels, self.margin_ok = [], [], margin_ok

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"} if self.margin_ok else {"status": "err", "response": "margin setup refused"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"px": px, "tif": tif["limit"]["tif"], "buy": is_buy, "reduce_only": reduce_only})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 9000 + len(self.calls)}}]}}}

        def cancel(self, coin, oid):
            self.cancels.append((coin, oid))
            return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}

    def gateway(fake):
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw._resolve_coin = lambda coin, allow_snapshot=False: dict(RESOLVED)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        gw._pre_send_ownership_gate = lambda intent: (True, {})
        return gw

    def core(fake):
        cc = c.LiveCopyCore(source_csv=tmp / "none.csv")
        cc.sender._resolve_coin = lambda coin, allow_snapshot=False: dict(RESOLVED)
        cc.sender._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        cc.sender._exchange_client_for_coin = lambda coin: (fake, "BTC")
        return cc

    def intent(f=None):
        return c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / ("led%d.json" % seq[0]))).build(f or fill())

    def rows(state):
        return [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("terminal_state") == state]

    def clear():
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})

    # R1 stale mid, then ONE forced fresh mid inside the tolerance -> IOC
    clear()
    set_mids(99.0, 100.0)
    c.follower_mid("BTC")
    set_mids(100.0, 100.0, cache=False)
    f1 = FakeExchange()
    o1 = gateway(f1)._missed_entry_rest_or_diff(intent(fill()), "FOLLOWER_PRICE_FRESHNESS_GATE")
    check("R1_STALE_THEN_FRESH_WITHIN_TOLERANCE_TAKES", o1.get("follower_px") == 100.0
          and o1.get("outcome") == "FILLED_AWAITING_COPY_POLL" and len(f1.calls) == 1 and f1.calls[0]["tif"] == "Ioc",
          "%s %s" % (o1, f1.calls))
    check("R1_ORDER_IS_AN_ENTRY_NOT_A_REDUCE", bool(f1.calls) and f1.calls[0]["reduce_only"] is False, str(f1.calls))

    # R2 stale mid, then a fresh mid beyond the tolerance -> GTC at the leader price
    clear()
    set_mids(99.0, 100.0)
    c.follower_mid("BTC")
    set_mids(101.0, 101.0, cache=False)
    f2 = FakeExchange()
    o2 = gateway(f2)._missed_entry_rest_or_diff(intent(fill()), "FOLLOWER_PRICE_FRESHNESS_GATE")
    check("R2_STALE_THEN_FRESH_BEYOND_TOLERANCE_RESTS_GTC", o2.get("outcome") == "MISSED_ENTRY_LIMIT_RESTED"
          and len(f2.calls) == 1 and f2.calls[0]["tif"] == "Gtc" and abs(f2.calls[0]["px"] - 100.0) < 1e-9,
          "%s %s" % (o2, f2.calls))
    check("R2_REAL_FOLLOWER_PRICE_NOT_THE_LEADER_PRICE", o2.get("follower_px") == 101.0
          and o2.get("market_px") == 101.0 and o2.get("adverse_bps") == 100.0, str(o2))

    # R3 no mid at all -> no order, named diff, OPEN incident
    clear()
    set_mids(0, 100.0)
    f3 = FakeExchange()
    i3 = intent()
    i3.reason = "no fresh follower-network (testnet) price for BTC; leader on mainnet"
    o3 = core(f3)._apply_missed_entry_rule_on_refusal(i3.fill, i3, "INTENT_NOT_SEND_ALLOWED")
    check("R3_NO_MID_MEANS_NO_ORDER", o3 is not None and o3.get("outcome") == "MISSED_ENTRY_DIFF_NO_FRESH_MID"
          and not f3.calls, "%s %s" % (o3, f3.calls))
    check("R3_NO_MID_WRITES_AN_OPEN_INCIDENT", bool(rows("MISSED_ENTRY_DIFF_NO_FRESH_MID"))
          and any(r.get("event") == c.MISSED_ENTRY_INCIDENT_EVENT for r in c.read_csv_rows(c.RECONCILIATION_CSV)),
          str(rows("MISSED_ENTRY_DIFF_NO_FRESH_MID"))[:300])

    # R4 margin setup fails -> no order, named diff, OPEN incident
    clear()
    set_mids(100.0, 100.0)
    f4 = FakeExchange(margin_ok=False)
    i4 = intent()
    o4 = core(f4)._apply_missed_entry_rule_on_refusal(i4.fill, i4, "MARGIN_MODE_UNSET")
    check("R4_MARGIN_SETUP_FAILS_MEANS_NO_ORDER", o4 is not None
          and o4.get("outcome") == "MISSED_ENTRY_DIFF_MARGIN_SETUP_FAILED" and not f4.calls,
          "%s %s" % (o4, f4.calls))
    check("R4_MARGIN_FAILURE_WRITES_AN_OPEN_INCIDENT", bool(rows("MISSED_ENTRY_DIFF_MARGIN_SETUP_FAILED"))
          and any(r.get("event") == c.MISSED_ENTRY_INCIDENT_EVENT for r in c.read_csv_rows(c.RECONCILIATION_CSV)),
          str(rows("MISSED_ENTRY_DIFF_MARGIN_SETUP_FAILED"))[:300])

    # R5 margin setup succeeds -> the order goes
    clear()
    set_mids(101.0, 101.0)
    f5 = FakeExchange()
    o5 = gateway(f5)._missed_entry_rest_or_diff(intent(fill()), "MARGIN_MODE_UNSET")
    check("R5_MARGIN_SETUP_SUCCEEDS_ORDER_GOES", o5.get("outcome") == "MISSED_ENTRY_LIMIT_RESTED"
          and len(f5.calls) == 1 and f5.calls[0]["tif"] == "Gtc" and abs(f5.calls[0]["px"] - 100.0) < 1e-9,
          "%s %s" % (o5, f5.calls))

    # R6 ORD-010: an old ENTRY takes the rule at the refusal choke point with the switch OFF; a fresh
    # one with no other refusal cause does not.
    os.environ["HL_LIVE_MISSED_ENTRY_RULE"] = "0"
    clear()
    set_mids(101.0, 101.0)
    f6 = FakeExchange()
    i6 = intent(fill(age_ms=60000))
    o6 = core(f6)._apply_missed_entry_rule_on_refusal(i6.fill, i6, "INTENT_NOT_SEND_ALLOWED")
    check("R6_ORD_010_OLD_ENTRY_TAKES_THE_RULE_WITH_SWITCH_OFF", o6 is not None
          and o6.get("cause") == "ORD_010_ENTRY_AGE_OVER_30S" and bool(f6.calls)
          and f6.calls[-1]["tif"] == "Gtc" and abs(f6.calls[-1]["px"] - 100.0) < 1e-9,
          "%s %s" % (o6, f6.calls))
    clear()
    set_mids(101.0, 101.0)
    f7 = FakeExchange()
    i7 = intent(fill(age_ms=0))
    o7 = core(f7)._apply_missed_entry_rule_on_refusal(i7.fill, i7, "INTENT_NOT_SEND_ALLOWED")
    check("R6_FRESH_ENTRY_WITH_SWITCH_OFF_DOES_NOT_TAKE_THE_RULE", o7 is None and not f7.calls,
          "%s %s" % (o7, f7.calls))

    # R7 (send-lane guard): the per-coin margin lock is held elsewhere -> the refusal path declines AT ONCE as
    # MARGIN_MODE_SETUP_PENDING, sends/rests nothing, and leaves the entry to convergence. Fails (>= 2 s here) if
    # the caller ever goes back to _ensure_margin_mode without wait_sec=0.0.
    clear()
    set_mids(100.0, 100.0)
    f8 = FakeExchange()
    cc8 = core(f8)
    held = cc8.sender._margin_mode_lock("BTC")
    held.acquire()
    try:
        t0 = time.monotonic()
        i8 = intent()
        o8 = cc8._apply_missed_entry_rule_on_refusal(i8.fill, i8, "MARGIN_MODE_UNSET")
        elapsed8 = time.monotonic() - t0
    finally:
        held.release()
    check("R7_MARGIN_SETUP_PENDING_RETURNS_AT_ONCE_WITH_LOCK_HELD",
          o8 is not None and o8.get("outcome") == "MISSED_ENTRY_DIFF_MARGIN_SETUP_PENDING" and elapsed8 < 0.5,
          "%s elapsed=%.3f" % (o8 and o8.get("outcome"), elapsed8))
    check("R7_MARGIN_SETUP_PENDING_SENDS_AND_RESTS_NOTHING",
          not f8.calls and not f8.cancels and not (c.load_json(c.RESTING_ENTRY_ORDERS_FILE, {}) or {}),
          "%s %s" % (f8.calls, c.load_json(c.RESTING_ENTRY_ORDERS_FILE, {})))
    _r7 = [r for r in rows("MISSED_ENTRY_DIFF_MARGIN_SETUP_PENDING")
           if r.get("event") == c.MISSED_ENTRY_INCIDENT_EVENT]
    check("R7_MARGIN_SETUP_PENDING_IS_NAMED_AND_RECORDED",
          bool(_r7) and "margin mode setup in flight" in str(_r7[0].get("notes")), str(_r7[:1])[:300])
    print("MEASURED::R7_ELAPSED_SEC=%.4f" % elapsed8)

    passed = sum(1 for _n, ok in RESULTS if ok)
    print("\n%d/%d passed" % (passed, len(RESULTS)))
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
