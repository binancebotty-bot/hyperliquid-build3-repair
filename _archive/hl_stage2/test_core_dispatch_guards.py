#!/usr/bin/env python3
"""PR4 guards: (F1) a re-read duplicate does no ledger work; (F2) a full queue never sends inline on the poll thread.

Run: python test_core_dispatch_guards.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import queue
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="dispguard_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_HOT_SEND_WORKERS": "2"})
    import HL_Live_Copy_Service_Core as c
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
        A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    core._hot_stop_event.clear()
    core.async_dispatch = True

    calls = []
    real = core._is_close_fill
    core._is_close_fill = lambda f: (calls.append(f.leader_fill_id), real(f))[1]

    f1 = c.LeaderFill("dup1", A, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"oid": "1", "dir": "Open Long"})
    core._dispatch_fill(f1)
    n1 = len(calls)
    core._dispatch_fill(f1)  # already queued
    check("F1_QUEUED_DUPLICATE_NO_LEDGER_WORK", len(calls) == n1, str(calls))

    f2 = c.LeaderFill("dup2", A, "ETH", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"oid": "2", "dir": "Open Long"})
    with core._idem_lock:
        core._idem_accepted.add(core._guard_key(f2))
    before = len(calls)
    ok = core._dispatch_fill(f2)  # already handled
    check("F1_HANDLED_DUPLICATE_NO_LEDGER_WORK", ok and len(calls) == before and "ETH" not in str(core.ledger.data.get("sleeves", "")),
          str(calls))

    # F2: queue full -> dispatch False, and the cycle must not send inline
    for q in core._hot_queues:
        q.maxsize = 1
        try:
            q.put_nowait(f1)
        except queue.Full:
            pass
    sent = []
    core._process_leader_fill = lambda f, s=None, b="": (sent.append(f.leader_fill_id), (False, "T", None))[1]
    f3 = c.LeaderFill("full3", A, "SOL", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", 0, {"oid": "3", "dir": "Open Long"})
    d = core._dispatch_fill(f3)
    check("F2_FULL_QUEUE_DISPATCH_FALSE", d is False)
    src = Path(HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    check("F2_POLL_DOES_NOT_FALL_BACK_INLINE", "poll_dispatch_deferred" in src)
    check("F2_NOTHING_SENT_INLINE", not sent, str(sent))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
