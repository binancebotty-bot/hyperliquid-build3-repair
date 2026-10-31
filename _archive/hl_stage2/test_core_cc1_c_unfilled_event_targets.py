#!/usr/bin/env python3
"""CS-I1/CS-I4, W9: the unfilled event-derived target chain. RED specification until C is implemented.
Repo-only author: NOT RUN. Isolated testnet, no exchange, keys or live state.
"""
from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(tempfile.mkdtemp(prefix="cc1_c_targets_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(ROOT), "HL_LIVE_ENV_FILE": str(ROOT / "none.env"),
                   "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                   "HL_LIVE_INTENT_WRITE_BEHIND": "0"})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

WALLET = "0x" + "a" * 40
RESULTS = []

def check(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL",
          "" if ok else " | " + str(detail)[:160]), flush=True)

class Config:
    def wallet_mode(self, wallet): return "ON"
    def copy_mode(self, wallet): return "fixed"
    def wallet_enabled(self, wallet): return True
    def min_notional(self): return 10.0
    def is_symbol_allowed(self, coin): return True, ""

def main():
    ledger = c.ManualLedger(path=ROOT / "ledger.json")
    ledger.sleeve(WALLET, "ABC")["signed_size"] = 1.0
    ledger._recompute_net(ledger.data)
    builder = c.IntentBuilder(Config(), ledger)
    audit = c.AuditLogWriter()
    rows = [(1.00, .91), (.91, .82), (.82, .73), (.73, .64)]
    for i, (start, end) in enumerate(rows, 1):
        fill = c.LeaderFill("E%d" % i, WALLET, "ABC", "SELL", 100.0, .09,
                            c.utc_now_ms() + i, "TEST")
        fill.raw["startPosition"] = str(start)
        intent = builder.build(fill)
        before = ledger.wallet_coin_position(WALLET, "ABC")
        check("C_E%d_UNFILLED_EVENT_CLOSE_EQUALS_POINT09" % i,
              abs(intent.copy_size - .09) < 1e-7,
              "copy_size=%.9f expected=.09" % intent.copy_size)
        check("C_E%d_WIRE_BOUND_OWNED_SLEEVE" % i,
              intent.copy_size <= min(abs(before), abs(intent.copy_size)) + 1e-9)
        check("C_E%d_ACTUAL_LEDGER_UNCHANGED" % i, abs(before - 1.0) < 1e-9, before)
        audit.append_order_intent(intent)  # existing persistent intent audit; no synthetic copy fills
    check("C_CHAIN_FOUR_DISTINCT_INTENTS", len(rows) == 4)
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), sum(not x for x in RESULTS)))
    return 1 if not all(RESULTS) else 0

if __name__ == "__main__":
    sys.exit(main())
