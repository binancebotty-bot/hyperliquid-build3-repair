#!/usr/bin/env python3
"""Deferred-entry lane guards (items 2 and 3), driven ACROSS the SenderGateway/LiveCopyCore boundary.

Item 2 (invariant C): the send path lives in SenderGateway and retention in LiveCopyCore. A queued replay is
re-checked INSIDE the lane; an item dropped by a leader reduce between enqueue and send aborts with a row.
Item 3 (invariants A/F): the aged-out diff row is appended BEFORE the item is removed. A failing append keeps
the item and raises an alert.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="deferred_lane_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet",
                   "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                   "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_LIQ_PARITY": "0",
                   "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0", "HL_LIVE_MISSED_ENTRY_RULE": "0",
                   "HL_LIVE_RATE_LIMIT_COOLDOWN_MS": "0"})
import HL_Live_Copy_Service_Core as c

R = []
A = "0x" + "a" * 40


def check(n, ok, d=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))


def rows(name=None):
    return [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
            if name is None or name in (r.get("event"), r.get("status"))]


def mk_fill(fid, coin="SOL"):
    return c.LeaderFill(fid, A, coin, "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"dir": "Open Long"})


def mk_intent(iid, fill):
    return c.Intent(iid, fill, "BUY", 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
                    "sleeve:%s:SOL" % A, "", "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=ENTRY;")


def gateway():
    g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / "led.json"))
    g.cfg.master_switch_now = lambda: True
    g.cfg.send_mode_now = lambda: "ON"
    g.cfg.liq_parity_enabled = lambda: False
    g.cfg.wallet_enabled = lambda w: True
    g.cfg.wallet_mode = lambda w: "ON"
    g._pre_send_ownership_gate = lambda it: (True, {})
    g._base_timing = lambda it: {}
    calls = []
    g._send_real = lambda intent, timing=None: (calls.append(intent.intent_id), (True, "SENT", {}))[1]
    g._sent_calls = calls
    return g


def main() -> None:
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    try:
        # ---- ITEM 2: the wiring actually crosses the boundary -------------------------------------------------
        check("LANE_GATEWAY_HOLDS_THE_CORE_RECHECK", core.sender.recheck_deferred_entry is not None)
        check("LANE_GATEWAY_RECHECK_IS_A_BOUND_METHOD",
              getattr(core.sender.recheck_deferred_entry, "__self__", None) is core)

        g = gateway()
        g.recheck_deferred_entry = core._recheck_deferred_entry_at_send   # exactly what LiveCopyCore.__init__ assigns
        fill = mk_fill("lane-1", coin="SOL")
        core.retention.retain(fill, "MARKET_HALTED")

        intent = mk_intent("lane-ok", fill)
        fill.raw["deferred_replay"] = "lane-1"
        c.AuditLogWriter().append_order_intent(intent)
        sent, status = g.send_if_allowed(intent)
        check("RETAINED_ITEM_STILL_SENDS", sent is True and status == "SENT" and g._sent_calls == ["lane-ok"],
              (sent, status))

        # ---- ITEM 2: a reduce arriving while the replay is queued stops the send -------------------------------
        fill2 = mk_fill("lane-2", coin="SOL")
        core.retention.retain(fill2, "UNIVERSE_STALE")
        queued = mk_intent("lane-queued", fill2)
        queued.fill.raw["deferred_replay"] = "lane-2"
        c.AuditLogWriter().append_order_intent(queued)
        before = len(rows("SEND_ABORTED_DEFERRED_ENTRY_DROPPED"))
        core._drop_retained_for_leader_reduce(
            c.LeaderFill("reduce-1", A, "SOL", "SELL", 99.0, 1.0, c.utc_now_ms() + 5, "TEST", 0,
                         {"dir": "Close Long"}))
        sent2, status2 = g.send_if_allowed(queued)
        check("QUEUED_REPLAY_ABORTS_WHEN_ITEM_DROPPED",
              sent2 is False and status2 == "SEND_ABORTED_DEFERRED_ENTRY_DROPPED", (sent2, status2))
        check("DROPPED_REPLAY_NEVER_REACHED_THE_EXCHANGE", "lane-queued" not in g._sent_calls, g._sent_calls)
        core._append_send_terminal(queued.fill, queued, status2)   # what _dispatch_fill does when not sent
        check("DROPPED_REPLAY_LEFT_AN_ABORT_ROW", len(rows("SEND_ABORTED_DEFERRED_ENTRY_DROPPED")) - before == 1,
              len(rows("SEND_ABORTED_DEFERRED_ENTRY_DROPPED")) - before)

        # ---- ITEM 2: the per-wallet+coin reduce marker, re-read inside the lane --------------------------------
        fill3 = mk_fill("lane-3", coin="ARB")
        core.retention.retain(fill3, "UNIVERSE_STALE")
        still = mk_intent("lane-marker", fill3)
        still.fill.raw["deferred_replay"] = "lane-3"
        c.AuditLogWriter().append_order_intent(still)
        core.sender.cancel_resting_entries_against(
            c.LeaderFill("reduce-2", A, "ARB", "SELL", 99.0, 1.0, still.fill.timestamp_ms + 1000, "TEST", 0,
                         {"dir": "Close Long"}))
        before = len(rows("SEND_ABORTED_DEFERRED_ENTRY_LEADER_REDUCED"))
        sent3, status3 = g.send_if_allowed(still)
        check("REDUCE_MARKER_ABORTS_THE_REPLAY_IN_THE_LANE",
              sent3 is False and status3 == "SEND_ABORTED_DEFERRED_ENTRY_LEADER_REDUCED", (sent3, status3))
        check("REDUCE_MARKER_NEVER_REACHED_THE_EXCHANGE", "lane-marker" not in g._sent_calls, g._sent_calls)
        core._append_send_terminal(still.fill, still, status3)   # what _dispatch_fill does when not sent
        check("REDUCE_MARKER_LEFT_AN_ABORT_ROW",
              len(rows("SEND_ABORTED_DEFERRED_ENTRY_LEADER_REDUCED")) - before == 1)

        # ---- ITEM 2: the replay path itself stamps the item it rides on ----------------------------------------
        fill4 = mk_fill("lane-4", coin="OP")
        core.retention.retain(fill4, "MARKET_HALTED")
        core.sender._market_halted_until_ms["op"] = c.utc_now_ms() - 1
        captured = []
        real_dispatch = core._dispatch_fill
        core._dispatch_fill = lambda f: (captured.append(dict(f.raw or {})), True)[1]
        try:
            core._retention_replay("lane-4", core.retention.snapshot()["lane-4"], "halt:op")
        finally:
            core._dispatch_fill = real_dispatch
        check("REPLAY_MARKS_THE_FILL_FOR_THE_LANE_RECHECK",
              captured and captured[0].get("deferred_replay") == "lane-4", captured)
        check("AN_ORDINARY_FIRST_SEND_IS_NOT_RE_CHECKED",
              core._recheck_deferred_entry_at_send(mk_intent("plain", mk_fill("plain"))) == "")

        # ---- SILENT-NONE HOLE: a replay with no recheck callback must fail closed ------------------------------
        gn = gateway()                      # gateway() leaves recheck_deferred_entry at the class default None
        check("GATEWAY_DEFAULT_RECHECK_IS_NONE", gn.recheck_deferred_entry is None)
        fill5 = mk_fill("lane-5", coin="AVAX")
        replay = mk_intent("lane-nowire", fill5)
        replay.fill.raw["deferred_replay"] = "lane-5"
        c.AuditLogWriter().append_order_intent(replay)
        alerts = len(rows("DEFERRED_ENTRY_RECHECK_UNWIRED_ALERT"))
        sent5, status5 = gn.send_if_allowed(replay)
        check("REPLAY_WITHOUT_RECHECK_CALLBACK_ABORTS",
              sent5 is False and status5 == "SEND_ABORTED_DEFERRED_ENTRY_RECHECK_UNAVAILABLE", (sent5, status5))
        check("REPLAY_WITHOUT_RECHECK_CALLBACK_NEVER_REACHED_THE_EXCHANGE", gn._sent_calls == [], gn._sent_calls)
        check("REPLAY_WITHOUT_RECHECK_CALLBACK_RAISED_AN_ALERT",
              len(rows("DEFERRED_ENTRY_RECHECK_UNWIRED_ALERT")) - alerts == 1)
        core._append_send_terminal(replay.fill, replay, status5)   # what _dispatch_fill does when not sent
        check("UNWIRED_REPLAY_LEFT_A_NAMED_TERMINAL_ROW",
              any(r.get("terminal_state") == "SEND_ABORTED_DEFERRED_ENTRY_RECHECK_UNAVAILABLE"
                  for r in rows("SEND_ABORTED_DEFERRED_ENTRY_RECHECK_UNAVAILABLE")))

        first = mk_intent("first-nowire", mk_fill("first-1", coin="AVAX"))
        c.AuditLogWriter().append_order_intent(first)
        sent6, status6 = gn.send_if_allowed(first)
        check("FIRST_SEND_WITHOUT_RECHECK_CALLBACK_STILL_PROCEEDS",
              sent6 is True and status6 == "SENT" and gn._sent_calls == ["first-nowire"], (sent6, status6))

        # ---- the hand-off itself refuses to dispatch a replay it cannot re-check --------------------------------
        fill7 = mk_fill("lane-7", coin="DOT")
        core.retention.retain(fill7, "MARKET_HALTED")
        core.sender._market_halted_until_ms["dot"] = c.utc_now_ms() - 1
        wired = core.sender.recheck_deferred_entry
        dispatched = []
        real_dispatch2 = core._dispatch_fill
        core._dispatch_fill = lambda f: (dispatched.append(f.leader_fill_id), True)[1]
        core.sender.recheck_deferred_entry = None
        try:
            core._retention_replay("lane-7", core.retention.snapshot()["lane-7"], "halt:dot")
        finally:
            core.sender.recheck_deferred_entry = wired
            core._dispatch_fill = real_dispatch2
        check("HANDOFF_REFUSES_TO_DISPATCH_WITHOUT_THE_CALLBACK", dispatched == [], dispatched)
        check("HANDOFF_PUTS_THE_ITEM_BACK_TO_RETAINED",
              str((core.retention.snapshot().get("lane-7") or {}).get("state")) == "RETAINED",
              core.retention.snapshot().get("lane-7"))

        # ---- MUTATION CHECK: strip the call-site guard from a COPY and the same replay sends --------------------
        import importlib.util
        src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8")
        gs = src.find('            elif isinstance(intent.fill.raw, dict) and intent.fill.raw.get("deferred_replay"):')
        tail = "                return False, _unwired" + "\n"
        ge = src.find(tail, gs)
        check("MUTATION_CAN_LOCATE_THE_GUARD", gs != -1 and ge != -1, (gs, ge))
        stripped = src[:gs] + src[ge + len(tail):]
        mut_path = tmp / "mut_core.py"
        mut_path.write_text(stripped, encoding="utf-8")
        spec = importlib.util.spec_from_file_location("core_mut", str(mut_path))
        m = importlib.util.module_from_spec(spec)
        sys.modules["core_mut"] = m
        spec.loader.exec_module(m)
        gm = m.SenderGateway(m.ConfigManager(), m.AuditLogWriter())
        gm.cfg.master_switch_now = lambda: True
        gm.cfg.send_mode_now = lambda: "ON"
        gm.cfg.liq_parity_enabled = lambda: False
        gm.cfg.wallet_enabled = lambda w: True
        gm.cfg.wallet_mode = lambda w: "ON"
        gm._pre_send_ownership_gate = lambda it: (True, {})
        gm._base_timing = lambda it: {}
        mut_calls = []
        gm._send_real = lambda intent, timing=None: (mut_calls.append(intent.intent_id), (True, "SENT", {}))[1]
        mut_fill = m.LeaderFill("mut-1", A, "AVAX", "BUY", 100.0, 1.0, m.utc_now_ms(), "TEST", 0, {"dir": "Open Long"})
        mut_fill.raw["deferred_replay"] = "mut-1"
        mut_intent = m.Intent("mut-intent", mut_fill, "BUY", 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
                              "sleeve:%s:AVAX" % A, "", "FLAT", 0.0, 0.0, False, False, m.utc_now_ms(),
                              "lifecycle=ENTRY;")
        m.AuditLogWriter().append_order_intent(mut_intent)
        msent, mstatus = gm.send_if_allowed(mut_intent)
        check("MUTATION_WITHOUT_THE_GUARD_THE_REPLAY_SENDS", msent is True and mut_calls == ["mut-intent"],
              (msent, mstatus, mut_calls))

        # ---- ITEM 3: the diff row is appended BEFORE the item is removed ---------------------------------------
        aged = mk_fill("aged-ok", coin="ADA")
        core.retention.retain(aged, "UNIVERSE_STALE")
        with core.retention._lock:
            core.retention.items["aged-ok"]["first_ms"] = c.utc_now_ms() - c.DEFERRED_ENTRY_MAX_AGE_MS - 1000
        core.retention._save()
        order = []
        real_append = core.audit.append_reconciliation
        real_drop = core.retention.drop

        def spy_append(event, status, **kw):
            if status == "DEFERRED_ENTRY_AGED_OUT_DIFF":
                order.append("append")
            return real_append(event, status, **kw)

        def spy_drop(fid, why):
            if fid == "aged-ok":
                order.append("drop")
            return real_drop(fid, why)

        core.audit.append_reconciliation = spy_append
        core.retention.drop = spy_drop
        try:
            core._retention_tick()
        finally:
            core.audit.append_reconciliation = real_append
            core.retention.drop = real_drop
        check("AGE_OUT_APPENDS_THEN_DROPS", order == ["append", "drop"], order)
        check("AGE_OUT_STILL_REMOVES_THE_ITEM", "aged-ok" not in core.retention.snapshot())

        # ---- ITEM 3: a FAILING append keeps the item and raises an alert ---------------------------------------
        kept = mk_fill("aged-fail", coin="LINK")
        core.retention.retain(kept, "UNIVERSE_STALE")
        with core.retention._lock:
            core.retention.items["aged-fail"]["first_ms"] = c.utc_now_ms() - c.DEFERRED_ENTRY_MAX_AGE_MS - 1000
        core.retention._save()

        def failing_append(event, status, **kw):
            if status == "DEFERRED_ENTRY_AGED_OUT_DIFF":
                raise OSError("disk full")
            return real_append(event, status, **kw)

        core.audit.append_reconciliation = failing_append
        alerts = [len(rows("DEFERRED_ENTRY_AGED_OUT_APPEND_FAILED_ALERT"))]
        try:
            core._retention_tick()
        finally:
            core.audit.append_reconciliation = real_append
        check("FAILED_APPEND_KEEPS_THE_ITEM", "aged-fail" in core.retention.snapshot(),
              sorted(core.retention.snapshot()))
        check("FAILED_APPEND_WRITES_THE_ALERT",
              len(rows("DEFERRED_ENTRY_AGED_OUT_APPEND_FAILED_ALERT")) - alerts[0] == 1,
              len(rows("DEFERRED_ENTRY_AGED_OUT_APPEND_FAILED_ALERT")) - alerts[0])
        alert_row = [r for r in rows("DEFERRED_ENTRY_AGED_OUT_APPEND_FAILED_ALERT")
                     if r.get("leader_fill_id") == "aged-fail"]
        check("ALERT_NAMES_THE_KEPT_ITEM", bool(alert_row) and "KEPT" in str(alert_row[-1].get("notes")),
              alert_row[-1:])
        check("ALERT_IS_AN_ALERT_NOT_A_LOG_ONLY", bool(alert_row) and alert_row[-1].get("event") == "ALERT",
              alert_row[-1:])
        check("ITEM_STILL_ON_DISK_AFTER_THE_FAILED_APPEND",
              "aged-fail" in json.loads((c.AUDIT_DIR / "deferred_entry_retention.json").read_text())["items"])

        core._retention_tick()
        check("RECOVERED_TICK_WRITES_THE_DIFF_AND_REMOVES_IT",
              "aged-fail" not in core.retention.snapshot()
              and any(r.get("leader_fill_id") == "aged-fail" for r in rows("DEFERRED_ENTRY_AGED_OUT_DIFF")))
    finally:
        core.stop()

    print("TOTAL=%d FAILED=%d" % (len(R), R.count(False)))
    sys.exit(1 if False in R else 0)


if __name__ == "__main__":
    main()
