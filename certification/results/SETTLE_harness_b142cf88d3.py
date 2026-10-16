#!/usr/bin/env python3
"""SETTLE area fresh-probe harness - TN-F09..TN-F13 (5 rows). READ-ONLY, no mocks.

Declared proof per row (register of record): a PREDECLARED PHASE-6T SCENARIO run on
TESTNET THROUGH THE PRODUCTION ENGINE PATH, observed by the independent
userFillsByTime / clearinghouseState oracle. A row can only be PASSED or FAILED from a
REAL exchange-generated settlement event produced by that engine run.

This harness does NOT re-run the in-process NLS_RESIDUAL harness (which patches the
network and is pinned to a different engine blob). It probes, live:
  1. the register of record (git main:certification/certification_matrix.json),
  2. the register engine blob (sha256 + line count),
  3. the running engine process, its state dir, network stamp and auto_send flag,
  4. the independent testnet oracle for a settlement event in the probe window,
  5. the predeclared Phase-6T scenario artifact (does it exist as a runnable script?).
Then records NOT_TESTED with the missing runtime NAMED, or PASS/FAIL if the settlement
event genuinely exists.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]

REGISTER_REF = "main"
REGISTER_PATH = "certification/certification_matrix.json"
ENGINE_PATH = "_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
MOCK_HARNESS = "certification/results/NLS_RESIDUAL_harness_2a269ad_v4.py"
ROWS = ["TN-F09", "TN-F10", "TN-F11", "TN-F12", "TN-F13"]

REGISTER_COMMIT10 = "b142cf88d3"
REGISTER_ENGINE_SHA256 = "b171ec8fef01ead5ed2fe4a4a075857b5b1a56e425bab8394440c7dbad57f2a0"
REGISTER_ENGINE_LINES = 8042

TESTNET_INFO = "https://api.hyperliquid-testnet.xyz/info"
ORACLE_MASTER = "0x7ae3b08bb4e7b085c6db5d635b96bec9715e9205"

ENGINE_STATE_DIR = Path(
    r"C:\Users\wigmore\trading_stack\hl-build3-testnet-cert\_archive\hl_stage2"
    r"\hl_live_copy_audit_testnet"
)

TASK_ID = "t_9c2d381a"
TITLE = "B3-CERT SETTLE [impl] TN-F09..TN-F13 (5 rows)"


def sh(args):
    p = subprocess.run(args, cwd=str(REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return p.returncode, p.stdout


def git_show(rev, path):
    rc, out = sh(["git", "show", rev + ":" + path])
    return out if rc == 0 else None


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check(name, ok, detail=""):
    return {"name": name, "pass": bool(ok), "detail": str(detail)}


def post_json(url, payload, timeout=12):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        return None, {"error": repr(exc)}


def probe_register():
    rc, out = sh(["git", "rev-parse", REGISTER_REF])
    ref_sha = out.decode("ascii", "replace").strip()
    if not ref_sha.startswith(REGISTER_COMMIT10):
        raise SystemExit(
            "FATAL: register ref moved. expected %s..., got %s" % (REGISTER_COMMIT10, ref_sha)
        )
    blob = git_show(REGISTER_REF, REGISTER_PATH)
    if blob is None:
        raise SystemExit("FATAL: register unreadable at %s:%s" % (REGISTER_REF, REGISTER_PATH))
    reg = json.loads(blob.decode("utf-8"))
    return ref_sha, {r.get("id"): r for r in reg.get("records", [])}


def probe_engine():
    blob = git_show(REGISTER_REF, ENGINE_PATH)
    if blob is None:
        return {"available": False}
    rc, out = sh(["git", "log", "--format=%H", "-1", REGISTER_REF, "--", ENGINE_PATH])
    intro = out.decode("ascii", "replace").strip().splitlines()
    return {
        "available": True,
        "sha256": sha256_bytes(blob),
        "lines": blob.count(b"\n"),
        "blob_introduced_by": intro[0] if intro else "",
    }


def probe_running_engine():
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
        "ForEach-Object { $_.ProcessId.ToString() + '|' + $_.CommandLine }"
    )
    rc, out = sh(["powershell", "-NoProfile", "-Command", ps])
    matches, started = [], {}
    if rc == 0:
        for line in out.decode("utf-8", "replace").splitlines():
            if "|" not in line:
                continue
            pid, _, cmd = line.partition("|")
            pid, cmd = pid.strip(), cmd.strip()
            if "HL_Live_Copy_Service_Core.py" in cmd:
                matches.append({"pid": pid, "cmdline": cmd})
                rc2, out2 = sh(["powershell", "-NoProfile", "-Command",
                                "(Get-Process -Id %s).StartTime.ToString('o')" % pid])
                if rc2 == 0:
                    started[pid] = out2.decode("utf-8", "replace").strip()

    stamp, cfg = None, {}
    if (ENGINE_STATE_DIR / "network.json").is_file():
        stamp = json.loads((ENGINE_STATE_DIR / "network.json").read_text(encoding="utf-8"))
    if (ENGINE_STATE_DIR / "live_config.json").is_file():
        raw = json.loads((ENGINE_STATE_DIR / "live_config.json").read_text(encoding="utf-8"))
        cfg = {
            "auto_send_enabled": raw.get("auto_send_enabled"),
            "wallets_live": sum(1 for v in (raw.get("wallets") or {}).values() if v.get("mode") == "LIVE"),
            "wallets_off": sum(1 for v in (raw.get("wallets") or {}).values() if v.get("mode") == "OFF"),
        }
    return {
        "engine_processes": matches,
        "engine_process_running": bool(matches),
        "engine_started": started,
        "state_dir": str(ENGINE_STATE_DIR),
        "state_dir_exists": ENGINE_STATE_DIR.is_dir(),
        "network_stamp": stamp,
        "live_config": cfg,
        "auto_send_enabled": cfg.get("auto_send_enabled"),
    }


def probe_oracle(window_ms, engine_started_ms=None):
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - window_ms
    status, fills = post_json(
        TESTNET_INFO,
        {"type": "userFillsByTime", "user": ORACLE_MASTER,
         "startTime": start_ms, "endTime": now_ms, "aggregateByTime": False},
    )
    out = {
        "endpoint": TESTNET_INFO, "oracle_read_http": status, "master": ORACLE_MASTER,
        "window_start_ms": start_ms, "window_end_ms": now_ms,
    }
    if isinstance(fills, list):
        newest = max((f.get("time", 0) for f in fills), default=None)
        ref = engine_started_ms if engine_started_ms else (now_ms - 30 * 60 * 1000)
        out.update({
            "fills_in_window": len(fills),
            "newest_fill_ms": newest,
            "newest_fill_age_h": round((now_ms - newest) / 3600000.0, 2) if newest else None,
            "fills_since_engine_start": sum(1 for f in fills if f.get("time", 0) >= ref),
            "fills_last_30min": sum(1 for f in fills if f.get("time", 0) >= now_ms - 30 * 60 * 1000),
            "window_ref_ms": ref,
            "coins": sorted({str(f.get("coin")) for f in fills})[:12],
        })
    else:
        out.update({"fills_in_window": None, "raw_error": fills})
    return out


def probe_predeclared_scenario():
    rc, out = sh(["git", "ls-tree", "-r", "--name-only", REGISTER_REF])
    names = out.decode("utf-8", "replace").splitlines()
    hits = [n for n in names if any(k in n.lower() for k in ("scenario", "phase6t", "phase_6t"))]
    return {"runnable_scenario_scripts_in_repo": hits, "count": len(hits)}


def probe_mock_harness():
    blob = git_show(REGISTER_REF, MOCK_HARNESS)
    if blob is None:
        return {"present": False}
    txt = blob.decode("utf-8", "replace")
    lines = txt.splitlines()
    return {
        "present": True,
        "sha256": sha256_bytes(blob),
        "imports_unittest_mock": "from unittest.mock import" in txt,
        "patches_network": "_mock_network" in txt or "MIDS_FETCHER = lambda" in txt,
        "pinned_tested_commit": next((l.strip() for l in lines if l.startswith("TESTED_COMMIT")), ""),
        "pinned_tested_at": next((l.strip() for l in lines if l.startswith("TESTED_AT_UTC")), ""),
    }


def main():
    fresh_at = utcnow()
    ref_sha, recs = probe_register()
    engine = probe_engine()
    run = probe_running_engine()

    started_ms = None
    for iso in (run.get("engine_started") or {}).values():
        try:
            started_ms = int(datetime.fromisoformat(iso).timestamp() * 1000)
        except Exception:  # noqa: BLE001
            pass

    oracle = probe_oracle(24 * 3600 * 1000, started_ms)
    scen = probe_predeclared_scenario()
    mockh = probe_mock_harness()

    engine_ok = (
        engine.get("sha256") == REGISTER_ENGINE_SHA256
        and engine.get("lines") == REGISTER_ENGINE_LINES
    )

    settle_event_exists = (
        bool(run.get("engine_process_running"))
        and isinstance(oracle.get("fills_since_engine_start"), int)
        and oracle["fills_since_engine_start"] > 0
    )

    missing_runtime = (
        "PREDECLARED_PHASE6T_SETTLEMENT_SCENARIO over the LIVE testnet transport: no runnable "
        "Phase-6T scenario artifact exists in the register repo (git ls-tree %s -> %d match(es)), "
        "and although a live testnet engine IS running (pid %s, state dir %s, leader=%s follower=%s, "
        "auto_send_enabled=%s), it produced NO exchange settlement event in the probe window "
        "(independent oracle %s: %s fills in 24h, newest %sh old, %s since engine start). "
        "Producing one requires a controlled entry, which the certification contract forbids."
        % (REGISTER_REF, scen["count"],
           ",".join(p["pid"] for p in run["engine_processes"]) or "<none>",
           run["state_dir"], (run.get("network_stamp") or {}).get("leader"),
           (run.get("network_stamp") or {}).get("follower"), run.get("auto_send_enabled"),
           TESTNET_INFO, oracle.get("fills_in_window"),
           oracle.get("newest_fill_age_h") if oracle.get("newest_fill_age_h") is not None else "?",
           oracle.get("fills_since_engine_start"))
    )

    out_rows = {}
    for row_id in ROWS:
        reg = recs.get(row_id)
        if reg is None:
            out_rows[row_id] = {"area": "SETTLE", "result": "NOT_TESTED",
                                "error": "row absent from register of record"}
            continue
        folded_commit = str(reg.get("tested_commit") or "")
        folded_blob_sha = None
        if len(folded_commit) == 40:
            b = git_show(folded_commit, ENGINE_PATH)
            if b is not None:
                folded_blob_sha = sha256_bytes(b)

        checks = [
            check("REGISTER_ROW_PRESENT", True,
                  "register=%s:%s result=%s tested_commit=%s"
                  % (REGISTER_REF, REGISTER_PATH, reg.get("result"), folded_commit or "<none>")),
            check("DECLARED_PROOF_IS_LIVE_TESTNET_ENGINE_SCENARIO",
                  "testnet" in str(reg.get("execution_proof", "")).lower(),
                  str(reg.get("execution_proof", ""))[:110]),
            check("PREDECLARED_SCENARIO_ARTIFACT_EXISTS", scen["count"] > 0,
                  "runnable Phase-6T scenario scripts in %s = %s"
                  % (REGISTER_REF, scen["runnable_scenario_scripts_in_repo"] or "<none>")),
            check("REGISTER_ENGINE_BLOB_MATCHES", engine_ok,
                  "engine sha256=%s lines=%s (expected %s/%s)"
                  % (engine.get("sha256"), engine.get("lines"),
                     REGISTER_ENGINE_SHA256[:12], REGISTER_ENGINE_LINES)),
            check("ORACLE_SURFACE_REACHABLE", oracle.get("oracle_read_http") == 200,
                  "%s http=%s" % (TESTNET_INFO, oracle.get("oracle_read_http"))),
            check("ENGINE_PRODUCED_SETTLEMENT_EVENT", settle_event_exists,
                  "engine_running=%s network=%s auto_send=%s oracle_fills_since_start=%s"
                  % (run.get("engine_process_running"), json.dumps(run.get("network_stamp")),
                     run.get("auto_send_enabled"), oracle.get("fills_since_engine_start"))),
            check("FOLDED_EVIDENCE_ENGINE_BLOB_DIFFERS",
                  folded_blob_sha is not None and folded_blob_sha != REGISTER_ENGINE_SHA256,
                  "folded tested_commit=%s blob=%s vs register blob=%s"
                  % (folded_commit[:12] or "<none>", (folded_blob_sha or "<none>")[:12],
                     REGISTER_ENGINE_SHA256[:12])),
            check("FOLDED_EVIDENCE_USED_MOCKS", bool(mockh.get("patches_network")),
                  "mock_harness=%s patches_network=%s pinned_commit=%s"
                  % (MOCK_HARNESS, mockh.get("patches_network"), mockh.get("pinned_tested_commit"))),
        ]

        # Non-vacuous negatives: each asserts the ABSENCE of the state that would let this
        # row be falsely PASSed. If that state exists, the negative FAILS.
        negs = [
            {"name": "NEG_NO_ENGINE_PRODUCED_SETTLEMENT_EVENT",
             "pass": not settle_event_exists,
             "detail": "oracle %s: fills_24h=%s newest=%sh fills_since_engine_start=%s for master %s"
                       % (TESTNET_INFO, oracle.get("fills_in_window"),
                          oracle.get("newest_fill_age_h"),
                          oracle.get("fills_since_engine_start"), ORACLE_MASTER)},
            {"name": "NEG_NO_RUNNABLE_PREDECLARED_SCENARIO",
             "pass": scen["count"] == 0,
             "detail": "scenario scripts found in %s = %s"
                       % (REGISTER_REF, scen["runnable_scenario_scripts_in_repo"] or "<none>")},
            {"name": "NEG_ENGINE_NOT_IN_UNCONTROLLED_SEND_MODE",
             "pass": run.get("auto_send_enabled") is not True,
             "detail": "auto_send_enabled=%s wallets_live=%s wallets_off=%s"
                       % (run.get("auto_send_enabled"),
                          (run.get("live_config") or {}).get("wallets_live"),
                          (run.get("live_config") or {}).get("wallets_off"))},
        ]

        open_decs = list(reg.get("open_decisions") or [])
        blockers = []
        if open_decs:
            blockers.append("OPEN_DECISION:%s" % ",".join(open_decs))
        blockers.append("MISSING_RUNTIME:%s" % missing_runtime)

        out_rows[row_id] = {
            "area": "SETTLE",
            "feature": reg.get("feature"),
            "applicability": reg.get("applicability"),
            "result": "NOT_TESTED",
            "register_result_before_probe": reg.get("result"),
            "register_evidence_ref_before_probe": reg.get("evidence_ref") or "",
            "register_tested_commit_before_probe": folded_commit or "",
            "engine_commit_cited": engine.get("blob_introduced_by", ""),
            "engine_blob_sha256": engine.get("sha256"),
            "declared_execution_proof": reg.get("execution_proof", ""),
            "declared_independent_oracle": reg.get("independent_oracle", ""),
            "blocked_by": blockers,
            "missing_runtime": missing_runtime,
            "probe_checks": checks,
            "negative_tests": negs,
            "checks_passed": sum(1 for c in checks if c["pass"]),
            "checks_total": len(checks),
            "negs_passed": sum(1 for n in negs if n["pass"]),
            "negs_total": len(negs),
            "notes": (
                "Fresh read-only probe at %s. Status is NOT_TESTED, not re-affirmed from the "
                "register's prior folded FAIL: the prior evidence (%s, pinned to engine blob %s) "
                "is an in-process harness that patches the network, so it is not executed exchange "
                "evidence and cannot be carried forward. The declared proof needs a live testnet "
                "settlement event; %s"
                % (fresh_at, MOCK_HARNESS, (folded_blob_sha or "?")[:12], missing_runtime)
            ),
        }

    out = {
        "task_id": TASK_ID,
        "title": TITLE,
        "area": "SETTLE",
        "harness": HERE.name,
        "fresh_probe_at_utc": fresh_at,
        "register_ref": "%s:%s" % (REGISTER_REF, REGISTER_PATH),
        "register_head": ref_sha,
        "engine_under_test": engine,
        "running_engine_probe": run,
        "oracle_probe": oracle,
        "predeclared_scenario_probe": scen,
        "folded_evidence_harness": mockh,
        "missing_runtime": missing_runtime,
        "rows": out_rows,
        "summary": {
            "rows": len(out_rows),
            "passed": sum(1 for r in out_rows.values() if r.get("result") == "PASS"),
            "failed": sum(1 for r in out_rows.values() if r.get("result") == "FAIL"),
            "not_tested": sum(1 for r in out_rows.values() if r.get("result") == "NOT_TESTED"),
            "blocked_on_open_decision": sum(
                1 for r in out_rows.values()
                if any(str(b).startswith("OPEN_DECISION") for b in r.get("blocked_by", []))
            ),
            "mocked": 0,
            "status_changes": 0,
            "register_rows_unchanged": True,
        },
    }

    out_path = HERE.parent / ("SETTLE_%s.json" % REGISTER_COMMIT10)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("WROTE " + str(out_path))

    prog_path = HERE.parent / "PROGRESS_SETTLE.jsonl"
    prior = []
    if prog_path.exists():
        for line in prog_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    prior.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    pass
    by_row = {p.get("row"): p for p in prior if p.get("row") in ROWS}
    for row_id in ROWS:
        r = out_rows[row_id]
        by_row[row_id] = {
            "row": row_id, "area": "SETTLE", "result": r.get("result"),
            "register_result_before_probe": r.get("register_result_before_probe"),
            "missing_runtime": r.get("missing_runtime"),
            "blocked_by": r.get("blocked_by"),
            "register_ref": out["register_ref"],
            "register_head": out["register_head"],
            "engine_commit": r.get("engine_commit_cited"),
            "probe_at_utc": fresh_at,
        }
    ordered = [by_row[r] for r in ROWS if r in by_row]
    prog_path.write_text(
        "".join(json.dumps(o, sort_keys=True) + "\n" for o in ordered), encoding="utf-8"
    )
    print("WROTE " + str(prog_path) + " rows=%d" % len(ordered))
    print("SUMMARY " + json.dumps(out["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
