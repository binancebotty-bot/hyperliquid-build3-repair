#!/usr/bin/env python3
"""A follower entry exclusion must never read as ACTIVE_RED.

The exclusion writes ONE terminal no-send row: status=terminal_state=EXCLUDED_NOT_LISTED_ON_FOLLOWER_NETWORK or
ILLIQUID_SKIP, action=NO_SEND_EXCLUDED_MARKET, engine_can_send=False (Core:13211-13216). Before this fix neither
name was in any proof set, so both fell through to ACTIVE_RED with the live banner text
'copy-required/no-send intent lacks copied, excluded, or valid close proof'.

Run: python test_core_exclusion_not_active_red.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
import csv
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
LEADER = "0x" + "d" * 40


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="excl_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                       "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_INTEGRITY_TAIL_BYTES": "0"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 10}},
        "global_controls": {"min_notional": 1},
    })
    c.atomic_write_json(c.SERVICE_STATE_FILE, {})

    now_ms = c.utc_now_ms()

    def intent(iid, coin):
        return {"intent_id": iid, "created_at_ms": str(now_ms), "created_at": c.utc_now_iso(),
                "leader_wallet": LEADER, "coin": coin, "decision": "ENTRY_ALLOWED", "reason": "ENTRY",
                "wallet_position_before": "0", "notes": "lifecycle=ENTRY"}

    def exclusion_row(iid, coin, status):
        return {"created_at": c.utc_now_iso(), "created_at_ms": str(now_ms), "event": "SEND_TERMINAL",
                "status": status, "leader_wallet": LEADER, "leader_fill_id": "lf-" + iid, "intent_id": iid,
                "coin": coin, "action": "NO_SEND_EXCLUDED_MARKET", "reject_category": status,
                "terminal_state": status, "engine_can_send": "False",
                "notes": "excluded; one terminal row per leader fill; no order and no diff by design; lifecycle=ENTRY"}

    rows = [intent("excl-unlisted", "OBSCURE"), intent("excl-illiquid", "THIN")]
    recon = [exclusion_row("excl-unlisted", "OBSCURE", "EXCLUDED_NOT_LISTED_ON_FOLLOWER_NETWORK"),
             exclusion_row("excl-illiquid", "THIN", "ILLIQUID_SKIP")]
    write_csv(c.ORDER_INTENTS_CSV, rows)
    write_csv(c.SEND_ATTEMPTS_CSV, [])
    write_csv(c.LIVE_FILLS_CSV, [])
    write_csv(c.RECONCILIATION_CSV, recon)

    counts = c.build_live_integrity_status().get("hard_copy_invariant", {}).get("counts", {})

    check("EXCL_UNLISTED_IS_NAMED_CLASS", counts.get("VALID_EXCLUDED_NOT_LISTED", 0) >= 1, str(counts))
    check("EXCL_ILLIQUID_IS_NAMED_CLASS", counts.get("VALID_EXCLUDED_ILLIQUID", 0) >= 1, str(counts))
    check("EXCL_UNLISTED_NOT_ACTIVE_RED", counts.get("ACTIVE_RED", 0) == 0, str(counts))
    check("EXCL_NOTHING_UNCLASSIFIED", counts.get("UNCLASSIFIED", 0) == 0, str(counts))

    check("EXCL_NAMES_ARE_TERMINAL_ROWS",
          c.classify_terminal_row("EXCLUDED_NOT_LISTED_ON_FOLLOWER_NETWORK") == "TERMINAL"
          and c.classify_terminal_row("ILLIQUID_SKIP") == "TERMINAL")

    # regression guard: follower_entry_exclusion itself never excludes when a position is held or the size is unknown
    check("HELD_CLOSE_NEVER_EXCLUDED",
          c.follower_entry_exclusion("OBSCURE", True, {}, held_net=0.5) == ("", "")
          and c.follower_entry_exclusion("THIN", True, {}, held_net=-1e-9) == ("", ""))
    check("UNKNOWN_POSITION_NEVER_EXCLUDED",
          c.follower_entry_exclusion("OBSCURE", True, {}, held_net=None) == ("", ""))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
