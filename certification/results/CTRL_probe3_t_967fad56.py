"""CONTROL-plane probe, part 3 (card t_967fad56) — carrier-level integrity.

Binds, against the REAL durable carrier origin/control-mailbox (280 envelopes):
    CTRL-ESC   architect escalation can actually traverse the governed path
    CTRL-EVID  handoff evidence discipline, measured on the handoff-typed envelopes
and records the dead-letter census that makes those verdicts non-vacuous.
"""

import collections
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MOD_DIR = r"C:\Users\wigmore\.hermes\state\projects\hyperliquid-build3-repair\lane-artifacts\minimal_transport"
RESULTS = []
FAILURES = []


def record(row, check, ok, active, control, detail=""):
    v = "PASS" if ok else "FAIL"
    print("RESULT::%s::%s::%s:: active=%s control=%s" % (row, check, v, active, control))
    RESULTS.append({"row": row, "check": check, "verdict": v, "active": active,
                    "control": control, "detail": detail})
    if v == "FAIL":
        FAILURES.append(row + "::" + check)


def git(*a):
    return subprocess.run(["git"] + list(a), cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


EVIDENCE_TOKENS = ("TASK_ID", "COMMIT_SHA", "FILES_CHANGED", "LOC", "TESTS", "OUTPUTS",
                   "UNCERTAINTY", "STAND_DOWN_REQUEST")
HANDOFF_TYPES = ("RESULT", "STATUS", "NOTIFICATION")


def main():
    env = load("p3_env", os.path.join(MOD_DIR, "envelope.py"))
    paths = [p for p in git("ls-tree", "-r", "--name-only", "origin/control-mailbox").split()
             if p.startswith("control_mailbox/") and p.endswith(".json")]
    docs = []
    for p in paths:
        raw = git("show", "origin/control-mailbox:" + p)
        try:
            d = json.loads(raw)
        except Exception:
            continue
        if not isinstance(d, dict) or "MESSAGE_ID" not in d:
            continue
        docs.append((p, raw, d))

    # gate verdict for every envelope (the governed intake path)
    gate = {"valid": [], "MISSING_FIELDS": [], "DIGEST_MISMATCH": [], "INVALID_TYPE": [], "other": []}
    for p, raw, d in docs:
        try:
            env.parse_envelope(raw)
            gate["valid"].append((p, d))
        except env.EnvelopeError as exc:
            key = str(exc).split(":")[0]
            gate.setdefault(key, []).append((p, d))

    # ---------------- CTRL-ESC: escalation is deliverable through the governed path ----------------
    escalation = [(p, d) for p, raw, d in docs if str(d.get("TYPE")).upper() == "ESCALATION"]
    esc_rejected = [p for p, d in escalation
                    if any(str(d.get("TYPE")) == str(x.get("TYPE")) and p == xp for xp, x in gate.get("INVALID_TYPE", []))]
    record("CTRL-ESC", "escalation_type_traverses_gate",
           len(escalation) > 0 and len(esc_rejected) == 0,
           "ESCALATION envelopes on carrier=%d, rejected by gate allowlist=%d (%s)"
           % (len(escalation), len(esc_rejected), esc_rejected[:2]),
           "gate allowlist=%s" % list(env.VALID_TYPES),
           "escalation_message_ids=%s" % [d["MESSAGE_ID"] for p, d in escalation][:6])

    record("CTRL-ESC", "escalation_tripwire_present",
           False,
           "no tripwire evaluator (LOC/files/process/dependency/send-path/repeat-failure) exists in the "
           "certified tree; only a manual CONTROL_STATE scope_budget exception records escalation",
           "n/a",
           "control_mailbox ESCALATION envelopes=%d are requests, not evaluated tripwires" % len(escalation))

    # ---------------- CTRL-EVID: handoff evidence discipline on real handoffs ----------------
    handoffs = [(p, d) for p, raw, d in docs if str(d.get("TYPE")).upper() in HANDOFF_TYPES]
    hits = []
    for p, d in handoffs:
        blob = json.dumps(d).upper()
        present = [t for t in EVIDENCE_TOKENS if t in blob]
        hits.append((len(present), d["MESSAGE_ID"], present, p))
    hits.sort(reverse=True)
    full = [h for h in hits if h[0] == len(EVIDENCE_TOKENS)]
    record("CTRL-EVID", "handoff_carries_full_evidence_set",
           len(handoffs) > 0 and len(full) == len(handoffs),
           "handoff envelopes=%d, carrying all 8 evidence fields=0, best=%d/8 (%s)"
           % (len(handoffs), hits[0][0] if hits else 0, hits[0][1] if hits else None),
           "required=%s" % list(EVIDENCE_TOKENS),
           "per-token presence=%s" % json.dumps({t: sum(1 for p, d in handoffs if t in json.dumps(d).upper())
                                                 for t in EVIDENCE_TOKENS}, sort_keys=True))

    # ---------------- dead-letter census (makes the verdicts non-vacuous) ----------------
    census = {
        "carrier_ref": "origin/control-mailbox",
        "envelope_files": len(paths),
        "v1_shaped_envelopes": len(docs),
        "gate_valid": len(gate["valid"]),
        "gate_rejected": {k: len(v) for k, v in gate.items() if k != "valid"},
        "handoff_envelopes": len(handoffs),
        "escalation_envelopes": len(escalation),
    }
    print("CENSUS::%s" % json.dumps(census, sort_keys=True))

    out = os.path.join(HERE, "CTRL_carrier_census_t_967fad56.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"card": "t_967fad56", "part": 3, "census": census, "checks": RESULTS,
                   "failures": FAILURES}, fh, indent=1)
    print("SUMMARY::part3 checks=%d pass=%d fail=%d"
          % (len(RESULTS), sum(1 for r in RESULTS if r["verdict"] == "PASS"), len(FAILURES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
