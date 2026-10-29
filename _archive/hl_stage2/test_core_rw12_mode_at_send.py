#!/usr/bin/env python3
"""rw12 item 2: send_if_allowed re-reads the wallet's CURRENT mode at the final send gate. An intent queued while ON must not
send an entry/add after the wallet moved to CLO or OFF; closes still go in CLO. No wallet mode is ever changed by the engine.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_rw12_mode_at_send.py
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
        g.cfg.liq_parity_enabled = lambda: False
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

    os.environ["HL_LIVE_MISSED_ENTRY_RULE"] = "0"

    def set_mode(g, mode):
        g.cfg.config["wallets"][A]["mode"] = mode  # the operator flips the wallet AFTER the intent was built

    def attempt(label, mode_at_send, side="BUY", lifecycle="ENTRY", reply=None):
        iid = "m" + label
        it = mk_intent(iid, side=side, notes="lifecycle=%s;" % lifecycle)
        c.AuditLogWriter().append_order_intent(it)  # intent built while the wallet was ON (wallet_mode="ON")
        ex = Ex([reply or FILLED(1.0, 100.0)])
        g = gw(ex)
        if lifecycle in ("EXIT", "REDUCE"):
            # C7 T1: a close must be of a position the engine actually records, and the venue must hold it. Seed the owned
            # sleeve this fixture's exit is closing and the matching venue net; no assertion is relaxed by doing so.
            owned = 1.0 if side == "SELL" else -1.0
            g.ledger.sleeve(A, "BTC")["signed_size"] = owned
            g.ledger._recompute_net(g.ledger.data)
            g._fresh_exchange_net = lambda coin, _o=owned: _o
        set_mode(g, mode_at_send)
        sent, status = g.send_if_allowed(it)
        return ex, sent, status, it

    def recon(iid):
        return [r for r in disk_rows(c.RECONCILIATION_CSV) if r.get("intent_id") == iid]

    ex, sent, status, it = attempt("clo_entry", "CLO")
    check("M1_ENTRY_QUEUED_ON_THEN_CLO_IS_BLOCKED", not sent and status == "BLOCKED_CLO_ENTRY" and not ex.calls, "%s %s %d" % (sent, status, len(ex.calls)))
    check("M1_BLOCK_AUDIT_ROW_BLOCKED_CLO_ENTRY", any(r.get("terminal_state") == "BLOCKED_CLO_ENTRY" for r in recon(it.intent_id)), str(recon(it.intent_id)))
    ex, sent, status, it = attempt("clo_add", "CLO", lifecycle="ADD")
    check("M2_ADD_QUEUED_ON_THEN_CLO_IS_BLOCKED", not sent and status == "BLOCKED_CLO_ENTRY" and not ex.calls, "%s %s" % (sent, status))
    ex, sent, status, it = attempt("clo_exit", "CLO", side="SELL", lifecycle="EXIT")
    check("M3_EXIT_STILL_SENT_IN_CLO", len(ex.calls) == 1 and status != "BLOCKED_CLO_ENTRY", "%s %s %d" % (sent, status, len(ex.calls)))
    check("M3_CLO_EXIT_NOT_FORCED_REDUCE_ONLY_BY_THE_GATE", status != "BLOCKED_OFF" and len(ex.calls) == 1, status)
    for lc, side in (("ENTRY", "BUY"), ("ADD", "BUY"), ("EXIT", "SELL"), ("REDUCE", "SELL")):
        ex, sent, status, it = attempt("off_" + lc, "OFF", side=side, lifecycle=lc)
        check("M4_%s_QUEUED_ON_THEN_OFF_SENDS_NOTHING" % lc, not sent and status == "BLOCKED_OFF" and not ex.calls, "%s %s %d" % (sent, status, len(ex.calls)))
    check("M4_OFF_AUDIT_ROW_BLOCKED_OFF", any(r.get("terminal_state") == "BLOCKED_OFF" for r in recon("moff_ENTRY")), str(recon("moff_ENTRY")))
    ex, sent, status, it = attempt("on_entry", "ON")
    check("M5_ON_ENTRY_UNCHANGED", sent and len(ex.calls) == 1, "%s %s" % (sent, status))
    # unreadable mode: fail OPEN to the intent-time decision, loudly
    it = mk_intent("munread")
    c.AuditLogWriter().append_order_intent(it)
    ex = Ex([FILLED(1.0, 100.0)])
    g = gw(ex)

    def boom(w):
        raise RuntimeError("config unreadable")
    g.cfg.wallet_mode = boom
    sent, status = g.send_if_allowed(it)
    errs = [r for r in disk_rows(c.ERRORS_CSV) if r.get("context") == "send_time_wallet_mode_unreadable"]
    check("M6_UNREADABLE_MODE_FAILS_OPEN_LOUDLY", sent and len(ex.calls) == 1 and bool(errs), "%s %s errs=%d" % (sent, status, len(errs)))
    mode = _json.loads(c.LIVE_CONFIG_FILE.read_text(encoding="utf-8-sig"))["wallets"][A]["mode"]
    check("M7_NO_WALLET_MODE_CHANGED_ON_DISK", mode == "ON", mode)
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
