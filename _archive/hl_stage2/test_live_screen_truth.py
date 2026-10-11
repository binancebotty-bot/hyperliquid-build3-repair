#!/usr/bin/env python3
"""The 13 May live screen ("Live Copy Command Centre", /live-copy) wired to the Core engine.

L1 the screen is the home page and carries the engine's Global Controls (daily loss, slippage, networks).
L2 Portfolio Value is the follower's whole-account value from the follower exchange, labelled by network.
L3 REAL ORDERS shows the engine's master switch, not whether a fill has happened yet.
L4 no fix-diff action on the screen (Boss reconciles on the exchange); diffs are still reported.
L5 the screen never overwrites the engine's own exchange snapshot file.
L6 follower reads go to the follower network; nothing imports or calls the walletproof engine.

Run: python test_live_screen_truth.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="livescreen_"))
    env_file = tmp / "stage2.env"
    env_file.write_text(f"HL_LIVE_HL_ACCOUNT_ADDRESS={FOLLOWER}\n", encoding="utf-8")
    for k in ("HL_LIVE_HL_ACCOUNT_ADDRESS", "HL_USER_WALLET", "HL_FOLLOWER_DEXES"):
        os.environ.pop(k, None)
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(env_file)})

    def offline(*a, **k):
        raise OSError("offline test: no network")
    urllib.request.urlopen = offline
    import HL_Live_Copy_Service_Core as c
    import HL_Copy_App_SSOT as ui
    from fastapi.testclient import TestClient
    ui.LIVE_COPY_CONFIG_FILE = c.LIVE_CONFIG_FILE
    client = TestClient(ui.app)
    src = (HERE / "HL_Copy_App_SSOT.py").read_text(encoding="utf-8-sig")

    # ---- L1 ------------------------------------------------------------------------------------
    r = client.get("/", follow_redirects=False)
    check("L1_HOME_OPENS_THE_LIVE_SCREEN", r.status_code in (302, 307) and r.headers.get("location") == "/live-copy",
          f"{r.status_code} {r.headers.get('location')}")
    page = client.get("/live-copy").text
    check("L1_LIVE_SCREEN_RENDERS", "Live Copy Command Centre" in page)
    check("L1_GLOBAL_CONTROLS_ON_SCREEN", all(f'id="{i}"' in page for i in
          ("gcMaxDailyLoss", "gcMktPct", "gcMaxOrder", "gcMaxTotal", "gcMaxDir", "gcNetworks")))
    gc = client.get("/api/global-controls").json()
    check("L1_DEFAULT_SLIPPAGE_IS_0_2_PCT", abs(float(gc["global_controls"]["marketable_slippage_pct"]) - 0.2) < 1e-9, str(gc))
    check("L1_NETWORKS_SHOWN", gc["networks"]["leader"] == "mainnet" and gc["networks"]["follower"] == "testnet", str(gc["networks"]))
    r = client.post("/api/global-controls", json={"max_daily_loss_usd": 25, "marketable_slippage_pct": 0.2})
    check("L1_SAVED_CONTROLS_REACH_ENGINE", r.status_code == 200 and c.ConfigManager().max_daily_loss() == 25.0
          and abs(c.ConfigManager().marketable_bps() - 20.0) < 1e-9, r.text[:200])

    # ---- L2 / L3 -------------------------------------------------------------------------------
    ui.ACCOUNT_VALUE_FETCHER = lambda payload: [["day", {"accountValueHistory": [[0, "1450.0"], [1, "1450.12"]],
                                                         "pnlHistory": [[0, "0"], [1, "0"]]}]]
    ui._ACCOUNT_VALUE_CACHE.clear()
    cfg = c.load_json(c.LIVE_CONFIG_FILE, {})
    cfg.update({"auto_send_enabled": True, "wallets": {"0x" + "d" * 40: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed"}}})
    c.atomic_write_json(c.LIVE_CONFIG_FILE, cfg)
    summary = client.get("/api/live-audit-summary").json()
    fa = summary.get("follower_account") or {}
    check("L2_SUMMARY_HAS_WHOLE_ACCOUNT_VALUE", fa.get("ok") and abs(fa.get("value", 0) - 1450.12) < 1e-9
          and summary.get("follower_network") == "testnet", str(fa))
    check("L2_CARD_USES_IT", "const fa=lcAudit.follower_account||{}" in page and "Portfolio Value ('+String(lcAudit.follower_network" in page)
    check("L3_MASTER_SWITCH_REPORTED", summary.get("master_real_orders_enabled") is True, str(summary.get("master_real_orders_enabled")))
    check("L3_PILL_FOLLOWS_MASTER_SWITCH", "const armed=lcAudit.master_real_orders_enabled===true" in page
          and "APP DISABLED" not in page)

    # ---- L4 ------------------------------------------------------------------------------------
    r = client.post("/api/manual-reconciliation/archive-ledger-row", json={"coin": "BTC"})
    check("L4_FIX_DIFF_ENDPOINT_REMOVED", r.status_code in (404, 405), str(r.status_code))
    check("L4_NO_FIX_DIFF_CONTROL_ON_SCREEN", "archive-ledger-row" not in page and "data-recon-act" not in page)
    check("L4_DIFFS_STILL_REPORTED", all(x in page for x in ("Lead↔Copy Diff", "lcReconCriticalRows", "lcReconWarningRows",
                                                             "lcReconRows", "lcOrphanPositionRows")))

    # ---- L5 ------------------------------------------------------------------------------------
    check("L5_SCREEN_SNAPSHOT_IS_ITS_OWN_FILE", ui.EXCHANGE_ACCOUNT_SNAPSHOT_FILE.name == "exchange_account_snapshot_app.json"
          and ui.EXCHANGE_ACCOUNT_SNAPSHOT_FILE != c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE
          and ui.EXCHANGE_ACCOUNT_SNAPSHOT_FILE == c.EXCHANGE_ACCOUNT_SNAPSHOT_APP_FILE, str(ui.EXCHANGE_ACCOUNT_SNAPSHOT_FILE))
    check("L5_ENGINE_SNAPSHOT_UNTOUCHED_BY_SCREEN", not c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE.exists())

    # ---- L6 ------------------------------------------------------------------------------------
    check("L6_NO_HARDCODED_MAINNET_READS", "api.hyperliquid.xyz" not in src)
    check("L6_FOLLOWER_READS_USE_FOLLOWER_NETWORK", src.count("FOLLOWER_INFO_URL,") >= 3 and ui.FOLLOWER_INFO_URL.endswith("hyperliquid-testnet.xyz/info"))
    imports = "\n".join(l for l in src.splitlines() if re.match(r"\s*(import|from)\s", l))
    check("L6_NO_WALLETPROOF_ENGINE", not re.search(r"walletproof|wallet_proof|WALLET FINDER|wallet_finder", src, re.I)
          and "HL_Live_Copy_Service" not in imports, imports[:300])

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
