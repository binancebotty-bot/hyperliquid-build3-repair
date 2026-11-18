#!/usr/bin/env python3
"""Gap 1 (plan check 18 Nov, Boss OD-14): an 11th LIVE wallet on the WebSocket is rejected LOUDLY.

G1_1 11 LIVE wallets -> WebSocket subscribes 10 and writes one WS_WALLET_OVER_CAP_REJECTED error row.
G1_2 the same 11 wallets asked again do not write a second row (one row per distinct over-count).
G1_3 10 wallets -> no rejection row.
Mutation check: remove the log_error call and G1_1 goes RED.

Run: python test_core_gap1_ws_over_cap.py   # RESULT:: markers, exit 0/1. No network, no orders.
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
    tmp = Path(tempfile.mkdtemp(prefix="gap1_"))
    os.environ.update({"HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env")})
    import HL_Live_Copy_Service_Core as c

    def rows() -> list:
        try:
            with open(c.ERRORS_CSV, newline="") as fh:
                return [r for r in csv.DictReader(fh) if r.get("context") == "WS_WALLET_OVER_CAP_REJECTED"]
        except OSError:
            return []

    wallets11 = ["0x%040x" % (0xB000 + i) for i in range(11)]
    ws = c.WSManager(lambda: list(wallets11), ingestor=None)
    got = ws.wallets_now()
    check("G1_1_ELEVENTH_WALLET_NOT_SUBSCRIBED_AND_LOGGED",
          len(got) == c.MAX_WALLETS and len(rows()) == 1, f"{len(got)} wallets, {len(rows())} rows")
    ws.wallets_now()
    check("G1_2_SAME_OVER_COUNT_NOT_LOGGED_TWICE", len(rows()) == 1, f"{len(rows())} rows")

    ws10 = c.WSManager(lambda: list(wallets11[:10]), ingestor=None)
    before = len(rows())
    check("G1_3_TEN_WALLETS_NO_REJECTION", len(ws10.wallets_now()) == 10 and len(rows()) == before)

    failed = [n for n, ok in RESULTS if not ok]
    print("RESULT::SUMMARY_%d_PASS_%d_FAIL" % (len(RESULTS) - len(failed), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
