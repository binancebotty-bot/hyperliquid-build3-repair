#!/usr/bin/env python3
"""Synthetic coverage for preserving exiting-wallet rows until their exposure is gone."""
from pathlib import Path
import tempfile

import HL_Copy_App_SSOT as ui


checks = []


def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))


def rows_for(config, manual_positions, resting_orders=None):
    tmp = Path(tempfile.mkdtemp(prefix="ui_exit_wallet_test_"))
    ui.WOULD_SEND_ORDERS_CSV = tmp / "would_send.csv"
    ui.LIVE_FILLS_CSV = tmp / "live_fills.csv"
    ui.RESTING_ENTRY_ORDERS_FILE = tmp / "resting_entry_orders.json"
    perf = ui._build_live_leader_performance(
        [], manual_positions, {"available": False, "positions_by_coin": {}}, config, []
    )
    kwargs = {"live_fills": [], "resting_orders": resting_orders or []}
    try:
        rows = ui._build_live_wallet_rows(
            config, [], [], manual_positions, {}, {"wallets": {}}, perf, **kwargs
        )
    except TypeError:
        return {}, perf
    return {row["wallet"].lower(): row for row in rows}, perf


wallet = "0xabc"
manual = {
    "schema": "manual_live_positions.v1.wallet_sleeves",
    "by_wallet": {wallet: {"BTC": {"signed_size": 2.0, "avg_entry_px": 100.0}}},
}

# A removed wallet with an unresolved/open sleeve still needs a diagnostic row.
rows, perf = rows_for({"wallets": {}}, manual)
row = rows.get(wallet)
check("EXITING_UNCONFIGURED_SLEEVE_RENDERS", row is not None)
check(
    "EXITING_UNCONFIGURED_POSITION_COUNT_AND_NOTIONAL",
    bool(row) and row["mode"] == "OFF" and row["open_position_count"] == 1
    and row["open_positions"] == ["BTC"] and row["current_exposure"] == 200.0,
    str({k: row.get(k) for k in ("mode", "open_position_count", "open_positions", "current_exposure")} if row else None),
)
check("EXITING_POSITION_DETAIL_SURVIVES", bool(perf.get(wallet, {}).get("current_open_positions")))

# A configured close-only wallet remains visibly identified while the sleeve is open.
config_clo = {"wallets": {wallet: {"mode": "CLO", "enabled": True}}}
clo_rows, _ = rows_for(config_clo, manual)
clo = clo_rows.get(wallet)
check(
    "CLOSE_ONLY_SLEEVE_RENDERS_WITH_MODE_AND_EXPOSURE",
    bool(clo) and clo["mode"] == "CLO" and clo["open_position_count"] == 1
    and clo["current_exposure"] == 200.0,
    str({k: clo.get(k) for k in ("mode", "open_position_count", "current_exposure")} if clo else None),
)

# A live resting entry/withdrawal record also retains its owner row.
resting = [{"leader_wallet": "0xdef", "coin": "ETH", "size": 3.0, "open_size": 2.0, "limit_px": 50.0}]
rest_rows, _ = rows_for({"wallets": {}}, {}, resting)
rest = rest_rows.get("0xdef")
check(
    "RESTING_ORDER_OWNER_RENDERS_UNTIL_FLAT",
    bool(rest) and rest["mode"] == "OFF" and rest["resting_order_count"] == 1
    and rest["resting_order_notional"] == 100.0,
    str({k: rest.get(k) for k in ("mode", "resting_order_count", "resting_order_notional")} if rest else None),
)
source = Path(ui.__file__).read_text(encoding="utf-8")
check(
    "ROW_RENDER_SHOWS_CLOSE_COINS_AND_RESTING_ORDERS",
    "const closeCoins=(d.open_positions||[]).join(', ')" in source
    and "d.resting_order_count" in source and "d.resting_order_notional" in source,
)

failed = [name for name, ok, _ in checks if not ok]
for name, ok, detail in checks:
    print(f"RESULT::{name}::{ 'PASS' if ok else 'FAIL' }" + (f"::{detail}" if detail and not ok else ""))
print(f"SUMMARY::{len(checks) - len(failed)}/{len(checks)}")
raise SystemExit(1 if failed else 0)
