#!/usr/bin/env python3
"""rw16: (1) a coin whose IOC keeps finding no match is PARKED, not re-fired every intent; (2) unresolved-symbol error rows are
rate-limited per symbol per window while a genuine exchange error still logs every time; (3) builder-dex (XYZ:*) symbols never
reach the send path.

P1 three consecutive IOC no-match rejects on one coin use HL_LIVE_IOC_NO_MATCH_PARK_MS (default 900 s) instead of the short
   retry window, write ONE PARKED_IOC_NO_MATCH row, and the next intent for that coin is skipped with no exchange call.
P2 a successful send (ORDER_FILLED or ORDER_RESTING) clears the counter, so a coin that trades again never parks.
P3 repeated MARGIN_MODE_UNSET symbol-unresolved rows for one symbol collapse to one per
   HL_LIVE_SYMBOL_UNRESOLVED_LOG_WINDOW_MS; a genuine exchange error is never suppressed.
P4 an XYZ:* intent is refused at intent admission with no exchange call; a normal coin still sends.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw16_park.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. No network, no orders: every send goes to a fake exchange.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="rw16_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_INTENT_DURABLE_WAIT_MS": "2000",
                       "HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_MISSED_ENTRY_RULE": "0",
                       "HL_LIVE_ENTRY_IOC_RETRY_BPS": "0", "HL_LIVE_MAX_ENTRY_IOC_RETRY_BPS": "0"})
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100", "SOL": "100", "XYZ:PLATINUM": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    c.HLAccount, c.HLExchange = object, object

    def disk_rows(path):
        if not path.exists():
            return []
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
    FILLED = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"filled": {"totalSz": "1.0", "avgPx": "100.0", "oid": 3}}]}}}
    RESTING = {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 9}}]}}}
    NOMATCH = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"error": "Order could not immediately match against any resting orders. asset=750035"}]}}}

    class Ex:
        def __init__(self, replies):
            self.replies, self.calls = list(replies), []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"coin": coin, "tif": tif["limit"]["tif"]})
            return self.replies.pop(0) if self.replies else RESTING

    def gw(ex):
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%d.json" % id(ex))))
        g._resolve_coin = lambda coin: dict(resolved, sdk_coin=coin)
        g._get_exchange_client = lambda *a, **k: ex
        g._exchange_client_has_symbol = lambda *a, **k: True
        g._validate_final_wire_order = lambda *a, **k: (True, {})
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._exchange_client_for_coin = lambda coin: (ex, coin)
        g._pre_send_ownership_gate = lambda it: (True, {})
        g.leader_reduced_since = lambda f: 0
        g._margin_mode_done = {"BTC", "ETH", "SOL", "XYZ:PLATINUM"}
        g.cfg.master_switch_now = lambda: True
        g.cfg.liq_parity_enabled = lambda: False
        return g

    seq = [0]

    def mk_intent(coin="BTC", side="BUY", lifecycle="ENTRY", decision="ENTRY_ALLOWED"):
        seq[0] += 1
        iid = "p%d" % seq[0]
        fill = c.LeaderFill("f_" + iid, A, coin, side, 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"dir": "Open Long"})
        it = c.Intent(iid, fill, side, 1.0, 100.0, "ON", "fixed", decision, lifecycle,
                      "sleeve:%s:%s" % (A, coin), "", "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(),
                      "lifecycle=%s;" % lifecycle)
        c.AuditLogWriter().append_order_intent(it)  # intent row on disk first (durable barrier)
        return it

    def recon(intent_id):
        return [r for r in disk_rows(c.RECONCILIATION_CSV) if r.get("intent_id") == intent_id]

    def expire(g, coin):
        """Live intents arrive 20-30 s apart, so the short window has run out before the next one: age it out."""
        g._ioc_no_match_until_ms[coin] = 0

    # ---- P1/P2: park after N consecutive no-match rejects, cleared by a successful send -------------------------
    ex = Ex([NOMATCH, NOMATCH, NOMATCH])
    g = gw(ex)
    out = []
    for i in range(3):
        out.append(g.send_if_allowed(mk_intent()))
        if i < 2:
            expire(g, "btc")
    check("P1_THREE_REJECTS_EACH_SENT_ONCE",
          [s for _, s in out] == ["ORDER_REJECTED"] * 3 and len(ex.calls) == 3, "%s calls=%d" % (out, len(ex.calls)))
    check("P1_STREAK_COUNTS_REJECTS", g._ioc_no_match_streak.get("btc") == 3, str(g._ioc_no_match_streak))
    left_ms = g._ioc_no_match_until_ms.get("btc", 0) - c.utc_now_ms()
    check("P1_THIRD_REJECT_PARKS_LONG", left_ms > 600000, "window left=%d ms" % left_ms)
    parked = [r for r in disk_rows(c.RECONCILIATION_CSV) if r.get("terminal_state") == "PARKED_IOC_NO_MATCH"]
    check("P1_ONE_PARK_ROW", len(parked) == 1 and parked[0].get("coin") == "btc", str(parked))
    n_calls = len(ex.calls)
    sent, status = g.send_if_allowed(mk_intent())
    check("P1_NEXT_INTENT_SKIPPED_NO_EXCHANGE_CALL",
          not sent and status == "SKIPPED_IOC_NO_IMMEDIATE_MATCH" and len(ex.calls) == n_calls, "%s %s calls=%d" % (sent, status, len(ex.calls)))
    check("P1_SHORT_WINDOW_NOT_USED_WHILE_PARKED",
          g._ioc_no_match_until_ms.get("btc", 0) - c.utc_now_ms() > 600000, str(g._ioc_no_match_until_ms))

    for coin, ok_reply, want in (("ETH", FILLED, "ORDER_FILLED"), ("SOL", RESTING, "ORDER_RESTING")):
        ex2 = Ex([NOMATCH, NOMATCH, ok_reply, NOMATCH, NOMATCH])
        g2 = gw(ex2)
        outs = []
        for i in range(3):
            outs.append(g2.send_if_allowed(mk_intent(coin=coin)))
            if i < 2:
                expire(g2, coin.lower())
        check("P2_%s_STREAK_TWO_BEFORE_SUCCESS" % coin, outs[2][1] == want, str(outs))
        check("P2_%s_SUCCESS_CLEARS_COUNTER" % coin, coin.lower() not in g2._ioc_no_match_streak,
              str(g2._ioc_no_match_streak))
        # two fresh rejects must stay on the SHORT window: the counter really restarted
        for i in range(2):
            g2.send_if_allowed(mk_intent(coin=coin))
            if i < 1:
                expire(g2, coin.lower())
        left = g2._ioc_no_match_until_ms.get(coin.lower(), 0) - c.utc_now_ms()
        check("P2_%s_COUNTER_RESTARTS_SHORT_WINDOW" % coin,
              g2._ioc_no_match_streak.get(coin.lower()) == 2 and 0 < left <= 15000, "streak=%s left=%d" % (g2._ioc_no_match_streak, left))

    # ---- P3: unresolved-symbol rows collapse per symbol per window; real exchange errors never do -----------------
    g3 = gw(Ex([]))
    unresolved = {"status": "SYMBOL_UNRESOLVED", "error": "GMX not in local meta cache"}

    def err_rows(text):
        return [r for r in disk_rows(c.ERRORS_CSV) if text in r.get("message", "")]

    for _ in range(3):
        g3._note_margin_symbol_unresolved("GMX", unresolved)
    check("P3_ONE_ROW_PER_SYMBOL_PER_WINDOW", len(err_rows("symbol unresolved: GMX")) == 1,
          str(err_rows("symbol unresolved: GMX")))
    g3._note_margin_symbol_unresolved("TRX", unresolved)
    check("P3_OTHER_SYMBOL_STILL_VISIBLE", len(err_rows("symbol unresolved: TRX")) == 1, str(err_rows("symbol unresolved: TRX")))
    os.environ["HL_LIVE_SYMBOL_UNRESOLVED_LOG_WINDOW_MS"] = "1"  # window expired: the same symbol is visible again
    g3._note_margin_symbol_unresolved("GMX", unresolved)
    check("P3_WINDOW_IS_ENV_DRIVEN", len(err_rows("symbol unresolved: GMX")) == 2, str(len(err_rows("symbol unresolved: GMX"))))
    os.environ.pop("HL_LIVE_SYMBOL_UNRESOLVED_LOG_WINDOW_MS")
    for _ in range(3):
        c.log_error("margin_mode_background", RuntimeError("real exchange error: rate limited"))
    check("P3_GENUINE_EXCHANGE_ERROR_LOGS_EVERY_TIME", len(err_rows("real exchange error: rate limited")) == 3,
          str(len(err_rows("real exchange error: rate limited"))))

    # ---- P4: XYZ:* refused at intent admission, a normal coin still sends ----------------------------------------
    builder = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "builder.json"))
    xyz = builder.build(c.LeaderFill("x1", A, "XYZ:PLATINUM", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"dir": "Open Long"}))
    check("P4_XYZ_DECISION_EXCLUDED", xyz.decision == "EXCLUDED_SEND_PREFIX" and not xyz.send_allowed, "%s %s" % (xyz.decision, xyz.reason))
    ex4 = Ex([])
    g4 = gw(ex4)
    sent, status = g4.send_if_allowed(xyz)
    check("P4_XYZ_SEND_REFUSED_NO_EXCHANGE_CALL", not sent and status == "INTENT_NOT_SEND_ALLOWED" and not ex4.calls,
          "%s %s calls=%d" % (sent, status, len(ex4.calls)))
    btc = builder.build(c.LeaderFill("x2", A, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"dir": "Open Long"}))
    check("P4_NORMAL_COIN_STILL_ALLOWED", btc.decision == "ENTRY_ALLOWED", "%s %s" % (btc.decision, btc.reason))
    ex5 = Ex([FILLED])
    g5 = gw(ex5)
    c.AuditLogWriter().append_order_intent(btc)
    sent, status = g5.send_if_allowed(btc)
    check("P4_NORMAL_COIN_STILL_SENDS", sent and status == "ORDER_FILLED" and len(ex5.calls) == 1, "%s %s calls=%d" % (sent, status, len(ex5.calls)))
    os.environ["HL_LIVE_SEND_EXCLUDE_PREFIXES"] = ""
    check("P4_PREFIX_LIST_IS_ENV_DRIVEN", builder.build(
        c.LeaderFill("x3", A, "XYZ:PLATINUM", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"dir": "Open Long"})).decision != "EXCLUDED_SEND_PREFIX")
    os.environ.pop("HL_LIVE_SEND_EXCLUDE_PREFIXES")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
