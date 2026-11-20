#!/usr/bin/env python3
"""SET-009 clause 6b: stale integrity state holds entries but not closes."""
from __future__ import annotations

import os
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

requests_stub = types.ModuleType("requests")
requests_stub.post = lambda *_args, **_kwargs: (_ for _ in ()).throw(
    RuntimeError("offline test: network access disabled")
)
sys.modules.setdefault("requests", requests_stub)

import HL_Live_Copy_Service_Core as c
from HL_Live_Copy_Service_Core import atomic_write_json

RESULTS: list[tuple[str, bool]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(condition)))
    status = "PASS" if condition else "FAIL"
    suffix = f" | {detail}" if detail and not condition else ""
    print(f"RESULT::{name}_{status}{suffix}")


def _offline(*_args, **_kwargs):
    raise RuntimeError("offline test: network access disabled")


def _core_for(tmp: Path):
    atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True,
        "global_controls": {},
        "wallets": {
            "0xwallet": {
                "enabled": True,
                "mode": "LIVE",
                "copy_mode": "fixed",
                "fixed_notional": 1000,
            }
        },
    })
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.wallets = ["0xwallet"]
    import requests
    requests.post = _offline
    c.requests.post = _offline
    return core


def _intent(intent_id: str, *, entry: bool):
    fill = c.LeaderFill(
        "fill-" + intent_id,
        "0xwallet",
        "BTC",
        "BUY" if entry else "SELL",
        100.0,
        1.0,
        c.utc_now_ms(),
        "TEST",
    )
    if entry:
        return c.Intent(
            intent_id, fill, "BUY", 1.0, 100.0, "LIVE", "fixed", "ENTRY_ALLOWED", "",
            "sleeve", "position", "FLAT", 0.0, 0.0, False, True, notes="lifecycle=ENTRY",
        )
    return c.Intent(
        intent_id, fill, "SELL", 1.0, 100.0, "LIVE", "fixed", "EXIT_ALLOWED", "",
        "sleeve", "position", "LONG", 1.0, 1.0, True, True, notes="",
    )


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="set009_clause6b_"))
    os.environ["HL_LIVE_AUDIT_DIR"] = str(tmp)
    os.environ["HL_LIVE_ENV_FILE"] = str(tmp / "none.env")
    c.AUDIT_DIR = tmp / "hl_live_copy_audit_testnet"
    c.APPEND_ONLY_DIR = c.AUDIT_DIR / "append_only"
    c.LIVE_CONFIG_FILE = c.AUDIT_DIR / "live_config.json"
    c.SERVICE_STATE_FILE = c.AUDIT_DIR / "live_service_state.json"
    c.CORE_RUNTIME_STATE_FILE = c.AUDIT_DIR / "clean_core_runtime_state.json"
    c.MANUAL_LIVE_POSITIONS_FILE = c.AUDIT_DIR / "manual_live_positions.json"
    c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE = c.AUDIT_DIR / "exchange_account_snapshot.json"
    c.RECONCILIATION_CSV = c.APPEND_ONLY_DIR / "reconciliation.csv"
    c.LIVE_INTEGRITY_STATUS_FILE = c.AUDIT_DIR / "live_integrity_status.json"
    c.ensure_dirs()

    core = _core_for(tmp)
    core._entry_sends_blocked_reason = "LEDGER_STATUS_STALE"

    entry_ok, entry_status = core.sender.send_if_allowed(_intent("stale-entry", entry=True),
                                                          core._entry_sends_blocked_reason)
    check("stale_state_blocks_entry",
          (entry_ok, entry_status) == (False, "ENTRY_BLOCKED_LEDGER_STATUS_STALE"),
          f"ok={entry_ok} status={entry_status}")

    close = _intent("stale-close", entry=False)
    check("unlabelled_reduce_only_intent_is_exit",
          c.classify_send_lifecycle(close) == "EXIT", c.classify_send_lifecycle(close))
    close_ok, close_status = core.sender.send_if_allowed(close, core._entry_sends_blocked_reason)
    check("close_refused_by_ownership_gate",
          close_ok is False and close_status.startswith("OWNERSHIP_GATE_"),
          f"ok={close_ok} status={close_status}")
    check("close_not_refused_for_stale_status",
          close_status != "ENTRY_BLOCKED_LEDGER_STATUS_STALE", f"status={close_status}")

    failed = [name for name, passed in RESULTS if not passed]
    print(f"\nTOTAL={len(RESULTS)} FAILED={len(failed)}")
    if failed:
        print("FAILED:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
