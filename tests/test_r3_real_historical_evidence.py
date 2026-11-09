"""R3 captured testnet snapshot four-CSV-only correlation, 9 November 2026 UTC.

NOT state.db-backed evidence: no state database existed for this cert run.
NOT authenticated exchange provenance: four local journals cannot attest
exchange identity. No replay, mutation, network calls, or synthetic history.
Missing cert-run evidence makes this test FAIL. Execution remains NOT_RUN until
build3 supplies all four read-only copies from r3c_20261109/snapshot_20261109T133856Z/state_20261109/append_only.
The match count is derived strictly from those CSV rows, never a target constant.
Known unresolved example: intent 7f71ca1390325e8d494e89820ed9ef70
(reconciliation row 5) has no corresponding captured send_attempts or
live_fills row, so these four files cannot establish whether its claimed
fill-level identifier or original intent identifier is authoritative.
It remains UNPROVEN; a reconciliation row cannot validate itself.
"""
import csv
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

SOURCES = {
    "sends": ("R3_HISTORY_SENDS", "send_attempts.csv"),
    "reconciliation": ("R3_HISTORY_RECONCILIATION", "reconciliation.csv"),
    "fills": ("R3_HISTORY_LIVE_FILLS", "live_fills.csv"),
    "intents": ("R3_HISTORY_ORDER_INTENTS", "order_intents.csv"),
}

# Exact column order from the pinned LiveCopyCore CSV writer, not a loose subset.
HEADERS = {
    "sends": ("created_at", "created_at_ms", "attempt_id", "intent_id", "leader_fill_id", "leader_wallet", "coin", "side", "order_type", "limit_price", "copy_size", "copy_notional", "reduce_only_sent", "sleeve_id", "position_id", "wallet_position_before", "wallet_position_after_expected", "coin_net_before", "coin_net_after_expected", "status", "exchange_response", "exchange_order_id", "error", "reject_category", "terminal_state", "operator_action", "latency_classification", "ws_received_ms", "leader_fill_timestamp_ms", "intent_created_at_ms", "send_decision_started_ms", "send_real_started_ms", "symbol_resolve_started_ms", "symbol_resolve_finished_ms", "sdk_client_started_ms", "sdk_client_finished_ms", "exchange_call_started_ms", "exchange_call_finished_ms", "send_attempt_written_ms", "queue_wait_ms", "leader_to_intent_ms", "intent_to_send_start_ms", "symbol_resolve_ms", "sdk_client_ms", "exchange_call_ms", "send_total_ms", "leader_to_send_attempt_ms", "notes", "cloid", "enqueued_ms", "picked_up_ms", "process_started_ms", "prewarm_done_ms", "lock_acquired_ms", "intent_written_ms", "ownership_gate_started_ms", "ownership_gate_finished_ms", "liq_parity_started_ms", "liq_parity_finished_ms", "wire_validated_ms", "margin_mode_started_ms", "margin_mode_finished_ms", "pending_send_done_ms"),
    "reconciliation": ("created_at", "created_at_ms", "event", "status", "leader_wallet", "leader_fill_id", "intent_id", "copy_fill_id", "coin", "manual_net", "exchange_net", "action", "reject_category", "terminal_state", "exchange_order_id", "engine_can_close", "engine_can_send", "notes", "cap_name", "cap_value", "measured_exposure_usd", "cap_coin"),
    "fills": ("created_at", "created_at_ms", "copy_fill_id", "intent_id", "leader_fill_id", "leader_wallet", "sleeve_id", "position_id", "coin", "side", "fill_price", "fill_size", "fill_notional", "fee", "source", "exchange_hash", "exchange_order_id", "ledger_action", "wallet_position_before", "wallet_position_after", "coin_net_after", "notes"),
    "intents": ("created_at", "created_at_ms", "intent_id", "leader_fill_id", "leader_wallet", "source", "coin", "leader_side", "copy_side", "leader_price", "leader_size", "leader_notional", "copy_size", "copy_notional", "wallet_mode", "copy_mode", "decision", "reason", "sleeve_id", "position_id", "position_direction_before", "wallet_position_before", "coin_net_before", "reduce_only_intended", "reduce_only_sent_planned", "marketable_bps", "max_close_adverse_diff_pct", "min_notional", "notes"),
}
START_MS = 1794229022124
END_MS = 1794231536107
CLOID = re.compile(r"0x[0-9a-fA-F]{32}\Z")
OID = re.compile(r"[0-9]+\Z")


