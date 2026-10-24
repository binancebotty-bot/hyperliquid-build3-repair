#!/usr/bin/env python3
"""Deferred-entry correctness core, across the SenderGateway/LiveCopyCore class boundary.

A: the halt path inside SenderGateway must reach the core through the callback the gateway already holds; the old code
   called a LiveCopyCore method on the gateway (AttributeError at the live halt). B: a retained item is a persisted
   RETAINED -> ATTEMPTING -> gone state machine, ATTEMPTING+cloid on disk BEFORE dispatch, dropped only on a terminal
   outcome, and an ATTEMPTING item left by a crashed process is reconciled by cloid, never blindly re-sent. C: triggers are
   cleared on load, so a persisted trigger cannot suppress the first post-restart publish.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_deferred_entry_attempting.py
No network, no orders: every send goes to a fake exchange."""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + str(detail)) if (detail and not cond) else ""))


HALTED = {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"error": "Trading is halted."}]}}}


class Ex:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def update_leverage(self, leverage, name, is_cross=True):
        return {"status": "ok"}

    def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
        self.calls.append({"cloid": str(cloid) if cloid is not None else None})
        r = self.replies.pop(0) if self.replies else HALTED
        if isinstance(r, BaseException):
            raise r
        return r


def disk_rows(path):
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="deferred_attempting_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
                       "HL_LIVE_INTENT_DURABLE_WAIT_MS": "2000", "HL_LIVE_MISSED_ENTRY_RULE": "0",
                       "HL_LIVE_RATE_LIMIT_COOLDOWN_MS": "0"})
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    c.HLAccount, c.HLExchange = object, object

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def gateway(ex):
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%s.json" % id(ex))))
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

    def mk_intent(iid, fid=None):
        fill = c.LeaderFill(fid or ("f_" + iid), A, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0,
                            {"dir": "Open Long"})
        return c.Intent(iid, fill, "BUY", 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
                        "sleeve:%s:BTC" % A, "", "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=ENTRY;")

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    try:
        store_path = c.AUDIT_DIR / "deferred_entry_retention.json"
        # no exchange reads anywhere unless a test explicitly allows them
        real_post_many = c._XNET.post_many
        def forbid_truth_reads(fetcher, payloads, url, timeout=None):
            ps = payloads if isinstance(payloads, list) else [payloads]
            for p in ps:
                if isinstance(p, dict) and p.get("type") in ("openOrders", "userFillsByTime"):
                    raise AssertionError("exchange truth read in a test that forbids it: %s" % p.get("type"))
            return [{"ok": True, "data": {"BTC": "100"}} for _ in ps]
        c._XNET.post_many = forbid_truth_reads
        real_all_fills = c._read_all_copy_fills

        # ---- A. the live crash: the halt path through the REAL SenderGateway.send_if_allowed ------------------
        ex = Ex([HALTED])
        g = gateway(ex)
        check("A0_GATEWAY_HAS_NO_RETENTION_METHOD", not hasattr(c.SenderGateway, "_retain_deferred_entry"))
        it = mk_intent("haltunwired", fid="halt-unwired")
        c.AuditLogWriter().append_order_intent(it)
        try:
            g.send_if_allowed(it)  # pre-fix shape: no core wired
            check("A1_HALT_WITHOUT_CORE_DOES_NOT_RAISE", True)
        except AttributeError as exc:
            check("A1_HALT_WITHOUT_CORE_DOES_NOT_RAISE", False, repr(exc))

        g2 = gateway(Ex([HALTED]))
        g2.retain_deferred_entry = core._retain_deferred_entry  # exactly what LiveCopyCore.__init__ assigns
        it2 = mk_intent("haltwired", fid="halt-wired")
        c.AuditLogWriter().append_order_intent(it2)
        sent, status = g2.send_if_allowed(it2)
        item = core.retention.snapshot().get("halt-wired") or {}
        check("A2_REAL_HALT_PATH_RETAINS_THROUGH_THE_CORE_CALLBACK",
              item.get("reason") == "MARKET_HALTED" and item.get("state") == "RETAINED", (sent, status, item))
        check("A3_HALT_RETENTION_IS_ON_DISK", store_path.exists() and "halt-wired" in json.loads(store_path.read_text())["items"])
        check("A4_HALT_COOLDOWN_SET_BY_THE_SEND_PATH", g2._market_halted_until_ms.get("btc", 0) > c.utc_now_ms())
        check("A5_HALT_TERMINAL_ROW_STILL_WRITTEN",
              any(r.get("terminal_state") == "SKIPPED_MARKET_HALTED" for r in disk_rows(c.RECONCILIATION_CSV)))

        # ---- B. write-ahead: ATTEMPTING + cloid on disk BEFORE dispatch --------------------------------------
        def fill(fid, coin="ETH"):
            return c.LeaderFill(fid, A, coin, "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"dir": "Open Long"})

        core.retention.retain(fill("wa-1"), "UNIVERSE_STALE")
        seen = []

        def spy_dispatch(f):
            raw = json.loads(store_path.read_text())["items"].get(f.leader_fill_id) or {}
            seen.append((raw.get("state"), raw.get("cloid")))
            return None  # leaves the fill unhandled: no terminal outcome
        real_dispatch = core._dispatch_fill
        core._dispatch_fill = spy_dispatch
        try:
            core._retention_replay("wa-1", core.retention.snapshot()["wa-1"], "universe::1")
        finally:
            core._dispatch_fill = real_dispatch
        check("B1_ATTEMPTING_AND_CLOID_ON_DISK_BEFORE_DISPATCH",
              len(seen) == 1 and seen[0][0] == "ATTEMPTING" and str(seen[0][1]).startswith("0x"), seen)
        check("B2_NO_TERMINAL_ROW_MEANS_BACK_TO_RETAINED",
              (core.retention.snapshot()["wa-1"]["state"]) == "RETAINED", core.retention.snapshot()["wa-1"])
        again = len(seen)
        core._dispatch_fill = spy_dispatch
        try:
            core._retention_replay("wa-1", core.retention.snapshot()["wa-1"], "universe::1")
        finally:
            core._dispatch_fill = real_dispatch
        check("B3_SAME_TRIGGER_IS_NOT_REPLAYED_TWICE",
              "universe::1" in core.retention.snapshot()["wa-1"]["triggers_done"] and len(seen) == again,
              (core.retention.snapshot()["wa-1"], seen))

        # ---- B4. crash between the write-ahead and the send: nothing on the exchange -------------------------
        cloid_a = c.generate_cloid("recon-a")
        core.retention.retain(fill("recon-a"), "UNIVERSE_STALE")
        core.retention.mark_attempting("recon-a", cloid_a, "intent-a")
        reloaded = c.DeferredEntryRetention()  # the next process
        check("B4_ATTEMPTING_SURVIVES_A_RESTART", reloaded.snapshot()["recon-a"]["state"] == "ATTEMPTING"
              and reloaded.snapshot()["recon-a"]["cloid"] == cloid_a)
        c._XNET.post_many = lambda *a, **k: [{"ok": True, "data": []} for _ in a[1]]  # no open orders
        c._read_all_copy_fills = lambda s, e, **k: ([], "FILLS_COMPLETE")
        core.retention = reloaded
        before_sends = len(disk_rows(c.SEND_ATTEMPTS_CSV))
        core._retention_tick()
        check("B5_NOTHING_SENT_RECONCILES_TO_RETAINED",
              core.retention.snapshot()["recon-a"]["state"] == "RETAINED", core.retention.snapshot().get("recon-a"))
        check("B6_NOTHING_SENT_IS_A_NAMED_ROW",
              any(r.get("terminal_state") == "DEFERRED_ENTRY_ATTEMPT_NOTHING_SENT" for r in disk_rows(c.RECONCILIATION_CSV)))
        check("B7_RECONCILE_SENT_NO_ORDER", len(disk_rows(c.SEND_ATTEMPTS_CSV)) == before_sends)

        # ---- B8. crash after the send before the drop: a send row carries the cloid --------------------------
        cloid_b = c.generate_cloid("recon-b")
        core.retention.retain(fill("recon-b", coin="SOL"), "UNIVERSE_STALE")
        core.retention.mark_attempting("recon-b", cloid_b, "intent-b")
        c.AuditLogWriter().append_send_attempt({"attempt_id": "at-recon-b", "intent_id": "intent-b",
            "leader_fill_id": "recon-b", "leader_wallet": A, "coin": "SOL", "side": "BUY", "status": "ORDER_FILLED",
            "terminal_state": "ORDER_FILLED", "exchange_order_id": "777", "cloid": cloid_b})

        def forbidden(*a, **k):
            raise AssertionError("exchange read after the cloid was already proven sent")
        c._XNET.post_many = forbidden
        core.retention = c.DeferredEntryRetention()
        core._retention_tick()
        check("B9_SENT_ATTEMPT_IS_TERMINAL_AND_DROPPED", "recon-b" not in core.retention.snapshot())
        check("B10_SENT_ATTEMPT_WRITES_A_NAMED_TERMINAL_ROW",
              any(r.get("terminal_state") == "DEFERRED_ENTRY_ATTEMPT_RECONCILED_TERMINAL" for r in disk_rows(c.RECONCILIATION_CSV)))
        check("B11_SENT_ATTEMPT_NEVER_READS_THE_EXCHANGE", True)

        # ---- B12. unreadable exchange: AMBIGUOUS diff + alert, never a resend -------------------------------
        cloid_c = c.generate_cloid("recon-c")
        core.retention.retain(fill("recon-c", coin="XRP"), "UNIVERSE_STALE")
        core.retention.mark_attempting("recon-c", cloid_c, "intent-c")
        real_open = core.sender._read_open_orders
        core.sender._read_open_orders = lambda: (False, [], "read refused")
        real_dispatch2 = core._dispatch_fill

        def no_resend_of_ambiguous(f):
            if f.leader_fill_id == "recon-c":
                raise AssertionError("ambiguous item was re-offered")
            return None
        core._dispatch_fill = no_resend_of_ambiguous
        try:
            core._retention_tick()
            alerts_before = len([r for r in disk_rows(c.RECONCILIATION_CSV)
                                 if r.get("terminal_state") == "DEFERRED_ENTRY_ATTEMPT_AMBIGUOUS_DIFF"])
            core._retention_tick()  # a second tick must not repeat or resend
            alerts_after = len([r for r in disk_rows(c.RECONCILIATION_CSV)
                                if r.get("terminal_state") == "DEFERRED_ENTRY_ATTEMPT_AMBIGUOUS_DIFF"])
        finally:
            core.sender._read_open_orders = real_open
            core._dispatch_fill = real_dispatch2
        check("B13_UNREADABLE_EXCHANGE_IS_AMBIGUOUS",
              core.retention.snapshot().get("recon-c", {}).get("state") == "AMBIGUOUS", core.retention.snapshot().get("recon-c"))
        check("B14_AMBIGUOUS_WRITES_ONE_ALERT_ROW", alerts_before == 1 and alerts_after == 1, (alerts_before, alerts_after))

        # ---- B15. duplicate trigger: one attempt per trigger, persisted -------------------------------------
        core._dispatch_fill = spy_dispatch
        try:
            core.retention.retain(fill("dup-1", coin="ADA"), "MARKET_HALTED")
            core.sender._market_halted_until_ms["ada"] = c.utc_now_ms() - 1
            snap = core.retention.snapshot()["dup-1"]
            trig = core._retention_trigger(snap, c.utc_now_ms())
            core._retention_replay("dup-1", core.retention.snapshot()["dup-1"], trig)
            core._retention_replay("dup-1", core.retention.snapshot()["dup-1"], trig)
        finally:
            core._dispatch_fill = real_dispatch
        item = core.retention.snapshot()["dup-1"]
        check("B16_DUPLICATE_TRIGGER_REPLAYS_ONCE",
              item["triggers_done"] == [trig] and int(item["attempts"]) == 1 and len(seen) == 2, (item, seen))

        # ---- C. a persisted trigger cannot suppress the first post-restart publish --------------------------
        for iid in list(core.retention.snapshot()):
            core.retention.drop(iid, "test cleanup")
        core.retention.retain(fill("uni-1", coin="BTC"), "UNIVERSE_STALE")
        with core.retention._lock:
            core.retention.items["uni-1"]["triggers_done"] = ["universe::1", "symbol:BTC"]
        core.retention._save()
        restarted = c.DeferredEntryRetention()  # item 7: load clears the trigger set
        check("C1_TRIGGERS_CLEARED_ON_LOAD", restarted.snapshot()["uni-1"]["triggers_done"] == [],
              restarted.snapshot()["uni-1"])
        core.retention = restarted
        c._publish_authoritative_universe("", {"BTC": {"symbol_source": "core_meta"}}, "core_meta")
        seq = c._UNIVERSE_PUBLISH_SEQ.get("", 0)
        got = core._retention_trigger(core.retention.snapshot()["uni-1"], c.utc_now_ms())
        check("C2_PERSISTED_UNIVERSE_TRIGGER_CANNOT_SUPPRESS_THE_FIRST_POST_RESTART_PUBLISH",
              got == "universe::%d" % seq, (seq, got))

        c._XNET.post_many = real_post_many
        c._read_all_copy_fills = real_all_fills
    finally:
        core.stop()

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
