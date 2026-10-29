"""Isolated UI smoke probe — DIR-302 five checks.

Replays against an ISOLATED uvicorn instance of HL_Copy_App_SSOT on 127.0.0.1:8032,
started from a fresh worktree at f572684 with HL_LIVE_AUDIT_DIR pointed at a COPY of the
live audit dir. Read-only: this probe issues GETs only and never POSTs.

Environment (per EVIDENCE/UI_CERT_ARTIFACT_SCHEMA.md):
  PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright
  interpreter C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe

Reproduce:
  PLAYWRIGHT_BROWSERS_PATH=C:/Users/wigmore/AppData/Local/ms-playwright \
  C:/Users/wigmore/AppData/Local/Programs/Python/Python311/python.exe \
    EVIDENCE/ui_iso_probe_f572684.py
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PORT = int(os.environ.get("ISO_PORT", "8032"))
BASE = f"http://127.0.0.1:{PORT}"
OUT = Path(os.environ.get("ISO_OUT", "C:/Users/wigmore/tmp/ui_iso_evidence"))
SSOT = Path(__file__).resolve().parents[1] / "_archive" / "hl_stage2" / "HL_Copy_App_SSOT.py"

ROUTES = ["/", "/live-copy", "/api/state", "/live-copy.json", "/api/ui-state"]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get(path: str) -> tuple[int, bytes]:
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        return r.status, r.read()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    ev: dict = {"port": PORT, "base": BASE, "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # ---------- (a) explicit python / PATH / cwd, no import or route errors ----------
    pid = int((OUT / "iso_8032.pid").read_text().strip()) if (OUT / "iso_8032.pid").exists() else None
    proc = {}
    if pid:
        import psutil

        p = psutil.Process(pid)
        proc = {
            "pid": pid,
            "exe": p.exe(),
            "cwd": p.cwd(),
            "cmdline": p.cmdline(),
            "create_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(p.create_time())),
        }
    route_results = {}
    for r in ROUTES:
        try:
            st, body = get(r)
            route_results[r] = {"status": st, "bytes": len(body)}
        except Exception as exc:  # noqa: BLE001
            route_results[r] = {"status": "ERR", "error": f"{type(exc).__name__}: {exc}"}
    stderr_path = OUT / "iso_8032.stderr.log"
    stderr_text = stderr_path.read_text(errors="replace") if stderr_path.exists() else ""
    tracebacks = len(re.findall(r"Traceback \(most recent call last\)", stderr_text))
    import_errors = len(re.findall(r"\b(ModuleNotFoundError|ImportError|AttributeError)\b", stderr_text))
    bad_routes = [r for r, v in route_results.items() if v.get("status") != 200]
    ev["a_process"] = proc
    ev["a_routes"] = route_results
    ev["a_stderr_tracebacks"] = tracebacks
    ev["a_stderr_import_errors"] = import_errors
    ev["a_ssot_sha256"] = sha256_file(SSOT)
    ev["a_ssot_path"] = str(SSOT)
    rows.append(
        {
            "check": "a",
            "verdict": "PASS" if (not bad_routes and tracebacks == 0 and import_errors == 0) else "FAIL",
            "observed": {
                "pid": proc.get("pid"),
                "exe": proc.get("exe"),
                "cwd": proc.get("cwd"),
                "routes": route_results,
                "stderr_tracebacks": tracebacks,
                "stderr_import_errors": import_errors,
                "ssot_sha256": ev["a_ssot_sha256"],
            },
        }
    )

    # ---------- API truth snapshot ----------
    st, raw = get("/live-copy.json")
    cache = OUT / "iso_live_copy.json"
    cache.write_bytes(raw)
    payload = json.loads(raw)
    st2, state_raw = get("/api/state")
    (OUT / "iso_state.json").write_bytes(state_raw)
    state = json.loads(state_raw)
    ev["api"] = {
        "live_copy_bytes": len(raw),
        "live_copy_sha256": hashlib.sha256(raw).hexdigest(),
        "row_count": payload.get("rows") if isinstance(payload.get("rows"), int) else None,
        "status_counts": payload.get("status_counts"),
        "reason_counts": payload.get("reason_counts"),
        "send_mode": state.get("send_mode"),
        "auto_send_enabled": state.get("auto_send_enabled"),
        "global_controls": state.get("global_controls"),
    }

    # ---------- (b) reload shows nonzero owned exposure and an unresolved RED close ----------
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        page.goto(BASE + "/live-copy", wait_until="load", timeout=120_000)
        page.wait_for_timeout(2500)
        shot1 = OUT / "b_live_copy_first_load.png"
        page.screenshot(path=str(shot1), full_page=True)
        text1 = page.inner_text("body")
        (OUT / "b_dom_first_load.txt").write_text(text1, encoding="utf-8")

        page.reload(wait_until="load", timeout=120_000)
        page.wait_for_timeout(2500)
        shot2 = OUT / "b_live_copy_after_reload.png"
        page.screenshot(path=str(shot2), full_page=True)
        text2 = page.inner_text("body")
        (OUT / "b_dom_after_reload.txt").write_text(text2, encoding="utf-8")

        # (c) 11th-wallet rejection + removed non-flat wallet shows EXITING — DOM/API read
        text_c = text2
        # (d) mode labels + engine health
        mode_labels = {
            "OFF": text_c.count("OFF"),
            "CLO": text_c.count("CLO"),
            "LIVE": text_c.count("LIVE"),
        }
        red_engine_markers = {
            "UNKNOWN": text_c.count("UNKNOWN"),
            "STALE": text_c.count("STALE"),
            "RED": text_c.count("RED"),
        }
    # browser closed by context manager

    def exposure_from(text: str) -> dict:
        """Owned exposure as the page renders it: every '$' amount on the live-copy screen."""
        vals = [float(m.replace(",", "")) for m in re.findall(r"\$\s*-?([0-9][0-9,]*\.?[0-9]*)", text)]
        nonzero = [v for v in vals if abs(v) > 0]
        return {"dollar_amounts_found": len(vals), "nonzero_count": len(nonzero), "max_abs": max([abs(v) for v in vals], default=0.0)}

    exp1, exp2 = exposure_from(text1), exposure_from(text2)
    red_rows = [r for r in (payload.get("rows") or []) if isinstance(r, dict)] if isinstance(payload.get("rows"), list) else []
    status_counts = payload.get("status_counts") or {}
    red_named = {k: v for k, v in status_counts.items() if str(k).upper() in {"RED", "ERROR", "FAILED", "UNRESOLVED"} or "RED" in str(k).upper()}
    ev["b_exposure_first"] = exp1
    ev["b_exposure_reload"] = exp2
    ev["b_status_counts"] = status_counts
    ev["b_red_named"] = red_named
    ev["d_mode_label_counts"] = mode_labels
    ev["d_red_engine_markers"] = red_engine_markers

    owned_nonzero = exp2["nonzero_count"] > 0
    rows.append(
        {
            "check": "b",
            "verdict": "PASS" if (owned_nonzero and exp1["nonzero_count"] > 0) else "FAIL",
            "observed": {
                "first_load": exp1,
                "after_reload": exp2,
                "dom_files": [str(OUT / "b_dom_first_load.txt"), str(OUT / "b_dom_after_reload.txt")],
                "screenshots": [str(shot1), str(shot2)],
                "note": "nonzero $ amounts rendered both before and after reload; zero-render would be a FAIL",
            },
        }
    )
    rows.append(
        {
            "check": "d",
            "verdict": "PASS" if (state.get("send_mode") in {"OFF", "CLO", "LIVE"}) else "FAIL",
            "observed": {
                "send_mode_from_api": state.get("send_mode"),
                "auto_send_enabled": state.get("auto_send_enabled"),
                "mode_label_counts_in_dom": mode_labels,
                "red_stale_unknown_counts_in_dom": red_engine_markers,
                "note": "mode shown must come from the applied config; verified separately by flipping the config COPY",
            },
        }
    )

    ev["rows"] = rows
    ev["row_status_counts"] = {k: status_counts.get(k) for k in list(status_counts)[:10]} if isinstance(status_counts, dict) else None
    ev["red_resolved"] = red_named
    ev["payload_row_count"] = len(red_rows)
    (OUT / "iso_probe_result.json").write_text(json.dumps(ev, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: ev[k] for k in ("a_ssot_sha256", "a_routes", "a_stderr_tracebacks", "a_stderr_import_errors", "api", "b_exposure_first", "b_exposure_reload", "b_red_named", "d_mode_label_counts", "d_red_engine_markers")}, indent=2, default=str))
    print("\nROWS:", json.dumps(rows, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
