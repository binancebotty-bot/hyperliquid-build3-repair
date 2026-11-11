#!/usr/bin/env python3
"""Codex review fixes on the send-integrity work (rw7b): durability barrier, supersede persistence, 429 vs timeout.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw7b_review_fixes.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. No network, no orders: every send goes to a fake exchange.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40
B = "0x" + "b" * 40
FOLLOWER = "0x" + "c" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="rw7b_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_INTENT_DURABLE_WAIT_MS": "2000"})
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12},
                    B: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    c.HLAccount, c.HLExchange = object, object

    def mk_intent(iid, wallet=A, side="BUY", notes="lifecycle=ENTRY;"):
        fill = c.LeaderFill("f_" + iid, wallet, "BTC", side, 100.0, 1.0, c.utc_now_ms(), "TEST")
        return c.Intent(iid, fill, side, 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
                        "sleeve:%s:BTC" % wallet, "", "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), notes)

    def disk_rows(path):
        if not path.exists():
            return []
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
    FILLED = lambda sz, px: {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"filled": {"totalSz": str(sz), "avgPx": str(px), "oid": 3}}]}}}
    NOMATCH = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"error": "Order could not immediately match against any resting orders. asset=3"}]}}}
    RESTING = {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 9}}]}}}

    class Ex:
        """Fake exchange: replies are values, or exception instances that are raised."""
        def __init__(self, replies):
            self.replies, self.calls = list(replies), []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"cloid": str(cloid) if cloid is not None else None, "tif": tif["limit"]["tif"]})
            r = self.replies.pop(0) if self.replies else RESTING
            if isinstance(r, BaseException):
                raise r
            return r

        def bulk_orders(self, *a, **k):  # pragma: no cover
            raise AssertionError("unexpected bulk_orders")

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

    def wait_for(fn, secs=8.0):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            if fn():
                return True
            time.sleep(0.05)
        return bool(fn())

    def barrier_errors(iid):
        return [r for r in disk_rows(c.ERRORS_CSV) if r.get("context") == "intent_durable_barrier" and iid in r.get("message", "")]

    real_append_csv = c.append_csv
    mode = {"fail": False}

    def wrapped_append(path, fieldnames, row, *a, **k):
        if mode["fail"] and path == c.ORDER_INTENTS_CSV and threading.current_thread().name == "HLCore-intent-writer":
            raise OSError("simulated intent writer failure")
        return real_append_csv(path, fieldnames, row, *a, **k)
    c.append_csv = wrapped_append

    try:
        # ---- F1: eviction of a failed sequence + mapping prune must not let the production barrier pass with no sequence
        os.environ["HL_LIVE_INTENT_FAILED_MAX"] = "1"
        os.environ["HL_LIVE_INTENT_DURABLE_WAIT_MS"] = "2000"
        mode["fail"] = True
        c.AuditLogWriter().append_order_intent(mk_intent("e1"))
        c.AuditLogWriter().append_order_intent(mk_intent("e2"))
        evicted = wait_for(lambda: int(c._INTENT_STATE.get("failed_evicted_seq") or 0) >= 1, 20.0)
        wait_for(lambda: not c._INTENT_QUEUE and not c._INTENT_STATE["busy"], 20.0)
        mode["fail"] = False
        for i in range(20001):  # a full id map, every entry already durable: the next enqueue prunes it
            c._INTENT_SEQ_BY_ID["dummy%d" % i] = 0
        c.AuditLogWriter().append_order_intent(mk_intent("e3"))  # this enqueue runs the production prune
        c.flush_intent_writer(10.0)
        check("F1_SETUP_FAILED_ROW_EVICTED", evicted and int(c._INTENT_STATE.get("failed_evicted_seq") or 0) >= 1,
              str({k: c._INTENT_STATE.get(k) for k in ("failed_evicted_seq", "durable_seq", "next_seq")}))
        ex = Ex([FILLED(1.0, 100.0)])
        g = gw(ex)
        fails_before = c.audit_write_failure_count()
        ok, status, res = g._send_real(mk_intent("e1"))  # production path: send hook -> intent_seq_for -> wait_intent_durable
        loud = wait_for(lambda: len(barrier_errors("e1")) >= 1, 5.0)
        check("F1_ORDER_STILL_SENT_FAIL_OPEN", ok and len(ex.calls) == 1, "%s %s" % (ok, ex.calls))
        check("F1_PRUNED_EVICTED_INTENT_IS_NOT_REPORTED_DURABLE",
              loud and c.audit_write_failure_count() > fails_before,
              "errors=%s seq=%s" % (barrier_errors("e1"), c.intent_seq_for("e1")))
        check("F1B_DURABLE_INTENT_STILL_PASSES_SILENTLY",
              c.wait_intent_durable(c.intent_seq_for("e3"), "e3") is True and c.wait_intent_durable(None, "inline") is True)
        os.environ.pop("HL_LIVE_INTENT_FAILED_MAX", None)

        # ---- F2: a later successful append must not mask an earlier failed row of the SAME wallet; other wallets are unaffected
        C = "0x" + "d" * 40
        for k in ("failed_unreported", "failed_unknown_wallets"):
            if k in c._INTENT_STATE:
                c._INTENT_STATE[k].clear()
        mode["fail"] = True
        c.AuditLogWriter().append_order_intent(mk_intent("m1", A))  # fails: wallet A
        c.AuditLogWriter().append_order_intent(mk_intent("m2", B))  # fails: wallet B
        wait_for(lambda: not c._INTENT_QUEUE and not c._INTENT_STATE["busy"], 20.0)
        mode["fail"] = False
        c.AuditLogWriter().append_order_intent(mk_intent("m3", A))  # succeeds, and is a later sequence than m1
        c.AuditLogWriter().append_order_intent(mk_intent("m4", C))
        c.flush_intent_writer(10.0)
        seq3, seq4 = c.intent_seq_for("m3"), c.intent_seq_for("m4")
        check("F2_SETUP_LATER_ROWS_DURABLE", seq3 is not None and seq4 is not None
              and int(c._INTENT_STATE["durable_seq"]) >= max(seq3, seq4))
        fails_before = c.audit_write_failure_count()
        t0 = time.monotonic()
        ok_c = c.wait_intent_durable(seq4, "m4", wallet=C)
        check("F2_UNRELATED_WALLET_FAILURES_DO_NOT_REPORT_OR_WAIT",
              ok_c is True and c.audit_write_failure_count() == fails_before and time.monotonic() - t0 < 0.2)
        ex = Ex([FILLED(1.0, 100.0)])
        ok, status, res = gw(ex)._send_real(mk_intent("m3", A))  # production hook; m3 itself is on disk
        loud = wait_for(lambda: len(barrier_errors("m3")) >= 1, 5.0)
        check("F2_EARLIER_FAILED_ROW_OF_SAME_WALLET_IS_REPORTED_NOT_MASKED",
              loud and "earlier" in barrier_errors("m3")[-1].get("message", "") and c.audit_write_failure_count() > fails_before,
              str(barrier_errors("m3")))
        check("F2_ORDER_STILL_SENT_AND_NOT_HELD_UP", ok and len(ex.calls) == 1)
        n_err = len(barrier_errors("m3"))
        check("F2_REPORTED_ONCE_NOT_ON_EVERY_LATER_SEND", c.wait_intent_durable(seq3, "m3", wallet=A) is True
              and len(barrier_errors("m3")) == n_err)

        # ---- F3: a failed supersede write is loud, keeps the prior attempt pending, and is never claimed as superseded
        def attempts(iid):
            return [r for r in disk_rows(c.SEND_ATTEMPTS_CSV) if r.get("intent_id") == iid]

        def latest_by_attempt(iid):
            out = {}
            for r in attempts(iid):
                out[r["attempt_id"]] = r
            return out

        def supersede_errors(iid):
            return [r for r in disk_rows(c.RECONCILIATION_CSV)
                    if r.get("status") == "SEND_ATTEMPT_SUPERSEDE_FAILED" and r.get("intent_id") == iid]

        ex = Ex([FILLED(1.0, 100.0)])
        g = gw(ex)
        it = mk_intent("p1")
        c.AuditLogWriter().append_order_intent(it)
        ex = Ex([NOMATCH, FILLED(1.0, 100.0)])
        g = gw(ex)
        ok, status, res = g._send_real(it)
        lat = latest_by_attempt("p1")
        check("F3_CONTROL_SUPERSEDE_OK_MARKS_FIRST_ATTEMPT", ok and len(ex.calls) == 2
              and sorted(r["terminal_state"] for r in lat.values()).count("SUPERSEDED_BY_RETRY") == 1,
              str([(r["status"], r["terminal_state"]) for r in lat.values()]))

        real_update = c.update_send_attempt_row
        for label, boom in (("FALSE", lambda *a, **k: False), ("RAISES", None)):
            iid = "p2" + label
            it = mk_intent(iid)
            c.AuditLogWriter().append_order_intent(it)
            ex = Ex([NOMATCH, FILLED(1.0, 100.0)])
            g = gw(ex)
            if boom is None:
                def boom(*a, **k):
                    raise OSError("simulated send_attempts write failure")
            c.update_send_attempt_row = boom
            try:
                ok, status, res = g._send_real(it)
            finally:
                c.update_send_attempt_row = real_update
            lat = latest_by_attempt(iid)
            last_id = (res.get("timing") or {}).get("send_attempt_id")
            first = [r for r in lat.values() if r["attempt_id"] != last_id and r.get("status") == "pending_send"]  # the retry owns last_id
            check("F3_%s_RETRY_STILL_PROCEEDS_NOT_BLOCKED" % label, ok and len(ex.calls) == 2, "ok=%s calls=%d" % (ok, len(ex.calls)))
            check("F3_%s_PRIOR_ATTEMPT_NOT_CLAIMED_SUPERSEDED_STAYS_PENDING" % label,
                  len(first) == 1 and not any(r.get("terminal_state") == "SUPERSEDED_BY_RETRY" for r in lat.values()),
                  str([(r["status"], r["terminal_state"]) for r in lat.values()]))
            pend = (res.get("timing") or {}).get("unsuperseded_attempt_ids") or []
            check("F3_%s_PENDING_ATTEMPT_KEPT_IN_MEMORY" % label, len(pend) == 1 and pend[0] == first[0]["attempt_id"] if first else False, str(pend))
            check("F3_%s_FAILURE_IS_VISIBLE_AUDIT_ROW_AND_ERROR_LINE" % label,
                  len(supersede_errors(iid)) == 1 and any(r.get("context") == "supersede_attempt" and iid in r.get("message", "")
                                                           for r in disk_rows(c.ERRORS_CSV)),
                  str(supersede_errors(iid)))

        # ---- F4: exception recovery: an explicit 429 (no order) supersedes the earlier pending row, a timeout keeps it pending
        os.environ["HL_LIVE_RATE_LIMIT_COOLDOWN_MS"] = "0"
        import json as _json

        def wallet_mode():
            return _json.loads(c.LIVE_CONFIG_FILE.read_text(encoding="utf-8-sig"))["wallets"][A]["mode"]

        def pending_rows(iid):
            return [r for r in attempts(iid) if r.get("status") == "pending_send"]

        class ClientError(Exception):  # shape of hyperliquid.utils.error.ClientError: structured status_code
            def __init__(self, status_code, error_code, error_message, header=None, error_data=None):
                super().__init__(status_code, error_code, error_message, header, error_data)
                self.status_code = status_code

        for label, exc in (("429", ClientError(429, None, "Too many requests")),
                           ("TIMEOUT", TimeoutError("Read timed out"))):
            iid = "q" + label
            it = mk_intent(iid)
            c.AuditLogWriter().append_order_intent(it)
            ex = Ex([exc, FILLED(1.0, 100.0)])
            g = gw(ex)
            g._resolve_ambiguous_send_outcome = lambda *a, **k: None  # rw8: a timeout reconciles first; here the original is confirmed absent
            ok, status, res = g._send_real(it)
            tm = res.get("timing") or {}
            rows = pending_rows(iid)  # first row = the attempt whose call raised
            first_id = rows[0]["attempt_id"] if rows else ""
            lat = latest_by_attempt(iid)
            check("F4_%s_RECOVERY_STILL_SENT_SAME_AS_BEFORE" % label, ok and len(ex.calls) == 2 and len(rows) == 2,
                  "ok=%s calls=%d rows=%d" % (ok, len(ex.calls), len(rows)))
            check("F4_%s_RECOVERY_HAS_OWN_ATTEMPT" % label, bool(first_id) and tm.get("send_attempt_id") not in ("", first_id))
            if label == "429":
                check("F4_429_SUPERSEDES_EARLIER_PENDING_ROW",
                      lat[first_id]["terminal_state"] == "SUPERSEDED_BY_RETRY" and lat[first_id]["status"] != "pending_send"
                      and not tm.get("ambiguous_attempt_ids"),
                      str((lat[first_id]["status"], lat[first_id]["terminal_state"], tm.get("ambiguous_attempt_ids"))))
            else:
                check("F4_TIMEOUT_KEEPS_EARLIER_ROW_PENDING_AND_ITS_ATTEMPT_ID",
                      lat[first_id]["status"] == "pending_send" and lat[first_id]["terminal_state"] == "PENDING_SEND"
                      and tm.get("ambiguous_attempt_ids") == [first_id],
                      str((lat[first_id]["status"], lat[first_id]["terminal_state"], tm.get("ambiguous_attempt_ids"))))
            check("F4_%s_NEVER_CHANGES_WALLET_MODE" % label, wallet_mode() == "ON")
        check("F4_CLASSIFIER_SPLITS_429_FROM_TIMEOUT",
              c.classify_rate_limit_kind(ClientError(429, None, "x")) == "RATE_LIMIT"
              and c.classify_rate_limit_kind("ClientError(429, None, 'x')") == "TIMEOUT"
              and c.classify_rate_limit_kind(RuntimeError("Too many requests")) == "TIMEOUT"
              and c.classify_rate_limit_kind("Read timed out") == "TIMEOUT"
              and c.classify_rate_limit_kind("429 then timed out") == "TIMEOUT"
              and c.classify_reject_category("ClientError(429, 'x')", {}) == c.classify_reject_category("Read timed out", {})
              == "RATE_LIMIT_OR_TIMEOUT")

        # ---- G1: the missed-entry GTC branch (IOC finds no match inside the tolerance window -> limit at the leader's price)
        iid = "g1"
        it = mk_intent(iid)
        c.AuditLogWriter().append_order_intent(it)
        ex = Ex([NOMATCH, RESTING])
        g = gw(ex)
        ok, status, res = g._send_real(it)
        lat = latest_by_attempt(iid)
        pr = pending_rows(iid)
        check("G1_MISSED_ENTRY_GTC_SENT_AFTER_IOC_NO_MATCH", len(ex.calls) == 2 and [x["tif"] for x in ex.calls] == ["Ioc", "Gtc"]
              and ok and status == "ORDER_RESTING", "%s %s %s" % (ok, status, [x["tif"] for x in ex.calls]))
        check("G1_MISSED_ENTRY_GTC_OWN_CLOID_AND_PENDING_ROW", len(pr) == 2 and len({x["cloid"] for x in ex.calls}) == 2
              and all(x["cloid"] for x in ex.calls) and {r["cloid"] for r in pr} == {x["cloid"] for x in ex.calls})
        first_id = pr[0]["attempt_id"] if pr else ""
        check("G1_MISSED_ENTRY_GTC_SUPERSEDES_REJECTED_IOC_ROW", lat[first_id]["terminal_state"] == "SUPERSEDED_BY_RETRY"
              and (res.get("timing") or {}).get("send_attempt_id") != first_id)
        check("G1_MISSED_ENTRY_GTC_REGISTERED_AS_RESTING_ENTRY", g.resting_entry_for(A, "BTC", "BUY") is not None)
    finally:
        c.append_csv = real_append_csv
        os.environ.pop("HL_LIVE_RATE_LIMIT_COOLDOWN_MS", None)
        os.environ.pop("HL_LIVE_INTENT_FAILED_MAX", None)

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
