#!/usr/bin/env python3
"""Core engine: a copy fill that matched nothing is offered again while young.

Before: the first failed match consumed the copy-fill id for good. A slow exchange reply (testnet: p50 6 s, up to 76 s)
writes the order id into send_attempts after the copy poll already read the fill, so the fill never reached the ledger
(J26 16 Oct: 13 of 20 coin gaps matched exchange fills to the unit). Now a young unmatched fill is released and the next
read retries it; matched, duplicate and old fills are not released. HL_LIVE_COPY_UNMATCHED_RETRY_MS=0 restores the old way.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_unmatched_release.py   # RESULT:: markers, exit 0/1. No network.
"""
from __future__ import annotations

import os
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="unmrel_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0"})
    import HL_Live_Copy_Service_Core as c

    d = c.DedupeStore({}, state_dir=None)
    check("R1_first_accept", d.accept_copy("a:1") is True)
    check("R2_second_accept_refused", d.accept_copy("a:1") is False)
    d.release_copy("a:1")
    check("R3_after_release_accepted_again", d.accept_copy("a:1") is True)
    d.release_copy("never-seen")  # no error
    check("R4_release_unknown_is_noop", True)

    now = c.utc_now_ms()
    stub = types.SimpleNamespace(dedupe=d, matcher=types.SimpleNamespace(matched_copy_fill_ids={"m:1"}, _is_liquidation_fill=lambda r: bool(r.get("liq"))))
    rel = c.CoreService._release_if_young_unmatched if hasattr(c, "CoreService") else None
    if rel is None:  # find the class that owns the method
        for v in vars(c).values():
            if isinstance(v, type) and "_release_if_young_unmatched" in vars(v):
                rel = vars(v)["_release_if_young_unmatched"]
                break
    check("R5_method_found", rel is not None)
    if rel is None:
        return
    d.accept_copy("y:1")
    rel(stub, {"timestamp_ms": now - 5000}, "y:1")
    d._retry_after.clear()  # the helper sets a gap; skip waiting for it
    check("R6_young_unmatched_released", d.accept_copy("y:1") is True)
    d.accept_copy("o:1")
    rel(stub, {"timestamp_ms": now - 600000}, "o:1")
    check("R7_old_unmatched_kept", d.accept_copy("o:1") is False)
    d.accept_copy("m:1")
    rel(stub, {"timestamp_ms": now - 5000}, "m:1")
    check("R8_matched_not_released", d.accept_copy("m:1") is False)
    os.environ["HL_LIVE_COPY_UNMATCHED_RETRY_MS"] = "0"
    d.accept_copy("z:1")
    rel(stub, {"timestamp_ms": now - 5000}, "z:1")
    check("R9_kill_switch", d.accept_copy("z:1") is False)
    os.environ.pop("HL_LIVE_COPY_UNMATCHED_RETRY_MS")
    d.accept_copy("t:1")
    rel(stub, {}, "t:1")  # no timestamp: kept (cannot tell its age)
    check("R10_no_timestamp_kept", d.accept_copy("t:1") is False)

    # liquidation fills are never retried
    d.accept_copy("l:1")
    rel(stub, {"timestamp_ms": now - 5000, "liq": True}, "l:1")
    check("R11_liquidation_kept", d.accept_copy("l:1") is False)

    # gap and cap: a released id is not offered again until the gap passes, and only N times
    d2 = c.DedupeStore({}, state_dir=None)
    d2.accept_copy("g:1")
    check("R12_release_with_gap", d2.release_copy("g:1", gap_ms=60000, max_releases=2) is True)
    check("R13_not_offered_inside_gap", d2.accept_copy("g:1") is False)
    d2._retry_after["g:1"] = 0
    check("R14_offered_after_gap", d2.accept_copy("g:1") is True)
    check("R15_second_release", d2.release_copy("g:1", gap_ms=1, max_releases=2) is True)
    d2._retry_after["g:1"] = 0
    d2.accept_copy("g:1")
    check("R16_cap_reached_stays_accepted", d2.release_copy("g:1", gap_ms=1, max_releases=2) is False)
    check("R17_still_deduped", d2.accept_copy("g:1") is False)

    # restart: a release after the flush survives a reload; a release before the flush leaves no trace;
    # an id released and accepted again stays accepted
    sd = Path(tempfile.mkdtemp(prefix="unmrel_state_"))
    s1 = c.DedupeStore({}, state_dir=sd)
    for i in ("f:1", "f:2", "f:3"):
        s1.accept_copy(i)
    s1.flush_jsonl()
    s1.accept_copy("p:1")  # not flushed yet
    check("R18_release_flushed", s1.release_copy("f:1") is True)
    check("R19_release_unflushed", s1.release_copy("p:1") is True)
    s1.release_copy("f:2")
    s1.accept_copy("f:2")  # released and accepted again before the next flush
    s1.flush_jsonl()
    s2 = c.DedupeStore({}, state_dir=sd)
    check("R20_restart_released_flushed_eligible", s2.accept_copy("f:1") is True)
    check("R21_restart_released_unflushed_eligible", s2.accept_copy("p:1") is True)
    check("R22_restart_reaccepted_stays_deduped", s2.accept_copy("f:2") is False)
    check("R23_restart_untouched_stays_deduped", s2.accept_copy("f:3") is False)
    # a second reload after more activity: release then flush then accept again then flush
    s2.flush_jsonl()
    s2.release_copy("f:3")
    s2.flush_jsonl()
    s2.accept_copy("f:3")
    s2.flush_jsonl()
    s3 = c.DedupeStore({}, state_dir=sd)
    check("R24_restart_release_then_reaccept_deduped", s3.accept_copy("f:3") is False)


if __name__ == "__main__":
    main()
    bad = [n for n, ok in RESULTS if not ok]
    print("FAILED=%d" % len(bad))
    sys.exit(1 if bad else 0)
