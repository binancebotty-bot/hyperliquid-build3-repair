#!/usr/bin/env python3
"""rw12 item 1: after an entry IOC retry (its OWN cloid) raises a timeout, the reconcile must resolve the RETRY cloid, not the
stale initial one; a further send is allowed only when every outstanding attempt is confirmed absent.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw12_retry_cloid.py
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
    tmp = Path(tempfile.mkdtemp(prefix="rw12_"))
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

    os.environ["HL_LIVE_MISSED_ENTRY_RULE"] = "0"  # plain entry IOC retry path, not the missed-entry GTC
    os.environ["HL_LIVE_ENTRY_IOC_RETRY_BPS"] = "300"
    os.environ["HL_LIVE_MAX_ENTRY_IOC_RETRY_BPS"] = "300"
    real_post_many = c._XNET_MODULE.post_many  # the true function: c._XNET is a guard proxy that re-resolves the patched attribute

    def post_many(fetcher, payloads, *a, **k):
        if any(isinstance(p, dict) and p.get("type") == "orderStatus" for p in payloads):
            raise RuntimeError("info down")  # the cloid lookup is unreadable
        return real_post_many(fetcher, payloads, *a, **k)
    c._XNET.post_many = post_many

    def run(label, retry_resolves_absent):
        iid = "r" + label
        it = mk_intent(iid)
        c.AuditLogWriter().append_order_intent(it)
        ex = Ex([NOMATCH, TimeoutError("Read timed out"), FILLED(1.0, 100.0)])
        g = gw(ex)
        seen = []
        real = g._resolve_ambiguous_send_outcome

        def spy(sdk_coin, intent, cloid, *a, **k):
            first = ex.calls[0]["cloid"] if ex.calls else None
            seen.append(str(cloid))
            if str(cloid) == first:
                return None  # the stale INITIAL cloid reads "cancelled/absent": the bug would then resend
            if retry_resolves_absent:
                return None
            return real(sdk_coin, intent, cloid, *a, **k)  # retry cloid unreadable -> hold + alert
        g._resolve_ambiguous_send_outcome = spy
        ok, status, res = g._send_real(it)
        return ex, seen, ok, status, res

    ex, seen, ok, status, res = run("HOLD", False)
    retry_cloid = ex.calls[1]["cloid"] if len(ex.calls) > 1 else None
    check("R1_RETRY_ACTUALLY_SENT_WITH_OWN_CLOID", len(ex.calls) >= 2 and ex.calls[0]["cloid"] != retry_cloid, str(ex.calls))
    check("R1_RECONCILE_RESOLVES_RETRY_CLOID_NOT_INITIAL", bool(seen) and seen[0] == retry_cloid and ex.calls[0]["cloid"] not in seen,
          "seen=%s calls=%s" % (seen, ex.calls))
    check("R1_THIRD_SEND_BLOCKED_WHILE_RETRY_UNRESOLVED", len(ex.calls) == 2 and not ok, "calls=%d ok=%s" % (len(ex.calls), ok))
    check("R1_HOLD_ROW_REPORTED", (res or {}).get("terminal_state") == "SEND_OUTCOME_UNKNOWN_HOLD", str((res or {}).get("terminal_state")))
    ex, seen, ok, status, res = run("GONE", True)
    tm = (res or {}).get("timing") or {}
    check("R2_THIRD_SEND_ONLY_AFTER_RETRY_CONFIRMED_ABSENT", ok and len(ex.calls) == 3 and seen[0] == ex.calls[1]["cloid"],
          "seen=%s calls=%d" % (seen, len(ex.calls)))
    retry_attempt = next((r["attempt_id"] for r in disk_rows(c.SEND_ATTEMPTS_CSV)
                          if r.get("intent_id") == "rGONE" and r.get("cloid") == ex.calls[1]["cloid"]), "")
    check("R2_RETRY_ATTEMPT_KEPT_AMBIGUOUS", bool(retry_attempt) and retry_attempt in (tm.get("ambiguous_attempt_ids") or []),
          str(tm.get("ambiguous_attempt_ids")))
    # R3: an EARLIER attempt still ambiguous blocks a further send even when the latest one reads absent
    it = mk_intent("rOLD")
    c.AuditLogWriter().append_order_intent(it)
    ex = Ex([TimeoutError("Read timed out"), FILLED(1.0, 100.0)])
    g = gw(ex)
    seen = []
    real = g._resolve_ambiguous_send_outcome

    def spy3(sdk_coin, intent, cloid, *a, **k):
        seen.append(str(cloid))
        return None if str(cloid) == ex.calls[0]["cloid"] else real(sdk_coin, intent, cloid, *a, **k)
    g._resolve_ambiguous_send_outcome = spy3
    tm0 = g._base_timing(it)
    tm0["ambiguous_attempt_ids"] = ["older_attempt"]
    tm0["attempt_cloids"] = {"older_attempt": "0x" + "9" * 32}
    ok, status, res = g._send_real(it, tm0)
    check("R3_EARLIER_AMBIGUOUS_ATTEMPT_BLOCKS_FURTHER_SEND", len(ex.calls) == 1 and not ok and len(seen) == 2
          and seen[1] == "0x" + "9" * 32, "seen=%s calls=%d" % (seen, len(ex.calls)))
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
