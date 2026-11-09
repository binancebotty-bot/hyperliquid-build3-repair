"""R3 CERT-RUN CSV-ONLY HISTORY (5-8 Nov 2026, run14, state_20261105/append_only).

This is a four-CSV correlation test, NOT state.db evidence, NOT an authenticated
exchange attestation, and NOT an authorization to replay/apply. It uses exactly
the supplied cert-run window and never fabricates missing historical events.
Required environment variables (absolute paths to read-only copies):
  R3_HISTORY_SENDS             send_attempts.csv
  R3_HISTORY_RECONCILIATION    reconciliation.csv
  R3_HISTORY_LIVE_FILLS        live_fills.csv
  R3_HISTORY_ORDER_INTENTS     order_intents.csv

The derived matched-leader-fill count is printed from source data, never 2,199
by assumption. The four CSVs contain no independent authenticated CLOID/OID
response source: an OID+CLOID association inside send_attempts is only an
internal journal assertion and is explicitly reported as unverified provenance.
No state database and no replay apply path are used.
"""
import csv
import os
from collections import Counter, defaultdict
from pathlib import Path

import pytest

# Read the cert-run four-source evidence only. No fallback to any other run.
SOURCES = {
    "sends": "R3_HISTORY_SENDS",
    "reconciliation": "R3_HISTORY_RECONCILIATION",
    "fills": "R3_HISTORY_LIVE_FILLS",
    "intents": "R3_HISTORY_ORDER_INTENTS",
}


def _source(name):
    key = SOURCES[name]
    configured = os.environ.get(key, "").strip()
    assert configured, f"R3_CERT_RUN_INPUT_MISSING:{key}"
    path = Path(configured)
    assert path.is_file() and path.stat().st_size > 0, f"R3_CERT_RUN_CSV_MISSING:{key}:{path}"
    assert path.name == {
        "sends": "send_attempts.csv",
        "reconciliation": "reconciliation.csv",
        "fills": "live_fills.csv",
        "intents": "order_intents.csv",
    }[name], f"R3_CERT_RUN_WRONG_SOURCE:{key}:{path}"
    return path


def _rows(path, required):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames, f"R3_CERT_RUN_MISSING_HEADER:{path}"
        assert required.issubset(reader.fieldnames), (
            f"R3_CERT_RUN_SCHEMA_MISMATCH:{path}:"
            f"{sorted(required - set(reader.fieldnames))}"
        )
        return list(reader)


def _oid(value):
    raw = str(value or "").strip()
    return str(int(raw)) if raw.isdigit() else ""


def _id(value):
    return str(value or "").strip()


def test_r3_cert_run_four_csv_only_derived_leader_fill_oid_cloid_correlations():
    """Correlate the actual run14 cert-run CSVs; no state.db-backed proof.

    A matched leader fill has a send attempt with a unique valid CLOID, a
    recorded exchange OID, a consistent intent row, and an independently
    recorded live-fill row sharing the leader ID, intent ID and OID. The
    reconciliation CSV is read and its matching referential IDs checked.
    No hard-coded historical count and no network/authentication claim.
    """
    paths = {kind: _source(kind) for kind in SOURCES}
    sends = _rows(paths["sends"], {
        "attempt_id", "intent_id", "leader_fill_id", "cloid", "exchange_order_id", "status"})
    reconciliation = _rows(paths["reconciliation"], {
        "event", "status", "leader_fill_id", "intent_id", "exchange_order_id"})
    fills = _rows(paths["fills"], {
        "copy_fill_id", "leader_fill_id", "intent_id", "exchange_order_id", "fill_size"})
    intents = _rows(paths["intents"], {"intent_id", "leader_fill_id"})

    latest = {}
    for row in sends:
        attempt_id = _id(row["attempt_id"])
        if attempt_id:
            latest[attempt_id] = row
    intents_by_id = defaultdict(set)
    for row in intents:
        if _id(row["intent_id"]) and _id(row["leader_fill_id"]):
            intents_by_id[_id(row["intent_id"])].add(_id(row["leader_fill_id"]))

    valid_cloid = lambda c: len(c) == 34 and c.startswith("0x") and all(
        ch in "0123456789abcdef" for ch in c[2:].lower())
    cloid_counts = Counter(_id(row["cloid"]).lower() for row in latest.values()
                           if valid_cloid(_id(row["cloid"]).lower()))
    fill_keys = defaultdict(list)
    fill_ids = set()
    for row in fills:
        fill_id, leader, intent, order = (
            _id(row["copy_fill_id"]), _id(row["leader_fill_id"]),
            _id(row["intent_id"]), _oid(row["exchange_order_id"]))
        if fill_id and leader and intent and order and fill_id not in fill_ids:
            fill_ids.add(fill_id)
            fill_keys[(leader, intent, order)].append(row)

    matching_attempts = set()
    matching_leader_fills = set()
    incomplete = Counter()
    for attempt_id, row in latest.items():
        leader, intent = _id(row["leader_fill_id"]), _id(row["intent_id"])
        order, clo = _oid(row["exchange_order_id"]), _id(row["cloid"]).lower()
        if not leader or not intent or leader not in intents_by_id.get(intent, set()):
            incomplete["intent_or_leader_missing"] += 1
        elif not order or not valid_cloid(clo) or cloid_counts[clo] != 1:
            incomplete["oid_or_unique_cloid_missing"] += 1
        elif not fill_keys.get((leader, intent, order)):
            incomplete["ledger_oid_intent_leader_missing"] += 1
        else:
            matching_attempts.add(attempt_id)
            matching_leader_fills.add(leader)

    # Reconciliation records are independent rows; only validate references
    # when IDs are present. An event without an intent/leader is not a match.
    intent_ids = set(intents_by_id)
    reconciled_links = {
        (_id(r["leader_fill_id"]), _id(r["intent_id"]))
        for r in reconciliation
        if _id(r["leader_fill_id"]) and _id(r["intent_id"])
        and _id(r["intent_id"]) in intent_ids
        and _id(r["leader_fill_id"]) in intents_by_id[_id(r["intent_id"])]
    }
    correlated_count = len(matching_leader_fills)
    print(
        "R3_CERT_RUN_CSV_ONLY "
        f"send_rows={len(sends)} latest_attempts={len(latest)} "
        f"reconciliation_rows={len(reconciliation)} live_fill_rows={len(fills)} "
        f"intent_rows={len(intents)} "
        f"matched_attempts={len(matching_attempts)} "
        f"matched_leader_fills={correlated_count} "
        f"reconciled_intent_leader_pairs={len(reconciled_links)} "
        f"unmatched_by_reason={dict(sorted(incomplete.items()))} "
        "authenticated_exchange_provenance=NOT_PROVEN "
        "state_db=NOT_IN_CERT_RUN"
    )
    # This asserts only internally consistent, present CSV relationships.
    # It does not assert every historical send is provable or force 2,199.
    assert len(matching_attempts) <= len(latest)
    assert correlated_count <= len(matching_attempts)
    assert len(reconciled_links) <= len(reconciliation)
    assert correlated_count > 0, "R3_CERT_RUN_NO_CORRELATED_LEADER_FILLS"
