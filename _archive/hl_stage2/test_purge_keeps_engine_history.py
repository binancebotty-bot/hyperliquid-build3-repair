#!/usr/bin/env python3
"""ADMIN PURGE scope guard: clearing a wallet's app config must never delete engine history.

Ruling in force: the purge clears the APP's wallet config / include / meta, its derived app
caches and its live per-wallet state entries. It must NOT touch the engine's audit trail or
position stores, because a retired wallet can still hold a position that has to be closed.

This suite seeds every store with the wallet's own rows (plus a bystander wallet), runs the
real purge - no mocks - and asserts both halves in one pass: the three app sections are gone
AND every engine store is byte-identical afterwards. Extend the purge to any engine store and
the matching check goes red.

Nothing here talks to the engine or the network: every path is repointed into a temp dir.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
W = "0x" + "c" * 40   # wallet being purged
K = "0x" + "d" * 40   # bystander wallet: must be left alone everywhere

AUDIT_STORES = (
    "append_only/live_fills.csv",
    "append_only/order_intents.csv",
    "append_only/send_attempts.csv",
    "append_only/would_send_orders.csv",
    "append_only/reconciliation.csv",
)


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + str(detail)[:400]) if detail and not ok else ""))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")


def write_json(path: Path, obj) -> None:
    write(path, json.dumps(obj, indent=2))


def digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def two_wallet_csv(header: str) -> str:
    return header + "\r\n" + W + ",1,BTC,BUY,100.0,1.0\r\n" + K + ",2,ETH,SELL,50.0,2.0\r\n"


def wallet_col(path: Path) -> list:
    lines = path.read_text(encoding="utf-8").splitlines()[1:]
    return [line.split(",")[0] for line in lines if line.strip()]


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="purge_scope_", dir=os.environ.get("TMPDIR") or None))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp / "audit"), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet"})
    import HL_Copy_App_SSOT as ui

    # --- repoint every path the purge can reach into the temp dir ------------------------
    data, audit = tmp / "hl_copy_output", tmp / "audit"
    ui.DATA_DIR, ui.LIVE_COPY_AUDIT_DIR = data, audit
    ui.SNAP_DIR = data / "snapshots"
    ui.UI_STATE_FILE = tmp / "ui_state.json"
    ui.WALLET_GATE_FILE = tmp / "wallet_gate.json"
    ui.MANUAL_WALLETS_FILE = tmp / "manual_wallets.txt"
    ui.PURGED_WALLETS_FILE = tmp / "purged_wallets.txt"
    ui.LIVE_COPY_CONFIG_FILE = audit / "live_config.json"
    ui.LIVE_CONFIG_FILE = ui.LIVE_COPY_CONFIG_FILE
    ui.RAW_FILLS_CSV = data / "raw_live_fills.csv"
    ui.EXPECTED_COPY_FILLS_CSV = data / "expected_copy_fills.csv"
    ui.COPY_TRADES_CSV = data / "copy_trades.csv"
    ui.LIVE_WALLET_METRICS_CSV = data / "live_wallet_metrics.csv"
    ui.ENGINE_TRUTH_JSON = data / "engine_truth.json"
    ui.EXCHANGE_BASELINES_JSON = data / "exchange_baselines.json"
    ui.LEGACY_LIVE_STATE_JSON = data / "live_state.json"
    ui.APP_MODEL_STATE_JSON = data / "app_model_state.json"
    ui.PORTFOLIO_HISTORY_FILE = data / "portfolio_history.json"
    ui.EQUITY_HISTORY_FILE = data / "equity_history.json"

    # engine-store constants are repointed too, so a purge that starts using them is caught
    engine_csvs = {name: audit / name for name in AUDIT_STORES}
    ui.LIVE_FILLS_CSV = engine_csvs["append_only/live_fills.csv"]
    ui.LIVE_COPY_ORDER_INTENTS_CSV = engine_csvs["append_only/order_intents.csv"]
    ui.SEND_ATTEMPTS_CSV = engine_csvs["append_only/send_attempts.csv"]
    ui.WOULD_SEND_ORDERS_CSV = engine_csvs["append_only/would_send_orders.csv"]
    ui.LIVE_COPY_RECONCILIATION_CSV = engine_csvs["append_only/reconciliation.csv"]
    ui.MANUAL_POSITIONS_FILE = audit / "manual_live_positions.json"
    ui.EXCHANGE_ACCOUNT_HISTORY_FILE = audit / "exchange_account_history.json"

    # --- seed the app side: the three sections, include list, gate, live config ----------
    write_json(ui.UI_STATE_FILE, {
        "wallet_config": {W: {"copy_mode": "fixed", "fixed_notional": 11.0}, K: {"copy_mode": "live"}},
        "wallet_include": {W: True, K: True},
        "wallet_meta": {W: {"tag": "retired", "note": "to be purged", "color": "blue"},
                        K: {"tag": "keep", "note": "bystander", "color": "green"}},
        "norm_base": 250.0,
    })
    write(ui.MANUAL_WALLETS_FILE, W + "\n" + K + "\n")
    write_json(ui.WALLET_GATE_FILE, {W: {"mode": "OFF", "off_mode": None}, K: {"mode": "ON", "off_mode": None}})
    write_json(ui.LIVE_COPY_CONFIG_FILE, {"mode": "LIVE", "wallets": {W: {"alloc": 100.0}, K: {"alloc": 50.0}}})
    write_json(ui.ENGINE_TRUTH_JSON, {"wallets": {W: {"equity": 101.0}, K: {"equity": 51.0}}})
    write_json(ui.EXCHANGE_BASELINES_JSON,
               {"baselines": [{"wallet": W, "equity": 100.0}, {"wallet": K, "equity": 50.0}]})
    write_json(ui.LEGACY_LIVE_STATE_JSON, {"wallets": {W: {"equity": 101.0}, K: {"equity": 51.0}}})

    # --- seed the app's projection CSVs --------------------------------------------------
    for path in (ui.COPY_TRADES_CSV, ui.EXPECTED_COPY_FILLS_CSV, ui.LIVE_WALLET_METRICS_CSV):
        write(path, two_wallet_csv("wallet,trade_id,coin,side,px,sz"))

    # --- derived app caches: whole files the purge is allowed to delete -------------------
    for path in (ui.APP_MODEL_STATE_JSON, ui.PORTFOLIO_HISTORY_FILE, ui.EQUITY_HISTORY_FILE):
        write_json(path, {"wallets": {W: {"equity": 101.0}}})

    # --- engine stores: the purge must not touch any of these ----------------------------
    for path in engine_csvs.values():
        write(path, two_wallet_csv("wallet,oid,coin,side,px,sz,ts"))
    write(ui.RAW_FILLS_CSV, two_wallet_csv("wallet,fill_id,coin,side,px,sz,ts"))
    # real v2 shape: wallet-keyed sleeves, so a wallet-key strip would be destructive
    write_json(ui.MANUAL_POSITIONS_FILE,
               {"schema": "manual_live_positions.v2",
                "by_wallet": {W: {"BTC": {"signed_size": 0.01, "last_updated_at": "2026-01-01T00:00:00Z"}},
                              K: {"ETH": {"signed_size": -2.0, "last_updated_at": "2026-01-01T00:00:00Z"}}}})
    write_json(ui.EXCHANGE_ACCOUNT_HISTORY_FILE,
               [{"wallet": W, "action": "open", "coin": "BTC", "sz": 0.01}])
    snapshot = ui.SNAP_DIR / "2026-01-01_00-00-00_app_model_state.json"
    write_json(snapshot, {"wallets": {W: {"equity": 101.0}}})

    engine_paths = list(engine_csvs.values()) + [ui.RAW_FILLS_CSV, ui.MANUAL_POSITIONS_FILE,
                                                 ui.EXCHANGE_ACCOUNT_HISTORY_FILE, snapshot]
    before = {str(p): digest(p) for p in engine_paths}
    assert len(before) == 9 and all(before.values()), before

    # --- run the real purge --------------------------------------------------------------
    proof = ui.purge_wallet_app_config(W)

    # ---- app side: the three sections are gone, the bystander is intact ------------------
    state = json.loads(ui.UI_STATE_FILE.read_text(encoding="utf-8"))
    sections = ("wallet_config", "wallet_include", "wallet_meta")
    gone = all(W not in (state.get(k) or {}) for k in sections)
    kept = all(K in (state.get(k) or {}) for k in sections)
    check("PURGE_APP_SECTIONS_GONE_BYSTANDER_KEPT",
          gone and kept and state.get("norm_base") == 250.0
          and (proof.get("json_removed") or {}).get("ui_state.json") == 3,
          "gone=%s kept=%s norm_base=%r proof=%r" % (gone, kept, state.get("norm_base"), proof.get("json_removed")))

    manual = ui.MANUAL_WALLETS_FILE.read_text(encoding="utf-8").split()
    gate = json.loads(ui.WALLET_GATE_FILE.read_text(encoding="utf-8"))
    live = (json.loads(ui.LIVE_COPY_CONFIG_FILE.read_text(encoding="utf-8")).get("wallets") or {})
    purged = (ui.PURGED_WALLETS_FILE.read_text(encoding="utf-8").split()
              if ui.PURGED_WALLETS_FILE.exists() else [])
    check("PURGE_INCLUDE_GATE_LIVE_CONFIG_CLEARED",
          W not in manual and K in manual and W not in gate and K in gate
          and W not in live and K in live and W in purged,
          "manual=%r gate=%r live=%r purged=%r" % (manual, sorted(gate), sorted(live), purged))

    projections = {p.name: wallet_col(p) for p in
                   (ui.COPY_TRADES_CSV, ui.EXPECTED_COPY_FILLS_CSV, ui.LIVE_WALLET_METRICS_CSV)}
    check("PURGE_APP_PROJECTIONS_CLEARED",
          all(W not in v and K in v for v in projections.values()), "rows=%r" % (projections,))

    still_there = [p.name for p in (ui.APP_MODEL_STATE_JSON, ui.PORTFOLIO_HISTORY_FILE, ui.EQUITY_HISTORY_FILE)
                   if p.exists()]
    check("PURGE_DERIVED_CACHES_DELETED", not still_there, "still present=%r" % (still_there,))

    backup = Path(proof.get("backup_dir") or "")
    backed = sorted(x.name for x in backup.rglob("*") if x.is_file()) if backup.is_dir() else []
    check("PURGE_BACKUP_COPIES_KEPT",
          backup.is_dir() and "ui_state.json" in backed and "manual_wallets.txt" in backed,
          "backup=%s files=%r" % (backup, backed))

    # ---- engine side: byte-identical, wallet rows still present -------------------------
    after_audit = {name: digest(p) for name, p in engine_csvs.items()}
    check("PURGE_ENGINE_AUDIT_CSVS_UNTOUCHED",
          all(after_audit[n] == before[str(engine_csvs[n])] for n in engine_csvs)
          and all(W in wallet_col(engine_csvs[n]) and K in wallet_col(engine_csvs[n]) for n in engine_csvs),
          "before=%r after=%r rows=%r" % (before, after_audit,
                                          {n: wallet_col(p) for n, p in engine_csvs.items()}))

    check("PURGE_ENGINE_RAW_LEADER_FILLS_UNTOUCHED",
          digest(ui.RAW_FILLS_CSV) == before[str(ui.RAW_FILLS_CSV)]
          and W in wallet_col(ui.RAW_FILLS_CSV)
          and "raw_live_fills.csv" not in (proof.get("csv_rows_removed") or {}),
          "same=%s wallets=%r removed=%r" % (digest(ui.RAW_FILLS_CSV) == before[str(ui.RAW_FILLS_CSV)],
                                             wallet_col(ui.RAW_FILLS_CSV), proof.get("csv_rows_removed")))

    positions = json.loads(ui.MANUAL_POSITIONS_FILE.read_text(encoding="utf-8"))
    history = json.loads(ui.EXCHANGE_ACCOUNT_HISTORY_FILE.read_text(encoding="utf-8"))
    check("PURGE_POSITIONS_AND_EXCHANGE_HISTORY_KEPT",
          digest(ui.MANUAL_POSITIONS_FILE) == before[str(ui.MANUAL_POSITIONS_FILE)]
          and digest(ui.EXCHANGE_ACCOUNT_HISTORY_FILE) == before[str(ui.EXCHANGE_ACCOUNT_HISTORY_FILE)]
          and W in (positions.get("by_wallet") or {})
          and (positions["by_wallet"][W] or {}).get("BTC", {}).get("signed_size") == 0.01
          and any((row or {}).get("wallet") == W for row in history),
          "positions=%r history=%r" % (positions, history))

    snap = json.loads(snapshot.read_text(encoding="utf-8"))
    check("PURGE_ENGINE_SNAPSHOTS_KEPT",
          snapshot.exists() and digest(snapshot) == before[str(snapshot)]
          and W in (snap.get("wallets") or {}),
          "exists=%s same=%s" % (snapshot.exists(), digest(snapshot) == before[str(snapshot)]))

    note = str(proof.get("note") or "").lower()
    check("PURGE_RESULT_SAYS_HISTORY_KEPT",
          "history" in note and "position" in note and "kept" in note, "note=%r" % (proof.get("note"),))

    try:
        ui.purge_wallet_app_config(ui.USER_WALLET)
        guarded = False
    except ValueError as exc:
        guarded = str(exc) == "CANNOT_PURGE_USER_WALLET"
    check("PURGE_USER_WALLET_REFUSED", guarded, "user wallet was not refused")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    if failed:
        print("FAILED: " + ", ".join(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
