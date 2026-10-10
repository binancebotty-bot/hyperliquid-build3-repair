#!/usr/bin/env python3
"""PR3 batch parallelism: a worker sends different coins side by side, one coin in order.

Test (1) 12 fills of 12 coins, 0.2 s each, finish in well under the serial 2.4 s
Test (2) 6 fills of one coin run in order, one at a time
Test (3) HL_LIVE_HOT_INNER=1 keeps the old serial behaviour
Test (4) a failing fill does not stop the rest
Test (5) HL_LIVE_HOT_SEND_WORKERS=24 is honoured (cap raised from 8)

Run: python test_core_batch_parallel.py   # RESULT:: markers, exit 0/1. No network, no orders.
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
A = "0x" + "a" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="batchpar_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_HOT_SEND_WORKERS": "24"})
    import HL_Live_Copy_Service_Core as c
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": {}, "wallets": {
        A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    check("workers_cap_24", core.hot_send_workers == 24, str(core.hot_send_workers))
    core._hot_stop_event.clear()

    log = []
    lock = threading.Lock()
    active = {}
    overlap = {"same_coin": False}

    def fake(fill, summary=None, reason=""):
        k = fill.coin
        with lock:
            if active.get(k):
                overlap["same_coin"] = True
            active[k] = True
        time.sleep(0.2)
        with lock:
            log.append(fill.leader_fill_id)
            active[k] = False
        if fill.leader_fill_id == "boom":
            raise RuntimeError("boom")
        return True, "", None

    core._process_leader_fill = fake
    n = [0]

    def fill(coin, fid=None):
        n[0] += 1
        return c.LeaderFill(fid or f"f{n[0]}", A, coin, "BUY", 100.0, 1.0, c.utc_now_ms() + n[0], "TEST", 0, {})

    t0 = time.time()
    core._run_plan(0, [fill(f"C{i}") for i in range(12)])
    dt = time.time() - t0
    check("different_coins_parallel", dt < 1.0 and len(log) == 12, "dt=%.2f n=%d" % (dt, len(log)))

    log.clear()
    ids = [f"s{i}" for i in range(6)]
    core._run_plan(0, [fill("SAME", i) for i in ids])
    check("same_coin_in_order", log == ids and not overlap["same_coin"], str(log))

    os.environ["HL_LIVE_HOT_INNER"] = "1"
    log.clear()
    t0 = time.time()
    core._run_plan(0, [fill(f"D{i}") for i in range(5)])
    dt = time.time() - t0
    check("inner_1_serial", dt >= 0.95 and len(log) == 5, "dt=%.2f" % dt)
    os.environ.pop("HL_LIVE_HOT_INNER")

    log.clear()
    core._run_plan(0, [fill("E1"), fill("E2", "boom"), fill("E3")])
    check("failure_does_not_stop_rest", len(log) == 3, str(log))

    # priority close drained between groups, and never overlapping the same coin
    log.clear()
    overlap["same_coin"] = False
    close = fill("P0", "close1")
    core._prio_queues[0].put(close)
    core._run_plan(0, [fill(f"G{i}") for i in range(12)] + [fill("P0", "entry_p0")])
    check("priority_close_drained_no_overlap", "close1" in log and not overlap["same_coin"], str(log))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
