#!/usr/bin/env python3
"""C3-MUTATE-1550: six repaired tests vs 12 single-site, disposable Core mutants."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "_archive" / "hl_stage2"
OUT = ROOT / "evidence" / "c3-mutate-1550"
OUT.mkdir(parents=True, exist_ok=True)
CORE = STAGE / "HL_Live_Copy_Service_Core.py"
# Contract: mutate the EXACT historical Core from the controller's source SHA,
# not the later Coder One branch's tracked Core (different Git blob).
SOURCE = subprocess.check_output(
    ["git", "show", "0a99d215c99b794717ce5b34f46cc299dae09106:_archive/hl_stage2/HL_Live_Copy_Service_Core.py"],
    cwd=ROOT).decode("utf-8-sig").replace("\r\n", "\n")
assert subprocess.check_output(["git", "rev-parse", "0a99d215c99b794717ce5b34f46cc299dae09106:_archive/hl_stage2/HL_Live_Copy_Service_Core.py"], cwd=ROOT, text=True).strip() == "e470862a291bbf241e22d8011b757ed9c2b53d68"

FILES = [
    "test_core_run3_fixes.py",
    "test_core_run4_fixes.py",
    "test_core_retry_send_integrity.py",
    "test_core_trace_stamps.py",
    "test_core_missed_entry_rule.py",
    "test_core_master_gate.py",
]
TEST_REFS = {
    **{name: "366a12a53209d68e6867910f8fa8051e761905d0" for name in FILES[:4]},
    **{name: "86c33120f149df16558c37dcc9ab739726c64e9e" for name in FILES[4:]},
}
TEST_BLOBS = {
    "test_core_run3_fixes.py": "fd4a52abd98a10a36a78f9a62e686911ffd608aa",
    "test_core_run4_fixes.py": "a4d2d24d8f9866d407da0a8446f8dc4f80f3a363",
    "test_core_retry_send_integrity.py": "773094250e61dd88db78c1605c6463d4d5a8b82e",
    "test_core_trace_stamps.py": "1a57cf6a7f0448551ac41158233fa367c3be7ec2",
    "test_core_missed_entry_rule.py": "e714d8c3033c7a6eb0ba07c98a1d9bebcda00000",
    "test_core_master_gate.py": "bdefdca2a2e16ffd8068bc98d76807e696fe7dca",
}
# Each mutation is ONE source-site replacement with exactly one occurrence,
# tested against an UNMODIFIED repaired test loaded from its immutable Git SHA.
MUTANTS = {
"test_core_run3_fixes.py": [
 ("force_reduce_only_on_netting_flip",
  "return bool(net * delta < 0 and abs(delta) <= abs(net) + POSITION_EPSILON)",
  "return True  # MUTANT: unsafe RO on flip or unreadable net",
  "N4_FLIP_THROUGH_FLAT_NOT_REDUCE_ONLY"),
 ("disable_reduce_only_even_for_safe_close",
  "return bool(net * delta < 0 and abs(delta) <= abs(net) + POSITION_EPSILON)",
  "return False  # MUTANT: safe close incorrectly loses RO",
  "N2_SINGLE_LEADER_CLOSE_STAYS_REDUCE_ONLY"),
],
"test_core_run4_fixes.py": [
 ("refuse_all_same_direction_merges",
  "        return False\n    return True\n\n\ndef merge_leader_fills",
  "        return False\n    return False  # MUTANT: no same-direction merges\n\n\ndef merge_leader_fills",
  "Q1_FIXED_SIZING_MERGES_TOO_RUN5"),
 ("merge_across_wallet_side_or_direction",
  "if (a.leader_wallet != b.leader_wallet or canonical_coin_key(a.coin) != canonical_coin_key(b.coin)\n            or a.side != b.side or _fill_dir(a) != _fill_dir(b)):",
  "if False and (a.leader_wallet != b.leader_wallet or canonical_coin_key(a.coin) != canonical_coin_key(b.coin)\n            or a.side != b.side or _fill_dir(a) != _fill_dir(b)):  # MUTANT: unsafe merge",
  "Q1_NEVER_ACROSS_SIDE_DIRECTION_WALLET_OR_COIN"),
],
"test_core_retry_send_integrity.py": [
 ("reuse_cloid_on_all_recovery_tries",
  "cloid, attempt_id = generate_cloid(key), generate_attempt_id(key)",
  "cloid, attempt_id = generate_cloid(intent.intent_id), generate_attempt_id(key)  # MUTANT: cloid collision",
  "S1_IOC_RETRY_OWN_CLOID_AND_PENDING_ROW_BEFORE_CALL"),
 ("drop_recovery_pending_send_callback",
  "        return cloid, _pre\n\n    @staticmethod\n    def _outstanding_attempt_cloids",
  "        return cloid, None  # MUTANT: no write-ahead hook\n\n    @staticmethod\n    def _outstanding_attempt_cloids",
  "S1_IOC_RETRY_OWN_CLOID_AND_PENDING_ROW_BEFORE_CALL"),
],
"test_core_trace_stamps.py": [
 ("discard_websocket_arrival_timestamp",
  'ws_received = int(fnum(raw.get("ws_received_ms", raw.get("_ws_received_ms")), 0))',
  "ws_received = 0  # MUTANT: WS ingest timestamp lost",
  "ws_fill_carries_ws_received_ms"),
 ("discard_real_send_start_trace",
  'trace_stages["send_real_started_ms"] = int(fnum(call_ms, 0))',
  'trace_stages["send_real_started_ms"] = None  # MUTANT: real send timestamp lost',
  "real_send_stamps_send_real_started_ms"),
],
"test_core_missed_entry_rule.py": [
 ("invert_missed_entry_tolerance",
  '"take": adverse_bps <= max(0.0, tolerance_bps) + 1e-9',
  '"take": adverse_bps >= max(0.0, tolerance_bps) + 1e-9  # MUTANT: inverted tolerance',
  "M1_SAME_PRICE_TAKEN"),
 ("ignore_cross_network_relative_price",
  "desired = leader_px if market_px == follower_px else follower_px * leader_px / market_px  # exact on one network",
  "desired = leader_px  # MUTANT: wrong cross-network price reference",
  "M1_CROSS_NETWORK_SAME_RELATIVE_DISTANCE"),
],
"test_core_master_gate.py": [
 ("allow_global_master_OFF_orders",
  'if mode == "OFF":\n            return "MASTER_REAL_ORDERS_OFF"',
  'if False and mode == "OFF":\n            return "MASTER_REAL_ORDERS_OFF"  # MUTANT: physical master OFF ignored',
  "MASTER_OFF_MAKES_NO_EXCHANGE_CALL"),
 ("allow_entry_when_global_CLOSE_only",
  'if mode == "CLOSE" and lifecycle in {"ENTRY", "ADD"}:',
  'if False and mode == "CLOSE" and lifecycle in {"ENTRY", "ADD"}:  # MUTANT: global close-only bypass',
  "GLOBAL_CLOSE_BLOCKS_AN_ENTRY_AT_THE_CALL"),
],
}
assert set(MUTANTS) == set(FILES)
assert all(len(v) == 2 for v in MUTANTS.values())

RESULT_RE = re.compile(r"RESULT::(\S+?)_(PASS|FAIL)(?:\s*\|\s*(.*))?$")
TOTAL_RE = re.compile(r"TOTAL=(\d+)\s+FAILED=(\d+)")
sitecustomize = """import socket
def _deny(*a, **k):
    raise RuntimeError('C3_MUTATE_OFFLINE_NETWORK_DENIED')
