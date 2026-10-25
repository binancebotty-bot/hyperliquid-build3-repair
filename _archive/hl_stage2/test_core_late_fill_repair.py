#!/usr/bin/env python3
"""A late fill wakes the existing convergence loop; the incident clears only on fresh account-net truth.

W  the incident's wake hook sets the convergence loop's event, and the next scan queues the ordinary CONVERGE
   close (the planner decides side, size and reduce-only; the label never forces reduce-only).
R  RED stays while either side is unreadable, an order is in flight or the follower net is off target; it clears
   (a RESOLVED row for the same incident_key) only on fresh follower account-net truth equal to the desired
   target within planner tolerance with nothing in flight.
H  the scan heartbeat is published after EVERY scan, a zero-action one included, with a monotonic scan_count; a
   stale one shows as amber/RED integrity; switch off publishes 'disabled' and no heartbeat fields.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_late_fill_repair.py   # no network, no orders
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="late_fill_repair_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                   "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_LIQ_PARITY": "0",
                   "HL_LIVE_CONVERGE_CONFIRM_SEC": "0", "HL_LIVE_CONVERGE_RETRY_SEC": "0"})
import HL_Live_Copy_Service_Core as c

R = []
WALLET = "0x" + "e" * 40
FOLLOWER = "0x" + "c" * 40


def check(n, ok, d=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))


def seed() -> None:
    for path, fields in ((c.ORDER_INTENTS_CSV, c.ORDER_INTENT_FIELDS), (c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS),
                         (c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS), (c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS)):
        c.ensure_csv_header(path, fields)


def incident_row(status: str, oid: str = "777", coin: str = "BTC") -> None:
    c.AuditLogWriter().append_reconciliation(
        c.LATE_FILL_INCIDENT_EVENT, status, leader_wallet=WALLET, coin=coin, exchange_order_id=oid,
        action="MANUAL_REVIEW_RECONCILE_ENTRY_LEADER_ALREADY_REDUCED",
        terminal_state="ENTRY_FILLED_AFTER_LEADER_REDUCED", engine_can_send="False",
        notes=("incident_key=%s|%s|%s; check_ts_ms=111; follower_fill_ts_ms=222; state=%s" % (WALLET, coin, oid, status)))


def incident_state(oid: str = "777", coin: str = "BTC"):
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
            if str(r.get("event") or "") == c.LATE_FILL_INCIDENT_EVENT
            and str(r.get("exchange_order_id") or "") == oid and str(r.get("coin") or "") == coin]
    return rows[-1] if rows else {}

def main() -> None:
    seed()
    c.USER_WALLET = FOLLOWER
    leader_pos = {WALLET: {}}
    follower_pos = {"BTC": 1.0}
    unreadable = set()
    c._follower_dex_names = lambda: None

    def mids(payload):
        return {} if payload.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100"}

    def leader_fetcher(payload):
        user = str(payload.get("user") or "")
        if user in unreadable:
            raise RuntimeError("unreadable leader")
        return {"marginSummary": {"accountValue": "1000"}, "assetPositions": [
            {"position": {"coin": k, "szi": str(v), "positionValue": str(abs(v) * 100)}}
            for k, v in leader_pos.get(user, {}).items() if v]}

    def exposure_fetcher(payload):
        return {"marginSummary": {"accountValue": "1000"}, "assetPositions": [
            {"position": {"coin": k, "szi": str(v), "positionValue": str(abs(v) * 100)}}
            for k, v in follower_pos.items() if v]}

    c.MIDS_FETCHER = mids
    c.LEADER_MIDS_FETCHER = mids
    c.LEADER_FETCHER = leader_fetcher
    c.EXPOSURE_FETCHER = exposure_fetcher
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {}, "wallets": {
        WALLET: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})

    switch = {"on": True}
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.cfg.master_switch_now = lambda: switch["on"]
    core.ledger.sleeve(WALLET, "BTC")["signed_size"] = 1.0
    core.ledger.sleeve(WALLET, "BTC")["position_id"] = "pid-btc"
    core.ledger._recompute_net(core.ledger.data)
    queued = []
    core._process_leader_fill = lambda f, s=None, b="": (queued.append(f), (False, "TEST_NO_SEND", None))[1]

    def scan():
        core.intent_builder._exposure = None   # the 2 s exposure cache would hide a changed net inside one test
        return core.converge_once()

    fill = c.LeaderFill("lf-1", WALLET, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "COPY_MATCH", 0, {})
    core._on_late_fill_incident(fill, "777")
    check("WAKE_SETS_THE_CONVERGENCE_EVENT", core._converge_wake.is_set(), str(core._converge_wake.is_set()))
    incident_row("OPEN")
    first = scan()
    core._converge_wake.clear()
    check("CONVERGE_QUEUES_A_CLOSE_FOR_THE_ORPHANED_SLEEVE", first.get("queued") == 1 and len(queued) == 1,
          "%s %s" % (first, [f.source for f in queued]))
    check("CONVERGE_FILL_IS_THE_ORDINARY_LEADER_CLOSE",
          bool(queued) and queued[0].source == "CONVERGE"
          and str((queued[0].raw or {}).get("dir")) == "Close Long", repr(queued[0].raw if queued else None))

    still = c.build_live_integrity_status()
    check("OFF_TARGET_KEEPS_RED", still["counts"]["open_late_fill_incidents"] == 1
          and str(incident_state().get("status")) == "OPEN", str(still["counts"].get("open_late_fill_incidents")))
    check("TIMESTAMPS_RECORDED_ON_THE_INCIDENT",
          "check_ts_ms=111" in str(incident_state().get("notes"))
          and "follower_fill_ts_ms=222" in str(incident_state().get("notes")), str(incident_state().get("notes")))

    follower_pos["BTC"] = 0.0
    unreadable.add(WALLET)
    scan()
    check("UNREADABLE_LEADER_KEEPS_RED", str(incident_state().get("status")) == "OPEN",
          str(incident_state().get("status")))
    unreadable.discard(WALLET)

    core._queued_keys.add("in-flight")
    scan()
    check("ORDER_IN_FLIGHT_KEEPS_RED", str(incident_state().get("status")) == "OPEN",
          str(incident_state().get("status")))
    core._queued_keys.discard("in-flight")

    scan()
    resolved = incident_state()
    check("FRESH_TRUTH_EQUAL_TO_TARGET_RESOLVES", str(resolved.get("status")) == "RESOLVED",
          str(resolved.get("status")))
    cleared = c.build_live_integrity_status()
    check("RESOLVED_INCIDENT_NO_LONGER_COUNTED", cleared["counts"]["open_late_fill_incidents"] == 0
          and "open_late_fill_incidents" not in cleared["reasons"],
          str(cleared["counts"].get("open_late_fill_incidents")))

    probe = c.Intent("probe", fill, "SELL", 1.0, 100.0, "ON", "fixed", "EXIT_ALLOWED", "", "s", "p", "LONG",
                     1.0, 1.0, False, False, notes="lifecycle=ENTRY")
    check("LABEL_DOES_NOT_FORCE_REDUCE_ONLY", c.SenderGateway._reduce_only_for_intent(probe) is False,
          str(c.SenderGateway._reduce_only_for_intent(probe)))

    idle = c.LiveCopyCore(source_csv=tmp / "none.csv")
    idle.cfg.master_switch_now = lambda: True
    idle._process_leader_fill = lambda f, s=None, b="": (False, "TEST_NO_SEND", None)
    scan1 = idle.converge_once()
    hb1 = c.load_json(c.CONVERGENCE_HEARTBEAT_FILE, {})
    check("ZERO_ACTION_SCAN_PUBLISHES_HEARTBEAT",
          scan1.get("checked") == 0 and scan1.get("queued") == 0 and int(hb1.get("sleeves_scanned", -1)) == 0
          and int(hb1.get("actions_queued", -1)) == 0 and int(hb1.get("last_scan_at_ms", 0)) > 0, str(hb1))
    check("HEARTBEAT_HAS_NO_ACCOUNT_DETAIL",
          not any(k in hb1 for k in ("wallet", "by_coin", "equity_usd", "notes")), str(sorted(hb1)))
    idle.converge_once()
    hb2 = c.load_json(c.CONVERGENCE_HEARTBEAT_FILE, {})
    idle.converge_once()
    hb3 = c.load_json(c.CONVERGENCE_HEARTBEAT_FILE, {})
    check("SCAN_COUNT_INCREASES_MONOTONICALLY",
          int(hb2.get("scan_count", 0)) == int(hb1.get("scan_count", 0)) + 1
          and int(hb3.get("scan_count", 0)) == int(hb2.get("scan_count", 0)) + 1,
          "%s %s %s" % (hb1.get("scan_count"), hb2.get("scan_count"), hb3.get("scan_count")))

    interval_ms = int(hb3.get("interval_ms"))
    fresh = c.build_live_integrity_status()
    check("FRESH_HEARTBEAT_ADDS_NO_REASON", not any("convergence heartbeat" in str(r) for r in fresh["reasons"]),
          str(fresh["reasons"]))
    c.atomic_write_json(c.CONVERGENCE_HEARTBEAT_FILE, dict(hb3, last_scan_at_ms=c.utc_now_ms() - 4 * interval_ms))
    amber = c.build_live_integrity_status()
    check("STALE_HEARTBEAT_IS_NOT_GREEN", amber["status"] != "GREEN"
          and any("3x the loop interval" in str(r) for r in amber["reasons"]),
          "%s %s" % (amber["status"], amber["reasons"]))
    c.atomic_write_json(c.CONVERGENCE_HEARTBEAT_FILE, dict(hb3, last_scan_at_ms=c.utc_now_ms() - 7 * interval_ms))
    dead = c.build_live_integrity_status()
    check("DEAD_HEARTBEAT_IS_RED", dead["status"] == "RED"
          and any("6x the loop interval" in str(r) for r in dead["reasons"]),
          "%s %s" % (dead["status"], dead["reasons"]))

    switch["on"] = False
    off = core.converge_once()
    hb_off = c.load_json(c.CONVERGENCE_HEARTBEAT_FILE, {})
    check("SWITCH_OFF_IS_DISABLED", off.get("status") == "SENDING_OFF" and hb_off.get("status") == "disabled"
          and "last_scan_at_ms" not in hb_off and "sleeves_scanned" not in hb_off, str(hb_off))
    check("SCAN_COUNT_STILL_MONOTONIC_WHEN_DISABLED", int(hb_off.get("scan_count", 0)) >= 1,
          str(hb_off.get("scan_count")))
    switch["on"] = True

    c.atomic_write_json(c.CONVERGENCE_HEARTBEAT_FILE, dict(hb3, scan_count=9))
    c.ServiceStateWriter().write_startup(c.CycleSummary(), core.dedupe, core.cfg)
    state = c.load_json(c.SERVICE_STATE_FILE, {})
    check("SERVICE_STATE_CARRIES_THE_HEARTBEAT", isinstance(state.get("convergence_heartbeat"), dict)
          and int((state.get("convergence_heartbeat") or {}).get("scan_count", 0)) == 9,
          str(state.get("convergence_heartbeat")))

    core.stop()
    idle.stop()
    print("TOTAL::%d_%d" % (len(R), sum(1 for x in R if not x)))
    sys.exit(0 if all(R) else 1)


if __name__ == "__main__":
    main()
