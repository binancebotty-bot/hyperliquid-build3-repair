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


def _engine_lock_path():
    """Same cross-process lease as core._global_instance_lock_path; never sidecar-only."""
    base = os.getenv("LOCALAPPDATA") or os.getenv("XDG_STATE_HOME") or tempfile.gettempdir()
    return Path(os.getenv("HL_LIVE_GLOBAL_LOCK_FILE") or
                str(Path(base) / "HL_Live_Copy_Service_Core" / "engine-global.lock"))


def _exclusive_engine_lock():
    """Acquire the ACTUAL engine lease; return a closable handle, fail if occupied."""
    path = _engine_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt
            if not path.stat().st_size:
                fd.write(b"0")
                fd.flush()
            fd.seek(0)
            msvcrt.locking(fd.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        fd.close()
        raise RuntimeError("R3_ENGINE_LEASE_HELD: stop sender; cannot rewrite audit") from exc
    return fd


def _sync_parent(path):
    if os.name != "nt":
        fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def _require_testnet_scope():
    """Fail closed before audit reads; caller-provided metadata is not authenticated exchange evidence."""
    network = os.getenv("HL_LIVE_REPLAY_NETWORK", "").strip().lower()
    account = os.getenv("HL_LIVE_REPLAY_ACCOUNT", "").strip().lower()
    dex = os.getenv("HL_LIVE_REPLAY_DEX", "").strip().lower()
    if network != "testnet":
        raise RuntimeError("R3_TESTNET_ONLY")
    if not account or not dex:
        raise RuntimeError("R3_AUTHENTICATED_SCOPE_REQUIRED")
    return network, account, dex


def _check_confirmation_scope(confirmations, scope):
    """Require per-row provenance fields; independent authentication is Runner responsibility."""
    expected_network, expected_account, expected_dex = scope
    for item in confirmations:
        if (str(item.get("network") or "").strip().lower() != expected_network
            or str(item.get("account") or "").strip().lower() != expected_account
            or str(item.get("dex") or "").strip().lower() != expected_dex):
            raise RuntimeError("R3_CONFIRMATION_SCOPE_UNVERIFIED")


def apply_locked(sends_path, confirmation_path, ledger_path):
    """Re-read and preflight under engine-wide lease; one same-directory atomic swap.

    No state.db transaction is claimed. Non-cooperating writers are unsupported.
    """
    import hashlib
    scope = _require_testnet_scope()
    sends_path = Path(sends_path)
    lease = _exclusive_engine_lock()
    try:
        # All evidence is read under the lease; never reuse pre-lock snapshots.
        with Path(confirmation_path).open(encoding="utf-8") as fh:
            confirmations = [json.loads(line) for line in fh if line.strip()]
        _check_confirmation_scope(confirmations, scope)
        sends = read_csv(sends_path)
        ledger = read_csv(ledger_path)
        changes = replay(sends, confirmations, ledger, strict=True)
        if not changes:
            return 0
        original = sends_path.read_bytes()
        before = sends_path.stat()
        digest = hashlib.sha256(original).digest()
        if not original.endswith((b"\r\n", b"\n")):
            raise RuntimeError("R3_INCOMPLETE_LAST_RECORD")
        with sends_path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.reader(fh)
            columns = next(reader, [])
        if not columns or any(not set(row).issubset(set(columns)) for row in changes):
            raise RuntimeError("R3_CSV_SCHEMA_MISMATCH")
        newline = "\r\n" if original.count(b"\r\n") > original.count(b"\n") - original.count(b"\r\n") else "\n"
        bom = original.startswith(b"\xef\xbb\xbf")
        mode = before.st_mode
        staged_path = None
        try:
            fd, staged_path = tempfile.mkstemp(prefix=".r3-", suffix=".csv", dir=str(sends_path.parent))
            with os.fdopen(fd, "wb") as output:
                output.write(original)
                output.flush()
                os.fsync(output.fileno())
            with open(staged_path, "a", newline="", encoding="utf-8") as output:
                writer = csv.DictWriter(output, fieldnames=columns, extrasaction="raise",
                                        lineterminator=newline)
                for row in changes:
                    writer.writerow(row)
                output.flush()
                os.fsync(output.fileno())
            os.chmod(staged_path, mode)
            # Protect against a non-cooperating writer between snapshot and staging.
            current = sends_path.stat()
            if ((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) !=
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    or hashlib.sha256(sends_path.read_bytes()).digest() != digest):
                raise RuntimeError("R3_JOURNAL_CHANGED_DURING_REPLAY")
            os.replace(staged_path, sends_path)
            staged_path = None
            _sync_parent(sends_path)
            # Byte BOM and newline convention are retained from original source.
            assert sends_path.read_bytes().startswith(b"\xef\xbb\xbf") == bom
            return len(changes)
        finally:
            if staged_path is not None:
                os.unlink(staged_path)
    finally:
        lease.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--sends", required=True)
    parser.add_argument("--confirmations", required=True)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--apply", action="store_true", help="OFFLINE ONLY: engine must be stopped")
    parser.add_argument("--non-strict", action="store_true", help="diagnostic dry-run only")
    args = parser.parse_args(argv)
    # This check precedes ALL journal or evidence reads.
    if args.apply and args.non_strict:
        raise RuntimeError("R3_STRICT_REQUIRED: partial replay cannot write")
    if args.apply and os.getenv("HL_LIVE_REPLAY_OFFLINE") != "1":
        raise RuntimeError("R3_OFFLINE_REQUIRED")
    if args.apply:
        _require_testnet_scope()
        applied = apply_locked(args.sends, args.confirmations, args.ledger)
        print(json.dumps({"applied": applied, "mode": "APPLY_OFFLINE"}))
        return
    sends = read_csv(args.sends)
    with Path(args.confirmations).open(encoding="utf-8") as fh:
        confirmations = [json.loads(line) for line in fh if line.strip()]
    changes = replay(sends, confirmations, read_csv(args.ledger), strict=not args.non_strict)
    print(json.dumps({"eligible": len(changes), "mode": "DRY_RUN"}))


if __name__ == "__main__":
    main()
