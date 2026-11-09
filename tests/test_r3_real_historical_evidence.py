"""R3 production-path historical gate; requires real REDACTED runner snapshots.
No synthetic 2,199 rows. No live-engine access. Never modifies supplied audit/state.db.
Set R3_HISTORY_SENDS, R3_HISTORY_LEDGER, R3_HISTORY_CONFIRMATIONS, R3_HISTORY_STATE_DB,
HL_LIVE_REPLAY_NETWORK=testnet, HL_LIVE_REPLAY_ACCOUNT, HL_LIVE_REPLAY_DEX.
Confirmation provenance must be independently authenticated by Runner.
"""
import os
import shutil
import sqlite3
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "tools/cert/replay_confirmed_attempts.py"
spec = importlib.util.spec_from_file_location("r3_real_history", MODULE)
r3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r3)

def _evidence(name):
    p = Path(os.environ[name])
    assert p.is_file() and p.stat().st_size > 0, f"R3_EVIDENCE_MISSING:{name}"
    return p

def test_real_2199_historical_audit_and_state_db(tmp_path, monkeypatch):
    # No defaults: failing to supply actual history is a FAIL, not an invented PASS.
    sends = _evidence("R3_HISTORY_SENDS")
    ledger = _evidence("R3_HISTORY_LEDGER")
    confirmations = _evidence("R3_HISTORY_CONFIRMATIONS")
    state = _evidence("R3_HISTORY_STATE_DB")
    assert r3._require_testnet_scope()[0] == "testnet"

    conn = sqlite3.connect(f"file:{state}?mode=ro", uri=True)
    try:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
        tables = {name for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert tables, "R3_STATE_DB_TABLES_MISSING"
    finally:
        conn.close()

    rows = r3.read_csv(sends)
    assert len(rows) == 2199, f"R3_REAL_HISTORY_COUNT:{len(rows)}"
    assert all(row.get("leader_fill_id") for row in rows), "R3_HISTORY_MISSING_LEADER_ID"
    # Mutate only an isolated snapshot and acquire the actual production replay lease.
    isolated = tmp_path / "send_attempts.csv"
    shutil.copyfile(sends, isolated)
    before = isolated.read_bytes()
    monkeypatch.setenv("HL_LIVE_GLOBAL_LOCK_FILE", str(tmp_path / "engine-global.lock"))
    try:
        applied = r3.apply_locked(isolated, confirmations, ledger)
    except RuntimeError:
        assert isolated.read_bytes() == before, "R3_PARTIAL_HISTORY_WRITE"
        raise
    assert applied >= 0
    assert len(r3.read_csv(isolated)) == len(rows) + applied
    assert sends.read_bytes() == before, "R3_ORIGINAL_AUDIT_MUTATED"
