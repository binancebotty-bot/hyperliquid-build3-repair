#!/usr/bin/env python3
"""Row-specific executed-probe harness for kanban t_b7f52cc1.

Rows: CTRL-BIND, B4-I13, B4-I20, B4-I21, B4-I26, F-EXC-016
Register of record: b142cf88:certification/certification_matrix.json
Independent oracle: reads git objects + OS HTTP surface only; imports NO engine/UI code.
"""
import json, os, subprocess, sys, hashlib, urllib.request

REPO = r"C:/Users/wigmore/hyperliquid-build3-repair"
REG = "b142cf88"
CORE = "_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
UI_URL = "http://127.0.0.1:8031/live-copy"


def sh(args, cwd=REPO):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def show(path):
    rc, out, err = sh(["git", "show", f"{REG}:{path}"])
    return out if rc == 0 else ""


results = {"register_ref": REG, "checks": {}}
reg = json.loads(show("certification/certification_matrix.json"))
rows = {r["id"]: r for r in reg["records"]}
results["register_row_status"] = {i: rows[i]["result"] for i in
    ["CTRL-BIND", "B4-I13", "B4-I20", "B4-I21", "B4-I26", "F-EXC-016"] if i in rows}

core_blob = show(CORE)
results["engine_commit"] = {"ref": REG,
    "core_sha256": hashlib.sha256(core_blob.encode()).hexdigest(),
    "core_lines": core_blob.count(chr(10)) + 1}

for sym in ["max_diff_pct", "follower_mid", "independent_oracle",
            "apply_fixed_sleeve_event", "ENTRY_PRICE_BOUND", "PRICE_WAIT"]:
    results["checks"]["core_has_" + sym] = core_blob.count(sym)

results["checks"]["pinned_hash_resolution"] = {}
for h in ["2dfbd57", "2dfbd571", "5bda57be", "5de53fa"]:
    rc, out, err = sh(["git", "cat-file", "-t", h])
    results["checks"]["pinned_hash_resolution"][h] = (out.strip() or err.strip()[:60])

rc, out, err = sh(["git", "ls-tree", "-r", "--name-only", REG])
names = out.splitlines()
results["checks"]["legacy_b4_tests_at_register"] = [n for n in names if any(
    k in n.lower() for k in ["delayed_entry", "sub_minimum", "exchange_size_quant",
                             "build4_internal_equity", "8014_proportional"])]
results["checks"]["independent_oracle_at_register"] = [n for n in names if "oracle" in n.lower()]
results["checks"]["core_min_notional_default_line"] = [l for l in core_blob.splitlines()
    if "HL_LIVE_MIN_NOTIONAL" in l][:3]

try:
    r = urllib.request.urlopen(UI_URL, timeout=8)
    body = r.read().decode("utf-8", "ignore")
    results["checks"]["ui_probe"] = {"url": UI_URL, "http": r.status, "bytes": len(body),
        "has_AUTHORITATIVE_EXCHANGE": "AUTHORITATIVE_EXCHANGE" in body,
        "truth_tier_tokens": sorted({t for t in ["AUTHORITATIVE_EXCHANGE", "LOCAL_LEDGER",
            "DISPLAY_ONLY", "LEADER_SIGNAL"] if t in body})}
except Exception as e:
    results["checks"]["ui_probe"] = {"url": UI_URL, "error": repr(e)}

results["env"] = {"PYTHONPATH": os.environ.get("PYTHONPATH"), "python": sys.version.split()[0]}
print(json.dumps(results, indent=1))
