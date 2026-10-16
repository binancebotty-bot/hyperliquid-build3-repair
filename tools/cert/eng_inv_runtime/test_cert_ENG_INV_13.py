#!/usr/bin/env python3
"""ENG-INV-13: restart/recovery adopts verified fills into ledger but creates zero new trade authority (no new orders).

Run: python -I test_cert_ENG_INV_13.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE2 = Path(r"C:\Users\wigmore\trading_stack\hl-build3-testnet-cert\_archive\hl_stage2")
sys.path.insert(0, str(STAGE2))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
A = "0x" + "a" * 40

def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))

def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="eng_inv_13_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "testnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
        "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
        "HL_LIVE_MANUAL_POSITIONS_FILE": str(tmp / "manual_live_positions.json"),
    })
    for k in ("HL_LIVE_HOT_SEND_WORKERS",):
        os.environ.pop(k, None)
    os.environ["HL_LIVE_HOT_SEND_WORKERS"] = "4"

    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100", "DOGE": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

    def config(**gc):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            "auto_send_enabled": False,
            "global_controls": gc,
            "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}
        })

    config()

    # Simulate a previous run: write positions to MANUAL_LIVE_POSITIONS_FILE
    # and verified fills to SEND_ATTEMPTS_CSV
    ledger_path = c.MANUAL_LIVE_POSITIONS_FILE
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    c.atomic_write_json(ledger_path, {
        "schema": "manual_live_positions.v1.wallet_sleeves",
        "by_wallet": {
            A: {
                "BTC": {
                    "sleeve_id": f"{A}::BTC",
                    "position_id": f"{A}::LONG::f1",
                    "leader_wallet": A,
                    "coin": "BTC",
                    "direction": "LONG",
                    "signed_size": 1.0,
                    "avg_entry_px": 100.0,
                    "opened_by_intent_id": "f1",
                    "opened_at_ms": c.utc_now_ms(),
                    "last_copy_fill_id": "f1",
                    "last_updated_ms": c.utc_now_ms(),
                },
                "ETH": {
                    "sleeve_id": f"{A}::ETH",
                    "position_id": f"{A}::LONG::f2",
                    "leader_wallet": A,
                    "coin": "ETH",
                    "direction": "LONG",
                    "signed_size": 2.0,
                    "avg_entry_px": 200.0,
                    "opened_by_intent_id": "f2",
                    "opened_at_ms": c.utc_now_ms(),
                    "last_copy_fill_id": "f2",
                    "last_updated_ms": c.utc_now_ms(),
                },
            }
        },
        "by_coin_net": {
            "BTC": {"signed_size": 1.0},
            "ETH": {"signed_size": 2.0},
        },
    })

    # Write verified fills to SEND_ATTEMPTS_CSV
    send_attempts_path = c.SEND_ATTEMPTS_CSV
    send_attempts_path.parent.mkdir(parents=True, exist_ok=True)
    import csv
    with open(send_attempts_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "leader_fill_id", "leader_wallet", "coin", "side", "copy_size",
            "copy_notional", "limit_price", "leader_fill_timestamp_ms",
            "wallet_position_before", "coin_net_before", "intent_id",
            "sleeve_id", "position_id", "reduce_only_sent", "terminal_state",
        ])
        writer.writeheader()
        writer.writerow({
            "leader_fill_id": "f1", "leader_wallet": A, "coin": "BTC", "side": "BUY",
            "copy_size": 1.0, "copy_notional": 100.0, "limit_price": 100.0,
            "leader_fill_timestamp_ms": c.utc_now_ms(), "wallet_position_before": 0.0,
            "coin_net_before": 0.0, "intent_id": "f1", "sleeve_id": f"{A}::BTC",
            "position_id": f"{A}::LONG::f1", "reduce_only_sent": "false",
            "terminal_state": "ORDER_FILLED",
        })
        writer.writerow({
            "leader_fill_id": "f2", "leader_wallet": A, "coin": "ETH", "side": "BUY",
            "copy_size": 2.0, "copy_notional": 400.0, "limit_price": 200.0,
            "leader_fill_timestamp_ms": c.utc_now_ms(), "wallet_position_before": 0.0,
            "coin_net_before": 0.0, "intent_id": "f2", "sleeve_id": f"{A}::ETH",
            "position_id": f"{A}::LONG::f2", "reduce_only_sent": "false",
            "terminal_state": "ORDER_FILLED",
        })

    # Create core (restart)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    core._hot_stop_event.clear()
    core.async_dispatch = True

    # Check ledger has the fills (adopted)
    btc_pos = core.ledger.wallet_coin_position(A, "BTC")
    eth_pos = core.ledger.wallet_coin_position(A, "ETH")
    check("ENG_INV_13_RESTART_ADOPTS_FILLS", btc_pos != 0 and eth_pos != 0, f"btc={btc_pos} eth={eth_pos}")

    # Check that fills are in _idem_accepted (verified)
    idem_count = len(core._idem_accepted)
    check("ENG_INV_13_IDEM_ACCEPTED_SEEDED", idem_count >= 2, f"count={idem_count}")

    # Try to dispatch the same fills again
    def fill(coin="BTC", side="BUY", price=100.0, size=1.0, wallet=A, ts=None, oid="", d=""):
        raw = {**({"oid": oid} if oid else {}), **({"dir": d} if d else {})}
        return c.LeaderFill("f1", wallet, coin, side, price, size, ts or c.utc_now_ms(), "TEST", 0, raw)

    fills = [fill(coin="BTC", oid="0", d="Open Long"), fill(coin="ETH", oid="1", d="Open Long")]
    for f in fills:
        core._dispatch_fill(f)

    # Check hot queues are empty (no new orders)
    time.sleep(1)
    queue_empty = all(q.empty() for q in core._hot_queues)
    check("ENG_INV_13_ZERO_NEW_ORDERS", queue_empty, "hot queues not empty")

    # Stop core
    core._hot_stop_event.set()
    for t in core._hot_threads:
        t.join(timeout=2)
    core.stop()

    failed = sum(1 for _n, ok in RESULTS if not ok)
    print(f"TOTAL={len(RESULTS)} FAILED={failed}")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    main()
