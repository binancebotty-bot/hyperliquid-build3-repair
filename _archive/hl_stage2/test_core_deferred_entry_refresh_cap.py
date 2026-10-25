#!/usr/bin/env python3
"""The refresh-worker cap bounds LIVE meta reads across ALL dexes, not one slot per dex.

A dex's thread reference used to be replaced on every spawn, so an older still-alive read stopped being
counted and the cap bounded nothing. Now every spawned thread is kept in a list, is_alive() is counted
across all of them, and a new worker is refused while the LIVE TOTAL is at the cap - even after its own
claim has lapsed. A refusal writes an ALERT and increments a COUNTER into the status output, and the
universe stays unknown (fail-closed: UNIVERSE_STALE entries are retained and replayed on the next publish).

Run (from _archive/hl_stage2): env -u HL_LIVE_AUDIT_DIR python3 test_core_deferred_entry_refresh_cap.py
No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="refresh_cap_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                   "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_LIQ_PARITY": "0"})
import HL_Live_Copy_Service_Core as c

R = []


def check(n, ok, d=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))


hung = []
gate = threading.Event()
try:
    # ---- a hung read that OUTLIVES its claim, on two dexes: the live total is at the cap ------------
    for i, dex in enumerate(("", "hungdex")):
        t = threading.Thread(target=lambda: gate.wait(30.0), daemon=True, name="hungrefresh-%d" % i)
        t.start()
        hung.append(t)
        c._UNIVERSE_REFRESH_LIVE[dex] = [t]
        c._UNIVERSE_REFRESH_THREADS[dex] = t
        c._UNIVERSE_REFRESH[dex] = {"until": 0, "inflight_until": 0, "seq": 1}
    check("LIVE_COUNT_IS_ACROSS_ALL_DEXES",
          c.universe_refresh_live_count() == c._UNIVERSE_REFRESH_MAX_LIVE == 2,
          c.universe_refresh_live_count())
    _before = c._UNIVERSE_REFRESH_CAP_REFUSALS
    check("HUNG_READ_PAST_ITS_CLAIM_STILL_REFUSES_A_NEW_WORKER",
          c.refresh_authoritative_universe("newdex") is False,
          sorted(c._UNIVERSE_REFRESH_LIVE))
    check("REFUSAL_COUNTER_AND_ALERT_ARE_IN_THE_STATUS",
          c._UNIVERSE_REFRESH_CAP_REFUSALS == _before + 1
          and c.universe_refresh_cap_status()["refusals"] == c._UNIVERSE_REFRESH_CAP_REFUSALS
          and c.universe_refresh_cap_status()["alert"] is True
          and c._UNIVERSE_REFRESH_CAP_ALERTS[-1]["reason"] == "UNIVERSE_REFRESH_CAP_LIVE"
          and c._UNIVERSE_REFRESH_CAP_ALERTS[-1]["live"] == 2,
          c.universe_refresh_cap_status())
    check("REFUSED_ENTRY_FAILS_CLOSED_ON_AN_UNKNOWN_UNIVERSE",
          "newdex" not in c._AUTHORITATIVE_UNIVERSE and c.follower_meta_lists("NEWDEX:NEWCOIN") is True)

    # ---- a REPLACED dict slot does not drop the older thread: the list keeps every spawn -------------
    older, newer = hung[0], threading.Thread(target=lambda: gate.wait(30.0), daemon=True, name="second-")
    newer.start()
    hung.append(newer)
    c._UNIVERSE_REFRESH_LIVE[""] = [older, newer]
    c._UNIVERSE_REFRESH_THREADS[""] = newer   # the slot now names only the newer read
    check("REPLACING_THE_SLOT_DOES_NOT_DROP_THE_OLDER_LIVE_READ",
          c._univ_threads_for("") == [older, newer] and c.universe_refresh_live_count() == 3,
          c._univ_threads_for(""))
finally:
    gate.set()
    for t in hung:
        t.join(5.0)

# ---- a finished read stops counting: the cap reopens once the live total drops ----------------------
c._UNIVERSE_REFRESH_LIVE.clear()
c._UNIVERSE_REFRESH_THREADS.clear()
check("FINISHED_READS_STOP_COUNTING", c.universe_refresh_live_count() == 0)

print("TOTAL::%d/%d" % (sum(1 for x in R if x), len(R)))
sys.exit(0 if all(R) else 1)