def _id(value, name, line, field):
    assert value is not None and str(value).strip(), (
        f"R3_INVALID_{field.upper()}:{name}:{line}")
    return str(value).strip()


def _oid(value, name, line):
    v = _id(value, name, line, "exchange_order_id")
    assert OID.fullmatch(v) and int(v) > 0, f"R3_BAD_OID:{name}:{line}"
    return str(int(v))


def _optional_oid(value, name, line):
    raw = str(value or "").strip()
    return _oid(raw, name, line) if raw else ""


def _source(kind):
    env, filename = SOURCES[kind]
    raw = os.environ.get(env, "").strip()
    assert raw, f"R3_CERT_RUN_INPUT_MISSING:{env}"
    path = Path(raw)
    assert path.is_absolute() and path.is_file() and path.stat().st_size > 0, (
        f"R3_CERT_RUN_CSV_MISSING:{env}:{path}")
    parts = path.parts
    assert path.name == filename, f"R3_CERT_RUN_WRONG_FILENAME:{kind}:{path}"
    assert len(parts) >= 4 and parts[-3:] == (
        "state_20261109", "append_only", filename), (
        f"R3_CERT_RUN_LAYOUT_INVALID:{kind}:{path}")
    assert parts[-5:-3] == ("r3c_20261109", "snapshot_20261109T133856Z"), (
        f"R3_CERT_RUN_PROVENANCE_PATH_MISSING:{kind}:{path}")
    return path


def _read(kind, path):
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, restkey="__extra__", restval=None, strict=True)
        assert tuple(reader.fieldnames or ()) == HEADERS[kind], (
            f"R3_EXACT_HEADER_MISMATCH:{kind}:{path}")
        rows = []
        for line, row in enumerate(reader, start=2):
            assert None not in row.values() and "__extra__" not in row, (
                f"R3_MALFORMED_CSV_ROW:{kind}:{line}")
            assert all(k is not None for k in row), (
                f"R3_MALFORMED_CSV_KEY:{kind}:{line}")
            stamp = _id(row["created_at_ms"], kind, line, "created_at_ms")
            assert stamp.isdigit(), f"R3_BAD_TIMESTAMP:{kind}:{line}"
            ms = int(stamp)
            assert START_MS <= ms < END_MS, (
                f"R3_OUTSIDE_CAPTURED_SNAPSHOT_WINDOW:{kind}:{line}:{ms}")
            rows.append(row)
    assert rows, f"R3_EMPTY_CERT_RUN_CSV:{kind}:{path}"
    return rows



def _reconciliation_link_is_proven(intent_id, leader_fill_id, intent_to_leader,
                                  related_fills):
    """An alternate leader fill requires a recorded same-intent association.

    The UI's intent-first / leader-fill-fallback lookup is a lookup order, not
    proof that an unrelated fill belongs to this intent. Do not infer ownership
    from a globally known leader_fill_id or the reconciliation claim itself.
    """
    if not intent_id or not leader_fill_id or intent_id not in intent_to_leader:
        return False
    return (leader_fill_id == intent_to_leader[intent_id]
            or leader_fill_id in related_fills.get(intent_id, set()))


def test_reconciliation_link_accepts_proven_later_fill():
    intent = {"intent-a": "fill-original"}
    related = {"intent-a": {"fill-later"}}
    assert _reconciliation_link_is_proven("intent-a", "fill-later", intent, related)
    assert _reconciliation_link_is_proven("intent-a", "fill-original", intent, related)


def test_reconciliation_link_rejects_unrelated_or_unproven_fill():
    intent = {"intent-a": "fill-original", "intent-b": "fill-unrelated"}
    related = {"intent-a": {"fill-later"}}
    assert not _reconciliation_link_is_proven("intent-a", "fill-unrelated", intent, related)
    assert not _reconciliation_link_is_proven("intent-a", "fill-unproven", intent, related)
    assert not _reconciliation_link_is_proven("missing-intent", "fill-later", intent, related)
    assert not _reconciliation_link_is_proven("intent-a", "", intent, related)


