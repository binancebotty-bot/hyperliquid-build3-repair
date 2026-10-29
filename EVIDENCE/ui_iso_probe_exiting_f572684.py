"""DEFECT (b) probe - EXITING must exist and be visible on /live-copy.

Writes NOTHING to :8031. Starts an ISOLATED instance on :8032 from this worktree pointed at
the COPY of the audit dir, seeds two archived wallets (one holding a NON-FLAT manual
position, one FLAT), renders /live-copy in headless Chromium and asserts on the DOM.

Assertions (each of which can fail):
  B1  the archived wallet holding a non-flat position renders a row whose mode is EXITING
  B2  the flat archived wallet renders NO row at all (it left the followed set)
  B3  the non-flat archived row is not labelled Live / Close-only / Off

Reproduce:
  PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright \
  C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe \
    EVIDENCE/ui_iso_probe_exiting_f572684.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STAGE2 = REPO / "_archive" / "hl_stage2"
AUDIT = Path("C:/Users/wigmore/tmp/ui_iso_audit")
CONFIG = AUDIT / "live_config.json"
MPOS = AUDIT / "manual_live_positions.json"
PORT = int(os.environ.get("ISO_PORT", "8032"))
BASE = f"http://127.0.0.1:{PORT}"
OUT = Path(os.environ.get("ISO_OUT", "C:/Users/wigmore/.hermes/cache/scratch/c7_t6_out2/probe_b"))
PYW311 = "C:/Users/wigmore/AppData/Local/Programs/Python/Python311/pythonw.exe"

NONFLAT = "0xbbbb0000000000000000000000000000000000b1"
FLAT = "0xbbbb0000000000000000000000000000000000b2"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return r.status, r.read()


def wait_ready(timeout=90.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            st, _ = get("/api/state")
            if st == 200:
                return True
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(0.5)
    print("SERVER NOT READY", last)
    return False


def start():
    exe = PYW311 if Path(PYW311).exists() else sys.executable
    env = dict(os.environ)
    env["HL_LIVE_AUDIT_DIR"] = str(AUDIT)
    env["PYTHONPATH"] = str(STAGE2)
    env["PYTHONUNBUFFERED"] = "1"
    out_f = open(OUT / "iso_8032.stdout.log", "wb")
    err_f = open(OUT / "iso_8032.stderr.log", "wb")
    p = subprocess.Popen(
        [exe, "-m", "uvicorn", "HL_Copy_App_SSOT:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--no-access-log"],
        cwd=str(STAGE2), env=env, stdout=out_f, stderr=err_f, stdin=subprocess.DEVNULL,
        creationflags=0x08000000,
    )
    (OUT / "iso_8032.pid").write_text(str(p.pid))
    return p


def seed():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    cfg.setdefault("wallets", {})
    cfg["wallets"].pop(NONFLAT, None)
    cfg["wallets"].pop(FLAT, None)
    cfg["archived_wallets"] = {
        NONFLAT: {"copy_mode": "fixed", "fixed_notional": 25},
        FLAT: {"copy_mode": "fixed", "fixed_notional": 25},
    }
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    mpos = {
        "schema": "manual_live_positions.v2",
        "by_wallet": {
            NONFLAT: {"BTC": {"signed_size": 0.01, "avg_entry_px": 60000.0, "coin": "BTC"}},
            FLAT: {"ETH": {"signed_size": 0.0, "avg_entry_px": 3000.0, "coin": "ETH"}},
        },
    }
    MPOS.write_text(json.dumps(mpos, indent=2), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    result: dict = {"port": PORT, "audit_dir": str(AUDIT),
                    "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    seed()
    proc = start()
    rc = 1
    try:
        if not wait_ready():
            result["verdict"] = "FAIL"
            result["reason"] = "isolated server did not become ready"
            return rc
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1200})
            page.goto(BASE + "/live-copy", wait_until="networkidle", timeout=120000)
            page.wait_for_timeout(3000)
            rows = page.eval_on_selector_all(
                "tr.lc-wallet-row",
                "els => els.map(e => ({wallet: e.getAttribute('data-wallet'), cls: e.className,"
                " text: (e.querySelector('td')||{}).innerText || ''}))",
            )
            page.screenshot(path=str(OUT / "live_copy_exiting.png"), full_page=True)
            (OUT / "live_copy_exiting.dom.txt").write_text(page.content(), encoding="utf-8")
            browser.close()

        by_wallet = {str(r["wallet"]).lower(): r for r in rows}
        nf = by_wallet.get(NONFLAT)
        fl = by_wallet.get(FLAT)
        nf_text = str((nf or {}).get("text", ""))
        result.update({"row_count": len(rows), "nonflat_row": nf, "flat_row": fl})
        checks = {
            "B1_nonflat_archived_renders_EXITING": bool(nf) and "EXITING" in nf_text,
            "B2_flat_archived_has_no_row": fl is None,
            "B3_exiting_row_not_live_or_off": ("Live" not in nf_text
                                               and "Close-only" not in nf_text
                                               and "Off" not in nf_text),
        }
        result["checks"] = checks
        result["verdict"] = "PASS" if all(checks.values()) else "FAIL"
        print(json.dumps({"verdict": result["verdict"], "checks": checks,
                          "nonflat_row_text": nf_text, "row_count": len(rows),
                          "flat_row_present": fl is not None}, indent=2))
        rc = 0 if result["verdict"] == "PASS" else 1
        return rc
    finally:
        if proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/F"], capture_output=True)
        result["server_pid"] = proc.pid
        (OUT / "probe_b_result.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.exit(main())
