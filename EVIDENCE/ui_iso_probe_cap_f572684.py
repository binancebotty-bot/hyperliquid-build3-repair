"""DEFECT (a) probe — CAP-10 must be observable through /api/live-config.

Writes NOTHING to :8031. Starts an ISOLATED instance on :8032 from this worktree, pointed at
the COPY of the audit dir, POSTs /api/set-wallet-mode ON for 11 followed wallets, then reads
/api/live-config and counts wallets whose mode is LIVE.

Assertions (each of which can fail):
  A1  exactly 10 wallets report mode LIVE
  A2  the 11th wallet POSTed is NOT LIVE
  A3  the 11th POST response says demoted=true, the first 10 say demoted=false
  A4  (sanity, guards the '0 LIVE = vacuous pass' trap) the wallet gate holds 11 ON

Reproduce:
  PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright \
  C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe \
    EVIDENCE/ui_iso_probe_cap_f572684.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STAGE2 = REPO / "_archive" / "hl_stage2"
AUDIT = Path("C:/Users/wigmore/tmp/ui_iso_audit")
CONFIG = AUDIT / "live_config.json"
GATE = STAGE2 / "wallet_gate.json"
PORT = int(os.environ.get("ISO_PORT", "8032"))
BASE = f"http://127.0.0.1:{PORT}"
OUT = Path(os.environ.get("ISO_OUT", "C:/Users/wigmore/.hermes/cache/scratch/c7_t6_out2/probe_a"))
PYW311 = "C:/Users/wigmore/AppData/Local/Programs/Python/Python311/pythonw.exe"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return r.status, r.read()


def post(path: str, payload: dict):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


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


def reset_config_to_off():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    for _w, v in cfg.get("wallets", {}).items():
        if isinstance(v, dict):
            v["mode"] = "OFF"
            v["enabled"] = False
    cfg["archived_wallets"] = {}
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    result: dict = {"port": PORT, "audit_dir": str(AUDIT),
                    "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    reset_config_to_off()
    if GATE.exists():
        GATE.unlink()

    proc = start()
    rc = 1
    try:
        if not wait_ready():
            result["verdict"] = "FAIL"
            result["reason"] = "isolated server did not become ready"
            return rc

        cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
        wallets = list(cfg["wallets"].keys())
        chosen = wallets[:11]
        result["wallets_reset_to_off"] = len(wallets)
        result["wallets_posted_ON"] = chosen

        responses = []
        for w in chosen:
            st, body = post("/api/set-wallet-mode", {"wallet": w, "mode": "ON"})
            responses.append({"wallet": w, "status": st, **body})
        result["post_responses"] = responses

        st, raw = get("/api/live-config")
        (OUT / "live_config_after_11_on.json").write_bytes(raw)
        payload = json.loads(raw)
        live = sorted(w for w, v in payload["config"]["wallets"].items()
                      if isinstance(v, dict) and str(v.get("mode", "")).upper() == "LIVE")
        result["status_live_config"] = st
        result["live_count"] = len(live)
        result["live_wallets"] = live
        result["eleventh_wallet"] = chosen[10]
        result["eleventh_mode"] = payload["config"]["wallets"][chosen[10]].get("mode")
        result["eleventh_response"] = responses[-1]
        result["active_wallets"] = payload.get("active_wallets")
        result["max_wallets"] = payload.get("max_wallets")

        gate = json.loads(GATE.read_text()) if GATE.exists() else {}
        gate_on = sorted(w for w, v in gate.items()
                         if isinstance(v, dict) and str(v.get("mode", "")).upper() == "ON")
        result["wallet_gate_on_count"] = len(gate_on)
        (OUT / "wallet_gate_after.json").write_text(json.dumps(gate, indent=2))

        checks = {
            "A1_live_count_is_10": len(live) == 10,
            "A2_eleventh_not_live": str(payload["config"]["wallets"][chosen[10]].get("mode")).upper() != "LIVE",
            "A3_eleventh_demoted_flag": (responses[-1].get("demoted") is True
                                         and all(r.get("demoted") is False for r in responses[:10])),
            "A4_gate_held_11_on": len(gate_on) == 11,
        }
        result["checks"] = checks
        result["verdict"] = "PASS" if all(checks.values()) else "FAIL"
        print(json.dumps({"verdict": result["verdict"], "live_count": len(live),
                          "live_wallets": live, "eleventh_mode": result["eleventh_mode"],
                          "gate_on": len(gate_on), "checks": checks}, indent=2))
        rc = 0 if result["verdict"] == "PASS" else 1
        return rc
    finally:
        if proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/F"], capture_output=True)
        result["server_pid"] = proc.pid
        (OUT / "probe_a_result.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.exit(main())
