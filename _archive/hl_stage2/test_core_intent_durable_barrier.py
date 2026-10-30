#!/usr/bin/env python3
"""Pre-send durability barrier for the write-behind order_intents row (Codex finding on move 2).

The intent row is queued behind the send; lifecycle/recovery code reads that journal, so the order's row (and every earlier
queued row) must be on disk BEFORE the exchange call. wait_intent_durable() runs in the pre_send hook, after the slot/cooldown
wait and before the pending_send write. On timeout / writer failure the order proceeds (pending_send is the idempotency
record) and the gap is reported loudly. HL_LIVE_INTENT_DURABLE_WAIT_MS=0 disables the barrier.

Run (from _archive/hl_stage2):  HL_LIVE_ENV_FILE=/nonexistent python3 test_core_intent_durable_barrier.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. No network, no orders.
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
FOLLOWER = "0x" + "c" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="idb_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    os.environ["HL_LIVE_GLOBAL_LOCK_FILE"] = str(Path(tempfile.mkdtemp(prefix="hl_lock_")) / "engine-global.lock")
    import HL_Live_Copy_Service_Core as c
    state_dir = Path(tempfile.mkdtemp(prefix="hl_state_"))
    c.acquire_global_instance_lock(state_dir)

    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})

    def mk_intent(iid, notes="lifecycle=ENTRY;"):
        fill = c.LeaderFill("f_" + iid, A, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST")
        return c.Intent(iid, fill, "BUY", 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
                        "sleeve:%s:BTC" % A, "", "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), notes)

    def disk_rows(path):
        if not path.exists():
            return []
        with path.open("r", newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    def intent_on_disk(iid):
        return any(r.get("intent_id") == iid for r in disk_rows(c.ORDER_INTENTS_CSV))

    def pending_on_disk(iid):
        return any(r.get("intent_id") == iid and r.get("status") == "pending_send" for r in disk_rows(c.SEND_ATTEMPTS_CSV))

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    class RecExchange:
        def __init__(self, iid):
            self.iid, self.calls = iid, []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"t": time.monotonic(), "intent_row": intent_on_disk(self.iid),
                               "pending": pending_on_disk(self.iid)})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 3}}]}}}

    def gw(fake_ex):
        gg = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%d.json" % id(fake_ex))))
        gg._resolve_coin = lambda coin: dict(resolved)
        gg._get_exchange_client = lambda *a, **k: fake_ex
        gg._exchange_client_has_symbol = lambda *a, **k: True
        gg._validate_final_wire_order = lambda *a, **k: (True, {})
        gg._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gg._exchange_client_for_coin = lambda coin: (fake_ex, "BTC")
        gg._pre_send_ownership_gate = lambda it: (True, {})
        gg.leader_reduced_since = lambda f: 0
        gg._margin_mode_done = {"BTC"}
        return gg

    # The intent writer thread is slowed / stalled / failed by wrapping append_csv for ORDER_INTENTS_CSV on that thread only
    # (inline appends, e.g. merged-fill rows, are on the caller's thread and are never touched by it).
    real_append_csv = c.append_csv
    mode = {"delay": 0.0, "gate": None, "fail": False, "durable_t": {}}

    def wrapped_append(path, fieldnames, row, *a, **k):
        if path == c.ORDER_INTENTS_CSV and threading.current_thread().name == "HLCore-intent-writer":
            if mode["gate"] is not None:
                mode["gate"].wait(30)
            if mode["delay"]:
                time.sleep(mode["delay"])
            if mode["fail"]:
                raise OSError("simulated intent writer failure")
        out = real_append_csv(path, fieldnames, row, *a, **k)
        if path == c.ORDER_INTENTS_CSV:
            mode["durable_t"][row.get("intent_id")] = time.monotonic()
        return out
    c.append_csv = wrapped_append

    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64
    saved = c.HLAccount, c.HLExchange
    c.HLAccount, c.HLExchange = object, object

    def run_send(iid, notes="lifecycle=ENTRY;", append=True):
        ex = RecExchange(iid)
        g = gw(ex)
        intent = mk_intent(iid, notes)
        if append:
            g.audit.append_order_intent(intent)
        box = {}

        def run():
            try:
                box["r"] = g._send_real(intent)
            except Exception as exc:  # pragma: no cover
                box["exc"] = exc
        t0 = time.monotonic()
        th = threading.Thread(target=run, daemon=True)
        th.start()
        th.join(15)
        box["elapsed"] = time.monotonic() - t0
        box["alive"] = th.is_alive()
        box["ex"] = ex
        return box

    def barrier_errors(iid):
        return [r for r in disk_rows(c.ERRORS_CSV) if r.get("context") == "intent_durable_barrier" and iid in r.get("message", "")]

    def wait_for(fn, secs=5.0):
        end = time.monotonic() + secs
        while time.monotonic() < end:
            if fn():
                return True
            time.sleep(0.05)
        return bool(fn())

    try:
        # ---- B1: slowed writer: the exchange call does not happen until the intent row is on disk
        os.environ["HL_LIVE_INTENT_DURABLE_WAIT_MS"] = "5000"
        mode.update(delay=0.6, gate=None, fail=False)
        b1 = run_send("b1")
        call = b1["ex"].calls[0] if b1["ex"].calls else {}
        check("B1_EXCHANGE_CALL_WAITS_FOR_INTENT_ROW_DURABLE",
              not b1["alive"] and len(b1["ex"].calls) == 1 and call.get("intent_row") is True and call.get("pending") is True
              and b1["elapsed"] >= 0.5, "%s elapsed=%.2f" % (call, b1["elapsed"]))
        durable_t = mode["durable_t"].get("b1", 1e18)
        check("B1B_ORDER_INTENT_DURABLE_THEN_PENDING_SEND_THEN_EXCHANGE", call and durable_t <= call.get("t", 0),
              "durable_t=%s call=%s" % (durable_t, call))
        pend_ts = [r for r in disk_rows(c.SEND_ATTEMPTS_CSV) if r.get("intent_id") == "b1" and r.get("status") == "pending_send"]
        check("B1C_PENDING_SEND_ROW_STILL_WRITTEN", len(pend_ts) == 1 and bool(pend_ts[0].get("cloid")))

        # ---- B2: writer stalled beyond the timeout: the order still proceeds, loudly
        os.environ["HL_LIVE_INTENT_DURABLE_WAIT_MS"] = "250"
        gate = threading.Event()
        mode.update(delay=0.0, gate=gate, fail=False)
        fails_before = c.audit_write_failure_count()
        t_before = c._INTENT_STATE["durable_timeouts"]
        b2 = run_send("b2")
        call2 = b2["ex"].calls[0] if b2["ex"].calls else {}
        loud = wait_for(lambda: len(barrier_errors("b2")) >= 1)
        check("B2_STALLED_WRITER_ORDER_STILL_PROCEEDS",
              not b2["alive"] and len(b2["ex"].calls) == 1 and call2.get("intent_row") is False and call2.get("pending") is True
              and 0.2 <= b2["elapsed"] < 5.0 and b2.get("r", (False,))[0] is True, "%s elapsed=%.2f" % (call2, b2["elapsed"]))
        check("B2B_TIMEOUT_IS_LOUD_ERRORS_CSV_ALERT_COUNTER_NAMES_INTENT",
              loud and c.audit_write_failure_count() > fails_before and c._INTENT_STATE["durable_timeouts"] == t_before + 1,
              "errors=%s fails=%s->%s" % (barrier_errors("b2")[-1:], fails_before, c.audit_write_failure_count()))
        gate.set()
        mode.update(gate=None)
        check("B2C_WRITER_DRAINS_AFTER_RELEASE", c.flush_intent_writer(10.0) is True and intent_on_disk("b2"))

        # ---- B3: merged-fill intents are written inline: no wait even when the writer is stalled
        os.environ["HL_LIVE_INTENT_DURABLE_WAIT_MS"] = "5000"
        gate = threading.Event()
        mode.update(delay=0.0, gate=gate, fail=False)
        c.AuditLogWriter().append_order_intent(mk_intent("stall_row"))  # keeps the writer stalled in the background
        t_before = c._INTENT_STATE["durable_timeouts"]
        b3 = run_send("b3", notes="lifecycle=ENTRY;merged_leader_fills=2:fa,fb;")
        check("B3_MERGED_FILL_INLINE_ROW_NEEDS_NO_WAIT",
              not b3["alive"] and len(b3["ex"].calls) == 1 and b3["ex"].calls[0]["intent_row"] is True
              and b3["elapsed"] < 2.0 and c._INTENT_STATE["durable_timeouts"] == t_before
              and c.intent_seq_for("b3") is None, "elapsed=%.2f" % b3["elapsed"])
        gate.set()
        mode.update(gate=None)
        c.flush_intent_writer(10.0)

        # ---- B4: HL_LIVE_INTENT_DURABLE_WAIT_MS=0 disables the barrier (old write-behind behaviour), silently
        os.environ["HL_LIVE_INTENT_DURABLE_WAIT_MS"] = "0"
        gate = threading.Event()
        mode.update(delay=0.0, gate=gate, fail=False)
        fails_before = c.audit_write_failure_count()
        b4 = run_send("b4")
        check("B4_ZERO_DISABLES_BARRIER",
              not b4["alive"] and len(b4["ex"].calls) == 1 and b4["ex"].calls[0]["intent_row"] is False
              and b4["elapsed"] < 2.0 and c.audit_write_failure_count() == fails_before, "elapsed=%.2f" % b4["elapsed"])
        gate.set()
        mode.update(gate=None)
        c.flush_intent_writer(10.0)

        # ---- B5: writer failure does not deadlock (row append fails 3x, then the barrier reports and the order goes on)
        os.environ["HL_LIVE_INTENT_DURABLE_WAIT_MS"] = "8000"
        mode.update(delay=0.0, gate=None, fail=True)
        fails_before = c.audit_write_failure_count()
        b5 = run_send("b5")
        loud5 = wait_for(lambda: len(barrier_errors("b5")) >= 1)
        check("B5_WRITER_FAILURE_DOES_NOT_DEADLOCK_AND_IS_LOUD",
              not b5["alive"] and len(b5["ex"].calls) == 1 and b5["ex"].calls[0]["pending"] is True
              and b5["elapsed"] < 7.0 and loud5 and c.audit_write_failure_count() > fails_before
              and "failed to append" in barrier_errors("b5")[-1].get("message", ""),
              "elapsed=%.2f errors=%s" % (b5["elapsed"], barrier_errors("b5")[-1:]))
        mode.update(fail=False)
        c.flush_intent_writer(10.0)

        # ---- B6: a dead writer thread returns at once instead of waiting out the timeout
        class DeadThread:
            def is_alive(self):
                return False
        real_thread = c._INTENT_STATE["thread"]
        c._INTENT_STATE["thread"] = DeadThread()
        os.environ["HL_LIVE_INTENT_DURABLE_WAIT_MS"] = "5000"
        t0 = time.monotonic()
        ok_dead = c.wait_intent_durable(c._INTENT_STATE["next_seq"] + 1000, "dead1")
        dead_elapsed = time.monotonic() - t0
        c._INTENT_STATE["thread"] = real_thread
        check("B6_DEAD_WRITER_THREAD_RETURNS_FALSE_FAST", ok_dead is False and dead_elapsed < 1.0, "%.2f" % dead_elapsed)
        check("B6B_NONE_SEQ_IS_NO_WAIT", c.wait_intent_durable(None, "x") is True)

        # ---- B7: normal case (row already durable): the barrier is a lock-and-compare, no file write on the caller's thread
        mode.update(delay=0.0, gate=None, fail=False)
        c.AuditLogWriter().append_order_intent(mk_intent("b7"))
        c.flush_intent_writer(10.0)
        wrote = []
        c.append_csv = lambda *a, **k: wrote.append(a[0]) or real_append_csv(*a, **k)
        ok7 = c.wait_intent_durable(c.intent_seq_for("b7"), "b7")
        c.append_csv = wrapped_append
        check("B7_DURABLE_ROW_RETURNS_TRUE_WITHOUT_FILE_WRITE", ok7 is True and not wrote, str(wrote))
    finally:
        c.append_csv = real_append_csv
        c.HLAccount, c.HLExchange = saved
        os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)
        os.environ.pop("HL_LIVE_INTENT_DURABLE_WAIT_MS", None)

    c.release_global_instance_lock()
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
