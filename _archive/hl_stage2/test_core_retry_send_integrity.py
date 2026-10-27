#!/usr/bin/env python3
"""Retry/recovery sends each get their OWN cloid and a synchronous pending_send row written BEFORE the exchange call.

Sites: entry IOC retry, missed-entry limit, netting close resend, 429/timeout recovery, standing close. Behaviour otherwise
unchanged: reduce-only only where _close_wire_plan says so, closes never blocked, 429 never changes a wallet mode.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_retry_send_integrity.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. No network, no orders.
"""
from __future__ import annotations

import csv
import os
import re
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
    tmp = Path(tempfile.mkdtemp(prefix="rsi_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_INTENT_DURABLE_WAIT_MS": "2000"})
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    c.HLAccount, c.HLExchange = object, object

    def mk_intent(iid, side="BUY", notes="lifecycle=ENTRY;"):
        fill = c.LeaderFill("f_" + iid, A, "BTC", side, 100.0, 1.0, c.utc_now_ms(), "TEST")
        return c.Intent(iid, fill, side, 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
                        "sleeve:%s:BTC" % A, "", "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), notes)

    def disk_rows(path):
        if not path.exists():
            return []
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def latest_by_attempt(iid):
        out = {}
        for r in disk_rows(c.SEND_ATTEMPTS_CSV):
            if r.get("intent_id") == iid:
                out[r["attempt_id"]] = r
        return out

    def pending_cloids(iid):
        return {r.get("cloid") for r in disk_rows(c.SEND_ATTEMPTS_CSV)
                if r.get("intent_id") == iid and r.get("status") == "pending_send"}

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
    NOMATCH = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"error": "Order could not immediately match against any resting orders. asset=3"}]}}}
    FILLED = lambda sz, px: {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"filled": {"totalSz": str(sz), "avgPx": str(px), "oid": 3}}]}}}
    RESTING = {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 9}}]}}}

    class Ex:
        def __init__(self, iid, replies):
            self.iid, self.replies, self.calls = iid, list(replies), []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"cloid": str(cloid) if cloid is not None else None, "tif": tif["limit"]["tif"],
                               "ro": reduce_only, "pending_at_call": pending_cloids(self.iid)})
            return self.replies.pop(0) if self.replies else RESTING

    def gw(ex):
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%d.json" % id(ex))))
        g._resolve_coin = lambda coin: dict(resolved)
        g._get_exchange_client = lambda *a, **k: ex
        g._exchange_client_has_symbol = lambda *a, **k: True
        g._validate_final_wire_order = lambda *a, **k: (True, {})
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._exchange_client_for_coin = lambda coin: (ex, "BTC")
        g._pre_send_ownership_gate = lambda it: (True, {})
        g.leader_reduced_since = lambda f: 0
        g._margin_mode_done = {"BTC"}
        g.cfg.master_switch_now = lambda: True
        return g

    def own_cloid_each(ex, iid, n):
        cl = [x["cloid"] for x in ex.calls]
        return (len(ex.calls) == n and all(cl) and len(set(cl)) == n
                and all(x["cloid"] in x["pending_at_call"] for x in ex.calls))

    # ---- S1: IOC no-match then the follow-up send (entry IOC retry / missed-entry limit)
    ex = Ex("s1", [NOMATCH, FILLED(1.0, 100.0)])
    g = gw(ex)
    it = mk_intent("s1")
    g.audit.append_order_intent(it)
    ok, status, res = g._send_real(it)
    check("S1_IOC_RETRY_ACTUALLY_SENT_TWICE", ok and len(ex.calls) == 2, "calls=%d ok=%s" % (len(ex.calls), ok))
    check("S1_IOC_RETRY_OWN_CLOID_AND_PENDING_ROW_BEFORE_CALL", own_cloid_each(ex, "s1", 2), str(ex.calls))
    st = [r["status"] for r in latest_by_attempt("s1").values()]
    # _send_real returns the LAST attempt for the caller's final row; the superseded first attempt must already be closed
    check("S1_SUPERSEDED_ATTEMPT_NOT_LEFT_PENDING", len(st) == 2 and st.count("pending_send") == 1, str(st))
    check("S1_RETRY_NOT_REDUCE_ONLY", all(x["ro"] is False for x in ex.calls))

    # ---- S2: 429 recovery
    ex = Ex("s2", [RESTING])
    g = gw(ex)
    it = mk_intent("s2")
    g.audit.append_order_intent(it)
    g.ledger.sleeve(A, "BTC")
    timing = g._base_timing(it)
    modes_before = dict(__import__("json").loads(c.LIVE_CONFIG_FILE.read_text(encoding="utf-8-sig")).get("wallets", {}).get(A, {}))
    g._entry_add_rate_limit_recovery(ex, "BTC", it, 2, 1.0, 100.0, 100.0, "429 too many requests", timing, dict(resolved))
    check("S2_RATE_LIMIT_RECOVERY_OWN_CLOID_AND_PENDING_ROW_BEFORE_CALL", own_cloid_each(ex, "s2", 1), str(ex.calls))
    modes_after = dict(__import__("json").loads(c.LIVE_CONFIG_FILE.read_text(encoding="utf-8-sig")).get("wallets", {}).get(A, {}))
    check("S2_429_NEVER_CHANGES_WALLET_MODE", modes_before.get("mode") == modes_after.get("mode") == "ON")

    # ---- S3: standing close (opposes and fits inside the net => reduce-only; never blocked)
    ex = Ex("s3", [RESTING])
    g = gw(ex)
    g.ledger.sleeve(A, "BTC")["signed_size"] = 2.0
    it = c.IntentBuilder(c.ConfigManager(), g.ledger).build(
        c.LeaderFill("f_s3", A, "BTC", "SELL", 100.0, 1.0, c.utc_now_ms(), "TEST"))
    it.intent_id = "s3"
    g.audit.append_order_intent(it)
    g._queue_exit_recovery_if_needed(ex, "BTC", it, 99.0, 2.0, {}, "could not immediately match")
    check("S3_STANDING_CLOSE_SENT", len(ex.calls) == 1, str(ex.calls))
    check("S3_STANDING_CLOSE_OWN_CLOID_AND_PENDING_ROW_BEFORE_CALL", own_cloid_each(ex, "s3", 1), str(ex.calls))
    check("S3_STANDING_CLOSE_STILL_REDUCE_ONLY", bool(ex.calls) and ex.calls[0]["ro"] is True)
    recovery_rows = [r for r in disk_rows(c.SEND_ATTEMPTS_CSV) if r.get("cloid") == ex.calls[0]["cloid"]]
    check("S3_STANDING_CLOSE_PENDING_ATTEMPT_FINALISED",
          len(recovery_rows) == 2 and recovery_rows[-1].get("terminal_state") == "EXIT_RECOVERY_ACTIVE"
          and recovery_rows[-1].get("pending_send_done_ms") and recovery_rows[-1].get("status") != "pending_send",
          str([(r.get("status"), r.get("terminal_state"), r.get("pending_send_done_ms")) for r in recovery_rows]))

    # ---- S4: every non-first physical send site passes its own cloid and a pre_send hook
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    sites = re.findall(r"self\._place_order\((.*?)\)\n", src, re.S)
    bad = [s[:70] for s in sites if "pre_send=" not in s or "cloid=" not in s]
    check("S4_ALL_SIX_PLACE_ORDER_SITES_HAVE_CLOID_AND_PRE_SEND", len(sites) == 7 and not bad, "%d %s" % (len(sites), bad))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
