#!/usr/bin/env python3
"""S1 (chaos): a gate-blocked entry must stay retryable once the gate clears.

B: an entry refused by ENTRY_BLOCKED_* kept its send authority for the rest of the
   process lifetime, so the retry returned DUPLICATE_BLOCKED until restart.
A: a genuinely SENT intent is still duplicate-suppressed.
C: a blocked entry stays blocked while the gate condition still holds.
R: release only fires for pre-wire refusals.

Run: python test_core_blocked_entry_retry.py   # RESULT:: markers, exit 0/1.
Offline only: no orders, no keys, no exchange calls, no engine start/stop.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40
GATE = "DAILY_LOSS_LIMIT_REACHED"


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="blockretry_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "mainnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
        "HL_LIVE_MOCK_SEND": "1",
        "HL_LIVE_PREWARM_SYMBOL_META": "0",
        "HL_LIVE_PREWARM_SDK_CLIENT": "0",
    })
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.MIDS_FETCHER = lambda payload: [] if payload.get("type") == "perpDexs" else {"BTC": "100"}
    c.USER_WALLET = FOLLOWER

    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": {},
        "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100}},
    })

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    # Ownership gate needs exchange proof on disk; an empty flat account is the offline stand-in.
    c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {}})
    core.run_cycle(use_source_csv=False)

    def fill(fid, side="BUY", price=100.0, size=1.0):
        return c.LeaderFill(fid, LEADER, "BTC", side, price, size, c.utc_now_ms(), "TEST")

    def attempts():
        return [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV) if r.get("leader_fill_id")]

    # ---- B: blocked entry is retryable once the gate clears ------------------------------
    sent, status, _ = core._process_leader_fill(fill("blk-1"), None, GATE)
    check("B1_BLOCKED_ENTRY_IS_REFUSED_NOT_SENT",
          not sent and status == "ENTRY_BLOCKED_" + GATE, status)
    sent2, status2, intent2 = core._process_leader_fill(fill("blk-1"), None, "")
    check("B2_RETRY_AFTER_GATE_CLEARS_ATTEMPTS_THE_SEND",
          sent2 and status2 == "MOCK_ORDER_SENT" and intent2 is not None, status2)
    check("B3_RETRY_WAS_NOT_DUPLICATE_BLOCKED", status2 != "DUPLICATE_BLOCKED", status2)
    check("B4_RETRY_REACHED_THE_WIRE_SITE", len(attempts()) == 1, str(len(attempts())))

    # ---- A: a sent intent is still duplicate-suppressed ----------------------------------
    sent3, status3, _ = core._process_leader_fill(fill("blk-1"), None, "")
    check("A1_SENT_INTENT_STILL_DUPLICATE_SUPPRESSED",
          not sent3 and status3 == "DUPLICATE_BLOCKED", status3)
    check("A2_NO_SECOND_SEND_ROW", len(attempts()) == 1, str(len(attempts())))

    # ---- C: still blocked while the gate holds -------------------------------------------
    s4, st4, _ = core._process_leader_fill(fill("blk-2"), None, GATE)
    s5, st5, _ = core._process_leader_fill(fill("blk-2"), None, GATE)
    check("C1_BLOCKED_STAYS_BLOCKED_WHILE_GATE_HOLDS",
          not s4 and not s5 and st4 == st5 == "ENTRY_BLOCKED_" + GATE, f"{st4} {st5}")
    s6, st6, _ = core._process_leader_fill(fill("blk-2"), None, "")
    check("C2_CLEARS_AFTER_GATE_CLEARS", s6 and st6 == "MOCK_ORDER_SENT", st6)

    # ---- R: only pre-wire refusals release authority -------------------------------------
    check("R1_GATE_BLOCKS_RELEASE_AUTHORITY", c._pre_wire_block("ENTRY_BLOCKED_DAILY_LOSS_LIMIT_REACHED"))
    check("R2_PERMANENT_AND_POST_WIRE_STATUSES_DO_NOT_RELEASE",
          not any(c._pre_wire_block(s) for s in ("SEND_NOT_ATTEMPTED_SPOT_MARKET_SKIPPED", "ORDER_REJECTED",
                                                 "ORDER_FILLED", "EXCHANGE_ERROR", "DUPLICATE_BLOCKED",
                                                 "PENDING_EXIT_GUARD_ACTIVE", "MOCK_ORDER_SENT")))

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
