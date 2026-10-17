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
    stub = types.SimpleNamespace(dedupe=d, matcher=types.SimpleNamespace(matched_copy_fill_ids={"m:1"}))
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


if __name__ == "__main__":
    main()
    bad = [n for n, ok in RESULTS if not ok]
    print("FAILED=%d" % len(bad))
    sys.exit(1 if bad else 0)
