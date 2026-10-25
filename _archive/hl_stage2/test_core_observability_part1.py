#!/usr/bin/env python3
"""PART 1 observability: late-fill incident + RED, restart survival, heartbeat, wake, exact row allow-list.

Run: python test_core_observability_part1.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
import ast
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


DYNAMIC_ROW_VARS = ("terminal_state", "outcome", "status_label")


def dynamic_row_names(source):
    """Row names the writer builds in a variable (`outcome = "X"`) or a module constant. A literal scan of the
    call site cannot see these, so a new one could reach the journal unclassified (Codex's finding)."""
    tree = ast.parse(source)
    consts = {}
    for n in tree.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                    consts[t.id] = n.value.value

    def values(node):
        out = set()

        def walk(n):
            if isinstance(n, (ast.Call, ast.JoinedStr)):
                return
            if isinstance(n, ast.IfExp):
                walk(n.body)
                walk(n.orelse)
                return
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                out.add(n.value)
            for ch in ast.iter_child_nodes(n):
                walk(ch)
        walk(node)
        return out

    found = set()
    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        local = {}
        for n in ast.walk(fn):
            if isinstance(n, ast.Assign):
                for t in n.targets:
                    elts = [t] if isinstance(t, ast.Name) else list(t.elts) if isinstance(t, (ast.Tuple, ast.List)) else []
                    for t2 in elts:
                        if isinstance(t2, ast.Name) and t2.id in DYNAMIC_ROW_VARS:
                            local.setdefault(t2.id, set()).update(values(n.value))
        for n in ast.walk(fn):
            if isinstance(n, ast.keyword) and n.arg in DYNAMIC_ROW_VARS and isinstance(n.value, ast.Name):
                if n.value.id in local:
                    found |= local[n.value.id]
                elif n.value.id in consts:
                    found.add(consts[n.value.id])
    found.discard("")
    return found


def main():
    tmp = Path(tempfile.mkdtemp(prefix="obs_p1_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                       "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_INTEGRITY_TAIL_BYTES": "0"})
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = "0x" + "c" * 40
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False})
    for _f in (c.ORDER_INTENTS_CSV, c.SEND_ATTEMPTS_CSV, c.LIVE_FILLS_CSV, c.RECONCILIATION_CSV):
        if not _f.exists() or _f.stat().st_size <= 0:
            _f.parent.mkdir(parents=True, exist_ok=True)
            _f.write_bytes(b"header\n")  # the audit-proof gate is not what O3 measures

    # ---- O3 first: on a clean journal, so a GREEN/AMBER verdict is about the heartbeat alone ----------
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    switch = {"on": False}
    core.cfg.master_switch_now = lambda: switch["on"]
    core.converge_once()
    hb = c.load_json(c.CONVERGENCE_HEARTBEAT_FILE, {})
    check("O3_DISABLED_HEARTBEAT_HAS_STATUS_AND_NO_SCAN_FIELDS",
          hb.get("status") == "disabled" and "last_scan_at_ms" not in hb and hb.get("scan_count") == 1, str(hb))
    switch["on"] = True
    core.converge_once()
    hb2 = c.load_json(c.CONVERGENCE_HEARTBEAT_FILE, {})
    check("O3_OK_HEARTBEAT_CARRIES_EVERY_FIELD",
          hb2.get("status") == "ok" and all(k in hb2 for k in (
              "last_scan_at_ms", "sleeves_scanned", "candidates", "actions_queued", "unreadable", "interval_ms")),
          str(hb2))
    core.converge_once()
    check("O3_SCAN_COUNT_IS_MONOTONIC_AND_ZERO_ACTION_SCANS_COUNT",
          c.load_json(c.CONVERGENCE_HEARTBEAT_FILE, {}).get("scan_count") == 3,
          str(c.load_json(c.CONVERGENCE_HEARTBEAT_FILE, {}).get("scan_count")))

    def age(mult):
        hb3 = dict(hb2)
        hb3.update(interval_ms=30000, last_scan_at_ms=c.utc_now_ms() - int(mult * 30000))
        c.atomic_write_json(c.CONVERGENCE_HEARTBEAT_FILE, hb3)
        return c.build_live_integrity_status()["status"]

    check("O3_FRESH_HEARTBEAT_IS_GREEN", age(1) == "GREEN", age(1))
    check("O3_HEARTBEAT_AMBER_PAST_3X", age(4) == "AMBER", age(4))
    check("O3_HEARTBEAT_RED_PAST_6X", age(7) == "RED", age(7))

    core._converge_wake.clear()
    core.sender.on_late_fill_incident(None, "777002")
    check("O4_LATE_FILL_INCIDENT_WAKES_CONVERGENCE", core._converge_wake.is_set())

    # ---- O1/O2: the incident record, its RED, and survival across a restart ---------------------------
    audit = c.AuditLogWriter()
    check("O1_BOTH_LATE_FILL_STATES_ARE_RED",
          c.classify_integrity_severity("ENTRY_FILLED_AFTER_LEADER_REDUCED") == "RED"
          and c.classify_integrity_severity("RESTING_ENTRY_FILLED_AFTER_LEADER_REDUCED") == "RED")
    audit.append_reconciliation(
        c.LATE_FILL_INCIDENT_EVENT, "OPEN", leader_wallet=LEADER, coin="BTC", exchange_order_id="777001",
        action="MANUAL_REVIEW_RECONCILE_ENTRY_LEADER_ALREADY_REDUCED",
        terminal_state="ENTRY_FILLED_AFTER_LEADER_REDUCED", engine_can_send="False",
        notes="check_ts_ms=1000; follower_fill_ts_ms=2000; state=OPEN")
    rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("event") == c.LATE_FILL_INCIDENT_EVENT]
    check("O1_OPEN_INCIDENT_ROW_CARRIES_KEY_AND_BOTH_TIMESTAMPS",
          len(rows) == 1 and rows[0].get("status") == "OPEN" and rows[0].get("exchange_order_id") == "777001"
          and "check_ts_ms=1000" in str(rows[0].get("notes"))
          and "follower_fill_ts_ms=2000" in str(rows[0].get("notes")), str(rows[-1:]))
    # O1B: the SAME row, written by the REAL writer in run_cycle (not by a hand-built notes string): the in-lane
    # check time and the matched follower fill's own timestamp. Fails if check_ts_ms goes back to the order's
    # placement time (PLACED_MS) or follower_fill_ts_ms back to 0.
    PLACED_MS, FILL_MS = c.utc_now_ms() - 60000, c.utc_now_ms() - 1234
    live = c.LiveCopyCore(source_csv=tmp / "none.csv")
    live.cfg.master_switch_now = lambda: False
    live.sender.take_withdrawn_late = lambda: [{"oid": "555001", "coin": "BTC", "leader_wallet": LEADER,
                                                "placed_ms": PLACED_MS, "withdraw_outcome": "RESTING_ENTRY_FILLED"}]
    live._read_fills_of_withdrawn_limits = lambda rows: ([{"coin": "BTC", "side": "BUY", "sz": "1", "px": "100",
                                                          "oid": "555001", "time": FILL_MS, "hash": "h1"}],
                                                         "COPY_ACCOUNT_POLLED")
    live._apply_fills_of_withdrawn_limits = lambda rows, read, seen=None: (seen.add("555001") if seen is not None else None) or 1
    live.run_cycle(use_source_csv=False)
    _live_rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
                  if r.get("event") == c.LATE_FILL_INCIDENT_EVENT and r.get("exchange_order_id") == "555001"]
    check("O1B_REAL_WRITER_RECORDS_REAL_CHECK_AND_FOLLOWER_FILL_TS",
          len(_live_rows) == 1
          and ("check_ts_ms=%d" % FILL_MS) not in str(_live_rows[0].get("notes"))
          and ("check_ts_ms=%d" % PLACED_MS) not in str(_live_rows[0].get("notes"))
          and "follower_fill_ts_ms=%d" % FILL_MS in str(_live_rows[0].get("notes")),
          str(_live_rows[:1])[:400])

    live.audit.append_reconciliation(
        c.LATE_FILL_INCIDENT_EVENT, "RESOLVED", leader_wallet=LEADER, coin="BTC", exchange_order_id="555001",
        action="RECONCILED_ON_EXCHANGE", terminal_state="RESTING_ENTRY_FILLED_AFTER_LEADER_REDUCED",
        engine_can_send="False", notes="state=RESOLVED")

    st = c.build_live_integrity_status()
    check("O1_OPEN_INCIDENT_DRIVES_RED", st["status"] == "RED" and st["counts"]["open_late_fill_incidents"] == 1,
          "%s %s" % (st["status"], st["counts"].get("open_late_fill_incidents")))

    # a restart AFTER the incident row was written: is_current_core_row excludes the row from now on
    c.atomic_write_json(c.SERVICE_STATE_FILE, {"started_at_ms": c.utc_now_ms() + 3600000})
    st2 = c.build_live_integrity_status()
    check("O2_OPEN_INCIDENT_SURVIVES_A_RESTART",
          st2["status"] == "RED" and st2["counts"]["open_late_fill_incidents"] == 1,
          "%s %s" % (st2["status"], st2["counts"].get("open_late_fill_incidents")))
    audit.append_reconciliation(
        c.LATE_FILL_INCIDENT_EVENT, "RESOLVED", leader_wallet=LEADER, coin="BTC", exchange_order_id="777001",
        action="RECONCILED_ON_EXCHANGE", terminal_state="ENTRY_FILLED_AFTER_LEADER_REDUCED", engine_can_send="False",
        notes="state=RESOLVED")
    check("O2_A_RESOLVED_ROW_CLEARS_IT",
          c.build_live_integrity_status()["counts"]["open_late_fill_incidents"] == 0)

    # ---- O5: the allow-list oracle, every row name the sender writes, from its own source with ast ------
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.keyword) and node.arg == "terminal_state" \
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            names.add(node.value.value)
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value == "terminal_state" \
                        and isinstance(v, ast.Constant) and isinstance(v.value, str):
                    names.add(v.value)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "append_reconciliation" \
                and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                and isinstance(node.args[1].value, str) and not (
                    getattr(node.args[0], "id", "") == "LATE_FILL_INCIDENT_EVENT"
                    or (isinstance(node.args[0], ast.Constant) and node.args[0].value == c.LATE_FILL_INCIDENT_EVENT)):
            names.add(node.args[1].value)
        if isinstance(node, ast.FunctionDef) and node.name == "classify_terminal_state":
            for n2 in ast.walk(node):
                if isinstance(n2, ast.Return) and isinstance(n2.value, ast.Constant) \
                        and isinstance(n2.value.value, str):
                    names.add(n2.value.value)
    names |= dynamic_row_names(src)  # plus every name that only ever comes from a variable
    unclassified = sorted(n for n in names if c.classify_terminal_row(n) == "UNCLASSIFIED")
    both = sorted(n for n in names if n in c.TERMINAL_ROW_NAMES and n in c.NON_TERMINAL_ROW_NAMES)
    check("O5_EVERY_SENDER_ROW_NAME_IS_CLASSIFIED", bool(names) and not unclassified and not both,
          "unclassified=%s both=%s" % (unclassified, both))
    # Non-vacuity: the dynamic pass really reaches names no call-site literal contains.
    check("O5_DYNAMIC_WRITER_STATUSES_ARE_ENUMERATED",
          {"ENTRY_BLOCKED_RISK", "ORPHAN_ORDER_ALREADY_GONE", "ENTRY_ADD_RATE_LIMIT_RECOVERY_IOC"} <= names)
    # Negative proof: a brand-new name that only ever comes from a variable is caught and is UNCLASSIFIED.
    synthetic = ("def f(self, audit, ok):\n"
                 "    outcome = \"SOME_NEW_ROW_NAME\" if ok else \"OTHER_NEW_ROW\"\n"
                 "    audit.append_reconciliation(\"E\", terminal_state=outcome)\n")
    negative = sorted(n for n in dynamic_row_names(synthetic) if c.classify_terminal_row(n) == "UNCLASSIFIED")
    check("O5_NEGATIVE_PROOF_A_NEW_DYNAMIC_NAME_FAILS",
          negative == ["OTHER_NEW_ROW", "SOME_NEW_ROW_NAME"], "negative=%s" % negative)
    check("O5_SUBSTRING_MATCHING_MISSED_NAMES_ARE_NON_TERMINAL",
          c.classify_terminal_row("PENDING_SEND") == "NON_TERMINAL"
          and c.classify_terminal_row("ORDER_RESTING") == "NON_TERMINAL")
    check("O5_A_NEW_NAME_CONTAINING_SENT_OR_REJECTED_IS_NOT_TERMINAL",
          c.classify_terminal_row("SOME_NEW_ORDER_SENT_LATER") == "UNCLASSIFIED"
          and c.classify_terminal_row("REJECTED_SOMETHING_NEW") == "UNCLASSIFIED")
    # ---- O6: the per-coin SYMBOL_NOT_LISTED counter, published beside the other window counters ----------
    c.atomic_write_json(c.SERVICE_STATE_FILE, {})  # an earlier block stamped a restart time after these rows
    audit.append_reconciliation(
        "SEND_TERMINAL", "MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED", leader_wallet=LEADER, coin="xyz:NVDA",
        action="MISSED_ENTRY_RULE_AT_REFUSAL", terminal_state="MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED")
    audit.append_reconciliation(
        "SEND_TERMINAL", "MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED", leader_wallet=LEADER, coin="xyz:NVDA",
        action="MISSED_ENTRY_RULE_AT_REFUSAL", terminal_state="MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED")
    audit.append_reconciliation(
        "SEND_TERMINAL", "MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED", leader_wallet=LEADER, coin="OBSCURE",
        action="MISSED_ENTRY_RULE_AT_REFUSAL", terminal_state="MISSED_ENTRY_SKIP_SYMBOL_NOT_LISTED")
    st2 = c.build_live_integrity_status()
    by_coin = st2["hard_copy_invariant"].get("symbol_not_listed_by_coin") or {}
    check("O6_SYMBOL_NOT_LISTED_COUNTED_PER_COIN",
          by_coin.get("XYZ:NVDA") == 2 and by_coin.get("OBSCURE") == 1, str(by_coin))
    check("O6_SYMBOL_NOT_LISTED_WINDOW_TOTAL_PUBLISHED",
          st2["counts"].get("symbol_not_listed_window") == 3, str(st2["counts"].get("symbol_not_listed_window")))
    check("O5_COUNTERS_PUBLISHED", "blocked_fills_window" in st["counts"]
          and "retained_fills_window" in st["counts"]
          and isinstance(st["hard_copy_invariant"].get("status_counters"), dict))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
