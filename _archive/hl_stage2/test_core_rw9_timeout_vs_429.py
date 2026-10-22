#!/usr/bin/env python3
"""rw9 integration: rw8 reconcile-by-cloid-before-resend must coexist with rw7b 429-vs-timeout recovery.

A TIMEOUT is reconciled by cloid before any resend (never blind-resent); an explicit 429 supersedes its pending row and retries.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw9_timeout_vs_429.py
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
    tmp = Path(tempfile.mkdtemp(prefix="rw9_"))
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

    import json as _json
    os.environ["HL_LIVE_RATE_LIMIT_COOLDOWN_MS"] = "0"

    def attempts(iid):
        return [r for r in disk_rows(c.SEND_ATTEMPTS_CSV) if r.get("intent_id") == iid]

    def latest(iid):
        out = {}
        for r in attempts(iid):
            out[r["attempt_id"]] = r
        return out

    def run(label, exc, resolver):
        iid = "z" + label
        it = mk_intent(iid)
        c.AuditLogWriter().append_order_intent(it)
        ex = Ex([exc, FILLED(1.0, 100.0)])
        g = gw(ex)
        seen = []
        real = g._resolve_ambiguous_send_outcome

        def spy(*a, **k):
            seen.append(len(ex.calls))  # exchange calls made before this reconcile ran
            return resolver(real, *a, **k)
        g._resolve_ambiguous_send_outcome = spy
        ok, status, res = g._send_real(it)
        return ex, seen, ok, res, latest(iid), it

    TO = TimeoutError("Read timed out")
    class ClientError(Exception):
        """Shape of hyperliquid.utils.error.ClientError: status_code is the structured HTTP status."""
        def __init__(self, status_code, error_code, error_message, header=None, error_data=None):
            super().__init__(status_code, error_code, error_message, header, error_data)
            self.status_code = status_code

    R429 = ClientError(429, None, "Too many requests")  # structural 429 (was RuntimeError("ClientError(429...)") text)
    unreadable = lambda real, *a, **k: real(*a, **k)  # real resolver; orderStatus read raises below
    real_post_many = c._XNET.post_many

    def post_many(fetcher, payloads, *a, **k):
        if any(isinstance(p, dict) and p.get("type") == "orderStatus" for p in payloads):
            raise RuntimeError("info down")  # the cloid lookup is unreadable
        return real_post_many(fetcher, payloads, *a, **k)
    c._XNET.post_many = post_many

    # 1. timeout, reconcile unreadable -> hold, exactly ONE exchange call, never resent
    ex, seen, ok, res, lat, it = run("TOHOLD", TO, unreadable)
    check("W1_TIMEOUT_RECONCILED_BEFORE_ANY_RESEND", seen == [1], str(seen))
    check("W1_TIMEOUT_UNREADABLE_NEVER_BLIND_RESENT", len(ex.calls) == 1 and not ok, "calls=%d ok=%s" % (len(ex.calls), ok))
    # 2. timeout, original confirmed absent -> one retry, earlier row stays pending + recorded as ambiguous
    ex, seen, ok, res, lat, it = run("TOGONE", TO, lambda real, *a, **k: None)
    tm = res.get("timing") or {}
    first = next((r["attempt_id"] for r in attempts("zTOGONE") if r.get("status") == "pending_send"), "")
    check("W2_TIMEOUT_CONFIRMED_ABSENT_RETRIES_ONCE_AFTER_RECONCILE", ok and seen == [1] and len(ex.calls) == 2, "seen=%s calls=%d" % (seen, len(ex.calls)))
    check("W2_TIMEOUT_EARLIER_ROW_STAYS_PENDING_AND_AMBIGUOUS", bool(first) and lat[first]["status"] == "pending_send"
          and tm.get("ambiguous_attempt_ids") == [first], str(tm.get("ambiguous_attempt_ids")))
    # 3. explicit 429 -> definite refusal: no reconcile needed, earlier row superseded, retried
    ex, seen, ok, res, lat, it = run("429", R429, unreadable)
    tm = res.get("timing") or {}
    first = next((r["attempt_id"] for r in attempts("z429") if r.get("status") == "pending_send"), "")
    check("W3_429_RETRIES_ONCE", ok and len(ex.calls) == 2 and seen == [], "seen=%s calls=%d ok=%s" % (seen, len(ex.calls), ok))
    check("W3_429_SUPERSEDES_EARLIER_PENDING_ROW", bool(first) and lat[first]["terminal_state"] == "SUPERSEDED_BY_RETRY"
          and not tm.get("ambiguous_attempt_ids"), str(lat.get(first)))
    mode = _json.loads(c.LIVE_CONFIG_FILE.read_text(encoding="utf-8-sig"))["wallets"][A]["mode"]
    check("W4_NEITHER_CHANGES_WALLET_MODE", mode == "ON")
    # 4. mixed text (429 then timed out) is a TIMEOUT: reconciled, never blind
    ex, seen, ok, res, lat, it = run("MIX", RuntimeError("429 then timed out"), unreadable)
    check("W5_MIXED_429_TIMEOUT_TEXT_RECONCILES_NOT_BLIND", seen == [1] and len(ex.calls) == 1, "seen=%s calls=%d" % (seen, len(ex.calls)))

    # 5. structural-only: text that merely contains 429 / looks like a 429 is NOT a definite refusal
    for lbl, exc in (("PX", RuntimeError("px 429.5 connection aborted")), ("RESET", ConnectionResetError("reset by peer 429 bytes")),
                     ("TEXT", RuntimeError("ClientError(429, 'Too many requests')")), ("OTHER", ValueError("rate limit 429"))):
        ex, seen, ok, res, lat, it = run("S" + lbl, exc, unreadable)
        check("S1_%s_TEXT_429_RECONCILES_NO_BLIND_RESEND" % lbl, seen == [1] and len(ex.calls) == 1 and not ok,
              "seen=%s calls=%d ok=%s" % (seen, len(ex.calls), ok))
    check("S2_CLASSIFIER_IS_STRUCTURAL", c.classify_rate_limit_kind(R429) == "RATE_LIMIT"
          and c.classify_rate_limit_kind(RuntimeError("ClientError(429, 'x')")) == "TIMEOUT"
          and c.classify_rate_limit_kind(RuntimeError("px 429.5 connection aborted")) == "TIMEOUT"
          and c.classify_rate_limit_kind(TimeoutError("Read timed out")) == "TIMEOUT"
          and c.classify_rate_limit_kind(RuntimeError("Too many requests")) == "TIMEOUT"
          and c.classify_rate_limit_kind("px 429.5 aborted") == "TIMEOUT" and c.classify_rate_limit_kind("rate limit") == "TIMEOUT"
          and c.classify_rate_limit_kind("ClientError(429, None, 'x')") == "RATE_LIMIT"
          and c.classify_rate_limit_kind(ClientError(500, None, "x")) == "TIMEOUT"
          and c.classify_rate_limit_kind(None) == "TIMEOUT")
    # 6. EXIT / REDUCE closes still reconcile first even on a structural 429 (never blind-resent, no definite shortcut)
    for lc in ("EXIT", "REDUCE"):
        iid = "zX" + lc
        it = mk_intent(iid, side="SELL", notes="lifecycle=%s;" % lc)
        c.AuditLogWriter().append_order_intent(it)
        ex = Ex([R429, FILLED(1.0, 100.0)])
        g = gw(ex)
        seen = []
        real = g._resolve_ambiguous_send_outcome

        def spy(*a, _seen=seen, _real=real, _ex=ex, **k):
            _seen.append(len(_ex.calls))
            return _real(*a, **k)
        g._resolve_ambiguous_send_outcome = spy
        ok, status, res = g._send_real(it)
        check("S3_%s_STRUCTURAL_429_STILL_RECONCILES_FIRST" % lc, seen == [1] and len(ex.calls) == 1 and not ok,
              "seen=%s calls=%d ok=%s" % (seen, len(ex.calls), ok))

    os.environ.pop("HL_LIVE_RATE_LIMIT_COOLDOWN_MS", None)
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
