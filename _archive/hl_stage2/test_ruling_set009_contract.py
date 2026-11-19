#!/usr/bin/env python3
"""SET-009 ruling contract - executable, anti-gaming form.

Every clause runs repository code against real on-disk ledger-status files. There is no
source-text slicing and no literal-symbol pinning: the LEDGER_* family of reasons is
accepted wherever the gate expresses the same condition. A comment-only edit to the
engine cannot change any outcome here.

Run:  python test_ruling_set009_contract.py [path_to_hl_stage2_dir]
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import types
from pathlib import Path

DIR = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"
os.environ.pop("HL_LIVE_GATES_ALERT_ONLY", None)
import HL_Live_Copy_Service_Core as core

RESULTS = []


def check(clause, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"RESULT::{clause}_{'PASS' if ok else 'FAIL'}" + (f" | {detail}" if detail else ""))


def _offline(*_a, **_k):
    raise RuntimeError("SET-009 contract is offline: no network calls permitted")


import requests  # noqa: E402  (dependency already used by the engine)

requests.post = _offline
core.requests.post = _offline


def _setup(alert_only="0"):
    """Isolated real engine with its global file paths pointed at a fresh temp tree."""
    tmp = Path(tempfile.mkdtemp(prefix="set009_contract_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)
    os.environ["HL_LIVE_ENV_FILE"] = str(tmp / "none.env")
    os.environ["HL_LIVE_GATES_ALERT_ONLY"] = str(alert_only)
    os.environ["HL_LEADER_NETWORK"] = "testnet"
    os.environ["HL_FOLLOWER_NETWORK"] = "testnet"
    core.AUDIT_DIR = tmp / "hl_live_copy_audit_testnet"
    core.APPEND_ONLY_DIR = core.AUDIT_DIR / "append_only"
    core.LIVE_CONFIG_FILE = core.AUDIT_DIR / "live_config.json"
    core.SERVICE_STATE_FILE = core.AUDIT_DIR / "live_service_state.json"
    core.CORE_RUNTIME_STATE_FILE = core.AUDIT_DIR / "clean_core_runtime_state.json"
    core.MANUAL_LIVE_POSITIONS_FILE = core.AUDIT_DIR / "manual_live_positions.json"
    core.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = core.AUDIT_DIR / "exchange_account_snapshot.json"
    core.RECONCILIATION_CSV = core.APPEND_ONLY_DIR / "reconciliation.csv"
    core.LIVE_INTEGRITY_STATUS_FILE = core.AUDIT_DIR / "live_integrity_status.json"
    core.ensure_dirs()
    core.USER_WALLET = "0x" + "c" * 40
    core.atomic_write_json(core.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": {},
        "wallets": {"0xwallet": {"enabled": True, "mode": "LIVE", "copy_mode": "fixed",
                                "fixed_notional": 1000}},
    })
    core.atomic_write_json(core.MANUAL_LIVE_POSITIONS_FILE, {"by_wallet": {}, "by_coin_net": {}})
    core.atomic_write_json(core.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {}})
    svc = core.LiveCopyCore(source_csv=tmp / "none.csv")
    svc.wallets = ["0xwallet"]
    return svc, tmp


def _gate(svc):
    """Execute the real cycle gate and return the block reason it publishes."""
    svc.run_cycle(poll_live=False, poll_copy=False, reconcile_exchange=False)
    return svc._entry_sends_blocked_reason


def _write_status(payload):
    core.LIVE_INTEGRITY_STATUS_FILE.write_text(json.dumps(payload), encoding="utf-8")


def _is_ledger(reason):
    return isinstance(reason, str) and reason.startswith("LEDGER_")


def _status_family(reason):
    return isinstance(reason, str) and reason.startswith("LEDGER_STATUS_")


def _divergence_family(reason):
    return _is_ledger(reason) and "DIVERGENCE" in reason


def _rows(path):
    if not path.exists():
        return []
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


# ---- Clauses 1-4: execute the real gate on real status files --------------------
svc, _ = _setup()
_write_status({"created_at_ms": core.utc_now_ms() - 600_000, "counts": {}})
r_stale = _gate(svc)
check("CLAUSE_1_STALE_STATUS_BLOCKS_ENTRY_AT_REPO_DEFAULT",
      _status_family(r_stale), r_stale)

svc, _ = _setup()
try:
    core.LIVE_INTEGRITY_STATUS_FILE.unlink()
except OSError:
    pass
r_missing = _gate(svc)
check("CLAUSE_2_MISSING_STATUS_BLOCKS_ENTRY_AT_REPO_DEFAULT",
      _status_family(r_missing), r_missing)

svc, _ = _setup()
core.LIVE_INTEGRITY_STATUS_FILE.write_text("{not json", encoding="utf-8")
r_unreadable = _gate(svc)
check("CLAUSE_3_UNREADABLE_STATUS_BLOCKS_ENTRY_AT_REPO_DEFAULT",
      _status_family(r_unreadable), r_unreadable)

svc, _ = _setup()
_write_status({"created_at_ms": core.utc_now_ms(),
               "counts": {"exchange_manual_mismatch": 1}})
r_diverged = _gate(svc)
check("CLAUSE_4_FRESH_MANUAL_MISMATCH_BLOCKS_ENTRY",
      _divergence_family(r_diverged), r_diverged)


# ---- Clause 5: entry blocked by a REAL reason; close passes that same block -----
class _PassedEntryGuard(Exception):
    """Raised by the stubbed ownership gate: proof the close got past the entry block."""


def _sender_shell():
    s = object.__new__(core.SenderGateway)
    s.ledger = None
    s.sender_key_invalid = False
    s.cfg = types.SimpleNamespace(
        master_switch_now=lambda: True,
        send_mode_now=lambda: "LIVE",
        wallet_over_stream_cap=lambda _w: False,
    )
    s.audit = s
    s.append_reconciliation = types.MethodType(core.AuditLogWriter.append_reconciliation, s)
    s._note_fill_row = lambda *_a, **_k: None
    s._pre_send_ownership_gate = lambda intent: (_ for _ in ()).throw(_PassedEntryGuard())
    return s


def _intent(notes, reduce_only, decision, direction):
    fill = core.LeaderFill("lf-1", "0xwallet", "BTC", "SELL", 100.0, 1.0,
                           core.utc_now_ms(), "TEST")
    return core.Intent(
        "i-1", fill, "SELL", 1.0, 100.0, "LIVE", "fixed", decision, "",
        "sleeve", "position", direction, 0.0, 0.0, reduce_only, False, notes=notes,
    )


# The reason is produced by the real gate on a real stale status file, never hand-typed.
svc, _ = _setup()
_write_status({"created_at_ms": core.utc_now_ms() - 600_000, "counts": {}})
block_reason = _gate(svc)
sender = _sender_shell()

entry_status = sender.send_if_allowed(
    _intent("lifecycle=ENTRY", False, "ENTRY_ALLOWED", "FLAT"), block_reason)[1]
check("CLAUSE_5A_ENTRY_BLOCKED_BY_REAL_GATE_REASON",
      entry_status == f"ENTRY_BLOCKED_{block_reason}", entry_status)

try:
    sender.send_if_allowed(
        _intent("lifecycle=EXIT", True, "EXIT_ALLOWED", "LONG"), block_reason)
    close_status = "NO_ENTRY_GUARD_REACHED"
except _PassedEntryGuard:
    close_status = "PASSED_ENTRY_GUARD"
except Exception as exc:  # noqa: BLE001 - report the exact raised type
    close_status = f"RAISED:{type(exc).__name__}"
check("CLAUSE_5B_REDUCE_ONLY_CLOSE_PASSES_THE_SAME_BLOCK",
      close_status == "PASSED_ENTRY_GUARD", close_status)

check("CLAUSE_5C_BLOCK_REASON_PRODUCIBLE_FROM_REAL_STATUS_FILE",
      _status_family(block_reason) and block_reason != "", block_reason)


# ---- Clause 6: production intent + the real classify defect site ----------------
prod_close = _intent("lifecycle=EXIT", True, "EXIT_ALLOWED", "LONG")
lifecycle = core.classify_send_lifecycle(prod_close)
check("CLAUSE_6A_PRODUCTION_CLOSE_INTENT_CLASSIFIED_AS_CLOSE",
      lifecycle in {"EXIT", "REDUCE"}, lifecycle)

core.atomic_write_json(core.MANUAL_LIVE_POSITIONS_FILE,
                       {"by_wallet": {}, "by_coin_net": {}})
ledger = core.ManualLedger(core.MANUAL_LIVE_POSITIONS_FILE)
kind, is_reduce = ledger.classify_leader_side_for_wallet("0xwallet", "BTC", "SELL")
check("CLAUSE_6B_FLAT_LEDGER_SELL_NOT_MISCLASSIFIED_AS_ENTRY",
      kind in {"EXIT", "REDUCE"} and is_reduce is True,
      f"kind={kind} reduce_only={is_reduce}")


# ---- Clause 7: real GATE_WOULD_BLOCK row, gate echo, fresh writes no row ---------
audit = object.__new__(core.LiveCopyCore)
audit.audit = audit
audit.append_reconciliation = types.MethodType(core.AuditLogWriter.append_reconciliation, audit)
audit._note_fill_row = lambda *_a, **_k: None
recon = core.RECONCILIATION_CSV
if recon.exists():
    recon.unlink()
audit._gate_would_block(block_reason)  # a real reason the gate produced above
gate_rows = [r for r in _rows(recon) if r.get("event") == "GATE_WOULD_BLOCK"]
check("CLAUSE_7A_STALE_CONDITION_WRITTEN_AS_REAL_RECON_ROW",
      bool(gate_rows), f"gate_rows={len(gate_rows)}")
check("CLAUSE_7B_ROW_TERMINAL_STATE_EQUALS_GATE_OUTPUT",
      any((r.get("terminal_state") or r.get("status") or "") == block_reason
          for r in gate_rows),
      str([r.get("terminal_state") or r.get("status") for r in gate_rows]))

svc, _ = _setup()
recon = core.RECONCILIATION_CSV
before = sum(1 for r in _rows(recon) if r.get("event") == "GATE_WOULD_BLOCK")
_write_status({"created_at_ms": core.utc_now_ms(),
               "counts": {"exchange_manual_mismatch": 0}})
fresh_reason = _gate(svc)
after = sum(1 for r in _rows(recon) if r.get("event") == "GATE_WOULD_BLOCK")
check("CLAUSE_7C_FRESH_MATCHED_STATUS_WRITES_NO_ROW",
      after == before and not _is_ledger(fresh_reason),
      f"reason={fresh_reason!r} before={before} after={after}")


print("TOTAL=%d FAILED=%d" % (len(RESULTS), RESULTS.count(False)))
sys.exit(1 if False in RESULTS else 0)