def test_fill_level_witness_cannot_be_borrowed_across_intents():
    # The same alternate fill is valid only for its independently recorded
    # intent; neither a global fill match nor a reconciliation claim suffices.
    intent = {"intent-a": "fill-original-a", "intent-b": "fill-original-b"}
    captured_live_fills = [
        {"intent_id": "intent-a", "leader_fill_id": "fill-later-a"},
        {"intent_id": "intent-b", "leader_fill_id": "fill-b"},
    ]
    related = defaultdict(set)
    for row in captured_live_fills:
        related[row["intent_id"]].add(row["leader_fill_id"])
    assert _reconciliation_link_is_proven("intent-a", "fill-later-a", intent, related)
    assert not _reconciliation_link_is_proven("intent-b", "fill-later-a", intent, related)
    assert not _reconciliation_link_is_proven("intent-a", "fill-b", intent, related)


def test_r3_cert_run_four_csv_only_derived_leader_fill_oid_cloid_correlations():
    """Fail closed on corrupt captured-snapshot CSVs, report actual OID+CLOID/leader joins.

    Not state.db evidence, not an authenticated exchange confirmation, NOT_RUN
    pending four actual cert-run paths. Status-based no-send rows are counted
    separately; unresolved send rows or missing joins cause a failure, never a
    partial pass from one good join among invalid history.
    """
    files = {kind: _source(kind) for kind in SOURCES}
    rows = {kind: _read(kind, path) for kind, path in files.items()}
    sends, reconciliations, fills, intents = (
        rows["sends"], rows["reconciliation"], rows["fills"], rows["intents"])

    intent_to_leader = {}
    for i, row in enumerate(intents, 2):
        iid = _id(row["intent_id"], "intents", i, "intent_id")
        leader = _id(row["leader_fill_id"], "intents", i, "leader_fill_id")
        assert iid not in intent_to_leader or intent_to_leader[iid] == leader, (
            f"R3_CONFLICTING_INTENT:{i}:{iid}")
        intent_to_leader[iid] = leader

    # send_attempts is an append-only lifecycle log. A PENDING_SEND followed
    # by one terminal row is one attempt; terminal-only attempts are valid too.
    # Row order is immaterial, but duplicate terminals, orphan pending rows
    # and three-or-more rows for one attempt must fail closed.
    attempts = defaultdict(list)
    for i, row in enumerate(sends, 2):
        aid = _id(row["attempt_id"], "sends", i, "attempt_id")
        iid = _id(row["intent_id"], "sends", i, "intent_id")
        leader = _id(row["leader_fill_id"], "sends", i, "leader_fill_id")
        assert intent_to_leader.get(iid) == leader, f"R3_UNMATCHED_SEND_INTENT:{i}:{aid}"
        clo = str(row["cloid"] or "").strip().lower()
        if clo:
            assert CLOID.fullmatch(clo), f"R3_BAD_CLOID:{i}:{aid}"
        _optional_oid(row["exchange_order_id"], "sends", i)
        status = _id(row["status"], "sends", i, "status").upper()
        attempts[aid].append((status, row))
        assert len(attempts[aid]) <= 2, f"R3_THREE_OR_MORE_ATTEMPT_ROWS:{i}:{aid}"

    latest = {}
    for aid, records in attempts.items():
        pending = [row for status, row in records if status == "PENDING_SEND"]
        terminal = [row for status, row in records if status != "PENDING_SEND"]
        assert len(terminal) <= 1, f"R3_DUPLICATE_TERMINAL_ATTEMPT:{aid}"
        assert terminal, f"R3_ORPHAN_PENDING_SEND:{aid}"
        assert len(pending) <= 1, f"R3_DUPLICATE_PENDING_SEND:{aid}"
        latest[aid] = terminal[0]
    assert sum(len(records) for records in attempts.values()) == len(sends), (
        "R3_UNACCOUNTED_SEND_LIFECYCLE_ROWS")

    fill_keys = defaultdict(set)
    seen_fills = set()
    for i, row in enumerate(fills, 2):
        fid = _id(row["copy_fill_id"], "fills", i, "copy_fill_id")
        assert fid not in seen_fills, f"R3_DUPLICATE_COPY_FILL_ID:{i}:{fid}"
        seen_fills.add(fid)
        iid = _id(row["intent_id"], "fills", i, "intent_id")
        leader = _id(row["leader_fill_id"], "fills", i, "leader_fill_id")
        # live_fills is fill-level evidence: the observed leader fill may be a
        # later fill for the same intent, not the original intent-level fill.
        # The independently captured row must still identify a known intent;
        # reconciliation's own claim never establishes its association.
        assert iid in intent_to_leader, f"R3_UNMATCHED_FILL_INTENT:{i}:{fid}"
        order = _oid(row["exchange_order_id"], "fills", i)
        try:
            value = float(_id(row["fill_size"], "fills", i, "fill_size"))
        except ValueError:
            raise AssertionError(f"R3_BAD_FILL_SIZE:{i}:{fid}") from None
        assert 0 < value < float("inf"), f"R3_BAD_FILL_SIZE:{i}:{fid}"
        fill_keys[(iid, leader, order)].add(fid)

    # Reconciliation is FILL-level (writer: fill.fill_id); order_intents
    # records the original INTENT-level leader_fill_id. A mismatch is valid
    # only with an independent live_fills row binding that fill to the intent.
    # An attempted send, an unrelated intent's fill, or the reconciliation
    # record's own assertion cannot prove that binding.
    related_fills = defaultdict(set)
    for row in fills:
        related_fills[row["intent_id"].strip()].add(row["leader_fill_id"].strip())

    reconciliation_count = Counter()
    for i, row in enumerate(reconciliations, 2):
        assert _id(row["event"], "reconciliation", i, "event")
        leader = str(row["leader_fill_id"] or "").strip()
        iid = str(row["intent_id"] or "").strip()
        _optional_oid(row["exchange_order_id"], "reconciliation", i)
        if iid or leader:
            # System-wide reconciliation events without identifiers are allowed
            # but explicitly accounted as non-correlatable, never silently used.
            assert _reconciliation_link_is_proven(
                iid, leader, intent_to_leader, related_fills), (
                f"R3_UNMATCHED_RECONCILIATION_LINK:{i}")
            reconciliation_count["linked"] += 1
        else:
            reconciliation_count["system_event_without_link"] += 1
    assert sum(reconciliation_count.values()) == len(reconciliations)

    cloid_counts = Counter(str(r["cloid"] or "").lower().strip()
                           for r in latest.values() if str(r["cloid"] or "").strip())
    matched_attempts, rejected, unresolved = set(), Counter(), Counter()
    matched_leaders = set()
    for aid, row in latest.items():
        iid, leader = row["intent_id"].strip(), row["leader_fill_id"].strip()
        clo = str(row["cloid"] or "").lower().strip()
        order = _optional_oid(row["exchange_order_id"], "sends", aid)
        status = str(row["status"] or "").strip().upper()
        assert status, f"R3_BLANK_SEND_STATUS:{aid}"
        # Only explicit terminal refusal/no-call is an acceptable exclusion.
        explicitly_rejected = (status.startswith(("BLOCKED", "SKIPPED", "REJECTED",
                              "SEND_BLOCKED", "SEND_NOT_ATTEMPTED", "PRE_CUTOVER",
                              "AUTO_SEND_DISABLED", "MASTER_REAL_ORDERS_OFF"))
                              or bool(str(row["reject_category"] or "").strip())
                              and status in {"ORDER_REJECTED", "ORDER_FAILED"})
        if explicitly_rejected:
            rejected[status] += 1
        elif clo and cloid_counts[clo] == 1 and order and (iid, leader, order) in fill_keys:
            matched_attempts.add(aid)
            matched_leaders.add(leader)
        else:
            unresolved[status] += 1
    assert len(matched_attempts) + sum(rejected.values()) + sum(unresolved.values()) == len(latest), (
        "R3_UNACCOUNTED_ATTEMPT_ROWS")
    print("R3_CERT_RUN_CSV_ONLY "
          f"send_rows={len(sends)} latest_attempts={len(latest)} "
          f"intents={len(intents)} live_fills={len(fills)} "
          f"reconciliations={len(reconciliations)} "
          f"matched_attempts={len(matched_attempts)} "
          f"matched_leader_fills={len(matched_leaders)} "
          f"explicit_rejections={sum(rejected.values())} "
          f"unresolved={dict(sorted(unresolved.items()))} "
          f"reconciliation_accounting={dict(reconciliation_count)} "
          "authenticated_exchange_provenance=NOT_PROVEN state_db=NOT_IN_CERT_RUN")
    assert not unresolved, f"R3_UNRESOLVED_CSV_JOINS:{dict(unresolved)}"
    assert len(matched_leaders) <= len(matched_attempts)
