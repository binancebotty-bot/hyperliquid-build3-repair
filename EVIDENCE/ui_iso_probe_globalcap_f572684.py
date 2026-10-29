"""DEFECT (c) probe - applied global exposure cap must be VISIBLE on /live-copy.
Isolated :8032 + config COPY only; nothing is written to :8031.
C1 DOM contains 4242.42 / C2 #lcGlobalCap pill shows it / C3 cap=0 -> OFF, value gone.
"""
import json, os, subprocess, sys, time, urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STAGE2 = REPO / "_archive" / "hl_stage2"
AUDIT = Path("C:/Users/wigmore/tmp/ui_iso_audit")
CONFIG = AUDIT / "live_config.json"
PORT = int(os.environ.get("ISO_PORT", "8032"))
BASE = f"http://127.0.0.1:{PORT}"
OUT = Path(os.environ.get("ISO_OUT", "C:/Users/wigmore/.hermes/cache/scratch/c7_t6_out2/probe_c"))
PYW311 = "C:/Users/wigmore/AppData/Local/Programs/Python/Python311/pythonw.exe"
CAP = 4242.42


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return r.status, r.read()


def wait_ready(timeout=90.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if get("/api/state")[0] == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    print("SERVER NOT READY")
    return False


def start():
    exe = PYW311 if Path(PYW311).exists() else sys.executable
    env = dict(os.environ)
    env["HL_LIVE_AUDIT_DIR"] = str(AUDIT)
    env["PYTHONPATH"] = str(STAGE2)
    env["PYTHONUNBUFFERED"] = "1"
    out_f = open(OUT / "iso_8032.stdout.log", "wb")
    err_f = open(OUT / "iso_8032.stderr.log", "wb")
    p = subprocess.Popen([exe, "-m", "uvicorn", "HL_Copy_App_SSOT:app", "--host", "127.0.0.1",
                          "--port", str(PORT), "--no-access-log"],
                         cwd=str(STAGE2), env=env, stdout=out_f, stderr=err_f,
                         stdin=subprocess.DEVNULL, creationflags=0x08000000)
    (OUT / "iso_8032.pid").write_text(str(p.pid))
    return p


def write_cap(value):
    cfg = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    gc = cfg.get("global_controls")
    if not isinstance(gc, dict):
        gc = {}
    gc["max_total_live_exposure_usd"] = value
    cfg["global_controls"] = gc
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def render(page):
    page.goto(BASE + "/live-copy", wait_until="networkidle", timeout=120000)
    page.wait_for_timeout(3000)
    pill = page.eval_on_selector("#lcGlobalCap", "e => ({text: e.innerText, cls: e.className})")
    return pill, page.content()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = {"port": PORT, "cap_written": CAP,
              "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    write_cap(CAP)
    proc = start()
    rc = 1
    try:
        if not wait_ready():
            result["verdict"] = "FAIL"
            result["reason"] = "server not ready"
            return rc
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1600, "height": 1200})
            pill_on, dom_on = render(page)
            page.screenshot(path=str(OUT / "live_copy_globalcap.png"), full_page=True)
            (OUT / "live_copy_globalcap.dom.txt").write_text(dom_on, encoding="utf-8")
            write_cap(0.0)
            pill_off, dom_off = render(page)
            page.screenshot(path=str(OUT / "live_copy_globalcap_off.png"), full_page=True)
            (OUT / "live_copy_globalcap_off.dom.txt").write_text(dom_off, encoding="utf-8")
            browser.close()
        result.update({"pill_on": pill_on, "pill_off": pill_off})
        def _has_cap(s):
            return "4242.42" in s or "4,242.42" in s

        checks = {
            "C1_dom_contains_applied_value": _has_cap(dom_on),
            "C2_header_pill_shows_value": _has_cap(str(pill_on.get("text", ""))),
            "C3_zero_cap_renders_off_and_drops_value": ("OFF" in str(pill_off.get("text", "")).upper() and not _has_cap(dom_off)),
        }
        result["checks"] = checks
        result["verdict"] = "PASS" if all(checks.values()) else "FAIL"
        print(json.dumps({"verdict": result["verdict"], "checks": checks,
                          "pill_on": pill_on, "pill_off": pill_off}, indent=2))
        rc = 0 if result["verdict"] == "PASS" else 1
        return rc
    finally:
        if proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/F"], capture_output=True)
        result["server_pid"] = proc.pid
        (OUT / "probe_c_result.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.exit(main())
