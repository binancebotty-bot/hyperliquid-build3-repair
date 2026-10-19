"""CONTROL-plane probe, part 2 (card t_967fad56).

Binds CTRL-I1, CTRL-I3, CTRL-HWM offline and records a named census for every CONTROL row
that has no executable control in the certified tree.
"""

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MOD_DIR = r"C:\Users\wigmore\.hermes\state\projects\hyperliquid-build3-repair\lane-artifacts\minimal_transport"
RESULTS = []
FAILURES = []


def record(row, check, ok, active, control, detail="", verdict=None):
    v = verdict or ("PASS" if ok else "FAIL")
    print("RESULT::%s::%s::%s:: active=%s control=%s" % (row, check, v, active, control))
    RESULTS.append({"row": row, "check": check, "verdict": v,
                    "active": active, "control": control, "detail": detail})
    if v == "FAIL":
        FAILURES.append(row + "::" + check)


def read(p):
    with open(p, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def check_i1():
    env = load("i1_env", os.path.join(MOD_DIR, "envelope.py"))
    P = "binancebotty-bot/hyperliquid-build3-repair"
    doc = env.build_envelope(project_id=P, from_logical_role="hermes:implementation-owner",
                             target_logical_role="gpt:project-architect", message_id="MSG-I1",
                             type="RESULT", payload="p", sequence=7, binding_version=2)
    text = json.dumps(doc, sort_keys=True)
    a = env.parse_envelope(text)
    b = env.parse_envelope(text)
    routed = env.directory_for_role(a.target_role)
    same = (b.target_role == a.target_role and b.source_role == a.source_role
            and b.digest == a.digest and b.message_id == a.message_id)
    record("CTRL-I1", "authority_from_fields_not_path", routed == "architect" and same,
           "path_dir=reviewer field_target=%s routed=%s" % (a.target_role, routed),
           "identical bytes keep target=%s source=%s" % (b.target_role, b.source_role),
           "reviewer_path=%s field_path=%s" % (env.envelope_path(doc, "reviewer"), env.envelope_path(doc)))


def git(*a):
    return subprocess.run(["git"] + list(a), cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def check_i3():
    paths = [p for p in git("ls-tree", "-r", "--name-only", "origin/control-mailbox").split()
             if p.startswith("control_mailbox/") and p.endswith(".json")]
    found = None
    for p in paths:
        try:
            d = json.loads(git("show", "origin/control-mailbox:" + p))
        except Exception:
            continue
        if isinstance(d, dict) and d.get("MESSAGE_ID"):
            m = re.search(r"\b[0-9a-f]{40}\b", json.dumps(d))
            if m:
                found = (p, d["MESSAGE_ID"], m.group(0))
                break
    if not found:
        record("CTRL-I3", "ruling_recoverable_from_git", False, "no 40-hex commit ref in any envelope", "n/a")
        return
    path, mid, sha = found
    real = git("cat-file", "-t", sha).strip() == "commit"
    bogus = "0" * 40
    fake = git("cat-file", "-t", bogus).strip() in ("commit", "tree", "blob")
    record("CTRL-I3", "ruling_recoverable_from_git", bool(mid) and real and not fake,
           "carrier_only message_id=%s commit=%s resolves=%s" % (mid, sha[:12], real),
           "fabricated_commit=%s resolves=%s" % (bogus[:12], fake), "envelope=%s" % path)


SCAN = re.compile(r"CONTROL_STATE")


def check_hwm():
    tmp = tempfile.mkdtemp(prefix="ctrl_hwm_")
    bait = os.path.join(tmp, "bait.py")
    with open(bait, "w", encoding="utf-8") as fh:
        fh.write("import json\n"
                 "STATE='C:/x/CONTROL_STATE.json'\n"
                 "def gate_truth():\n"
                 "    return json.load(open(STATE))['current_gate']\n")
    def offenders_in(text):
        lines = text.splitlines()
        bound = set()
        for line in lines:
            m = re.match(r"\s*([A-Za-z_]\w*)\s*=\s*[\"'].*CONTROL_STATE\.json", line)
            if m:
                bound.add(m.group(1))
        found = []
        for i, line in enumerate(lines, 1):
            direct = re.search(r"(open|read_text|json\.load)\s*\(.*CONTROL_STATE\.json", line) \
                if "CONTROL_STATE" in line else None
            indirect = any(re.search(r"(open|read_text|json\.load)\s*\([^)]*\b%s\b" % re.escape(v), line)
                           for v in bound)
            if direct or indirect:
                found.append(i)
        return found

    bait_hits = offenders_in(read(bait))
    tracked = [p for p in git("ls-tree", "-r", "--name-only", "origin/main").split() if p.endswith(".py")]
    real = {}
    for rel in tracked:
        hits = offenders_in(git("show", "origin/main:" + rel))
        if hits:
            real[rel] = hits
    clean = len(real) == 0
    record("CTRL-HWM", "no_gate_truth_from_local_state", bool(bait_hits) and clean,
           "bait consumer flagged at lines %s (scanner is live)" % bait_hits,
           "py files scanned=%d, actual readers of CONTROL_STATE.json=%d, offenders=%s"
           % (len(tracked), len(real), json.dumps(real, sort_keys=True)[:300]))


UNBOUND = {
    "CTRL-GATE0": "requires a real provider PUSH event on refs/heads/control-mailbox plus a correlated wake/consumption receipt; not synthesizable offline",
    "CTRL-BIND": "row applicability is OPEN_DECISION (OD-03 controller_uuid_dispute); an open decision cannot be certified",
    "CTRL-ESC": "census found no ARCHITECT_REVIEW_REQUIRED / tripwire evaluation in the certified tree; escalation is a protocol duty with no executable control",
    "CTRL-I5": "remote-ref absence proof lives in the consumer fetch path, which is not in this repository",
    "CTRL-I10": "BUSY/progress detection is a controller-side liveness duty",
    "CTRL-I11": "stand-down lifecycle is an agent protocol duty",
    "CTRL-I12": "awaiting-ruling restart persistence is harness state",
    "CTRL-I13": "gate-PASS architect wake is a harness/transport duty",
    "CTRL-I14": "controller-closes-tasks is an authority rule",
    "CTRL-I15": "commit-before-review is a handoff duty, verifiable only against a live handoff",
    "CTRL-I16": "graphify freshness is checked by an external tool not in this repository",
    "CTRL-I17": "one-writer is an authority rule",
    "CTRL-I19": "EVENT_INGRESS health flag is produced by the live ingress",
    "CTRL-I20": "live provider push proof requires a real delivery event",
    "CTRL-I21": "blocker-admission rules are review duties",
    "CTRL-I22": "notification-is-not-authority holds by absence of any notification path; absence alone is not a positive control",
    "CTRL-I23": "model/provider routing is a binding-registry field",
}


def main():
    for fn, row in ((check_i1, "CTRL-I1"), (check_i3, "CTRL-I3"), (check_hwm, "CTRL-HWM")):
        try:
            fn()
        except Exception as exc:
            record(row, fn.__name__, False, "EXCEPTION:%s" % type(exc).__name__, "n/a", str(exc)[:300])
    for row, why in sorted(UNBOUND.items()):
        record(row, "cannot_bind_offline", False, "NOT_TESTED: " + why, "n/a", verdict="NOT_TESTED")
    out = os.path.join(HERE, "CTRL_probe2_t_967fad56.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"card": "t_967fad56", "part": 2, "checks": RESULTS, "failures": FAILURES,
                   "subjects": {n: hashlib.sha256(read(os.path.join(MOD_DIR, n)).encode("utf-8")).hexdigest()
                                for n in ("envelope.py", "push_gate.py")}}, fh, indent=1)
    print("SUMMARY::part2 checks=%d pass=%d fail=%d unbound=%d" % (
        len(RESULTS), sum(1 for r in RESULTS if r["verdict"] == "PASS"), len(FAILURES), len(UNBOUND)))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
