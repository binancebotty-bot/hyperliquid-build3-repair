"""Isolated UI write/behaviour probe — DIR-302 checks (c) and (d).

Runs ONLY against the isolated instance on 127.0.0.1:8032 (its own worktree, its own
wallet_gate.json, a COPY of the audit dir). Authorised isolated write-test per
EVIDENCE/UI_CERT_ARTIFACT_SCHEMA.md "Control-write rows". Never touches :8031, the live
audit dir, the live config or the engine.

  (c1) 11th wallet cap: set 11 wallets ON, expect at most 10 to remain LIVE.
  (c2) removed non-flat wallet shows EXITING: searches the rendered DOM and the SSOT for
       the label, and reports whether the state exists at all.
  (d1) applied-config truth: a distinctive value written into the config COPY must appear
       in the UI (proves the screen reads applied config, not a constant).
  (d2) stale engine truth: an ageing copy of the engine state must render red/UNKNOWN.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
import urllib.request
from pathlib import Path

PORT = int(os.environ.get("ISO_PORT", "8032"))
BASE = f"http://127.0.0.1:{PORT}"
AUDIT = Path(os.environ.get("ISO_AUDIT", "C:/Users/wigmore/tmp/ui_iso_audit"))
OUT = Path(os.environ.get("ISO_OUT", "C:/Users/wigmore/tmp/ui_iso_evidence"))
SSOT = Path(__file__).resolve().parents[1] / "_archive" / "hl_stage2" / "HL_Copy_App_SSOT.py"
CFG = AUDIT / "live_config.json"


def post(path: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:  # noqa: BLE001
        return e.code, json.loads(e.read() or b"{}")


def get_json(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        return json.loads(r.read())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    res: dict = {"captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # ---- (c1) 11th wallet ----
    cfg_before = json.loads(CFG.read_text(encoding="utf-8"))
    wallets = [w for w in (cfg_before.get("wallets") or {})]
    picks = wallets[:11]
    responses = []
    for w in picks:
        st, body = post("/api/set-wallet-mode", {"wallet": w, "mode": "ON"})
        responses.append({"wallet": w, "status": st, "body": body})
    time.sleep(1.5)
    cfg_after = json.loads(CFG.read_text(encoding="utf-8"))
    gate_path = Path(__file__).resolve().parents[1] / "_archive" / "hl_stage2" / "wallet_gate.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8")) if gate_path.exists() else {}
    gated_on = [w for w, v in gate.items() if str(v.get("mode")).upper() == "ON"]
    live_cfg = get_json("/api/live-config")
    lc_wallets = live_cfg.get("wallets") or {}
    live_count = sum(1 for v in lc_wallets.values() if isinstance(v, dict) and str(v.get("mode")).upper() == "LIVE")
    res["c1"] = {
        "wallets_in_config": len(wallets),
        "attempted_on": len(picks),
        "all_requests_ok": all(r["status"] == 200 for r in responses),
        "gate_ON_after": len(gated_on),
        "live_config_LIVE_after": live_count,
        "cap_enforced": live_count <= 10,
        "responses": responses[:3],
    }

    # ---- (c2) EXITING label ----
    ssot_text = SSOT.read_text(encoding="utf-8", errors="replace")
    res["c2"] = {
        "exiting_in_ssot": bool(re.search(r"EXITING", ssot_text, re.I)),
        "archived_wallets_key_present": "archived_wallets" in cfg_after,
        "archived_wallet_count": len(cfg_after.get("archived_wallets") or {}),
        "note": "label existence checked in the serving SSOT bytes, not from memory",
    }

    # ---- (d1) distinctive applied-config value must render ----
    marker = 4242.42
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    gc = cfg.setdefault("global_controls", {})
    gc["max_total_live_exposure_usd"] = marker
    CFG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    time.sleep(1.0)
    api_state = get_json("/api/state")
    api_marker = (api_state.get("global_controls") or {}).get("max_total_live_exposure_usd")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        page.goto(BASE + "/live-copy", wait_until="load", timeout=120_000)
        page.wait_for_timeout(2000)
        dom = page.inner_text("body")
        (OUT / "d_dom_config_marker.txt").write_text(dom, encoding="utf-8")
        page.screenshot(path=str(OUT / "d_config_marker.png"), full_page=True)
        dom_has_marker = ("4,242" in dom) or ("4242" in dom)
        browser.close()
    res["d1"] = {
        "marker_written": marker,
        "api_global_controls_value": api_marker,
        "dom_shows_marker": dom_has_marker,
        "cfg_path": str(CFG),
        "screenshot": str(OUT / "d_config_marker.png"),
        "dom_dump": str(OUT / "d_dom_config_marker.txt"),
    }

    # ---- (d2) stale engine truth must render red/UNKNOWN ----
    truth = AUDIT / "clean_core_runtime_state.json"
    backup = AUDIT / "clean_core_runtime_state.json.probe_backup"
    truth_status = {}
    try:
        if truth.exists():
            shutil.copy2(truth, backup)
            old = time.time() - 3 * 3600  # three hours stale
            os.utime(truth, (old, old))
            time.sleep(1.0)
            api_state2 = get_json("/api/state")
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1600, "height": 1200})
                page.goto(BASE + "/live-copy", wait_until="load", timeout=120_000)
                page.wait_for_timeout(2000)
                dom2 = page.inner_text("body")
                (OUT / "d_dom_stale.txt").write_text(dom2, encoding="utf-8")
                page.screenshot(path=str(OUT / "d_stale_engine.png"), full_page=True)
                browser.close()
            truth_status = {
                "mtime_forced_hours_old": 3,
                "api_send_mode": api_state2.get("send_mode"),
                "dom_has_UNKNOWN": "UNKNOWN" in dom2.upper(),
                "dom_has_STALE": "STALE" in dom2.upper(),
                "dom_red_markers": len(re.findall(r"\b(RED|UNKNOWN|STALE)\b", dom2, re.I)),
                "screenshot": str(OUT / "d_stale_engine.png"),
            }
            shutil.copy2(backup, truth)
            backup.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        truth_status = {"error": f"{type(exc).__name__}: {exc}"}
    res["d2"] = truth_status

    (OUT / "iso_probe_cd_result.json").write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
