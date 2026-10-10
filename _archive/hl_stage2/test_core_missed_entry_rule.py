#!/usr/bin/env python3
"""Boss's missed-entry rule (2026-10-09) and the polling backstop that catches missed trades of any age.

"If we have the same price or better we take the entry that we missed, or in tolerance; otherwise a diff is
produced so that I can reconcile it, and a limit order at the desired price is placed in the meantime."
"The web socket should be the primary low-latency path; a separate polling mechanism detects missed entries,
whether missed a few seconds or a few days ago."

M1 the rule itself: same / better / within tolerance (Global Controls slippage) = take; beyond = rest.
M2 one network: within tolerance the copy never pays beyond leader price + tolerance; beyond it, no chase:
   one resting limit at the leader's price, shown on the screen's Critical diffs, recorded for withdrawal.
M3 an order that finds no match retries no further than leader price + tolerance, then rests at the leader's price.
M4 leader on mainnet, follower on testnet: the leader's market move is measured on the leader's network and
   the limit rests at the same relative distance on the follower's market; no leader price = no order.
M5 a resting limit is withdrawn only when the leader reduces/closes/flips that coin (no clock expiry);
   failed withdrawals stay and show as a diff; the list survives a restart.
M6 catch-up: a late entry the leader already closed again is reported, not traded; exits always run.
M7 the polling backstop resumes from the last good poll however old (up to 7 days), says when it could not
   read everything, and reports a gap older than that; the live feed's health gate follows --ws.

Run: python test_core_missed_entry_rule.py   # RESULT:: markers, exit 0/1. No network, no orders.
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
OTHER = "0x" + "e" * 40
NO_MATCH = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
    {"error": "Order could not immediately match against any resting orders. asset=0"}]}}}


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="missedentry_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
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

    def set_mids(follower=None, leader=None):
        if follower is not None:
            mids["follower"] = follower
        if leader is not None:
            mids["leader"] = leader
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)

    def config(**gc):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": gc, "wallets": {
            LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000}}})

    seq = [0]

    def fill(side="BUY", price=100.0, size=1.0, wallet=LEADER, coin="BTC", ts=None, start=None):
        seq[0] += 1
        raw = {} if start is None else {"startPosition": str(start)}
        return c.LeaderFill(f"m{seq[0]}", wallet, coin, side, price, size, ts or (c.utc_now_ms() + seq[0]), "TEST", 0, raw)

    # ---- M1: the rule --------------------------------------------------------------------------------
    d = c.missed_entry_decision
    check("M1_SAME_PRICE_TAKEN", d("BUY", 100, 100, 100, 20)["take"])
    check("M1_BETTER_PRICE_TAKEN", d("BUY", 100, 99, 99, 20)["take"] and d("SELL", 100, 101, 101, 20)["take"])
    r = d("BUY", 100, 100.2, 100.2, 20)
    check("M1_WITHIN_TOLERANCE_TAKEN_CAPPED_AT_LEADER_PLUS_TOL", r["take"] and abs(r["cap_px"] - 100.2) < 1e-9, str(r))
    check("M1_BEYOND_TOLERANCE_RESTS", not d("BUY", 100, 100.3, 100.3, 20)["take"] and not d("SELL", 100, 99.7, 99.7, 20)["take"])
    check("M1_ZERO_TOLERANCE_ONLY_SAME_OR_BETTER", d("BUY", 100, 100, 100, 0)["take"] and not d("BUY", 100, 100.01, 100.01, 0)["take"])
    r = d("BUY", 100, 101, 93, 20)
    check("M1_CROSS_NETWORK_SAME_RELATIVE_DISTANCE", abs(r["desired_px"] - 93 * 100 / 101) < 1e-9 and not r["take"], str(r))
    check("M1_NO_PRICE_NO_DECISION", not d("BUY", 100, 0, 100, 20)["ok"] and not d("BUY", 0, 100, 100, 20)["ok"])

    # ---- wire harness (fake exchange, no network) ---------------------------------------------------
    class FakeExchange:
        def __init__(self, replies=None):
            self.calls, self.cancels, self.replies = [], [], list(replies or [])

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"px": px, "tif": tif["limit"]["tif"], "buy": is_buy, "size": size, "reduce_only": reduce_only})
            if self.replies:
                return self.replies.pop(0)
            if tif["limit"]["tif"] == "Gtc":
                return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 4242}}]}}}
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}]}}}

        def cancel(self, coin, oid):
            self.cancels.append((coin, oid))
            return self.cancel_reply

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def gateway(fake):
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw._resolve_coin = lambda coin: dict(resolved)
        gw._get_exchange_client = lambda *a, **k: fake
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._validate_final_wire_order = lambda *a, **k: (True, {})
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        return gw

    def send(gc, side="BUY", follower=100.0, leader=None, replies=None, f=None, sleeve=0.0):
        config(**gc)
        led = c.ManualLedger(path=tmp / f"l{seq[0]}.json")
        if sleeve:
            led.sleeve(LEADER, "BTC")["signed_size"] = sleeve
        intent = c.IntentBuilder(c.ConfigManager(), led).build(f or fill(side))
        # earlier scenarios' limits count as filled: one resting entry per wallet/coin/side (run 4) is tested in M9
        reg = c.load_json(c.RESTING_ENTRY_ORDERS_FILE, {}) or {}
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {k: {**v, "open_size": 0.0} for k, v in reg.items()})
        fake = FakeExchange(replies)
        gw = gateway(fake)
        set_mids(follower, leader)
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64   # placeholder; the fake exchange never signs
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        try:
            ok, status, res = gw._send_real(intent)
        finally:
            c.HLAccount, c.HLExchange = saved
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        return ok, status, res, fake, gw, intent

    # ---- M2: one network ---------------------------------------------------------------------------
    saved_leader = c.LEADER_NETWORK
    c.LEADER_NETWORK = c.FOLLOWER_NETWORK
    try:
        ok, status, res, fake, gw, _ = send({"marketable_bps": 20}, follower=100.1)
        check("M2_WITHIN_TOLERANCE_IOC_NEVER_BEYOND_LEADER_PLUS_TOL",
              ok and len(fake.calls) == 1 and fake.calls[0]["tif"] == "Ioc" and fake.calls[0]["px"] <= 100.2 + 1e-9, str(fake.calls))
        ok, status, res, fake, gw, intent = send({"marketable_bps": 20}, follower=101.0)
        check("M2_BEYOND_TOLERANCE_NO_CHASE_ONE_LIMIT_AT_LEADER_PRICE",
              ok and status == "ORDER_RESTING" and fake.calls == [{"px": 100.0, "tif": "Gtc", "buy": True,
                                                                   "size": intent.copy_size, "reduce_only": False}], str(fake.calls))
        check("M2_DIFF_REPORTED_AS_CRITICAL_ON_SCREEN",
              res.get("terminal_state") == "ENTRY_LIMIT_RESTING_PRICE_MOVED"
              and "RECOVERY" in res.get("operator_action", "") and "leader_price=100.0" in res.get("notes", ""), str(res)[:300])
        gw._append_real_attempt(intent, status, res)
        rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("terminal_state") == "ENTRY_LIMIT_RESTING_PRICE_MOVED"]
        check("M2_DIFF_ROW_WRITTEN_FOR_THE_SCREEN", rows and rows[-1]["event"] == "SEND_TERMINAL", str(rows[-1:])[:300])
        sends = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV) if r.get("exchange_order_id") == "4242"]
        check("M2_RESTING_ORDER_ID_KEPT_SO_ITS_FILL_IS_OWNED", sends and sends[-1]["status"] == "ORDER_RESTING", str(sends[-1:])[:200])
        reg = c.load_json(c.RESTING_ENTRY_ORDERS_FILE, {})
        check("M2_RESTING_LIMIT_RECORDED_FOR_WITHDRAWAL", "4242" in reg and reg["4242"]["leader_wallet"] == LEADER
              and reg["4242"]["side"] == "BUY", str(reg))
        ok, status, res, fake, gw, _ = send({"marketable_bps": 20}, side="SELL", follower=99.0)
        check("M2_SELL_SIDE_MIRRORED", status == "ORDER_RESTING" and fake.calls[0]["px"] == 100.0 and fake.calls[0]["tif"] == "Gtc",
              str(fake.calls))
        os.environ["HL_LIVE_MISSED_ENTRY_RULE"] = "0"
        ok, status, res, fake, gw, _ = send({"marketable_bps": 20}, follower=101.0)
        check("M2_RULE_SWITCH_OFF_RESTORES_OLD_BEHAVIOUR", fake.calls[0]["tif"] == "Ioc", str(fake.calls))
        os.environ.pop("HL_LIVE_MISSED_ENTRY_RULE", None)

        # ---- M3: no match while sending ---------------------------------------------------------------
        ok, status, res, fake, gw, _ = send({"marketable_bps": 20}, follower=99.9, replies=[NO_MATCH, NO_MATCH])
        pxs = [(x["tif"], x["px"]) for x in fake.calls]
        check("M3_RETRY_CAPPED_AT_LEADER_PLUS_TOLERANCE_NOT_1PCT",
              len(fake.calls) == 3 and fake.calls[1]["tif"] == "Ioc" and fake.calls[1]["px"] <= 100.2 + 1e-9
              and max(x["px"] for x in fake.calls) <= 100.2 + 1e-9, str(pxs))
        check("M3_THEN_LIMIT_RESTS_AT_LEADER_PRICE_WITH_DIFF",
              pxs[-1] == ("Gtc", 100.0) and status == "ORDER_RESTING" and res.get("terminal_state") == "ENTRY_LIMIT_RESTING_PRICE_MOVED",
              f"{status} {pxs}")
        ok, status, res, fake, gw, _ = send({"marketable_bps": 20}, follower=100.2, replies=[NO_MATCH, NO_MATCH])
        check("M3_NO_RETRY_WHEN_ALREADY_AT_THE_CAP", [x["tif"] for x in fake.calls] == ["Ioc", "Gtc"], str(fake.calls))
        ok, status, res, fake, gw, _ = send({"marketable_bps": 20}, side="SELL", follower=100.0, replies=[NO_MATCH], sleeve=10.0)
        check("M3_EXITS_UNCHANGED_NO_ENTRY_LIMIT", fake.calls and all(x["reduce_only"] for x in fake.calls), str(fake.calls))
    finally:
        c.LEADER_NETWORK = saved_leader

    # ---- M4: leader mainnet, follower testnet ---------------------------------------------------------
    ok, status, res, fake, gw, _ = send({"marketable_bps": 20}, follower=93.0, leader=100.1)
    check("M4_CROSS_NETWORK_WITHIN_TOLERANCE_TAKEN_ON_FOLLOWER_MARKET",
          ok and fake.calls[0]["tif"] == "Ioc" and fake.calls[0]["px"] <= 93 * 100 / 100.1 * 1.002 + 0.01, str(fake.calls))
    ok, status, res, fake, gw, _ = send({"marketable_bps": 20}, follower=93.0, leader=101.0)
    check("M4_CROSS_NETWORK_MOVED_TOO_FAR_RESTS_AT_SAME_RELATIVE_DISTANCE",
          status == "ORDER_RESTING" and fake.calls[0]["tif"] == "Gtc" and abs(fake.calls[0]["px"] - 92.08) < 0.011, str(fake.calls))
    ok, status, res, fake, gw, _ = send({"marketable_bps": 20}, follower=93.0, leader=0)
    check("M4_NO_LEADER_PRICE_NO_ORDER_AND_A_DIFF",
          not ok and not fake.calls and status == "SEND_NOT_ATTEMPTED_LEADER_PRICE_UNAVAILABLE"
          and res.get("terminal_state") == "MISSED_ENTRY_LEADER_PRICE_UNAVAILABLE", status)
    set_mids(100.0, 100.0)

    # ---- M5: withdrawal tied to the leader's position, not a clock --------------------------------------
    fake = FakeExchange()
    fake.cancel_reply = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}
    gw = gateway(fake)
    check("M5_LIST_SURVIVES_RESTART", "4242" in {r["oid"] for r in gw.resting_entries()}, str(gw.resting_entries()))
    gw._resting_entries["4242"]["placed_ms"] = c.utc_now_ms() - 5 * 86400000   # five days old: still kept
    check("M5_LEADER_ADDING_KEEPS_IT", not gw.cancel_resting_entries_against(fill("BUY")) and not fake.cancels)
    check("M5_OTHER_WALLET_OR_COIN_KEEPS_IT", not gw.cancel_resting_entries_against(fill("SELL", wallet=OTHER))
          and not gw.cancel_resting_entries_against(fill("SELL", coin="ETH")) and not fake.cancels)
    check("M5_LEADER_REDUCING_WITHDRAWS_IT", len(gw.cancel_resting_entries_against(fill("SELL"))) == 1
          and fake.cancels == [("BTC", 4242)] and "4242" not in c.load_json(c.RESTING_ENTRY_ORDERS_FILE, {}), str(fake.cancels))
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("exchange_order_id") == "4242"]
    check("M5_WITHDRAWAL_SHOWN", rows and rows[-1]["status"] == "RESTING_ENTRY_CANCELLED_LEADER_REDUCED"
          and rows[-1]["event"] == "SEND_TERMINAL", str(rows[-1:])[:300])
    old_sell = fill("SELL", ts=c.utc_now_ms() - 60000)   # a replayed OLDER close must not withdraw a newer entry's limit
    intent = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "m5.json")).build(fill("BUY"))
    gw._register_resting_entry(intent, "BTC", "77", 100.0, 1.0, "test")
    check("M5_OLDER_OPPOSITE_FILL_DOES_NOT_WITHDRAW", not gw.cancel_resting_entries_against(old_sell)
          and [r["oid"] for r in gw.resting_entries()] == ["77"])
    fake.cancel_reply = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": [
        {"error": "Order was never placed, already canceled, or filled. asset=0"}]}}}
    check("M5_ALREADY_FILLED_OR_GONE_IS_CLEARED", len(gw.cancel_resting_entries_against(fill("SELL"))) == 1 and not gw.resting_entries())
    # the leader's SELL above came after that BUY: a limit registered late for it is withdrawn at once (thread race)
    gw._register_resting_entry(intent, "BTC", "79", 100.0, 1.0, "test")
    check("M5_LATE_REGISTRATION_AFTER_LEADER_REDUCED_IS_WITHDRAWN", not gw.resting_entries() and fake.cancels[-1] == ("BTC", 79),
          str(fake.cancels[-1:]))
    intent = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "m5b.json")).build(fill("BUY"))
    gw._register_resting_entry(intent, "BTC", "78", 100.0, 1.0, "test")
    fake.cancel_reply = {"status": "err", "response": "rate limited"}
    check("M5_FAILED_WITHDRAWAL_KEPT_AND_FLAGGED", not gw.cancel_resting_entries_against(fill("SELL"))
          and [r["oid"] for r in gw.resting_entries()] == ["78"])
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("exchange_order_id") == "78"]
    check("M5_FAILED_WITHDRAWAL_IS_CRITICAL_ON_SCREEN", rows and "MANUAL_REVIEW" in rows[-1]["action"], str(rows[-1:])[:300])
    check("M5_FAILED_WITHDRAWAL_MARKED_FOR_RETRY", gw.resting_entries()[0].get("withdraw_pending"))

    # the running engine withdraws before it handles the leader's reduce
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
        LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000}}})
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    fake.cancel_reply = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}
    core.sender._exchange_client_for_coin = lambda coin: (fake, "BTC")
    order = []
    core.sender.cancel_resting_entries_against = (lambda real: lambda f: order.append("cancel") or real(f))(
        core.sender.cancel_resting_entries_against)
    core.sender.send_if_allowed = lambda intent, block="": order.append("send") or (False, "TEST_NO_SEND")
    core._append_send_terminal = lambda *a, **k: None
    check("M5_ENGINE_LOADED_THE_LIST", [r["oid"] for r in core.sender.resting_entries()] == ["78"])
    core._process_leader_fill(fill("SELL"))
    check("M5_ENGINE_WITHDRAWS_BEFORE_HANDLING_THE_REDUCE", order == ["cancel", "send"] and not core.sender.resting_entries(),
          f"{order} {core.sender.resting_entries()}")

    # ---- M8: sending switched off withdraws the engine's own resting entry limits (run 4 finding) ----------
    def m8_core(send_on):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": send_on, "global_controls": {}, "wallets": {
            LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 1000}}})
        k = c.LiveCopyCore(source_csv=tmp / "none.csv")
        k.sender._exchange_client_for_coin = lambda coin: (fake, "BTC")
        # the fill read is made outside the send lock, the ledger half inside it (run 5)
        k._read_fills_of_withdrawn_limits = lambda rows: ([], "COPY_ACCOUNT_POLLED")
        k._apply_fills_of_withdrawn_limits = lambda rows, read, seen=None: owned.extend(r["oid"] for r in rows) or 0
        return k
    owned = []
    m8_start = len(fake.cancels)
    fake.cancel_reply = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}
    k = m8_core(True)
    for oid in ("90", "91"):
        k.sender._register_resting_entry(c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / f"m8{oid}.json")).build(fill("BUY")),
                                         "BTC", oid, 100.0, 1.0, "test")
    before = len(fake.cancels)
    k.run_cycle(use_source_csv=False)
    check("M8_SENDING_ON_LIMITS_KEEP_RESTING", len(fake.cancels) == before and len(k.sender.resting_entries()) == 2)
    k = m8_core(False)   # the screen switched sending off; a restarted or running engine reloads the list
    k.run_cycle(use_source_csv=False)
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("status") == "RESTING_ENTRY_CANCELLED_SENDING_OFF"]
    check("M8_SENDING_OFF_WITHDRAWS_OWN_ENTRY_LIMITS", not k.sender.resting_entries()
          and sorted(o for _, o in fake.cancels[before:]) == [90, 91], str(fake.cancels[before:]))
    check("M8_SHOWN_ON_SCREEN", {r.get("exchange_order_id") for r in rows} >= {"90", "91"}
          and all(r.get("event") == "SEND_TERMINAL" for r in rows), str(rows[-2:])[:300])
    check("M8_FILLS_OF_WITHDRAWN_LIMITS_OWNED", sorted(owned) == ["90", "91"], str(owned))
    k.sender._register_resting_entry(c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "m8x.json")).build(fill("BUY")),
                                     "BTC", "93", 100.0, 1.0, "test")
    fake.cancel_reply = {"status": "err", "response": "rate limited"}
    before = len(fake.cancels)
    k.run_cycle(use_source_csv=False)
    check("M8_FAILED_WITHDRAWAL_ONE_CANCEL_PER_CYCLE_KEPT", len(fake.cancels) == before + 1
          and [r["oid"] for r in k.sender.resting_entries()] == ["93"] and k.sender.resting_entries()[0].get("withdraw_pending"))
    fake.cancel_reply = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}
    k.run_cycle(use_source_csv=False)
    check("M8_FAILED_WITHDRAWAL_RETRIED_NEXT_CYCLE", not k.sender.resting_entries() and len(fake.cancels) == before + 2)
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("exchange_order_id") == "93"]
    check("M8_RETRY_KEEPS_THE_SENDING_OFF_REASON", rows and rows[-1]["status"] == "RESTING_ENTRY_CANCELLED_SENDING_OFF", str(rows[-1:])[:300])
    # a limit already being withdrawn by one path is not cancelled again by another at the same moment
    k.sender._register_resting_entry(c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "m8y.json")).build(fill("BUY")),
                                     "BTC", "94", 100.0, 1.0, "test")
    with k.sender._resting_lock:
        claimed = k.sender._claim_rows(list(k.sender._resting_entries.values()))
    before = len(fake.cancels)
    check("M8_CLAIMED_LIMIT_NOT_CANCELLED_TWICE", [r["oid"] for r in claimed] == ["94"]
          and not k.sender.withdraw_resting_entries_sending_off() and len(fake.cancels) == before)
    k.sender._withdraw_rows(claimed, "test", "", "RESTING_ENTRY_CANCELLED_SENDING_OFF")
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {"95": {"oid": "95", "coin": "BTC", "side": "BUY", "withdrawing": True}})
    k2 = m8_core(False)
    check("M8_STALE_CLAIM_CLEARED_ON_START", not k2.sender.resting_entries()[0].get("withdrawing"))
    k2.run_cycle(use_source_csv=False)
    check("M8_STALE_CLAIM_ROW_WITHDRAWN", not k2.sender.resting_entries())
    k2.stop()
    check("M8_ONLY_ITS_OWN_ORDER_IDS_CANCELLED", {o for _, o in fake.cancels[m8_start:]} == {90, 91, 93, 94, 95}, str(fake.cancels[m8_start:]))
    k.stop()

    # ---- M6: catch-up of an old gap -------------------------------------------------------------------
    now = c.utc_now_ms()
    old = now - 3 * 86400000   # three days ago
    a = fill("BUY", ts=old, start=0)          # opened
    b = fill("SELL", ts=old + 1, start=1)     # closed again
    e = fill("BUY", ts=old + 2, start=0, size=2)   # opened again, still open
    skip = c.already_closed_late_entries([a, b, e], now)
    check("M6_ENTRY_ALREADY_CLOSED_IS_REPORTED_NOT_TRADED", a.leader_fill_id in skip, str(skip))
    check("M6_EXITS_AND_STILL_OPEN_ENTRIES_RUN", b.leader_fill_id not in skip and e.leader_fill_id not in skip, str(skip))
    live = [fill("BUY", start=0), fill("SELL", start=1)]
    check("M6_LIVE_FILLS_NEVER_NETTED", not c.already_closed_late_entries(live, now))
    check("M6_NO_START_POSITION_NOTHING_SKIPPED", not c.already_closed_late_entries([fill("BUY", ts=old), fill("SELL", ts=old + 1)], now))
    flip = [fill("SELL", ts=old, start=1, size=2), fill("BUY", ts=old + 1, start=-1)]
    check("M6_FLIP_IS_NEVER_SKIPPED_ITS_EXIT_MUST_RUN", not c.already_closed_late_entries(flip, now))
    reduce_ = [fill("BUY", ts=old, start=0, size=2), fill("SELL", ts=old + 1, start=2), fill("SELL", ts=old + 2, start=1)]
    skip = c.already_closed_late_entries(reduce_, now)
    check("M6_REDUCES_NEVER_SKIPPED", list(skip) == [reduce_[0].leader_fill_id], str(skip))
    recent = [fill("BUY", ts=now - 300000, start=0), fill("SELL", ts=now - 10000, start=1)]
    skip = c.already_closed_late_entries(recent, now)
    check("M6_LATE_ENTRY_WITH_A_FRESH_CLOSE_IS_SEEN", list(skip) == [recent[0].leader_fill_id], str(skip))

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    handled = []
    core._process_leader_fill = lambda f, summary=None, block="": handled.append(f.leader_fill_id) or (False, "T", None)
    a2, b2, e2 = fill("BUY", ts=old, start=0), fill("SELL", ts=old + 1, start=1), fill("BUY", ts=old + 2, start=0)
    core.ingestor.poll_hyperliquid_fills = lambda w, s, t=None: ([a2, b2, e2] if w == LEADER else [], "POLL_OK")
    core.run_cycle(use_source_csv=False, poll_live=True)
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("leader_fill_id") == a2.leader_fill_id]
    check("M6_CYCLE_SKIPS_CLOSED_ENTRY_WITH_A_DIFF", handled == [b2.leader_fill_id, e2.leader_fill_id]
          and rows and rows[-1]["status"] == "MISSED_ENTRY_LEADER_ALREADY_CLOSED", f"{handled} {rows[-1:]}")

    # ---- M7: polling backstop ---------------------------------------------------------------------------
    starts = []
    core.ingestor.poll_hyperliquid_fills = lambda w, s, t=None: starts.append(s) or ([], "POLL_OK")
    state = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    state["last_leader_poll_cursor_ms"] = {LEADER: now - 3 * 86400000}
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, state)
    core.run_cycle(use_source_csv=False, poll_live=True)
    check("M7_THREE_DAY_GAP_CAUGHT_UP_FROM_LAST_GOOD_POLL",
          starts and abs(starts[-1] - (now - 3 * 86400000 - c.LEADER_POLL_OVERLAP_MS)) < 60000, f"{starts} now={now}")
    state = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    state["last_leader_poll_cursor_ms"] = {LEADER: c.utc_now_ms() - 9 * 86400000}
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, state)
    core.run_cycle(use_source_csv=False, poll_live=True)
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("status") == "LEADER_HISTORY_GAP"]
    check("M7_GAP_BEYOND_7_DAYS_REPORTED", rows and rows[-1]["event"] == "SEND_TERMINAL"
          and "MANUAL_REVIEW" in rows[-1]["action"], str(rows[-1:])[:200])

    pages = {"n": 0}

    def page_post(url, json=None, timeout=None):
        pages["n"] += 1
        t0 = json["startTime"]
        n = 2000 if pages["mode"] == "full" else 3
        return type("R", (), {"json": lambda self: [{"coin": "BTC", "side": "B", "px": "100", "sz": "1", "time": t0 + i,
                                                     "hash": f"h{pages['n']}_{i}", "startPosition": "0"} for i in range(n)]})()
    c.requests.post = page_post
    pages["mode"] = "full"
    got, status = c.LeaderFillIngestor().poll_hyperliquid_fills(LEADER, now - 1000, now)
    check("M7_PAGES_RAN_OUT_SAYS_PARTIAL", status == "POLL_PARTIAL" and len(got) == 2000 * c.POLL_MAX_PAGES_PER_WALLET,
          f"{status} {len(got)}")
    pages["mode"] = "short"
    got, status = c.LeaderFillIngestor().poll_hyperliquid_fills(LEADER, now - 1000, now)
    check("M7_WHOLE_WINDOW_READ_SAYS_OK", status == "POLL_OK" and len(got) == 3, f"{status} {len(got)}")
    c.requests.post = offline

    partial_fills = [fill("BUY", ts=now - 5000)]
    core.ingestor.poll_hyperliquid_fills = lambda w, s, t=None: (partial_fills if w == LEADER else [], "POLL_PARTIAL")
    core._process_leader_fill = lambda f, summary=None, block="": (False, "T", None)
    core.run_cycle(use_source_csv=False, poll_live=True)
    cur = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("last_leader_poll_cursor_ms", {}).get(LEADER, 0)
    check("M7_PARTIAL_POLL_RESUMES_FROM_LAST_FILL_READ", cur - c.LEADER_POLL_OVERLAP_MS == partial_fills[0].timestamp_ms, f"{cur}")

    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    check("M7_FEED_HEALTH_GATE_UNCHANGED_FILL_SILENCE_NEVER_BLOCKS_ALL_ENTRIES",
          'bval(os.getenv("HL_LIVE_WS_ENABLED"), False) or self.ws.enabled' not in src)

    # ---- R: independent review fixes ---------------------------------------------------------------------
    # R2 a resting limit that filled just before the leader closes: its fill is owned BEFORE the close is classified
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    fake = FakeExchange()
    fake.cancel_reply = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": [
        {"error": "Order was never placed, already canceled, or filled. asset=0"}]}}}
    core.sender._exchange_client_for_coin = lambda coin: (fake, "BTC")
    buy = fill("BUY")
    core.sender._register_resting_entry(core.intent_builder.build(buy), "BTC", "555", 100.0, 1.0, "test")
    seen = []
    core.copy_ingestor.poll_copy_account_fills = lambda w, s0, s1, **k: ([{"coin": "BTC", "oid": 555, "side": "B", "sz": "1", "px": "100",
                                                                      "time": c.utc_now_ms(), "hash": "hx", "tid": 1}], "COPY_ACCOUNT_POLLED")

    def own(raw, intents):
        seen.append("own")
        core.ledger.sleeve(LEADER, "BTC")["signed_size"] = 1.0
        return True
    core.matcher.match_and_apply = own
    core.sender.send_if_allowed = lambda intent, block="": seen.append(c.classify_send_lifecycle(intent)) or (False, "TEST_NO_SEND")
    core._append_send_terminal = lambda *a, **k: None
    close = fill("SELL", start=1)
    core._process_leader_fill(close)
    check("R2_FILLED_LIMIT_OWNED_BEFORE_THE_LEADER_CLOSE_IS_CLASSIFIED", seen == ["own", "EXIT"], str(seen))
    core.sender._register_resting_entry(core.intent_builder.build(fill("BUY")), "BTC", "556", 100.0, 1.0, "test")
    core.copy_ingestor.poll_copy_account_fills = lambda w, s0, s1, **k: ([], "COPY_ACCOUNT_POLL_ERROR")
    core._process_leader_fill(fill("SELL"))
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("status") == "RESTING_ENTRY_FILL_UNVERIFIED"]
    check("R2_UNREADABLE_FILLS_AFTER_WITHDRAWAL_IS_CRITICAL", rows and "MANUAL_REVIEW" in rows[-1]["action"], str(rows[-1:])[:200])

    # R3 a failed withdrawal is retried every cycle
    core.sender._register_resting_entry(core.intent_builder.build(fill("BUY")), "BTC", "557", 100.0, 1.0, "test")
    fake.cancel_reply = {"status": "err", "response": "rate limited"}
    core.sender.cancel_resting_entries_against(fill("SELL"))
    pending = [r["oid"] for r in core.sender.resting_entries() if r.get("withdraw_pending")]
    fake.cancel_reply = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}
    core.copy_ingestor.poll_copy_account_fills = lambda w, s0, s1, **k: ([], "COPY_ACCOUNT_POLLED")
    core.run_cycle(use_source_csv=False)
    check("R3_FAILED_WITHDRAWAL_RETRIED_BY_THE_CYCLE", pending == ["557"] and not core.sender.resting_entries(),
          f"{pending} {core.sender.resting_entries()}")

    # R4 an exception while placing a resting limit: look it up, never send a second one
    class RaisingGtc(FakeExchange):
        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"px": px, "tif": tif["limit"]["tif"], "buy": is_buy, "size": size, "reduce_only": reduce_only})
            raise TimeoutError("read timed out")
    open_orders = {"rows": []}
    c.OPEN_ORDERS_FETCHER = lambda payload: open_orders["rows"]
    saved_leader = c.LEADER_NETWORK
    c.LEADER_NETWORK = c.FOLLOWER_NETWORK   # same network: the old rate-limit recovery would have re-sent
    try:
        config(marketable_bps=20)
        led = c.ManualLedger(path=tmp / "r4.json")
        intent = c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY"))
        rf = RaisingGtc()
        gw4 = gateway(rf)
        set_mids(101.0, None)
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        try:
            open_orders["rows"] = [{"coin": "BTC", "side": "B", "limitPx": "100.0", "sz": str(intent.copy_size), "oid": 9001}]
            ok, status, res = gw4._send_real(intent)
            check("R4_TIMED_OUT_LIMIT_FOUND_RESTING_AND_OWNED", ok and status == "ORDER_RESTING" and res.get("oid") == "9001"
                  and len(rf.calls) == 1 and "9001" in {r["oid"] for r in gw4.resting_entries()}, f"{status} {rf.calls} {res.get('oid')}")
            open_orders["rows"] = []
            rf.calls.clear()
            for row in gw4._resting_entries.values():
                row["open_size"] = 0.0   # the found limit has since filled
            intent = c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY"))
            ok, status, res = gw4._send_real(intent)
            check("R4_NOT_FOUND_IS_CRITICAL_AND_NEVER_RESENT", not ok and len(rf.calls) == 1
                  and res.get("terminal_state") == "MISSED_ENTRY_LIMIT_OUTCOME_UNKNOWN"
                  and "MANUAL_REVIEW" in res.get("operator_action", ""), f"{status} {rf.calls} {res.get('terminal_state')}")
        finally:
            c.HLAccount, c.HLExchange = saved
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)

        # R5 rounding never goes past the leader's price (rest) or leader price + tolerance (take)
        ok, status, res, fake5, _, _ = send({"marketable_bps": 0}, side="SELL", follower=99.0, f=fill("SELL", price=99.983))
        check("R5_SELL_RESTS_NEVER_BELOW_LEADER_PRICE", fake5.calls[0]["tif"] == "Gtc" and fake5.calls[0]["px"] >= 99.983, str(fake5.calls))
        ok, status, res, fake5, _, _ = send({"marketable_bps": 0}, side="BUY", follower=101.0, f=fill("BUY", price=99.987))
        check("R5_BUY_RESTS_NEVER_ABOVE_LEADER_PRICE", fake5.calls[0]["tif"] == "Gtc" and fake5.calls[0]["px"] <= 99.987, str(fake5.calls))
        ok, status, res, fake5, _, _ = send({"marketable_bps": 20}, side="SELL", follower=99.9)
        check("R5_SELL_TAKE_NEVER_BELOW_LEADER_MINUS_TOLERANCE", fake5.calls[0]["tif"] == "Ioc" and fake5.calls[0]["px"] >= 99.8 - 1e-9,
              str(fake5.calls))
        check("R5_ONE_NETWORK_DESIRED_IS_EXACTLY_THE_LEADER_PRICE",
              all(c.missed_entry_decision("SELL", lp, 6000.0, 6000.0, 0)["desired_px"] == lp for lp in (6118.0, 61.17, 0.30103)))
    finally:
        c.LEADER_NETWORK = saved_leader
        set_mids(100.0, 100.0)

    # R6 paging re-reads the boundary millisecond instead of skipping fills that share it
    starts6 = []

    def page6(url, json=None, timeout=None):
        starts6.append(json["startTime"])
        n = 2000 if len(starts6) == 1 else 1
        return type("R", (), {"json": lambda self: [{"coin": "BTC", "side": "B", "px": "100", "sz": "1", "time": 5000 + (i // 1000),
                                                     "hash": f"p{len(starts6)}_{i}"} for i in range(n)]})()
    c.requests.post = page6
    c.LeaderFillIngestor().poll_hyperliquid_fills(LEADER, 1000, 9000)
    c.requests.post = offline
    check("R6_BOUNDARY_MILLISECOND_RE_READ", starts6 == [1000, 5001] or starts6[:2] == [1000, 5001], str(starts6))

    # ---- R7: second independent review ------------------------------------------------------------------
    def recon(status, oid=None):
        return [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
                if r.get("status") == status and (oid is None or r.get("exchange_order_id") == oid)]
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {"marketable_bps": 20}, "wallets": {
        LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000}}})
    set_mids(100.0, 100.0)
    saved_leader = c.LEADER_NETWORK
    c.LEADER_NETWORK = c.FOLLOWER_NETWORK
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64   # placeholder; the fake exchange never signs
    saved = c.HLAccount, c.HLExchange
    c.HLAccount, c.HLExchange = object, object
    try:
        # A1 the leader's close was handled before its (late) entry arrived: the entry is not copied
        fake7 = FakeExchange()
        gw7 = gateway(fake7)
        late_sell = fill("SELL")
        gw7.cancel_resting_entries_against(late_sell)
        early_buy = fill("BUY", ts=late_sell.timestamp_ms - 2000)
        intent = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "r7a.json")).build(early_buy)
        intent.decision = "ENTRY_ALLOWED"
        ok, status = gw7.send_if_allowed(intent)
        check("R7_ENTRY_REFUSED_WHEN_LEADER_ALREADY_REDUCED", not ok and status == "SEND_BLOCKED_LEADER_ALREADY_REDUCED"
              and not fake7.calls, f"{status} {fake7.calls}")
        core7 = c.LiveCopyCore(source_csv=tmp / "none.csv")
        core7._append_send_terminal(early_buy, intent, status)
        rows = recon("MISSED_ENTRY_LEADER_ALREADY_REDUCED")
        check("R7_REFUSED_ENTRY_IS_A_DIFF_ON_SCREEN", rows and "MANUAL_REVIEW" in rows[-1]["action"], str(rows[-1:])[:200])
        check("R7_SAME_MILLISECOND_ADD_STILL_COPIED", not gw7.leader_reduced_since(fill("BUY", ts=late_sell.timestamp_ms))
              and gw7.leader_reduced_since(fill("BUY", ts=late_sell.timestamp_ms - 1)) > 0)

        # A2 the leader's close is handled by another thread while our entry is in flight and then fills
        class RacingExchange(FakeExchange):
            def order(self, coin, is_buy, size, px, tif, reduce_only=False):
                s = fill("SELL")   # what the other thread records when it handles the leader's close
                gw8._leader_side_seen_ms[(c.normalise_wallet(LEADER), c.canonical_coin_key("BTC"), "SELL")] = s.timestamp_ms
                return FakeExchange.order(self, coin, is_buy, size, px, tif, reduce_only)
        fake8 = RacingExchange()
        gw8 = gateway(fake8)
        gw8._pre_send_ownership_gate = lambda intent: (True, {})   # exchange-proof gate is covered elsewhere
        intent = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "r7b.json")).build(fill("BUY"))
        intent.decision = "ENTRY_ALLOWED"
        ok, status = gw8.send_if_allowed(intent)
        rows = recon("ENTRY_FILLED_AFTER_LEADER_REDUCED")
        check("R7_ENTRY_FILLED_WHILE_LEADER_REDUCED_IS_CRITICAL", status == "ORDER_FILLED" and rows
              and "MANUAL_REVIEW" in rows[-1]["action"], f"{status} {str(rows[-1:])[:200]}")
    finally:
        c.HLAccount, c.HLExchange = saved
        os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        c.LEADER_NETWORK = saved_leader

    # A3 a limit withdrawn at registration (leader already reduced): the engine owns its fill and shows a diff
    config(marketable_bps=20)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    fake = FakeExchange()
    fake.cancel_reply = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": [
        {"error": "Order was never placed, already canceled, or filled. asset=0"}]}}}
    core.sender._exchange_client_for_coin = lambda coin: (fake, "BTC")
    sell = fill("SELL")
    core.sender.cancel_resting_entries_against(sell)
    core.sender._register_resting_entry(core.intent_builder.build(fill("BUY", ts=sell.timestamp_ms - 1000)), "BTC", "600", 100.0, 1.0, "t")
    owned = []
    core.copy_ingestor.poll_copy_account_fills = lambda w, s0, s1, **k: ([{"coin": "BTC", "oid": 600, "side": "B", "sz": "1",
                                                                           "px": "100", "time": c.utc_now_ms(), "hash": "h600", "tid": 6}],
                                                                         "COPY_ACCOUNT_POLLED")
    core.matcher.match_and_apply = lambda raw, intents: owned.append(raw["oid"]) or True
    core.run_cycle(use_source_csv=False)
    rows = recon("RESTING_ENTRY_FILLED_AFTER_LEADER_REDUCED")
    check("R7_LIMIT_WITHDRAWN_AT_REGISTRATION_HAS_ITS_FILL_OWNED", owned == [600] and not core.sender.take_withdrawn_late(), str(owned))
    check("R7_AND_SHOWN_AS_CRITICAL", rows and "MANUAL_REVIEW" in rows[-1]["action"] and rows[-1]["exchange_order_id"] == "600",
          str(rows[-1:])[:200])
    # the regular copy poll took that fill first, or the API does not show it yet: still a Critical diff
    for oid, poll in (("610", [{"coin": "BTC", "oid": 610, "side": "B", "sz": "1", "px": "100", "time": c.utc_now_ms(),
                                "hash": "h610", "tid": 61}]), ("611", [])):
        sell = fill("SELL")
        core.sender.cancel_resting_entries_against(sell)
        core.sender._register_resting_entry(core.intent_builder.build(fill("BUY", ts=sell.timestamp_ms - 1000)), "BTC", oid, 100.0, 1.0, "t")
        core.copy_ingestor.poll_copy_account_fills = lambda w, s0, s1, _p=poll, **k: (_p, "COPY_ACCOUNT_POLLED")
        core.dedupe.accept_copy = lambda cid, allow_retry=False: False   # already owned by the regular poll
        core.run_cycle(use_source_csv=False)
        check(f"R7_DIFF_EVEN_WHEN_FILL_{'ALREADY_OWNED' if poll else 'NOT_YET_VISIBLE'}",
              recon("RESTING_ENTRY_FILLED_AFTER_LEADER_REDUCED", oid), oid)

    # C the early read starts where the regular copy poll stopped; a capped read is not taken as complete
    last = c.utc_now_ms() - 60000
    st = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    st["last_copy_poll_ms"] = last
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, st)
    starts7 = []
    core.copy_ingestor.poll_copy_account_fills = lambda w, s0, s1, **k: starts7.append(s0) or ([], "COPY_ACCOUNT_POLL_PARTIAL")
    res = core._own_fills_of_withdrawn_limits([{"oid": "601", "coin": "BTC", "placed_ms": last - 5 * 86400000}])
    check("R7_EARLY_READ_STARTS_AT_LAST_COPY_POLL_NOT_DAYS_BACK", starts7 == [last - c.POLL_OVERLAP_MS], f"{starts7} {last}")
    check("R7_CAPPED_READ_IS_UNVERIFIED_CRITICAL", res == -1 and recon("RESTING_ENTRY_FILL_UNVERIFIED", "601"))
    pages["mode"] = "full"
    c.requests.post = page_post
    got, status = c.CopyAccountIngestor().poll_copy_account_fills(FOLLOWER, 1000, 2000, report_partial=True)
    c.requests.post = offline
    check("R7_COPY_READ_PAGE_CAP_SAYS_PARTIAL", status == "COPY_ACCOUNT_POLL_PARTIAL", status)

    # B while sending is stopped for a bad key the leader cursors stay put, so a restart replays the exits
    st = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    st["last_leader_poll_cursor_ms"] = {LEADER: c.utc_now_ms() - 3600000}
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, st)
    before = st["last_leader_poll_cursor_ms"][LEADER]
    core.ingestor.poll_hyperliquid_fills = lambda w, s, t=None: ([], "POLL_OK")
    core.sender.sender_key_invalid = "User or API Wallet does not exist"
    core.run_cycle(use_source_csv=False, poll_live=True)
    cur = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("last_leader_poll_cursor_ms", {}).get(LEADER)
    check("R7_KEY_STOP_HOLDS_LEADER_CURSOR_FOR_REPLAY", cur == before, f"{cur} {before}")
    core.sender.sender_key_invalid = ""
    core.run_cycle(use_source_csv=False, poll_live=True)
    cur = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("last_leader_poll_cursor_ms", {}).get(LEADER)
    starts_b = []
    core.ingestor.poll_hyperliquid_fills = lambda w, s, t=None: starts_b.append(s) or ([], "POLL_OK")
    core.sender.sender_key_invalid = "User or API Wallet does not exist"
    core._held_read_cursor.clear()
    st = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    st["last_leader_poll_cursor_ms"] = {LEADER: before}
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, st)
    core.run_cycle(use_source_csv=False, poll_live=True)
    core.run_cycle(use_source_csv=False, poll_live=True)
    check("R7_HELD_CURSOR_DOES_NOT_GROW_THE_READ_WINDOW", len(starts_b) == 2 and starts_b[1] > starts_b[0] + 1000000, str(starts_b))
    core.sender.sender_key_invalid = ""
    core.run_cycle(use_source_csv=False, poll_live=True)
    cur = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("last_leader_poll_cursor_ms", {}).get(LEADER)
    check("R7_CURSOR_MOVES_AGAIN_WITH_A_GOOD_KEY", cur > before, f"{cur} {before}")

    # lesser review points
    fake = FakeExchange()
    fake.cancel_reply = {"status": "err", "response": "rate limited"}
    gw9 = gateway(fake)
    gw9._register_resting_entry(c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "r7c.json")).build(fill("BUY")),
                                "BTC", "602", 100.0, 1.0, "t")
    gw9.cancel_resting_entries_against(fill("SELL"))
    gw9.retry_pending_withdrawals()
    gw9.retry_pending_withdrawals()
    check("R7_FAILED_CANCEL_SHOWN_ONCE_NOT_EVERY_CYCLE", len(recon("RESTING_ENTRY_CANCEL_FAILED", "602")) == 1
          and len(fake.cancels) == 3, f"{len(recon('RESTING_ENTRY_CANCEL_FAILED', '602'))} {fake.cancels}")
    fake.cancel_reply = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}
    gw9.retry_pending_withdrawals()
    t0 = c.utc_now_ms() + 10 ** 6
    gw9._register_resting_entry(c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "r7d.json")).build(fill("BUY", ts=t0)),
                                "BTC", "603", 100.0, 1.0, "t")
    check("R7_SAME_MILLISECOND_CLOSE_WITHDRAWS_THE_LIMIT", len(gw9.cancel_resting_entries_against(fill("SELL", ts=t0))) == 1)
    gw9._resting_entries["604"] = {"oid": "604", "leader_wallet": LEADER, "coin": "BTC", "side": "BUY", "placed_ms": c.utc_now_ms()}
    check("R7_OLD_ROW_WITHOUT_FILL_TIME_KEPT_AGAINST_OLDER_FILLS",
          not gw9.cancel_resting_entries_against(fill("SELL", ts=c.utc_now_ms() - 600000)) and "604" in gw9._resting_entries)
    check("R7_NO_DEPOSIT_IS_NOT_A_KEY_PROBLEM",
          c.classify_reject_category("Must deposit before performing actions. User: 0xabc") != "SENDER_KEY_NOT_VALID"
          and c.classify_reject_category("User or API Wallet 0xabc does not exist.") == "SENDER_KEY_NOT_VALID")
    open_orders["rows"] = [{"coin": "BTC", "side": "B", "limitPx": "100.0", "sz": "0.4", "origSz": "1.0", "oid": 605}]
    check("R7_PART_FILLED_LIMIT_FOUND_BY_ORIGINAL_SIZE", gw9.find_open_entry_order("BTC", "BTC", "BUY", 100.0, 1.0) == "605")

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
