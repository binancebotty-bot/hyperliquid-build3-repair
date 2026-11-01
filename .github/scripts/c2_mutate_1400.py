#!/usr/bin/env python3
"""C2-MUTATE-1400 diagnostic; mutates TEMPORARY Core copies, never Git source."""
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
OUT = ROOT / "evidence" / "c2-mutate-1400"
OUT.mkdir(parents=True, exist_ok=True)
CORE = STAGE / "HL_Live_Copy_Service_Core.py"
# Contract: mutate the EXACT historical Core from the controller's source SHA,
# not the later Coder One branch's tracked Core (different Git blob).
SOURCE = subprocess.check_output(
    ["git", "show", "0a99d215c99b794717ce5b34f46cc299dae09106:_archive/hl_stage2/HL_Live_Copy_Service_Core.py"],
    cwd=ROOT).decode("utf-8-sig")
FILES = [
    "test_core_append_truncate.py",
    "test_core_disk_full.py",
    "test_core_liq_parity.py",
    "test_core_margin_gate_and_single_terminal.py",
    "test_core_off_path_skip.py",
    "test_core_r1_cursor.py",
]
# Anchor/replacement is intentionally exactly ONE source change per temporary
# copy. No replacement is committed, even for a mutant that passes the tests.
MUTANTS = {
"test_core_append_truncate.py": [
 ("remove_partial_truncate",
  "os.truncate(path, size_before)", "pass  # MUTANT: leave partial audit row",
  "APPEND_FAILURE_LEAVES_NO_HALF_ROW"),
 ("drop_audit_spill",
  'if not _spill_row(path, fieldnames, row):\n                raise OSError("audit row could not be persisted to the live file or fallback") from exc',
  'if True:\n                return False  # MUTANT: silently discard append',
  "APPEND_FAILURE_SPILLS_ROW"),
 ("disable_spill_replay",
  "return _replay_audit_fallback(path, fieldnames)",
  "return 0  # MUTANT: lost durable replay",
  "SPILLED_ROW_REPLAYED"),
],
"test_core_disk_full.py": [
 ("bypass_pending_send_audit",
  "self.audit.append_send_attempt(_row, durable=True)",
  "pass  # MUTANT: no fsynced pending_send before physical wire",
  "B1_NO_EXCHANGE_CALL_WHEN_PENDING_ROW_CANNOT_BE_WRITTEN"),
 ("omit_final_attempt_append",
  "self.audit.append_send_attempt(row)  # same attempt_id as the pending_send row: the newest row is the state",
  "pass  # MUTANT: no final send-attempt revision",
  "B3_FINAL_ROW_WRITE_FAILURE_STILL_SENDS_THE_ORDER_ONCE_AND_KEEPS_IT_NAMED"),
 ("mute_append_write_failure",
  "            note_audit_write_failure(path, exc)\n            if not spill_on_failure:",
  "            pass  # MUTANT: suppress audit write failure record\n            if not spill_on_failure:",
  "A3_LOUD_RECORD_OF_THE_FAILURE"),
],
"test_core_liq_parity.py": [
 ("disable_parity_threshold",
  "if follower_dist + 1e-9 < (leader_dist or 0.0):",
  "if False:  # MUTANT: always admit unsafe follower liquidation",
  "L6_PARITY_BLOCKS_WORSE_THAN_SAFEST_LEADER"),
 ("skip_parity_send_gate",
  'if lifecycle in {"ENTRY", "ADD"} and self.cfg.liq_parity_enabled():',
  'if False and lifecycle in {"ENTRY", "ADD"} and self.cfg.liq_parity_enabled():',
  "L6_PARITY_BLOCKS_WORSE_THAN_SAFEST_LEADER"),
 ("allow_unknown_liq_projection",
  "        liq, how = self._follower_projected_liq_px(intent, mark)\n        if liq is None:",
  "        liq, how = self._follower_projected_liq_px(intent, mark)\n        if liq is None:\n            return None  # MUTANT: allow unproved projection",
  "L8_UNKNOWN_PROJECTION_FAILS_CLOSED"),
],
"test_core_margin_gate_and_single_terminal.py": [
 ("bypass_margin_cooldown",
  'if lifecycle in {"ENTRY", "ADD"} and getattr(self, "_margin_reject_until_ms", {}).get(coin_key, 0) > utc_now_ms():',
  'if False and lifecycle in {"ENTRY", "ADD"} and getattr(self, "_margin_reject_until_ms", {}).get(coin_key, 0) > utc_now_ms():',
  "SEND_LANE_GATES_INSUFFICIENT_MARGIN_BEFORE_ANY_ORDER"),
 ("bypass_ioc_cooldown",
  'if lifecycle in {"ENTRY", "ADD"} and getattr(self, "_ioc_no_match_until_ms", {}).get(coin_key, 0) > utc_now_ms():',
  'if False and lifecycle in {"ENTRY", "ADD"} and getattr(self, "_ioc_no_match_until_ms", {}).get(coin_key, 0) > utc_now_ms():',
  "SEND_LANE_GATES_IOC_NO_IMMEDIATE_MATCH_BEFORE_ANY_ORDER"),
 ("duplicate_terminal_on_gate_flip",
  'if str(outcome.get("outcome") or "") == "BLOCKED_AT_PLACE_ORDER":',
  'if False and str(outcome.get("outcome") or "") == "BLOCKED_AT_PLACE_ORDER":',
  "GATE_FLIP_WRITES_EXACTLY_ONE_TERMINAL_ROW"),
],
"test_core_off_path_skip.py": [
 ("skip_master_off_early_exit",
  'if str(send_status) == "MASTER_REAL_ORDERS_OFF":',
  'if False and str(send_status) == "MASTER_REAL_ORDERS_OFF":',
  "OFF_REFUSAL_NEVER_REACHES_THE_REST_PATH"),
 ("fake_exchange_called_on_gate_refusal",
  'return {"status": "err", "response": "BLOCKED_AT_PLACE_ORDER:" + _blocked,\n                    "exchange_called": False,',
  'return {"status": "err", "response": "BLOCKED_AT_PLACE_ORDER:" + _blocked,\n                    "exchange_called": True,  # MUTANT',
  "GATE_REFUSAL_SAYS_THE_EXCHANGE_WAS_NOT_CALLED"),
 ("stamp_post_wait_refusal_as_physical_send",
  "        if _late_block:\n            # the lease wins the message when both would refuse",
  "        if timing is not None and started_key:\n            timing[started_key] = utc_now_ms()  # MUTANT: call stamp before late refusal\n        if _late_block:\n            # the lease wins the message when both would refuse",
  "POST_WAIT_REFUSAL_HAS_NO_CALL_STAMP"),
],
"test_core_r1_cursor.py": [
 ("skip_queued_cursor_floor",
  "return min(int(proposed_ms), floor) if floor and proposed_ms else int(proposed_ms)",
  "return int(proposed_ms)  # MUTANT: queued fills skipped after restart",
  "queued_fill_holds_cursor"),
 ("never_release_handled_cursor_floor",
  "self._pending_ts.pop(_gk, None)",
  "pass  # MUTANT: handled fill continues pinning cursor",
  "handled_cursor_moves_on"),
 ("persist_poll_cursor_past_uncopied_fill",
  "_next = self.leader_cursor_next(w, _next)  # never past a fill still waiting on a worker",
  "_next = int(_next) + 120000  # MUTANT: silently advance past unqueued source fills",
  "poll_queue_full_cursor_holds_unqueued_fill"),
],
}
assert all(len(v) == 3 for v in MUTANTS.values())
assert set(MUTANTS) == set(FILES)

RESULT_RE = re.compile(r"RESULT::(\S+?)_(PASS|FAIL)(?:\s*\|\s*(.*))?$")
TOTAL_RE = re.compile(r"TOTAL=(\d+)\s+FAILED=(\d+)")
sitecustomize = """import socket
def _deny(*a, **k):
    raise RuntimeError('C2_MUTATE_OFFLINE_NETWORK_DENIED')
socket.socket.connect = _deny
socket.socket.connect_ex = _deny
socket.create_connection = _deny
"""
def run_test(fname, code, label):
    work = Path(tempfile.mkdtemp(prefix="c2mut_"))
    try:
        (work / "HL_Live_Copy_Service_Core.py").write_text(code, encoding="utf-8")
        shutil.copy2(STAGE / fname, work / fname)
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
        "coder_tests":"ad384e4922c5e9707abeb072d6ec502bc7691c9f",
        "baseline":[], "mutations":[]}
for file in FILES:
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
