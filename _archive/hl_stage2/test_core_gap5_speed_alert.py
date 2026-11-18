#!/usr/bin/env python3
"""Gap 5 (plan check 18 Nov, Boss OD-19): the follower send must be within 2 s of the leader's EXCHANGE-recorded fill
time. Measured and alerted (error row LEADER_TO_SEND_OVER_2S), NEVER blocking.

G5_1 leader fill at T, send written at T+2500 ms -> SLOW flag and one alert row; timing still returned (not blocked).
G5_2 send written at T+1500 ms -> no flag, no row.
Mutation check: remove the log_error call and G5_1 goes RED.

Run: python test_core_gap5_speed_alert.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="gap5_"))
    os.environ.update({"HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env")})
    import HL_Live_Copy_Service_Core as c

    def slow_rows() -> list:
        try:
            with open(c.ERRORS_CSV, newline="") as fh:
                return [r for r in csv.DictReader(fh) if r.get("context") == "LEADER_TO_SEND_OVER_2S"]
        except OSError:
            return []

    T = 1_700_000_000_000
    t_slow = c.SenderGateway._finish_timing({"leader_fill_timestamp_ms": T}, T + 2500)
    check("G5_1_SLOW_SEND_FLAGGED_ALERTED_NOT_BLOCKED",
          t_slow.get("speed_over_2s") == "SLOW" and t_slow.get("leader_to_send_attempt_ms") == 2500 and len(slow_rows()) == 1,
          f"{t_slow} rows={len(slow_rows())}")
    t_ok = c.SenderGateway._finish_timing({"leader_fill_timestamp_ms": T}, T + 1500)
    check("G5_2_FAST_SEND_NOT_FLAGGED", "speed_over_2s" not in t_ok and len(slow_rows()) == 1, str(t_ok))

    failed = [n for n, ok in RESULTS if not ok]
    print("RESULT::SUMMARY_%d_PASS_%d_FAIL" % (len(RESULTS) - len(failed), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
