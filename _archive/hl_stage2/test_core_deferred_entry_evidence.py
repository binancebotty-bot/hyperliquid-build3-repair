#!/usr/bin/env python3
"""Item 1/2: status-aware _cloid_evidence and the missed-entry OUTCOME row.

A write-ahead PENDING_SEND row is not a send; only an exchange-response row or the exchange's own open order/fill
proves one. A stored ORDER_RESTING row is re-validated. A rejected missed-entry send row alone never removes a
retained item: the outcome row must exist.

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_deferred_entry_evidence.py
No network, no orders."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
R = []
A = "0x" + "a" * 40


def check(n, ok, d=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))


def rows(path):
    return c.read_csv_rows(path) if path.exists() else []


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="deferred_evidence_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                       "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_LIQ_PARITY": "0"})
    global c
    import HL_Live_Copy_Service_Core as c

    class Sender:
        def __init__(self):
            self.orders, self.ok, self.detail = [], True, "read 1/1 dexes"
            self.reads = 0

        def _read_open_orders(self):
            self.reads += 1
            if isinstance(self.orders, BaseException):
                raise self.orders
            return self.ok, list(self.orders), self.detail

    core = c.LiveCopyCore.__new__(c.LiveCopyCore)   # no threads, no sockets
    core.sender = Sender()
    core.audit = c.AuditLogWriter()
    core.retention = c.DeferredEntryRetention()
    c._read_all_copy_fills = lambda s, e, **k: ([], "FILLS_COMPLETE")

    def item(fid, cloid, age_ms):
        core.retention.items[fid] = {"leader_fill_id": fid, "leader_wallet": A, "coin": "BTC", "side": "BUY",
                                     "price": 100.0, "size": 1.0, "reason": "UNIVERSE_STALE", "first_ms": c.utc_now_ms(),
                                     "state": "ATTEMPTING", "cloid": cloid, "intent_id": "i-" + fid,
                                     "attempt_ms": c.utc_now_ms() - age_ms, "reconciled_ms": 0}
        return dict(core.retention.items[fid])

    margin = c.DEFERRED_ENTRY_ATTEMPT_TIMEOUT_MS

    # ---- 1. crash after the write-ahead, before exchange.order: re-offered, never dropped -----------------
    cl1 = c.generate_cloid("t1")
    core.audit.append_send_attempt({"attempt_id": "at-t1", "intent_id": "i-t1", "leader_fill_id": "t1",
        "leader_wallet": A, "coin": "BTC", "side": "BUY", "status": "pending_send", "terminal_state": "PENDING_SEND",
        "exchange_order_id": "", "exchange_response": "", "cloid": cl1})
    it1 = item("t1", cl1, margin + 5000)
    sends_before = len(rows(c.SEND_ATTEMPTS_CSV))
    core._reconcile_attempting("t1", it1)
    live1 = core.retention.snapshot().get("t1") or {}
    check("E1_PENDING_SEND_AFTER_MARGIN_REOFFERS_AND_NEVER_DROPS",
          live1.get("state") == "RETAINED" and "t1" in core.retention.snapshot()
          and len(rows(c.SEND_ATTEMPTS_CSV)) == sends_before, live1)

    # ---- 2. crash AFTER the exchange accepted: terminal, dropped, exchange never re-read -------------------
    cl2 = c.generate_cloid("t2")
    item("t2", cl2, 1000)
    core.audit.append_send_attempt({"attempt_id": "at-t2", "intent_id": "i-t2", "leader_fill_id": "t2",
        "leader_wallet": A, "coin": "BTC", "side": "BUY", "status": "ORDER_FILLED", "terminal_state": "ORDER_FILLED",
        "exchange_order_id": "9001", "cloid": cl2})
    core.sender.reads = 0   # E1 read open orders to prove nothing was sent; count from here
    core.sender.orders = AssertionError("exchange read after the send was already proven")
    core._reconcile_attempting("t2", dict(core.retention.snapshot()["t2"]))
    check("E2_ACCEPTED_SEND_IS_TERMINAL_AND_DROPPED", "t2" not in core.retention.snapshot()
          and core.sender.reads == 0, (core.retention.snapshot().keys(), core.sender.reads))
    core.sender.orders = []

    # ---- 3. a stored ORDER_RESTING row whose order is gone: AMBIGUOUS, not RESTED --------------------------
    cl3 = c.generate_cloid("t3")
    item("t3", cl3, 1000)
    core.audit.append_send_attempt({"attempt_id": "at-t3", "intent_id": "i-t3", "leader_fill_id": "t3",
        "leader_wallet": A, "coin": "BTC", "side": "BUY", "status": "ORDER_RESTING", "terminal_state": "ORDER_RESTING",
        "exchange_order_id": "9003", "cloid": cl3})
    core._reconcile_attempting("t3", dict(core.retention.snapshot()["t3"]))
    live3 = core.retention.snapshot().get("t3") or {}
    check("E3_STALE_RESTING_ROW_IS_AMBIGUOUS_NOT_RESTED", live3.get("state") == "AMBIGUOUS"
          and any(r.get("leader_fill_id") == "t3"
                  and r.get("terminal_state") == "DEFERRED_ENTRY_ATTEMPT_AMBIGUOUS_DIFF"
                  for r in rows(c.RECONCILIATION_CSV)), live3)

    # ---- 4. rejected replay: the send row alone is not the outcome row ------------------------------------
    cl4 = c.generate_cloid("t4")
    since = c.utc_now_ms()
    core.audit.append_send_attempt({"attempt_id": "at-t4", "intent_id": "i-t4", "leader_fill_id": "t4",
        "leader_wallet": A, "coin": "BTC", "side": "BUY", "status": "ORDER_REJECTED",
        "terminal_state": "MISSED_ENTRY_LIMIT_REJECTED", "exchange_order_id": "", "cloid": cl4})
    pending, _why = core._retention_terminal_outcome("t4", cl4, "i-t4", since)
    core.audit.append_reconciliation("SEND_TERMINAL", "MISSED_ENTRY_LIMIT_OUTCOME_UNKNOWN", leader_wallet=A,
                                     leader_fill_id="t4", intent_id="i-t4", coin="BTC",
                                     terminal_state="MISSED_ENTRY_LIMIT_OUTCOME_UNKNOWN")
    after, _why2 = core._retention_terminal_outcome("t4", cl4, "i-t4", since)
    check("E4_REJECTED_SEND_ROW_ALONE_IS_NOT_AN_OUTCOME_ROW", pending is False and after is True,
          (pending, after))

    failed = [i for i, ok in enumerate(R) if not ok]
    print("TOTAL=%d FAILED=%d" % (len(R), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
