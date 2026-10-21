#!/usr/bin/env python3
"""Startup orphan checks alert asynchronously and never pause entry cycles."""
from __future__ import annotations

import inspect
import os
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="orphan_async_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_MOCK_SEND": "1"})
    import HL_Live_Copy_Service_Core as c

    entered, release, cycle_called = threading.Event(), threading.Event(), threading.Event()
    alert_modes = []

    class Sender:
        def startup_orphan_order_check(self, alert_only=False):
            alert_modes.append(alert_only)
            entered.set()
            release.wait(4)
            return {"ok": False, "detail": "simulated slow open-orders read"}

    class Core:
        def __init__(self):
            self.sender = Sender()
            self.entry_sends_blocked_reason = ""

        def run_cycle(self):
            cycle_called.set()

    core = Core()
    starter = getattr(c, "start_startup_orphan_check_async", None)
    if callable(starter):
        worker = starter(core)
        started = entered.wait(1.0)
        core.run_cycle()
        check("S1_STUCK_ORPHAN_CHECK_DOES_NOT_PAUSE_ENTRY_CYCLE",
              started and cycle_called.is_set() and not release.is_set()
              and core.entry_sends_blocked_reason == "",
              f"started={started}, cycle={cycle_called.is_set()}, released={release.is_set()}, "
              f"block={core.entry_sends_blocked_reason!r}")
        check("S2_STARTUP_CHECK_IS_ALERT_ONLY", alert_modes == [True], str(alert_modes))
        release.set()
        worker.join(1.0)
    else:
        check("S1_STUCK_ORPHAN_CHECK_DOES_NOT_PAUSE_ENTRY_CYCLE", False, "async startup helper is absent")
        check("S2_STARTUP_CHECK_IS_ALERT_ONLY", False, "async startup helper is absent")

    main_source = inspect.getsource(c.main)
    check("S3_MAIN_STARTUP_HAS_NO_ORPHAN_ENTRY_PAUSE",
          "STARTUP_ORPHAN_CHECK_PENDING" not in main_source
          and "start_startup_orphan_check_async(core)" in main_source,
          "main must start the background diagnostic without setting an entry-block reason")
    failed = [name for name, passed in RESULTS if not passed]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
