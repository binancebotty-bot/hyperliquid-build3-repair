#!/usr/bin/env python3
"""rw13 item A: a recovery send (429/timeout entry-add recovery, standing close) that itself raises a timeout-class error is
reconciled by ITS cloid (and every earlier outstanding attempt) before anything else; unreadable -> SEND_OUTCOME_UNKNOWN_HOLD,
never a blind resend. A structural 429 (exception with int status_code 429) stays a definite refusal: superseded, no reconcile.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw13_recovery_reconcile.py
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


class E429(Exception):
    status_code = 429


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="rw13a_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_INTENT_DURABLE_WAIT_MS": "2000",
                       "HL_LIVE_RATE_LIMIT_COOLDOWN_MS": "0"})
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

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    class Ex:
        def __init__(self, replies):
            self.replies, self.calls = list(replies), []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"cloid": str(cloid) if cloid is not None else None, "ro": reduce_only})
            r = self.replies.pop(0)
            if isinstance(r, BaseException):
                raise r
            return r

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

    real_post_many = c._XNET.post_many

    def post_many(fetcher, payloads, *a, **k):
        if any(isinstance(p, dict) and p.get("type") == "orderStatus" for p in payloads):
            raise RuntimeError("info down")  # the cloid lookup is unreadable
        return real_post_many(fetcher, payloads, *a, **k)
    c._XNET.post_many = post_many

    def spy(g, absent_first=0):
        """Records every cloid the reconciler is asked about; the first `absent_first` answer 'confirmed absent'."""
        seen = []
        real = g._resolve_ambiguous_send_outcome

        def f(sdk_coin, intent, cloid, *a, **k):
            seen.append(str(cloid))
            if len(seen) <= absent_first:
                return None
            return real(sdk_coin, intent, cloid, *a, **k)
        g._resolve_ambiguous_send_outcome = f
        return seen

    def attempt_status(iid):
        out = {}
        for r in disk_rows(c.SEND_ATTEMPTS_CSV):
            if r.get("intent_id") == iid:
                out[r["attempt_id"]] = r
        return out

    # ---- A1: entry/add recovery send times out -> reconcile ITS cloid, hold, no further send
    ex = Ex([TimeoutError("Read timed out")])
    g = gw(ex)
    it = mk_intent("a1")
    g.audit.append_order_intent(it)
    seen = spy(g)
    r = g._entry_add_rate_limit_recovery(ex, "BTC", it, 2, 1.0, 100.0, 100.0, "429 too many requests", g._base_timing(it), dict(resolved))
    cl = ex.calls[0]["cloid"] if ex.calls else None
    check("A1_RECONCILE_CALLED_WITH_RECOVERY_CLOID", bool(cl) and seen[:1] == [cl], "seen=%s calls=%s" % (seen, ex.calls))
    check("A1_HOLD_RESULT_WHEN_UNREADABLE", r is not None and r[0] is False and (r[2] or {}).get("terminal_state") == "SEND_OUTCOME_UNKNOWN_HOLD",
          str(r and r[2].get("terminal_state")))
    check("A1_NO_FURTHER_SEND", len(ex.calls) == 1, str(ex.calls))

    # ---- A2: an earlier outstanding (timed-out) attempt is reconciled too, after the recovery cloid
    ex = Ex([TimeoutError("Read timed out")])
    g = gw(ex)
    it = mk_intent("a2")
    g.audit.append_order_intent(it)
    old = "0x" + "9" * 32
    tm = g._base_timing(it)
    tm["send_attempt_id"] = "att_old"
    tm["attempt_cloids"] = {"att_old": old}
    seen = spy(g, absent_first=1)  # the recovery cloid reads absent; the earlier one is unreadable -> hold
    r = g._entry_add_rate_limit_recovery(ex, "BTC", it, 2, 1.0, 100.0, 100.0, "Read timed out", tm, dict(resolved))
    check("A2_RECOVERY_CLOID_THEN_EARLIER_ATTEMPT", len(seen) == 2 and seen[0] == ex.calls[0]["cloid"] and seen[1] == old,
          "seen=%s calls=%s" % (seen, ex.calls))
    check("A2_EARLIER_UNREADABLE_HOLDS_NO_SEND", r is not None and r[2].get("terminal_state") == "SEND_OUTCOME_UNKNOWN_HOLD" and len(ex.calls) == 1)

    # ---- A3: every attempt confirmed absent -> plain failure (None), still no resend
    ex = Ex([TimeoutError("Read timed out")])
    g = gw(ex)
    it = mk_intent("a3")
    g.audit.append_order_intent(it)
    seen = spy(g, absent_first=9)
    r = g._entry_add_rate_limit_recovery(ex, "BTC", it, 2, 1.0, 100.0, 100.0, "429", g._base_timing(it), dict(resolved))
    check("A3_ABSENT_NO_RESEND", r is None and len(ex.calls) == 1 and seen == [ex.calls[0]["cloid"]], "r=%s seen=%s" % (r, seen))

    # ---- A4: a definite structural 429 in the recovery send: superseded, never reconciled
    ex = Ex([E429("too many requests")])
    g = gw(ex)
    it = mk_intent("a4")
    g.audit.append_order_intent(it)
    seen = spy(g)
    r = g._entry_add_rate_limit_recovery(ex, "BTC", it, 2, 1.0, 100.0, 100.0, "429", g._base_timing(it), dict(resolved))
    st = [x["status"] for x in attempt_status("a4").values()]
    check("A4_DEFINITE_429_NO_RECONCILE", seen == [] and r is None and len(ex.calls) == 1, "seen=%s r=%s" % (seen, r))
    check("A4_DEFINITE_429_ATTEMPT_SUPERSEDED", bool(st) and "pending_send" not in st, str(st))

    # ---- A5/A6: standing close
    def standing(label, exc):
        ex = Ex([exc])
        g = gw(ex)
        g.ledger.sleeve(A, "BTC")["signed_size"] = 2.0
        it = c.IntentBuilder(c.ConfigManager(), g.ledger).build(
            c.LeaderFill("f_" + label, A, "BTC", "SELL", 100.0, 1.0, c.utc_now_ms(), "TEST"))
        it.intent_id = label
        g.audit.append_order_intent(it)
        seen = spy(g)
        g._queue_exit_recovery_if_needed(ex, "BTC", it, 99.0, 2.0, {}, "could not immediately match")
        return g, it, ex, seen

    g, it, ex, seen = standing("a5", TimeoutError("Read timed out"))
    cl = ex.calls[0]["cloid"] if ex.calls else None
    check("A5_STANDING_CLOSE_TIMEOUT_RECONCILES_ITS_CLOID", bool(cl) and seen == [cl], "seen=%s calls=%s" % (seen, ex.calls))
    check("A5_STANDING_CLOSE_NO_BLIND_RESEND", len(ex.calls) == 1)
    holds = [r for r in disk_rows(c.RECONCILIATION_CSV) if r.get("intent_id") == "a5" and r.get("terminal_state") == "SEND_OUTCOME_UNKNOWN_HOLD"]
    check("A5_STANDING_CLOSE_HOLD_ROW_WRITTEN", len(holds) >= 1, str(len(holds)))
    check("A5_STANDING_CLOSE_NOT_REQUEUED", g._exit_recovery_exists(it))
    g, it, ex, seen = standing("a6", E429("too many requests"))
    check("A6_STANDING_CLOSE_DEFINITE_429_NO_RECONCILE", seen == [] and len(ex.calls) == 1, "seen=%s" % seen)

    # ---- A7: SDK Cloid construction fails after the durable pending row, before exchange.order is reached
    real_sdk_cloid = c._sdk_cloid

    def fail_sdk_cloid(_cloid):
        raise RuntimeError("SDK Cloid construction failed")

    c._sdk_cloid = fail_sdk_cloid
    try:
        g, it, ex, seen = standing("a7", None)
    finally:
        c._sdk_cloid = real_sdk_cloid
    row = next(iter(attempt_status("a7").values()), {})
    failures = [r for r in disk_rows(c.RECONCILIATION_CSV)
                if r.get("intent_id") == "a7" and r.get("status") == "EXIT_RECOVERY_QUEUE_FAILED"]
    check("A7_SETUP_FAILURE_FINALISES_PENDING_ATTEMPT",
          not ex.calls and not seen and row.get("terminal_state") == "EXIT_RECOVERY_QUEUE_FAILED"
          and row.get("pending_send_done_ms") and "SDK Cloid construction failed" in row.get("error", ""),
          str({"calls": ex.calls, "seen": seen, "row": {k: row.get(k) for k in
                                                               ("status", "terminal_state", "pending_send_done_ms", "error")}}))
    check("A7_SETUP_FAILURE_WRITES_RECOVERY_ERROR_ROW", bool(failures), str(failures))

    # ---- A8: three crash windows (after exchange reply, after terminal append,
    # after reconciliation append). SystemExit models a process death: no
    # exception handler/finaliser runs. A fresh gateway must fence blind resend
    # from the original durable pending/finalised send attempt.
    for name, stage in (("a8_parse", "parse"), ("a8_final", "final"), ("a8_reconcile", "reconcile")):
        ex = Ex([{"status": "ok", "response": {"type": "order", "data": {"statuses":
                  [{"resting": {"oid": 78}}]}}}])
        g = gw(ex)
        g.ledger.sleeve(A, "BTC")["signed_size"] = 2.0
        it = c.IntentBuilder(c.ConfigManager(), g.ledger).build(
            c.LeaderFill("f_" + name, A, "BTC", "SELL", 100.0, 1.0, c.utc_now_ms(), "TEST"))
        it.intent_id = name
        g.audit.append_order_intent(it)
        if stage == "parse":
            real = g._parse_hl_response
            def crash_parse(*args, **kwargs):
                real(*args, **kwargs)
                raise SystemExit("injected crash after order reply")
            g._parse_hl_response = crash_parse
        elif stage == "final":
            real = g._append_real_attempt
            def crash_final(*args, **kwargs):
                real(*args, **kwargs)
                raise SystemExit("injected crash after terminal append")
            g._append_real_attempt = crash_final
        else:
            real = g.audit.append_reconciliation
            def crash_reconcile(*args, **kwargs):
                real(*args, **kwargs)
                if args and args[0] == "EXIT_RECOVERY" and args[1] == "EXIT_RECOVERY_QUEUED":
                    raise SystemExit("injected crash after reconciliation")
            g.audit.append_reconciliation = crash_reconcile
        try:
            g._queue_exit_recovery_if_needed(ex, "BTC", it, 99.0, 2.0, {}, "no match")
        except SystemExit:
            pass
        else:
            check(name.upper() + "_CRASH_INJECTED", False)
        prior = [row for row in disk_rows(c.SEND_ATTEMPTS_CSV)
                 if row.get("intent_id") == name and row.get("order_type") == "REAL_GTC_RECOVERY_CLOSE"]
        terminals = [row for row in prior if row.get("status") != "pending_send"]
        fresh = gw(ex)
        fresh.ledger.sleeve(A, "BTC")["signed_size"] = 2.0
        check(name.upper() + "_RESTART_FENCE", fresh._exit_recovery_exists(it), str(prior))
        fresh._queue_exit_recovery_if_needed(ex, "BTC", it, 99.0, 2.0, {}, "no match")
        check(name.upper() + "_NO_BLIND_SECOND_SEND", len(ex.calls) == 1, str(ex.calls))
        check(name.upper() + "_ONE_ATTEMPT_ID", len({row.get("attempt_id") for row in prior}) == 1,
              str([(row.get("attempt_id"), row.get("status")) for row in prior]))
        check(name.upper() + "_MAX_ONE_TERMINAL", len(terminals) <= 1, str(terminals))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
