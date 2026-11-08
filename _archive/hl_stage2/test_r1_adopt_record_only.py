#!/usr/bin/env python3
"""R1: startup adopts as a record only; foreign orders remain human-owned.

Offline testnet fixture: no exchange writes, no live session, no host state.db.
Run: python _archive/hl_stage2/test_r1_adopt_record_only.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

def main():
    root = Path(tempfile.mkdtemp(prefix="r1_adopt_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(root),
        "HL_LEADER_NETWORK": "testnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(root / "nonexistent.env"),
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
    })
    import requests
    import HL_Live_Copy_Service_Core as core

    requests.post = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("R1 forbids network POST"))
    core.requests.post = requests.post
    core.USER_WALLET = "0x" + "c" * 40
    core.ConfigManager.auto_send_enabled = property(lambda self: True)
    core.follower_dex_scope = lambda: [""]
    core.ensure_dirs()
    core.ensure_csv_header(core.SEND_ATTEMPTS_CSV, core.SEND_ATTEMPT_FIELDS)
    core.ensure_csv_header(core.RECONCILIATION_CSV, core.RECONCILIATION_FIELDS)
    core.atomic_write_json(core.RESTING_ENTRY_ORDERS_FILE, {})

    owned_cloid = core.generate_cloid("r1-owned")
    foreign_cloid = core.generate_cloid("r1-foreign-shape")
    core.append_csv(core.SEND_ATTEMPTS_CSV, core.SEND_ATTEMPT_FIELDS, {
        "attempt_id": "r1-pending", "intent_id": "r1-intent",
        "coin": "BTC", "side": "BUY", "status": "pending_send",
        "cloid": owned_cloid, "copy_size": "1", "limit_price": "100",
    })
    orders = [
        {"oid": 101, "coin": "BTC", "side": "B", "sz": "1",
         "limitPx": "100", "cloid": owned_cloid},
        {"oid": 202, "coin": "ETH", "side": "A", "sz": "2",
         "limitPx": "20", "cloid": foreign_cloid},
        {"oid": 303, "coin": "SOL", "side": "B", "sz": "3", "limitPx": "10"},
    ]
    core.OPEN_ORDERS_FETCHER = lambda payload: list(orders)
    gateway = core.SenderGateway(core.ConfigManager(), core.AuditLogWriter())
    cancels = []
    gateway._cancel_order = lambda *a, **k: cancels.append((a, k))
    gateway._exchange_client_for_coin = lambda coin: (
        (_ for _ in ()).throw(AssertionError("exchange client forbidden")), "")

    result = gateway.startup_orphan_order_check()
    assert result["ok"], result
    assert {x["oid"] for x in result["adopted"]} == {"101"}, result
    assert {x["oid"] for x in result["user_owned"]} == {"202", "303"}, result
    assert not result["cancelled"] and not cancels
    assert not gateway._resting_entries
    assert not core.load_json(core.RESTING_ENTRY_ORDERS_FILE, {})
    attempts = [r for r in core.read_csv_rows(core.SEND_ATTEMPTS_CSV)
                if r.get("attempt_id") == "r1-pending"]
    assert attempts and attempts[-1]["status"] == "pending_send"
    recon = core.read_csv_rows(core.RECONCILIATION_CSV)
    adopted = [r for r in recon if r.get("status") == "ORPHAN_ORDER_ADOPTED"]
    foreign = [r for r in recon if r.get("status") == "ORPHAN_ORDER_USER_OWNED"]
    assert len(adopted) == 1 and adopted[0]["exchange_order_id"] == "101"
    assert adopted[0]["action"] == "RECORD_ONLY_NO_REARM"
    assert {r["exchange_order_id"] for r in foreign} == {"202", "303"}
    assert all(r.get("terminal_state") == "USER_OWNED_ORDER_LEFT_UNTOUCHED"
               for r in foreign)

    # Restart-like repeat: durable reconciliation rows are not duplicated.
    second = core.SenderGateway(core.ConfigManager(), core.AuditLogWriter())
    second._cancel_order = gateway._cancel_order
    second._exchange_client_for_coin = gateway._exchange_client_for_coin
    assert second.startup_orphan_order_check()["ok"]
    recon2 = core.read_csv_rows(core.RECONCILIATION_CSV)
    assert len([r for r in recon2 if r.get("status") == "ORPHAN_ORDER_ADOPTED"]) == 1
    assert len([r for r in recon2 if r.get("status") == "ORPHAN_ORDER_USER_OWNED"]) == 2
    assert not cancels
    print("R1_RECORD_ONLY_PASS adopted=1 foreign_user_owned=2 no_rearm=1")
    print("R1_RESTART_DEDUPE_PASS audit_rows=3")
    print("RESULT: 2 passed, 0 failed (offline testnet)")


if __name__ == "__main__":
    main()
