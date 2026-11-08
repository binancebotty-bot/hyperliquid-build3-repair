"""Offline replay of exchange-confirmed sends. Never queries, sends, cancels or touches state.db.

Input confirmations are read-only exchange evidence captured separately, with
cloid, oid, status and filled_size. Writes append-only send_attempt terminal rows
only when the ledger independently accounts for the entire exchange fill.
"""
import argparse
import csv
import decimal
import json
import os
import io
import shutil
import tempfile
import re
from collections import Counter
from pathlib import Path

D = decimal.Decimal
OPEN = {"PENDING_SEND", "ORDER_RESTING", "ORDER_UNKNOWN"}
CLOID = re.compile(r"^0x[0-9a-f]{32}$")


def oid(value):
    raw = str(value or "").strip()
    if not raw or len(raw) > 40:
        return ""
    try:
        n = D(raw)
        if not n.is_finite() or n.adjusted() > 40:
            return ""
        return str(int(n)) if n == n.to_integral_value() else ""
    except (decimal.InvalidOperation, ValueError, OverflowError):
        return ""


def cloid(value):
    raw = str(value or "").strip().lower()
    return raw if CLOID.fullmatch(raw) else ""


def positive(value):
    try:
        v = D(str(value))
        return v if v.is_finite() and v > 0 else D(0)
    except (decimal.InvalidOperation, ValueError):
        return D(0)


def replay(rows, confirmations, ledger_rows, strict=True):
    """Return immutable append-only closing rows, never an inferred exchange outcome."""
    latest = {}
    for row in rows:
        aid = str(row.get("attempt_id") or "")
        if aid:
            latest[aid] = dict(row)
    by_cloid = {}
    counts = Counter(cloid(r.get("cloid")) for r in latest.values())
    for row in latest.values():
        key = cloid(row.get("cloid"))
        if key and counts[key] == 1 and str(row.get("status") or "").upper() in OPEN:
            by_cloid[key] = row
    confirmations_by_cloid = {}
    oid_owners = {}
    conflicted = set()
    for item in confirmations:
        key, order = cloid(item.get("cloid")), oid(item.get("oid"))
        if not key or not order:
            continue
        pair = (order, str(item.get("status") or "").upper(), positive(item.get("filled_size")))
        if key in confirmations_by_cloid and confirmations_by_cloid[key] != pair:
            conflicted.add(key)
        confirmations_by_cloid[key] = pair
        if order in oid_owners and oid_owners[order] != key:
            conflicted.add(key)
            conflicted.add(oid_owners[order])
        oid_owners[order] = key
    ledger = {}
    seen = set()
    for row in ledger_rows:
        order, fill_id = oid(row.get("exchange_order_id")), str(row.get("copy_fill_id") or "")
        leader = str(row.get("leader_fill_id") or "")
        if not order or not fill_id or not leader:
            continue
        key = (order, fill_id)
        if key in seen:
            continue
        seen.add(key)
        lk = (order, leader)
        ledger[lk] = ledger.get(lk, D(0)) + positive(row.get("fill_size"))
    # A second attempt claiming the same OID makes the exchange-to-attempt link ambiguous.
    recorded_oid_counts = Counter(oid(r.get("exchange_order_id")) for r in latest.values()
                                  if oid(r.get("exchange_order_id")))
    closed = []
    unresolved = []
    for key, row in by_cloid.items():
        if key in conflicted or key not in confirmations_by_cloid:
            unresolved.append((row['attempt_id'], 'CLOID_UNCONFIRMED_OR_CONFLICT'))
            continue
        order, status, filled = confirmations_by_cloid[key]
        prior_order = str(row.get("exchange_order_id") or "").strip()
        if prior_order and (oid(prior_order) != order or recorded_oid_counts[order] > 1):
            unresolved.append((row['attempt_id'], 'OID_MISMATCH_OR_CONFLICT'))
            continue
        wanted = positive(row.get("copy_size"))
        leader = str(row.get("leader_fill_id") or "")
        if status != "FILLED" or not leader or wanted == 0 or filled < wanted:
            unresolved.append((row['attempt_id'], 'FILL_UNCONFIRMED'))
            continue
        if ledger.get((order, leader), D(0)) < wanted:
            unresolved.append((row['attempt_id'], 'LEDGER_COVERAGE_MISSING'))
            continue
        final = dict(row)
        final.update(status="ORDER_FILLED", terminal_state="EXCHANGE_CONFIRMED_OID_CLOID_LEDGER",
                     exchange_order_id=order, operator_action="JOURNAL_CLOSED_BY_CONFIRMED_REPLAY",
                     notes="offline replay: exchange oid and cloid confirmed; full ledger coverage; no resend")
        closed.append(final)
    matched = {r['attempt_id'] for r in closed}
    known = {r['attempt_id'] for r in by_cloid.values()}
    for aid, row in latest.items():
        if str(row.get('status') or '').upper() in OPEN and aid not in matched and aid not in known:
            unresolved.append((aid, 'NO_UNIQUE_VALID_CLOID'))
    if strict and unresolved:
        raise RuntimeError('R3_UNRESOLVED=%d; examples=%r' % (len(unresolved), unresolved[:20]))
    return closed


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sends", required=True)
    parser.add_argument("--confirmations", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--apply", action="store_true", help="OFFLINE ONLY: sender must be stopped")
    parser.add_argument("--non-strict", action="store_true", help="diagnostic dry-run only")
    args = parser.parse_args()
    sends_path = Path(args.sends)
    sends = read_csv(sends_path)
    with Path(args.confirmations).open(encoding="utf-8") as fh:
        confirmations = [json.loads(line) for line in fh if line.strip()]
    if args.apply and args.non_strict:
        raise RuntimeError('R3_STRICT_REQUIRED: non-strict cannot write')
    if args.apply and os.environ.get('HL_LIVE_REPLAY_OFFLINE') != '1':
        raise RuntimeError('R3_OFFLINE_REQUIRED: stopped sender and isolated testnet only')
    changes = replay(sends, confirmations, read_csv(args.ledger), strict=not args.non_strict)
    if args.apply and changes:
        # Audit header is unchanged. Every result is an append, never a destructive rewrite.
        with sends_path.open(newline="", encoding="utf-8-sig") as fh:
            columns = list(csv.DictReader(fh).fieldnames or [])
        if not columns or not all(set(row) >= set(columns) for row in changes):
            raise ValueError("send audit schema unavailable")
        # One atomic file replacement; no per-row writes to the authoritative journal.
        staged_path = None
        try:
            fd, staged_path = tempfile.mkstemp(prefix=".r3-", suffix=".csv", dir=str(sends_path.parent))
            with os.fdopen(fd, "wb") as output, sends_path.open("rb") as original:
                shutil.copyfileobj(original, output)
                output.flush()
                os.fsync(output.fileno())
            with open(staged_path, "a", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
                for row in changes:
                    writer.writerow(row)
                output.flush()
                os.fsync(output.fileno())
            os.replace(staged_path, sends_path)
            staged_path = None
        finally:
            if staged_path is not None:
                os.unlink(staged_path)
    latest = {r["attempt_id"]: r for r in sends if r.get("attempt_id")}
    unresolved = {aid for aid, row in latest.items() if str(row.get("status") or "").upper() in OPEN}
    print(json.dumps({"eligible": len(changes), "applied": len(changes) if args.apply else 0,
                      "still_unresolved": len(unresolved - {r["attempt_id"] for r in changes}),
                      "mode": "APPLY_OFFLINE" if args.apply else "DRY_RUN"}, sort_keys=True))


if __name__ == "__main__":
    main()
