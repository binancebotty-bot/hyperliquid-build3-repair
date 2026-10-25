#!/usr/bin/env python3
"""A late fill (entry filled after the leader had already reduced) must be RED while its incident is OPEN.

The incident is one append-only reconciliation row per wallet+coin+oid: LATE_FILL_INCIDENT / OPEN, and a
later RESOLVED row for the same key closes it. The severity comes from classify_integrity_severity and the
state is on the terminal scan list, so build_live_integrity_status reports RED without any UI change.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_late_fill_incident.py   # no network, no orders
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="late_fill_incident_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                   "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_LIQ_PARITY": "0"})
import HL_Live_Copy_Service_Core as c

R = []


def check(n, ok, d=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))


WALLET = "0x" + "e" * 40


def seed_proof_files() -> None:
    """The integrity gate reports RED on missing append-only proof: give it one header row each."""
    for path, fields in ((c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS), (c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS),
                         (c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS), (c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS)):
        c.ensure_csv_header(path, fields)


def incident(status: str, oid: str = "777", coin: str = "BTC", check_ts: int = 111, fill_ts: int = 222) -> None:
    c.AuditLogWriter().append_reconciliation(
        c.LATE_FILL_INCIDENT_EVENT, status, leader_wallet=WALLET, coin=coin, exchange_order_id=oid,
        action="MANUAL_REVIEW_RECONCILE_ENTRY_LEADER_ALREADY_REDUCED",
        terminal_state="ENTRY_FILLED_AFTER_LEADER_REDUCED", engine_can_send="False",
        notes=(f"incident_key={WALLET}|{coin}|{oid}; check_ts_ms={check_ts}; "
               f"follower_fill_ts_ms={fill_ts}; state={status}"))


def main() -> None:
    # ---- 1. the severity function: both late-fill states are RED, not the GREEN default --------------
    check("SEVERITY_ENTRY_LATE_FILL_IS_RED",
          c.classify_integrity_severity("ENTRY_FILLED_AFTER_LEADER_REDUCED") == "RED",
          c.classify_integrity_severity("ENTRY_FILLED_AFTER_LEADER_REDUCED"))
    check("SEVERITY_RESTING_LATE_FILL_IS_RED",
          c.classify_integrity_severity("RESTING_ENTRY_FILLED_AFTER_LEADER_REDUCED") == "RED",
          c.classify_integrity_severity("RESTING_ENTRY_FILLED_AFTER_LEADER_REDUCED"))
    check("SEVERITY_ORDINARY_FILL_STILL_GREEN",
          c.classify_integrity_severity("ORDER_FILLED") == "GREEN",
          c.classify_integrity_severity("ORDER_FILLED"))

    seed_proof_files()

    # ---- 2. nothing open yet: the real summary is not driven by an incident -------------------------
    quiet = c.build_live_integrity_status()
    check("SUMMARY_NO_INCIDENT_NOT_DRIVEN_BY_INCIDENT",
          quiet["counts"]["open_late_fill_incidents"] == 0 and "open_late_fill_incidents" not in quiet["reasons"],
          str(quiet["counts"].get("open_late_fill_incidents")))

    # ---- 3. an OPEN incident drives the real summary RED --------------------------------------------
    incident("OPEN", check_ts=111, fill_ts=222)
    first = c.build_live_integrity_status()
    check("SUMMARY_OPEN_INCIDENT_IS_RED", first["status"] == "RED", first["status"])
    check("SUMMARY_OPEN_INCIDENT_COUNTED", first["counts"]["open_late_fill_incidents"] == 1,
          str(first["counts"].get("open_late_fill_incidents")))
    check("SUMMARY_OPEN_INCIDENT_NAMED_IN_REASONS", "open_late_fill_incidents" in first["reasons"], str(first["reasons"]))

    # ---- 4. it stays RED: a later unrelated row does not clear it, and repeated reads agree ---------
    c.AuditLogWriter().append_reconciliation("SEND_LATENCY_WARN", "SLOW_SYMBOL_RESOLVE", coin="ETH",
                                             terminal_state="SEND_LATENCY_WARN")
    second = c.build_live_integrity_status()
    third = c.build_live_integrity_status()
    check("SUMMARY_OPEN_INCIDENT_STAYS_RED", second["status"] == "RED" and third["status"] == "RED",
          second["status"] + "/" + third["status"])
    check("SUMMARY_OPEN_INCIDENT_STILL_COUNTED_LATER",
          second["counts"]["open_late_fill_incidents"] == 1 and third["counts"]["open_late_fill_incidents"] == 1,
          str((second["counts"].get("open_late_fill_incidents"), third["counts"].get("open_late_fill_incidents"))))

    # ---- 5. a second OPEN key adds to the count; the sibling state is the same class ----------------
    incident("OPEN", oid="888", coin="ETH", check_ts=333, fill_ts=444)
    c.AuditLogWriter().append_reconciliation(
        c.LATE_FILL_INCIDENT_EVENT, "OPEN", leader_wallet=WALLET, coin="SOL", exchange_order_id="999",
        action="MANUAL_REVIEW_RECONCILE_ENTRY_LEADER_ALREADY_REDUCED",
        terminal_state="RESTING_ENTRY_FILLED_AFTER_LEADER_REDUCED", engine_can_send="False",
        notes=f"incident_key={WALLET}|SOL|999; check_ts_ms=555; follower_fill_ts_ms=0; state=OPEN")
    many = c.build_live_integrity_status()
    check("SUMMARY_EACH_KEY_IS_ITS_OWN_INCIDENT", many["counts"]["open_late_fill_incidents"] == 3,
          str(many["counts"].get("open_late_fill_incidents")))

    # ---- 6. RESOLVED for a key is not open; the newest row for the key wins -------------------------
    incident("RESOLVED")
    resolved = c.build_live_integrity_status()
    check("SUMMARY_RESOLVED_INCIDENT_NOT_COUNTED", resolved["counts"]["open_late_fill_incidents"] == 2,
          str(resolved["counts"].get("open_late_fill_incidents")))
    check("SUMMARY_RESOLVED_STILL_RED_BECAUSE_OTHERS_OPEN", resolved["status"] == "RED", resolved["status"])

    incident("RESOLVED", oid="888", coin="ETH")
    c.AuditLogWriter().append_reconciliation(
        c.LATE_FILL_INCIDENT_EVENT, "RESOLVED", leader_wallet=WALLET, coin="SOL", exchange_order_id="999",
        action="RECONCILED_ON_EXCHANGE", terminal_state="RESTING_ENTRY_FILLED_AFTER_LEADER_REDUCED",
        engine_can_send="False", notes="resolved by hand")
    clear = c.build_live_integrity_status()
    check("SUMMARY_ALL_RESOLVED_NOT_DRIVEN_BY_INCIDENT",
          clear["counts"]["open_late_fill_incidents"] == 0
          and "open_late_fill_incidents" not in clear["reasons"], str(clear["reasons"]))
    check("SUMMARY_ALL_RESOLVED_NOT_RED", clear["status"] != "RED", clear["status"])

    print("TOTAL::%d_%d" % (len(R), sum(1 for x in R if not x)))
    sys.exit(0 if all(R) else 1)


if __name__ == "__main__":
    main()
