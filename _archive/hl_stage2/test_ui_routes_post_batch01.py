#!/usr/bin/env python3
"""UI-ROUTE write path, batch 01: six POST routes invoked with a real payload, persisted state read back.

Gap this closes: the UI-ROUTE artefact (certification/results/UI_ROUTE_TRUTH_t_cfcad924.json) passed every
route on "HTTP 200 and body carries marker" and its own probe_method says "POST routes never invoked". A 200
is not a write. Each check below therefore does two things: it posts the route the way the page's own control
posts it, and then it re-reads the state from the file the engine reads (and through the app's own GET route)
to prove the change landed. A wrong form field name no-ops silently and still returns 200 - only the second
leg catches that.

Rows (DISPOSITION_2026-11-18.csv, bucket B, CSV order). UI-ROUTE-01..08 and 11/14/15 name GET-only endpoints
(/ , /model, /legacy-model, /api/model-cache-status, /api/state, /api/metrics, /api/trades, /api/equity,
/wallet-meta/{wallet}, /wallet/{wallet}, /api/ui-state), which cannot be posted in-process, so per the batch
rule they are skipped and the next rows are taken:
  UI-ROUTE-09  POST /api/wallet-include          wallet, included
  UI-ROUTE-10  POST /api/wallet-config           wallet, copy_mode, norm_base, fixed_notional
  UI-ROUTE-12  POST /api/wallet-meta             wallet, tag, note, color
  UI-ROUTE-13  POST /api/admin/purge-wallet      wallet
  UI-ROUTE-16  POST /api/ui-state                norm_base, copy_mode, fixed_notional, ranking_column,
                                                 ranking_direction
  UI-ROUTE-17  POST /api/norm                    norm_base   (this route parses a JSON body, not a form)

Isolation: every path the routes write is repointed into a temp dir, network is refused, follower stays
testnet, no order path is touched. Run: RESULT:: markers, TOTAL/FAILED, exit 0/1.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
A = "0x" + "a" * 40  # UI-ROUTE-09/10/12 wallet
P = "0x" + "b" * 40  # UI-ROUTE-13 wallet (purged)


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + str(detail)[:300]) if detail and not ok else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="uiroutes_", dir=os.environ.get("TMPDIR") or None))

    def offline(*a, **k):
        raise OSError("offline test: no network")
    urllib.request.urlopen = offline
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp / "audit"), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet"})
    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient

    # --- keep every write inside the temp dir; the repo/engine tree is never touched ---------------
    data = tmp / "hl_copy_output"
    ui.DATA_DIR = data
    ui.LIVE_COPY_AUDIT_DIR = tmp / "audit"
    ui.UI_STATE_FILE = tmp / "ui_state.json"
    ui.WALLET_GATE_FILE = tmp / "wallet_gate.json"
    ui.MANUAL_WALLETS_FILE = tmp / "manual_wallets.txt"
    ui.PURGED_WALLETS_FILE = tmp / "purged_wallets.txt"
    ui.RAW_FILLS_CSV = data / "raw_live_fills.csv"
    ui.EXPECTED_COPY_FILLS_CSV = data / "expected_copy_fills.csv"
    ui.COPY_TRADES_CSV = data / "copy_trades.csv"
    ui.LIVE_WALLET_METRICS_CSV = data / "live_wallet_metrics.csv"
    ui.EXCHANGE_BASELINES_JSON = data / "exchange_baselines.json"
    ui.ENGINE_TRUTH_JSON = data / "engine_truth.json"
    ui.LEGACY_LIVE_STATE_JSON = data / "live_state.json"
    ui.APP_MODEL_STATE_JSON = data / "app_model_state.json"
    ui.PORTFOLIO_HISTORY_FILE = data / "portfolio_history.json"
    ui.EQUITY_HISTORY_FILE = data / "equity_history.json"
    ui.LIVE_COPY_CONFIG_FILE = ui.LIVE_COPY_AUDIT_DIR / "live_config.json"
    ui.LIVE_CONFIG_FILE = ui.LIVE_COPY_CONFIG_FILE
    assert ui.FOLLOWER_NETWORK == "testnet", ui.FOLLOWER_NETWORK

    agent = TestClient(ui.app)

    def stored() -> dict:
        """The state file as the engine/app reads it off disk - not the in-memory copy a 200 came with."""
        path = ui.UI_STATE_FILE
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    # ---- UI-ROUTE-09 -----------------------------------------------------------------------------
    r = agent.post("/api/wallet-include", data={"wallet": A, "included": "0"})
    shape = r.status_code == 200 and 'url=/' in r.text
    disk = stored().get("wallet_include", {}).get(A)
    served = agent.get("/api/ui-state").json().get("wallet_include", {}).get(A)
    check("UI_ROUTE_09_WALLET_INCLUDE_PERSISTS", shape and disk is False and served is False,
          f"shape_ok={shape} disk={disk!r} served={served!r} ui_state={ui.UI_STATE_FILE}")

    # ---- UI-ROUTE-10 -----------------------------------------------------------------------------
    r = agent.post("/api/wallet-config",
                   data={"wallet": A, "copy_mode": "fixed", "norm_base": "300", "fixed_notional": "42.5"})
    shape = r.status_code == 200 and 'url=/' in r.text
    cfg = stored().get("wallet_config", {}).get(A) or {}
    served = agent.get("/api/ui-state").json().get("wallet_config", {}).get(A) or {}
    check("UI_ROUTE_10_WALLET_CONFIG_PERSISTS",
          shape and cfg.get("copy_mode") == "fixed" and cfg.get("norm_base") == 300.0
          and cfg.get("fixed_notional") == 42.5 and served == cfg,
          f"shape_ok={shape} disk={cfg!r} served={served!r}")

    # ---- UI-ROUTE-12 -----------------------------------------------------------------------------
    NOTE = "batch01 meta note"
    r = agent.post("/api/wallet-meta", data={"wallet": A, "tag": "watch", "note": NOTE, "color": "blue"})
    shape = r.status_code == 200 and f"/wallet-meta/{A}?saved=1" in r.text
    disk = stored().get("wallet_meta", {}).get(A) or {}
    page = agent.get(f"/wallet-meta/{A}").text
    check("UI_ROUTE_12_WALLET_META_PERSISTS_AND_RENDERS",
          shape and disk == {"tag": "watch", "note": NOTE, "color": "blue"}
          and NOTE in page and 'value="watch" selected' in page and 'value="blue" selected' in page,
          f"shape_ok={shape} disk={disk!r} page_has_note={NOTE in page}")

    # ---- UI-ROUTE-13 -----------------------------------------------------------------------------
    agent.post("/api/wallet-include", data={"wallet": P, "included": "1"})
    agent.post("/api/wallet-config", data={"wallet": P, "copy_mode": "fixed", "fixed_notional": "11"})
    ui_state = stored()
    ui_state["wallet_meta"] = ui.set_wallet_meta(ui_state, P, "purge-me", "metadata must be purged", "blue")
    ui.atomic_write_json(ui.UI_STATE_FILE, ui_state)
    seeded = (stored().get("wallet_include", {}).get(P) is True
              and P in stored().get("wallet_config", {})
              and P in stored().get("wallet_meta", {}))
    r = agent.post("/api/admin/purge-wallet", data={"wallet": P}, headers={"X-Requested-With": "fetch"})
    proof = r.json() if r.status_code == 200 else {}
    after = stored()
    tombstone = (ui.PURGED_WALLETS_FILE.read_text(encoding="utf-8").split() if ui.PURGED_WALLETS_FILE.exists() else [])
    purged = ui.load_purged_wallets()
    served = agent.get("/api/ui-state").json()
    guard = agent.post("/api/admin/purge-wallet", data={"wallet": ui.USER_WALLET},
                       headers={"X-Requested-With": "fetch"})
    guard_held = guard.status_code == 400 and not ui.is_purged(ui.USER_WALLET, purged)
    check("UI_ROUTE_13_PURGE_WALLET_PERSISTS",
          seeded and r.status_code == 200 and proof.get("ok") is True
          and proof.get("json_removed", {}).get("ui_state.json") == 3
          and P not in (after.get("wallet_config") or {}) and P not in (after.get("wallet_include") or {})
          and P not in (after.get("wallet_meta") or {})
          and P not in tombstone and ui.is_purged(P, purged)
          and P not in (served.get("wallet_config") or {}) and guard_held,
          f"seeded={seeded} status={r.status_code} proof_json_removed={proof.get('json_removed')} "
          f"wallet_meta={after.get('wallet_meta')} tombstone={tombstone} guard_held={guard_held}")

    # ---- UI-ROUTE-16 -----------------------------------------------------------------------------
    r = agent.post("/api/ui-state", data={"norm_base": "250", "copy_mode": "fixed", "fixed_notional": "7.5",
                                          "ranking_column": "pnl", "ranking_direction": "asc"})
    shape = r.status_code == 200 and 'url=/' in r.text
    disk = stored()
    served = agent.get("/api/ui-state").json()
    want = (250.0, "fixed", 7.5, {"column": "pnl", "direction": "asc"})

    def got(s):
        # the form path stores fixed_notional as typed ("7.5"); the engine reads it through fnum, so compare
        # the effective number, not the serialisation. Silent no-op would leave the 100.0 default here.
        return (s.get("norm_base"), s.get("copy_mode"), float(s.get("fixed_notional") or 0), s.get("ranking"))

    check("UI_ROUTE_16_UI_STATE_FORM_PERSISTS", shape and got(disk) == want and got(served) == want,
          f"shape_ok={shape} disk={got(disk)!r} served={got(served)!r}")

    # ---- UI-ROUTE-17 -----------------------------------------------------------------------------
    r = agent.post("/api/norm", json={"norm_base": 123.0})
    shape = r.status_code == 200 and r.json().get("ok") is True
    disk = stored().get("norm_base")
    served = agent.get("/api/ui-state").json().get("norm_base")
    check("UI_ROUTE_17_NORM_JSON_PERSISTS", shape and disk == 123.0 and served == 123.0,
          f"shape={shape} status={r.status_code} disk={disk!r} served={served!r}")

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    if failed:
        print("FAILED: " + ", ".join(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
