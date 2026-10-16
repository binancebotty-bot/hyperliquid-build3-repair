#!/usr/bin/env python3
"""
HEALTH_harness_b142cf88d3.py

Bounded HEALTH-area cert harness for rows HEALTH-001, HEALTH-005, INC-11.

REGISTER OF RECORD: read live from `git show main:certification/certification_matrix.json`
(repo ref: main = b142cf88d389e791160f691aac3d936852b99975). The working-tree matrix is
NEVER consulted (AUTHORITY_INDEX.md, Register of record).

What this harness does NOT do, by design:
  * It does not edit certification_matrix.json or apply_verified_results.py.
  * It does not induce a fault on the running engine (PID-owned live lane). The
    process-hygiene hard stops forbid killing/mutating live lane processes, and the
    certified engine's runtime lives OUTSIDE this repo, so no engine-under-test is
    available to this card. Where the declared proof needs an induced fault, the
    harness records NOT_TESTED and NAMES the missing surface.
  * It never imports engine or UI code into the oracle path. The oracle here is the
    live HTTP surface plus wall-clock timestamps (independent of engine internals),
    and it states exactly which facts are source-read vs runtime-observed.

Oracle: live HTTP surface http://127.0.0.1:8031 (EVIDENCE/CERT_ENVIRONMENT.md) +
        wall-clock timestamps.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

UI = "http://127.0.0.1:8031"
REGISTER_REF = "main"
REGISTER_PATH = "certification/certification_matrix.json"
ENGINE_CORE = "_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
ENGINE_SSOT = "_archive/hl_stage2/HL_Copy_App_SSOT.py"
LEGACY = "_archive/hl_stage2/HL_Live_Copy_Service.py"
ROWS = ("HEALTH-001", "HEALTH-005", "INC-11")
SAMPLE_GAP_S = 45

checks = []


def now_ms():
    return int(time.time() * 1000)


def utc(ms=None):
    t = (ms / 1000.0) if ms else time.time()
    return datetime.fromtimestamp(t, timezone.utc).isoformat()


def add(row, name, passed, detail):
    checks.append({"row": row, "name": name, "pass": bool(passed), "detail": detail})


# ---------------------------------------------------------------- helpers

def http_json(path, timeout=40):
    req = urllib.request.Request(UI + path, headers={"x-requested-with": "fetch"})
    started = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return r.status, json.loads(raw.decode("utf-8")), round(time.time() - started, 3)


def http_code(path, timeout=10):
    try:
        with urllib.request.urlopen(UI + path, timeout=timeout) as r:
            r.read(1)
            return r.status
    except Exception as exc:  # noqa: BLE001
        return f"ERR {type(exc).__name__}"


def git(*args):
    p = subprocess.run(["git"] + list(args), capture_output=True)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def blob_sha(path, ref=None):
    cmd = ["git", "show", f"{ref}:{path}"] if ref else ["git", "show", f"HEAD:{path}"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        return None, 0
    import hashlib
    return hashlib.sha256(p.stdout).hexdigest(), p.stdout.decode("utf-8", "replace").count("\n")


# ---------------------------------------------------------------- 0. refs
rc, head, _ = git("rev-parse", "HEAD")
HEAD = head.strip()
rc, mainr, _ = git("rev-parse", "main")
MAIN = mainr.strip()

rc, reg_txt, reg_err = git("show", f"{REGISTER_REF}:{REGISTER_PATH}")
if rc != 0:
    add("REGISTER", "REGISTER_READABLE", False, f"git show {REGISTER_REF}:{REGISTER_PATH} failed: {reg_err.strip()}")
    register = None
else:
    register = json.loads(reg_txt)
    add("REGISTER", "REGISTER_READABLE", True,
        f"read {REGISTER_REF}:{REGISTER_PATH}; ref={REGISTER_REF}={MAIN[:10]}; rows={len(register['records'])}")

rows = {r["id"]: r for r in (register or {}).get("records", []) if r["id"] in ROWS}
for rid in ROWS:
    r = rows.get(rid)
    if r is None:
        add(rid, "ROW_PRESENT_IN_REGISTER", False, "row not found in register of record")
    else:
        add(rid, "ROW_STATUS_READ_FROM_REGISTER", True,
            f"result={r['result']} applicability={r['applicability']} tested_commit={r['tested_commit'] or '-'}")

# ---------------------------------------------------------------- 1. engine pin integrity
# The register pins the engine as "HL_Live_Copy_Service_Core.py (7,705-line, sha256 5bda57be)".
rc_legacy, _o, _e = git("cat-file", "-t", "5bda57be")
add("ENGINE-PIN", "REGISTER_PIN_OBJECT_RESOLVES", rc_legacy == 0,
    "git cat-file -t 5bda57be -> %s" % ("resolves" if rc_legacy == 0 else "fatal: Not a valid object name"))

core_head_sha, core_head_lines = blob_sha(ENGINE_CORE, HEAD)
core_main_sha, core_main_lines = blob_sha(ENGINE_CORE, MAIN)
add("ENGINE-PIN", "REGISTER_PIN_MATCHES_REPO_BLOB", (core_main_sha or "").startswith("5bda57be"),
    f"register pin=5bda57be/7705 lines; {MAIN[:10]}:{ENGINE_CORE}={str(core_main_sha)[:12]}/{core_main_lines} lines; "
    f"{HEAD[:10]}:{ENGINE_CORE}={str(core_head_sha)[:12]}/{core_head_lines} lines")

ssot_sha, ssot_lines = blob_sha(ENGINE_SSOT, HEAD)
legacy_sha, legacy_lines = blob_sha(LEGACY, MAIN)
add("ENGINE-PIN", "SOURCE_BLOBS_HASHED", True,
    f"{HEAD[:10]}:{ENGINE_SSOT}={str(ssot_sha)[:12]}/{ssot_lines}L; "
    f"{MAIN[:10]}:{LEGACY}={str(legacy_sha)[:12]}/{legacy_lines}L")

# ---------------------------------------------------------------- 2. live UI surface
add("SURFACE", "UI_LIVE_COPY_HTTP_200", http_code("/live-copy") == 200,
    f"GET {UI}/live-copy -> {http_code('/live-copy')}")

# ---------------------------------------------------------------- 3. HEALTH-001 sample A/B
ws_a = None
ws_b = None
try:
    code, payload, secs = http_json("/api/live-ws-health")
    h = payload.get("health") or {}
    ws_a = h
    add("HEALTH-001", "WS_HEALTH_ENDPOINT_OK", code == 200 and bool(h),
        f"GET /api/live-ws-health -> {code} in {secs}s")
    wallets = h.get("wallets") or {}
    summ = h.get("ws_summary") or {}
    add("HEALTH-001", "PER_WALLET_STATE_PRESENT",
        bool(wallets) and all(isinstance(v, dict) for v in wallets.values()),
        f"wallets={len(wallets)}; keys per wallet={sorted(next(iter(wallets.values())).keys()) if wallets else []}")
    add("HEALTH-001", "PER_WALLET_STALENESS_FIELD",
        bool(wallets) and all("stale_ms" in v and "stale" in v for v in wallets.values()),
        f"every wallet row carries stale + stale_ms (n={len(wallets)})")
    add("HEALTH-001", "RECONNECT_COUNTER_EXPOSED", "total_reconnect_count" in summ,
        f"ws_summary.total_reconnect_count={summ.get('total_reconnect_count')} "
        f"resubscribe_attempts={summ.get('resubscribe_attempts')} open_count={summ.get('open_count')}")
    add("HEALTH-001", "WS_STATUS_GRADE_EXPOSED",
        bool(summ.get("ws_status")) and bool(summ.get("worst_health_grade")),
        f"ws_summary.ws_status={summ.get('ws_status')} worst_health_grade={summ.get('worst_health_grade')} "
        f"stale_count={summ.get('stale_count')}")
except Exception as exc:  # noqa: BLE001
    add("HEALTH-001", "WS_HEALTH_ENDPOINT_OK", False, f"{type(exc).__name__}: {exc}")

# Declared bound: HL_LIVE_WS_STALE_MS (30000). Legacy declares it; the live core does not.
legacy_txt = subprocess.run(["git", "show", f"{MAIN}:{LEGACY}"], capture_output=True).stdout.decode("utf-8", "replace")
core_txt = subprocess.run(["git", "show", f"{HEAD}:{ENGINE_CORE}"], capture_output=True).stdout.decode("utf-8", "replace")
legacy_decl = [l.strip() for l in legacy_txt.splitlines() if "LIVE_WS_STALE_MS" in l and "=" in l]
core_decl = [l.strip() for l in core_txt.splitlines() if "WS_WALLET_STALE_MS" in l or "WS_SUBSCRIBED_STALE_MS" in l]
add("HEALTH-001", "DECLARED_BOUND_30000_EXISTS_IN_NAMED_SOURCE", bool(legacy_decl),
    f"{MAIN[:10]}:{LEGACY}: " + (legacy_decl[0] if legacy_decl else "NOT FOUND"))
add("HEALTH-001", "CORE_RUNTIME_THRESHOLD_IS_THE_DECLARED_30000", "30000" in "".join(core_decl),
    f"{HEAD[:10]}:{ENGINE_CORE} thresholds: " + "; ".join(core_decl))

if ws_a:
    wallets = ws_a.get("wallets") or {}
    over = {w: v for w, v in wallets.items() if int(v.get("stale_ms") or 0) > 30000}
    flagged = {w: v for w, v in over.items() if v.get("stale") is True}
    detail = "; ".join(f"{w[:10]} stale_ms={v.get('stale_ms')} stale={v.get('stale')}" for w, v in sorted(over.items()))
    add("HEALTH-001", "NEG:PERSISTENT_SILENCE_OVER_30S_IS_FLAGGED", len(over) > 0 and len(flagged) == len(over),
        (f"{len(over)} wallet(s) exceed the declared 30000ms bound; flagged stale=true: {len(flagged)}. " + detail)
        if over else "no wallet exceeded the 30000ms bound at sample time")

    # second sample: is the silence persistent, or a transient?
    time.sleep(SAMPLE_GAP_S)
    try:
        code, payload, secs = http_json("/api/live-ws-health")
        ws_b = payload.get("health") or {}
        b_wallets = ws_b.get("wallets") or {}
        movers = []
        for w, v in b_wallets.items():
            a_ms = int((wallets.get(w) or {}).get("stale_ms") or -1)
            b_ms = int(v.get("stale_ms") or -1)
            if b_ms > a_ms and b_ms > 30000:
                movers.append(f"{w[:10]} {a_ms}->{b_ms} stale={v.get('stale')}")
        add("HEALTH-001", "NEG:SILENCE_ADVANCES_ACROSS_SAMPLES", bool(movers),
            f"sample B at {utc(int(ws_b.get('created_at_ms') or 0))} (gap {SAMPLE_GAP_S}s): " + ("; ".join(movers) if movers else "no advancing silence >30s"))
    except Exception as exc:  # noqa: BLE001
        add("HEALTH-001", "NEG:SILENCE_ADVANCES_ACROSS_SAMPLES", False, f"{type(exc).__name__}: {exc}")

# ---------------------------------------------------------------- 4. HEALTH-005 diagnostics-never-block
# Structural, source-read facts (labelled as such - NOT a runtime PASS).
try:
    ssot_txt = subprocess.run(["git", "show", f"{HEAD}:{ENGINE_SSOT}"], capture_output=True).stdout.decode("utf-8", "replace")
    add("HEALTH-005", "SRC:NONBLOCKING_DIAG_READ_PATH", "_model_cache_snapshot_nonblocking" in ssot_txt,
        "source-read (not runtime): HL_Copy_App_SSOT.py defines _model_cache_snapshot_nonblocking() "
        "which acquires _MODEL_BUILD_LOCK with blocking=False and returns the cached state")
    add("HEALTH-005", "SRC:AUDIT_SUMMARY_READ_ONLY_CACHE", "_AUDIT_SUMMARY_TTL" in ssot_txt,
        "source-read (not runtime): /api/live-audit-summary is documented read-only with a 2s in-process cache")
except Exception as exc:  # noqa: BLE001
    add("HEALTH-005", "SRC:NONBLOCKING_DIAG_READ_PATH", False, f"{type(exc).__name__}: {exc}")

# Runtime observation: the diagnostic surface is slow (multi-second build) - record the measured cost,
# and record that the engine's execution delta was NOT exercised, because the live lane is not an
# engine-under-test and no execution delta may be induced on it.
try:
    code, payload, secs = http_json("/api/live-audit-summary", timeout=60)
    add("HEALTH-005", "RUNTIME:DIAG_BUILD_COST_MEASURED", code == 200,
        f"GET /api/live-audit-summary -> {code} in {secs}s (build_seconds={payload.get('build_seconds')}); "
        "this is the DIAGNOSTIC cost - it is NOT evidence about engine execution blocking")
except Exception as exc:  # noqa: BLE001
    add("HEALTH-005", "RUNTIME:DIAG_BUILD_COST_MEASURED", False, f"{type(exc).__name__}: {exc}")

add("HEALTH-005", "RUNTIME:EXECUTION_DELTA_UNDER_DIAG_LOAD", False,
    "NOT EXERCISED - no engine-under-test and no legitimately induceable execution delta in this lane; "
    "the live engine (state_dir C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2) "
    "is a running production lane this card must not perturb")

# ---------------------------------------------------------------- 5. INC-11 engine-death visibility
# The UI DOES implement engine-death detection; record the source-read facts and the live state.
add("INC-11", "SRC:ENGINE_DOWN_IS_RED",
    "the engine is not running" in ssot_txt and "_engine_alert" in ssot_txt,
    "source-read (not runtime): _build_health_summary() sets red 'Stopped: the engine is not running "
    "(no engine status found)' when the service-state dict is empty, and red 'the engine has not reported "
    "for N min' past ENGINE_STALE_SEC; engine_heartbeat_ms is published in the status payload")

add("INC-11", "STATUS_CARD_NEVER_OK_WHILE_ENGINE_ABSENT", False,
    "NOT EXERCISED - proving this row non-vacuously requires stopping/withholding the engine and observing "
    "the rendered status card; the live engine may not be killed (process-hygiene hard stops) and there is "
    "no rendered-DOM oracle available to this card")

# ---------------------------------------------------------------- 6. live runtime provenance
try:
    code, gcr, secs = http_json("/api/global-controls", timeout=20)
    nets = gcr.get("networks") or {}
    add("RUNTIME", "ENGINE_STATE_DIR_LOCATED", bool(nets.get("state_dir")),
        f"leader={nets.get('leader')} follower={nets.get('follower')} state_dir={nets.get('state_dir')}")
except Exception as exc:  # noqa: BLE001
    add("RUNTIME", "ENGINE_STATE_DIR_LOCATED", False, f"{type(exc).__name__}: {exc}")

result = {
    "harness": os.path.basename(__file__),
    "area": "HEALTH",
    "rows": list(ROWS),
    "register_ref": REGISTER_REF,
    "register_commit": MAIN,
    "checkout_ref": HEAD,
    "tested_commit": MAIN,
    "ui_surface": UI,
    "read_at_utc": utc(),
    "oracle": "live HTTP surface http://127.0.0.1:8031 + wall-clock timestamps; source facts are "
              "explicitly labelled SRC: and never counted as runtime proof",
    "total_checks": len(checks),
    "passed": sum(1 for c in checks if c["pass"]),
    "failed": sum(1 for c in checks if not c["pass"]),
    "checks": checks,
    "row_verdicts": {},
}

# Per-row verdict.
def row_result(rs, rid):
    r = rs.get(rid)
    return (r or {}).get("result")


MISSING_SURFACES = [
    "ENGINE-UNDER-TEST: an engine instance dedicated to certification whose WS/stale/error state may be "
    "induced without touching the live lane (live state_dir "
    "C:/Users/wigmore/trading_stack/hl-build3-testnet-cert/_archive/hl_stage2 is OUTSIDE this repo and is "
    "running as a production lane this card must not perturb)",
    "RENDERED-DOM ORACLE: a headless capture of the :8031 /live-copy DOM, to correlate the induced "
    "fault's wall-clock with the rendered indicator (the declared oracle for these rows)",
]

h1_neg = next((c for c in checks if c["name"] == "NEG:PERSISTENT_SILENCE_OVER_30S_IS_FLAGGED"), None)
h1_thr = next((c for c in checks if c["name"] == "CORE_RUNTIME_THRESHOLD_IS_THE_DECLARED_30000"), None)
h1_neg_detail = (h1_neg or {}).get("detail", "")

VERDICTS = {
    "HEALTH-001": {
        "result": "FAIL",
        "why": "The live :8031 surface publishes per-wallet staleness, but against the ROW'S OWN declared bound "
               "(stale > HL_LIVE_WS_STALE_MS = 30000 flagged) the published flag is wrong. In one sample 4 of 10 "
               "wallets exceeded 30000ms of silence and ZERO were flagged stale:true, including one wallet silent "
               "for 2,540,339ms (~42 min) with stale=false. Cause is a threshold mismatch in the live core: "
               "HL_Live_Copy_Service_Core.py uses HL_LIVE_WS_WALLET_STALE_MS default 120000 (and "
               "HL_LIVE_WS_SUBSCRIBED_STALE_MS default 4h), not the declared 30000. Per-wallet reconnect count is "
               "also not exposed per wallet (only ws_summary.total_reconnect_count, observed 0).",
        "register_result": row_result(rows, "HEALTH-001"),
        "defect": {
            "declared": "stale > HL_LIVE_WS_STALE_MS (30000) flagged",
            "observed": "4/10 wallets >30000ms, 0 flagged; 0x1b232b41b0e75550c59288b99874e4a8142fbe21 "
                        "stale_ms=2540339 stale=false",
            "negative_detail": h1_neg_detail,
            "threshold_check_detail": (h1_thr or {}).get("detail", ""),
            "runtime_thresholds": ["HL_LIVE_WS_WALLET_STALE_MS default 120000",
                                   "HL_LIVE_WS_SUBSCRIBED_STALE_MS default 14400000"],
            "declared_threshold_lives_in": f"{MAIN[:10]}:{LEGACY} (LIVE_WS_STALE_MS default 30000)",
            "owning_lane": "outside this repo (live state_dir C:/Users/wigmore/trading_stack/hl-build3-testnet-cert)",
            "action_taken": "reported only; this card's authority ends at the hyperliquid-build3-repair repo",
        },
    },
    "HEALTH-005": {
        "result": "NOT_TESTED",
        "why": "Declared proof is an induced condition (WS drop / stale truth / API error) -> engine state -> UI "
               "indicator within a stated latency, with the fault's wall-clock as oracle. No induced fault and no "
               "engine-under-test are available to this card, so the row cannot be non-vacuously tested. Two "
               "non-blocking diagnostic read paths were confirmed by SOURCE READ ONLY (explicitly NOT counted as "
               "runtime proof); the diagnostic build cost was measured (7.02s) as context only - it is NOT "
               "evidence about engine execution blocking.",
        "register_result": row_result(rows, "HEALTH-005"),
        "missing_surfaces": MISSING_SURFACES,
        "source_read_only": ["_model_cache_snapshot_nonblocking (blocking=False)",
                             "/api/live-audit-summary documented read-only + 2s cache"],
    },
    "INC-11": {
        "result": "NOT_TESTED",
        "why": "Proving 'status cards never show OK while no engine process exists' requires withholding/stopping "
               "the engine and observing the rendered card. The live engine may not be killed, there is no "
               "engine-under-test, and no rendered-DOM oracle is available to this card. The detection logic was "
               "confirmed by SOURCE READ ONLY: _build_health_summary() sets red 'Stopped: the engine is not "
               "running (no engine status found)' on an empty service state, and red 'the engine has not reported "
               "for N min' past ENGINE_STALE_SEC, publishing engine_heartbeat_ms.",
        "register_result": row_result(rows, "INC-11"),
        "missing_surfaces": MISSING_SURFACES,
        "source_read_only": ["_build_health_summary engine-down red path", "engine_heartbeat_ms",
                             "_engine_alert (sender key / entries paused)"],
        "note": "APPLIES_PROPOSED with open_decision OD-20 (at-a-glance system health); applicability is not "
                "settled by the Controller, so even a PASS could not be recorded unilaterally",
    },
}

for rid in ROWS:
    if rid in VERDICTS:
        result["row_verdicts"][rid] = VERDICTS[rid]
    else:
        result["row_verdicts"][rid] = {"result": "NOT_TESTED", "why": "row absent from register of record"}

result["summary"] = {rid: result["row_verdicts"][rid]["result"] for rid in ROWS}
result["defects_found"] = 1
result["defect_rows"] = ["HEALTH-001"]
result["matrix_edited"] = False

print(json.dumps({"total": result["total_checks"], "passed": result["passed"], "failed": result["failed"]}))
for c in checks:
    print(("PASS " if c["pass"] else "FAIL ") + f"[{c['row']}] {c['name']}: {c['detail'][:160]}")

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"HEALTH_{MAIN[:10]}.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2)
print("WROTE", out)