socket.socket.connect = _deny
socket.socket.connect_ex = _deny
socket.create_connection = _deny
"""
def run_test(fname, code, label):
    work = Path(tempfile.mkdtemp(prefix="c3mut_"))
    try:
        (work / "HL_Live_Copy_Service_Core.py").write_text(code, encoding="utf-8")
        test_src = subprocess.check_output(
            ["git", "show", TEST_REFS[fname] + ":_archive/hl_stage2/" + fname], cwd=ROOT)
        (work / fname).write_bytes(test_src)  # never edit the repaired test

        # The disk-full test starts a Python -c child with its own stripped
        # environment. Link original sibling modules into its private CWD, so
        # exchange_truth and other imports work without changing the TEST.
        for dep in STAGE.glob("*.py"):
            if dep.name not in (fname, "HL_Live_Copy_Service_Core.py", "sitecustomize.py"):
                (work / dep.name).symlink_to(dep.resolve())
        (work / "sitecustomize.py").write_text(sitecustomize, encoding="utf-8")
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": os.pathsep.join((str(work), str(STAGE))),
            "HL_LIVE_ENV_FILE": "/nonexistent",
            "HL_LEADER_NETWORK": "testnet",
            "HL_FOLLOWER_NETWORK": "testnet",
            "HL_LIVE_AUTO_SEND_ENABLED": "0",
            "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
            "HL_LIVE_HL_PRIVATE_KEY": "",
            "HL_USER_WALLET": "",
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        t = time.monotonic()
        try:
            p = subprocess.run([sys.executable, "-u", fname],
                               cwd=work, env=env, capture_output=True,
                               text=True, errors="replace", timeout=100)
            returncode = p.returncode
            raw = p.stdout + "\n=== STDERR ===\n" + p.stderr
            timed_out = False
        except subprocess.TimeoutExpired as e:
            raw = repr(e.stdout) + "\n=== TIMEOUT ===\n" + repr(e.stderr)
            returncode = 124
            timed_out = True
        cases = []
        for line in raw.splitlines():
            m = RESULT_RE.search(line)
            if m:
                cases.append({"name":m.group(1),"verdict":m.group(2),"detail":m.group(3) or ""})
        totals = TOTAL_RE.findall(raw)
        safe = fname.replace(".py","") + "__" + label
        (OUT / (safe + ".log")).write_text(raw, encoding="utf-8")
        return {
            "file":fname, "mutation":label, "returncode":returncode,
            "timeout":timed_out, "totals":totals[-1] if totals else None,
            "failed_cases":[c for c in cases if c["verdict"]=="FAIL"],
            "passed_case_count":sum(c["verdict"]=="PASS" for c in cases),
            "duration_seconds":round(time.monotonic()-t,2),
            "tracebacks":[line for line in raw.splitlines() if
                          any(k in line for k in ("Traceback", "SyntaxError:", "NameError:", "Exception:", "Error:"))][-12:],
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)

def show(r):
    slim={k:v for k,v in r.items() if k not in ("failed_cases","tracebacks")}
    slim["failures"]=len(r.get("failed_cases",[]))
    slim["first_failures"]=[c["name"] for c in r.get("failed_cases",[])][:8]
    slim["tracebacks"]=r.get("tracebacks",[])[:3]
    print("MUTATION_RECORD " + json.dumps(slim,sort_keys=True),flush=True)

report={"core_source":"0a99d215c99b794717ce5b34f46cc299dae09106",
        "test_refs":TEST_REFS,"test_blobs":TEST_BLOBS,
        "baseline":[], "mutations":[]}
for file in FILES:
    # Immutable test-provenance guard, checked before execution.
    actual_blob = subprocess.check_output(
        ["git", "rev-parse", TEST_REFS[file] + ":_archive/hl_stage2/" + file],
        cwd=ROOT, text=True).strip()
    assert actual_blob == TEST_BLOBS[file], (file, actual_blob, TEST_BLOBS[file])
    b=run_test(file,SOURCE,"baseline")
    show(b)
    report["baseline"].append(b)
    for name,anchor,replacement,expected_case in MUTANTS[file]:
        count=SOURCE.count(anchor)
        if count!=1:
            item={"file":file,"mutation":name,"classification":"INVALID_ANCHOR",
                  "anchor_count":count,"expected_case":expected_case}
            print("MUTATION_RECORD "+json.dumps(item),flush=True)
            report["mutations"].append(item)
            continue
        mutated=SOURCE.replace(anchor,replacement,1)
        assert mutated!=SOURCE
        r=run_test(file,mutated,name)
        assert r["file"]==file
        r["expected_case"]=expected_case
        r["baseline_pass"]=(b["returncode"]==0 and b["totals"] and b["totals"][1]=="0")
        expected_found=any(c["name"]==expected_case for c in r["failed_cases"])
        r["expected_assertion_failed"]=expected_found
        if not r["baseline_pass"]:
            r["classification"]="BASELINE_NOT_GREEN"
        elif expected_found:
            r["classification"]="CAUGHT_EXPECTED_ASSERTION"
        elif r["failed_cases"]:
            r["classification"]="CAUGHT_OTHER_ASSERTION_REVIEW"
        elif r["returncode"]!=0 or r["timeout"]:
            r["classification"]="CRASH_OR_TIMEOUT_INCONCLUSIVE"
        else:
            r["classification"]="MISSED_FALSE_GREEN"
        show(r)
        report["mutations"].append(r)
        (OUT / "report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")

(OUT / "report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
with (OUT / "summary.tsv").open("w",encoding="utf-8") as f:
    f.write("file\tmutation\tclassification\tcase\tobserved_line\n")
    for r in report["mutations"]:
        case=next((c for c in r.get("failed_cases",[]) if c["name"]==r.get("expected_case")),None)
        if case is None:
            case=(r.get("failed_cases") or [{}])[0]
        obs=("RESULT::"+case["name"]+"_"+case["verdict"]+
             (" | "+case.get("detail","") if case.get("detail") else "")) if case.get("name") else "NO_RESULT_FAIL"
        f.write("\t".join(str(v).replace("\t"," ").replace("\n"," ") for v in
                          [r["file"],r["mutation"],r["classification"],r.get("expected_case",""),obs])+"\n")
print("MUTATION_SUMMARY "+json.dumps({
  k:sum(x.get("classification")==k for x in report["mutations"])
  for k in sorted(set(x.get("classification") for x in report["mutations"]))
},sort_keys=True),flush=True)
