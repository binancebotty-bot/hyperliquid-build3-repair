#!/usr/bin/env python3
"""rw16 (revised): (1) a coin the market keeps refusing is PARKED after 3 consecutive qualifying rejects, for
ENTRY/ADD only - a close can never be trapped by it; (2) unresolved-symbol error rows are rate-limited per symbol
per window, honouring the older seconds knob; (3) no coin-name prefix can refuse a send.

P1 three consecutive IOC no-match rejects on one coin park it (HL_LIVE_ILLIQUID_PARK_MS, default 1800000 ms), write
   ONE reconciliation row with reject_category ILLIQUID_SKIP / terminal_state SKIPPED_ILLIQUID, and the next ENTRY
   for that coin makes no exchange call.
P2 a successful send (ORDER_FILLED or ORDER_RESTING) clears the streak.
P3 a MARKET_HALTED ('Trading is halted.') reject counts toward the same streak.
P4 an EXIT/REDUCE on a parked coin is STILL SENT: the park gates ENTRY/ADD only.
P5 no coin-name prefix (including XYZ:*) can refuse a send.
P6 the log window honours HL_LIVE_MM_UNRESOLVED_LOG_SEC when HL_LIVE_SYMBOL_UNRESOLVED_LOG_WINDOW_MS is unset.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw16_park.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. No network, no orders: every send goes to a fake exchange.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import time
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
    for _k in ("HL_LIVE_ILLIQUID_PARK_AFTER", "HL_LIVE_ILLIQUID_PARK_MS", "HL_LIVE_SEND_EXCLUDE_PREFIXES",
               "HL_LIVE_SYMBOL_UNRESOLVED_LOG_WINDOW_MS", "HL_LIVE_MM_UNRESOLVED_LOG_SEC"):
        os.environ.pop(_k, None)
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100", "SOL": "100", "DOGE": "100", "XYZ:PLATINUM": "100"}
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
    HALTED = {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"error": "Trading is halted."}]}}}

    class Ex:
        def __init__(self, replies):
            self.replies, self.calls = list(replies), []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"coin": coin, "tif": tif["limit"]["tif"], "reduce_only": reduce_only})
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

    def park_rows():
        return [r for r in disk_rows(c.RECONCILIATION_CSV) if r.get("terminal_state") == "SKIPPED_ILLIQUID"]

    def expire(g, coin):
        """Live intents arrive 20-30 s apart, so the short windows have run out before the next one: age them out."""
        g._ioc_no_match_until_ms[coin] = 0
        g._market_halted_until_ms[coin] = 0

    # ---- P1: three consecutive no-match rejects park the coin -----------------------------------------------
    ex = Ex([NOMATCH, NOMATCH, NOMATCH])
    g = gw(ex)
    out = []
    for i in range(3):
        out.append(g.send_if_allowed(mk_intent()))
        if i < 2:
            expire(g, "btc")
    check("P1_THREE_REJECTS_EACH_SENT_ONCE",
          [s for _, s in out] == ["ORDER_REJECTED"] * 3 and len(ex.calls) == 3, "%s calls=%d" % (out, len(ex.calls)))
    check("P1_STREAK_IS_THREE", g._ioc_no_match_streak.get("btc") == 3, str(g._ioc_no_match_streak))
    left_ms = g._ioc_no_match_until_ms.get("btc", 0) - c.utc_now_ms()
    check("P1_PARKED_30_MIN", left_ms > 1700000, "window left=%d ms" % left_ms)
    parked = park_rows()
    check("P1_ONE_PARK_ROW_ILLIQUID",
          len(parked) == 1 and parked[0].get("coin") == "btc" and parked[0].get("reject_category") == "ILLIQUID_SKIP",
          str(parked))
    n_calls = len(ex.calls)
    sent, status = g.send_if_allowed(mk_intent())
    check("P1_NEXT_ENTRY_NO_EXCHANGE_CALL",
          not sent and status == "SKIPPED_IOC_NO_IMMEDIATE_MATCH" and len(ex.calls) == n_calls,
          "%s %s calls=%d" % (sent, status, len(ex.calls)))

    # ---- P4 (most important): an EXIT/REDUCE on the parked coin is still sent -------------------------------
    exx = Ex([FILLED, FILLED])
    g._get_exchange_client = lambda *a, **k: exx
    g._exchange_client_for_coin = lambda coin: (exx, coin)
    sent, status = g.send_if_allowed(mk_intent(lifecycle="EXIT"))
    check("P4_EXIT_ON_PARKED_COIN_STILL_SENDS",
          sent and status == "ORDER_FILLED" and len(exx.calls) == 1,
          "%s %s calls=%s" % (sent, status, exx.calls))
    g._last_exit_attempt_ms.clear()  # the 60 s exit pacing and the in-flight guard are unrelated to the park
    g._pending_exit_guard.clear()
    sent_r, status_r = g.send_if_allowed(mk_intent(lifecycle="REDUCE"))
    check("P4_REDUCE_ON_PARKED_COIN_STILL_SENDS", sent_r and status_r == "ORDER_FILLED" and len(exx.calls) == 2,
          "%s %s calls=%d" % (sent_r, status_r, len(exx.calls)))

    # ---- P2: a successful send clears the streak -----------------------------------------------------------
    for coin, ok_reply, want in (("ETH", FILLED, "ORDER_FILLED"), ("SOL", RESTING, "ORDER_RESTING")):
        ex2 = Ex([NOMATCH, NOMATCH, ok_reply, NOMATCH])
        g2 = gw(ex2)
        outs = []
        for i in range(3):
            outs.append(g2.send_if_allowed(mk_intent(coin=coin)))
            if i < 2:
                expire(g2, coin.lower())
        check("P2_%s_STREAK_TWO_BEFORE_SUCCESS" % coin, outs[2][1] == want, str(outs))
        check("P2_%s_SUCCESS_CLEARS_STREAK" % coin, coin.lower() not in g2._ioc_no_match_streak,
              str(g2._ioc_no_match_streak))
        before = len(park_rows())
        g2.send_if_allowed(mk_intent(coin=coin))  # fresh reject: the counter really restarted at 1
        left = g2._ioc_no_match_until_ms.get(coin.lower(), 0) - c.utc_now_ms()
        check("P2_%s_COUNTER_RESTARTS_SHORT" % coin,
              g2._ioc_no_match_streak.get(coin.lower()) == 1 and 0 < left <= 15000,
              "streak=%s left=%d" % (g2._ioc_no_match_streak, left))
        check("P2_%s_NOT_PARKED" % coin, len(park_rows()) == before, str(park_rows()))

    # ---- P3: a halted-market reject counts toward the same streak ------------------------------------------
    ex3 = Ex([NOMATCH, NOMATCH, HALTED])
    g3 = gw(ex3)
    for i in range(3):
        g3.send_if_allowed(mk_intent(coin="DOGE"))
        if i < 2:
            expire(g3, "doge")
    doge_rows = [r for r in park_rows() if r.get("coin") == "doge"]
    check("P3_HALTED_COUNTS_TOWARD_STREAK", g3._ioc_no_match_streak.get("doge") == 3, str(g3._ioc_no_match_streak))
    check("P3_HALTED_PARKS_COIN", len(doge_rows) == 1 and doge_rows[0].get("reject_category") == "ILLIQUID_SKIP",
          str(doge_rows))
    left_h = g3._ioc_no_match_until_ms.get("doge", 0) - c.utc_now_ms()
    check("P3_HALTED_PARK_IS_LONG", left_h > 1700000, "left=%d" % left_h)

    # ---- P5: no coin-name prefix refuses a send ------------------------------------------------------------
    builder = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "builder.json"))
    xyz = builder.build(c.LeaderFill("x1", A, "XYZ:PLATINUM", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"dir": "Open Long"}))
    check("P5_XYZ_DECISION_ALLOWED", xyz.decision == "ENTRY_ALLOWED", "%s %s" % (xyz.decision, xyz.reason))
    os.environ["HL_LIVE_BLOCK_XYZ_ENTRY"] = "0"  # P5 tests the dead prefix feature; P7 owns the xyz: entry rule
    ex4 = Ex([FILLED])
    g4 = gw(ex4)
    c.AuditLogWriter().append_order_intent(xyz)
    sent, status = g4.send_if_allowed(xyz)
    check("P5_XYZ_SEND_REACHES_EXCHANGE", sent and status == "ORDER_FILLED" and len(ex4.calls) == 1,
          "%s %s calls=%d" % (sent, status, len(ex4.calls)))
    os.environ.pop("HL_LIVE_BLOCK_XYZ_ENTRY", None)  # P5's BTC case needs the builder-dex switch off anyway
    os.environ["HL_LIVE_SEND_EXCLUDE_PREFIXES"] = "BTC,ETH,SOL"  # a prefix list must not be honoured at all
    ex5 = Ex([FILLED])
    g5 = gw(ex5)
    btc = builder.build(c.LeaderFill("x2", A, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"dir": "Open Long"}))
    c.AuditLogWriter().append_order_intent(btc)
    sent5, status5 = g5.send_if_allowed(btc)
    check("P5_PREFIX_LIST_IS_IGNORED", btc.decision == "ENTRY_ALLOWED" and sent5 and status5 == "ORDER_FILLED"
          and len(ex5.calls) == 1, "%s %s calls=%d" % (btc.decision, status5, len(ex5.calls)))
    os.environ.pop("HL_LIVE_SEND_EXCLUDE_PREFIXES")
    os.environ.pop("HL_LIVE_BLOCK_XYZ_ENTRY", None)

    # ---- P7: builder-dex ('xyz:*') new exposure refused; closes still go out. Every call here goes through
    # send_if_allowed - the classifier-then-exchange function a live fill reaches (fake exchange seam).
    def xyz_rows():
        return [r for r in disk_rows(c.RECONCILIATION_CSV) if r.get("terminal_state") == "SKIPPED_XYZ_ENTRY"]

    os.environ.pop("HL_LIVE_BLOCK_XYZ_ENTRY", None)  # unset = ON for the soak
    ex7 = Ex([FILLED] * 6)
    g7 = gw(ex7)
    sent_e, st_e = g7.send_if_allowed(mk_intent(coin="xyz:ORCL"))
    check("P7_XYZ_ENTRY_REFUSED_NO_EXCHANGE_CALL",
          not sent_e and st_e == "SKIPPED_XYZ_ENTRY" and len(ex7.calls) == 0,
          "%s %s calls=%s" % (sent_e, st_e, ex7.calls))
    rows7 = xyz_rows()
    check("P7_XYZ_ENTRY_ROW_HANDLED_DECISION",
          len(rows7) == 1 and rows7[0].get("reject_category") == "SKIPPED_BUILDER_DEX_ENTRY"
          and str(rows7[0].get("coin") or "").lower() == "xyz:orcl", str(rows7))
    sent_x, st_x = g7.send_if_allowed(mk_intent(coin="xyz:ORCL", side="SELL", lifecycle="EXIT"))
    check("P7_XYZ_EXIT_STILL_SENT", sent_x and st_x == "ORDER_FILLED" and len(ex7.calls) == 1,
          "%s %s calls=%s" % (sent_x, st_x, ex7.calls))
    g7._last_exit_attempt_ms.clear()
    g7._pending_exit_guard.clear()
    sent_r7, st_r7 = g7.send_if_allowed(mk_intent(coin="xyz:PLTR", side="SELL", lifecycle="REDUCE"))
    check("P7_XYZ_REDUCE_STILL_SENT", sent_r7 and st_r7 == "ORDER_FILLED" and len(ex7.calls) == 2,
          "%s %s calls=%s" % (sent_r7, st_r7, ex7.calls))
    sent_a, st_a = g7.send_if_allowed(mk_intent(coin="xyz:MSTR"))
    check("P7_XYZ_ADD_ALSO_REFUSED", not sent_a and st_a == "SKIPPED_XYZ_ENTRY" and len(ex7.calls) == 2,
          "%s %s" % (sent_a, st_a))
    sent_h, st_h = g7.send_if_allowed(mk_intent(coin="ETH"))
    check("P7_ETH_ENTRY_UNAFFECTED_ON", sent_h and st_h == "ORDER_FILLED" and len(ex7.calls) == 3,
          "%s %s" % (sent_h, st_h))
    os.environ["HL_LIVE_BLOCK_XYZ_ENTRY"] = "0"  # off restores the previous behaviour exactly
    sent_o, st_o = g7.send_if_allowed(mk_intent(coin="XYZ:PLATINUM"))  # upper-case name: the match must be case-insensitive
    check("P7_SWITCH_OFF_XYZ_ENTRY_ALLOWED", sent_o and st_o == "ORDER_FILLED" and len(ex7.calls) == 4,
          "%s %s calls=%s" % (sent_o, st_o, ex7.calls))
    sent_h2, st_h2 = g7.send_if_allowed(mk_intent(coin="ETH"))
    check("P7_SWITCH_OFF_ETH_STILL_FINE", sent_h2 and st_h2 == "ORDER_FILLED" and len(ex7.calls) == 5,
          "%s %s calls=%d" % (sent_h2, st_h2, len(ex7.calls)))
    os.environ.pop("HL_LIVE_BLOCK_XYZ_ENTRY")

    # ---- P6: unresolved-symbol rows collapse per symbol per window; the old seconds knob still works --------
    def err_rows(text):
        return [r for r in disk_rows(c.ERRORS_CSV) if text in r.get("message", "")]

    unresolved = {"status": "SYMBOL_UNRESOLVED", "error": "GMX not in local meta cache"}
    g6 = gw(Ex([]))
    for _ in range(3):
        g6._note_margin_symbol_unresolved("GMX", unresolved)
    check("P6_ONE_ROW_PER_SYMBOL_PER_WINDOW", len(err_rows("symbol unresolved: GMX")) == 1,
          str(err_rows("symbol unresolved: GMX")))
    g6._note_margin_symbol_unresolved("TRX", unresolved)
    check("P6_OTHER_SYMBOL_STILL_VISIBLE", len(err_rows("symbol unresolved: TRX")) == 1,
          str(err_rows("symbol unresolved: TRX")))
    os.environ["HL_LIVE_SYMBOL_UNRESOLVED_LOG_WINDOW_MS"] = "50"  # measurable window, expired: visible again
    time.sleep(0.1)
    g6._note_margin_symbol_unresolved("GMX", unresolved)
    check("P6_WINDOW_IS_ENV_DRIVEN", len(err_rows("symbol unresolved: GMX")) == 2,
          str(len(err_rows("symbol unresolved: GMX"))))
    os.environ.pop("HL_LIVE_SYMBOL_UNRESOLVED_LOG_WINDOW_MS")
    os.environ["HL_LIVE_MM_UNRESOLVED_LOG_SEC"] = "600"  # old knob honoured when the new one is unset: long window
    g6._note_margin_symbol_unresolved("GMX", unresolved)
    check("P6_OLD_SECONDS_KNOB_SUPPRESSES", len(err_rows("symbol unresolved: GMX")) == 2,
          str(len(err_rows("symbol unresolved: GMX"))))
    os.environ["HL_LIVE_MM_UNRESOLVED_LOG_SEC"] = "0.05"  # tiny old-knob window: the row appears again
    time.sleep(0.1)
    g6._note_margin_symbol_unresolved("GMX", unresolved)
    check("P6_OLD_SECONDS_KNOB_IS_HONOURED", len(err_rows("symbol unresolved: GMX")) == 3,
          str(len(err_rows("symbol unresolved: GMX"))))
    os.environ.pop("HL_LIVE_MM_UNRESOLVED_LOG_SEC")
    for _ in range(3):
        c.log_error("margin_mode_background", RuntimeError("real exchange error: rate limited"))
    check("P6_GENUINE_EXCHANGE_ERROR_LOGS_EVERY_TIME", len(err_rows("real exchange error: rate limited")) == 3,
          str(len(err_rows("real exchange error: rate limited"))))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
