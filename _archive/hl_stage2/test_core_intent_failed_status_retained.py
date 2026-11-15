#!/usr/bin/env python3
"""A failed write-behind order_intents row keeps its failure status for the pre-send barrier (Codex should-fix).

The writer used to keep only the newest 1000 failed sequence numbers and silently drop the oldest, so the barrier then read
an old failed row as durable. Failures are now retained (bounded by HL_LIVE_INTENT_FAILED_MAX, default 10000); past the
bound the oldest are evicted LOUDLY (errors.csv + alert counter) and a watermark makes the barrier report "status unknown"
for everything at or below the evicted sequence instead of "durable".

Run (from _archive/hl_stage2):  env -u HL_LIVE_AUDIT_DIR python3 test_core_intent_failed_status_retained.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ifs_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_INTENT_DURABLE_WAIT_MS": "3000"})
    import HL_Live_Copy_Service_Core as c

    fail = {"on": True}

    def failing_append(path, fieldnames, row, *a, **k):
        if threading.current_thread().name == "HLCore-intent-writer" and fail["on"]:
            raise OSError("simulated intent append failure")
        return None
    c.append_csv = failing_append
    real_sleep = time.sleep
    time.sleep = lambda s: None if threading.current_thread().name == "HLCore-intent-writer" else real_sleep(s)  # no 3x0.5s retry wait
    c.note_audit_write_failure = lambda *a, **k: None  # keep the test quiet; the loud path is asserted through errors below
    errs = []
    c.log_error = lambda ctx, exc=None, *a, **k: errs.append(str(ctx))

    def drain():
        assert c.flush_intent_writer(30.0, "test")

    # ---- R1: 1100 failed rows (more than the old 1000 cap): the FIRST one is still reported failed to the barrier
    n = 1100
    seqs = [c.enqueue_intent_row(c.ORDER_INTENTS_CSV, [], {}, "r1_%d" % i) for i in range(n)]
    drain()
    ok_first = c.wait_intent_durable(seqs[0], "r1_0", 500)
    ok_last = c.wait_intent_durable(seqs[-1], "r1_last", 500)
    check("R1_OLDEST_FAILURE_STILL_REPORTED_AFTER_MORE_THAN_1000_FAILURES", ok_first is False and ok_last is False,
          "first=%s last=%s failed=%d" % (ok_first, ok_last, len(c._INTENT_STATE["failed_seqs"])))
    check("R1_RETENTION_IS_BOUNDED", len(c._INTENT_STATE["failed_seqs"]) <= 10000)

    # ---- R2: past the bound the oldest are evicted loudly and the barrier never calls them durable
    os.environ["HL_LIVE_INTENT_FAILED_MAX"] = "5"
    errs.clear()
    seqs2 = [c.enqueue_intent_row(c.ORDER_INTENTS_CSV, [], {}, "r2_%d" % i) for i in range(12)]
    drain()
    check("R2_FAILED_SET_STAYS_BOUNDED", len(c._INTENT_STATE["failed_seqs"]) <= 5, str(len(c._INTENT_STATE["failed_seqs"])))
    check("R2_EVICTION_IS_LOUD", "intent_failed_status_evicted" in errs, str(errs[:5]))
    check("R2_EVICTED_SEQ_NOT_REPORTED_DURABLE", c.wait_intent_durable(seqs2[0], "r2_0", 500) is False)

    # ---- R3: a row that was written fine is still durable (no false alarm for newer good rows)
    fail["on"] = False
    seq3 = c.enqueue_intent_row(c.ORDER_INTENTS_CSV, [], {}, "r3")
    drain()
    check("R3_NEWER_GOOD_ROW_STILL_DURABLE", c.wait_intent_durable(seq3, "r3", 500) is True)

    failed = [k for k, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
