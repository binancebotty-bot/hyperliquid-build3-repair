#!/usr/bin/env python3
"""Ordering of the leader-invalidated resting-entry withdrawal vs the follower close (sol review 2026-11-23).

Switch ON: the withdrawal (cancel + own-fill read) happens BEFORE the close is sized/sent (base behaviour), so an
entry limit cannot fill between sizing the close and cancelling it. CLOSE ONLY keeps the post-close withdrawal.
Run (from _archive/hl_stage2):  HL_LIVE_ENV_FILE=/nonexistent python -u test_core_cancel_before_close_on.py
"""
from __future__ import annotations
import os, sys, tempfile, threading
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="cbc_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": str(tmp / "none.env")})
    import HL_Live_Copy_Service_Core as c
    c.stale_snapshot_replay_reason = lambda f: ""

    def run(mode):
        events = []
        core = object.__new__(c.LiveCopyCore)
        core._idem_lock = threading.Lock()
        core._idem_accepted = set()
        core._idem_duplicate_audited = set()
        core._guard_key = lambda f: "k"
        core._leader_fill_seen_locked = lambda f, k: False
        core.cfg = SimpleNamespace(send_mode_now=lambda: mode)
        row = {"oid": "1"}
        calls = []
        core.sender = SimpleNamespace(cancel_resting_entries_against=lambda f: (events.append("cancel"), calls.append(1), [row] if len(calls) == 1 else [])[2])
        core._read_fills_of_withdrawn_limits = lambda rows: ([], "COPY_ACCOUNT_POLLED")
        core._reconcile_late_resting_entries = lambda rows, seen=None: events.append("reconcile")
        core._apply_fills_of_withdrawn_limits = lambda *a, **k: events.append("apply")

        def handler(*a, **k):
            events.append("close")
            return True, "SENT", None
        core._handle_leader_fill = handler
        fill = SimpleNamespace(source="WS", raw={}, leader_wallet="0x1", leader_fill_id="f", coin="BTC", timestamp_ms=1)
        core._process_leader_fill_inner(fill)
        return events

    on = run("ON")
    check("CBC_ON_CANCELS_BEFORE_CLOSE", on.index("cancel") < on.index("close"), str(on))
    cl = run("CLOSE")
    check("CBC_CLOSE_ONLY_KEEPS_POST_CLOSE_WITHDRAWAL", cl.index("close") < cl.index("cancel"), str(cl))
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
