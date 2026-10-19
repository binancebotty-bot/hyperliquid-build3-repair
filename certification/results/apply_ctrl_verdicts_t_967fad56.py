"""Apply CONTROL-plane verdicts earned by card t_967fad56 to the register.

Only CONTROL rows are touched; every edit cites the artifact that earned it.
Run: python certification/results/apply_ctrl_verdicts_t_967fad56.py
"""

import csv
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.dirname(HERE)
REPO = os.path.dirname(CERT)
JSON_PATH = os.path.join(CERT, "certification_matrix.json")
CSV_PATH = os.path.join(CERT, "certification_matrix.csv")

P1 = "certification/results/CTRL_probe_t_967fad56.json"
P2 = "certification/results/CTRL_probe2_t_967fad56.json"
P3 = "certification/results/CTRL_carrier_census_t_967fad56.json"
SUBJECTS = ("envelope.py sha256 0cceff3286b2dcbeea7089baf7c782d7e355db7d961412834c330a95aac827cc, "
            "push_gate.py sha256 0a45dc8a0f40ee150b838b49ecf4c0f71c3ca0a8956fecae5c188bc5a7974510; "
            "HL_Live_Copy_Service_Core.py sha256 9072aa592331424acbf51cdb5b4246408bb282bb15b57e35787c6843890668e4 "
            "contains none of these control-plane symbols, so CONTROL rows bind to the control-plane modules, not the engine")

PASS_ROWS = {
    "CTRL-I1": (P2, "CTRL-I1::authority_from_fields_not_path",
                "authority comes from envelope FROM/TO fields: bytes filed under control_mailbox/reviewer/ still resolve to the architect target, and identical bytes on any surface keep the same source/target/digest"),
    "CTRL-I2": (P1, "CTRL-I2::role_to_single_canonical_directory",
                "hermes/reviewer/architect resolve to three distinct canonical directories"),
    "CTRL-I3": (P2, "CTRL-I3::ruling_recoverable_from_git",
                "a ruling is recoverable from the carrier alone (message_id B3-C2A-GATE0-PASS-1 plus a commit that resolves in git); a fabricated SHA does not resolve"),
    "CTRL-I4": (P1, "CTRL-I4::push_ref_exactness + deletion_not_authority + wrong_project_no_wake",
                "the gate accepts only refs/heads/control-mailbox on the right project; deletions and foreign projects grant no authority"),
    "CTRL-I6": (P1, "CTRL-I6::deposit_is_not_consumption",
                "a deposited envelope classifies NEW until consumed and REPLAY afterwards"),
    "CTRL-I7": (P1, "CTRL-I7::duplicate_delivery_no_second_effect + identity_collision_fails_closed",
                "duplicate delivery yields REPLAY with exactly one ledger record; same MESSAGE_ID with different payload yields CONFLICT"),
    "CTRL-I8": (P1, "CTRL-I8::unsupported_type_fails_loudly + type_allowlist_not_digest_forgeable",
                "an unsupported TYPE raises INVALID_TYPE even when the attacker recomputes the digest"),
    "CTRL-I9": (P1, "CTRL-I9::multi_file_push_deterministic_order + same_message_twice_collapses",
                "several eligible files in one push are processed in deterministic lexical order; a repeated MESSAGE_ID collapses to one"),
    "CTRL-I18": (P1, "CTRL-I18::tampered_payload_fails_closed + malformed_not_json + missing_fields + bad_directory",
                 "tampered payload, path traversal, non-JSON, missing fields and a non-allowlisted directory all fail closed"),
    "CTRL-HWM": (P2, "CTRL-HWM::no_gate_truth_from_local_state",
                 "the reader-detector is live on a bait consumer and finds 0 actual readers of a local CONTROL_STATE.json among 114 tracked .py files"),
}

FAIL_ROWS = {
    "CTRL-ESC": "CTRL-ESC::escalation_type_traverses_gate + escalation_tripwire_present -- 7 ESCALATION envelopes exist on the carrier, but 1 (B3-C2A-G4-AUTHORITY-ESCALATION-1) is rejected by the gate type allowlist, and no tripwire evaluator (LOC / production files / second process / new dependency / persistent store / second send path / repeat gate failure) exists anywhere in the certified tree. Escalation can be raised but cannot traverse the governed path.",
    "CTRL-EVID": "CTRL-EVID::handoff_carries_full_evidence_set -- of 118 handoff-typed envelopes (RESULT/STATUS/NOTIFICATION) on origin/control-mailbox, 0 carry all 8 required evidence fields; the best carries 5/8. Per-token presence: LOC 199, TASK_ID 111, STAND_DOWN_REQUEST 104, TESTS 65, COMMIT_SHA 40, FILES_CHANGED 8, OUTPUTS 2, UNCERTAINTY 0.",
}

NOT_TESTED_ROWS = {
    "CTRL-GATE0": "CTRL-GATE0::cannot_bind_offline -- needs a real provider PUSH event on refs/heads/control-mailbox plus a correlated wake/consumption receipt. The carrier holds 280 envelope files, but no push event and no consumer receipt can be produced offline.",
    "CTRL-BIND": "CTRL-BIND::cannot_bind_offline -- applicability is OPEN_DECISION (OD-03 controller_uuid_dispute: CONTROL_STATE names 6ac6427b..., CONTROL_CONTRACT names 6ac7a51f...). An open decision cannot be certified by a worker.",
    "CTRL-I5": "CTRL-I5::cannot_bind_offline -- remote-ref absence proof lives in the consumer fetch path, which is not in this repository.",
    "CTRL-I10": "CTRL-I10::cannot_bind_offline -- BUSY/progress detection is a controller-side liveness duty; no implementation in the certified tree.",
    "CTRL-I11": "CTRL-I11::cannot_bind_offline -- stand-down lifecycle is an agent protocol duty; no implementation in the certified tree.",
    "CTRL-I12": "CTRL-I12::cannot_bind_offline -- awaiting-ruling restart persistence is harness state, not in this repository.",
    "CTRL-I13": "CTRL-I13::cannot_bind_offline -- gate-PASS architect wake is a harness/transport duty.",
    "CTRL-I14": "CTRL-I14::cannot_bind_offline -- controller-closes-tasks is an authority rule with no executable control.",
    "CTRL-I15": "CTRL-I15::cannot_bind_offline -- commit-before-review is a handoff duty, verifiable only against a live handoff.",
    "CTRL-I16": "CTRL-I16::cannot_bind_offline -- graphify freshness is checked by an external tool not in this repository.",
    "CTRL-I17": "CTRL-I17::cannot_bind_offline -- one-writer is an authority rule with no executable control.",
    "CTRL-I19": "CTRL-I19::cannot_bind_offline -- EVENT_INGRESS health is produced by the live ingress, not by these modules.",
    "CTRL-I20": "CTRL-I20::cannot_bind_offline -- live provider push proof requires a real delivery event.",
    "CTRL-I21": "CTRL-I21::cannot_bind_offline -- blocker-admission rules are review duties.",
    "CTRL-I22": "CTRL-I22::cannot_bind_offline -- notification-is-not-authority holds by absence of any notification path in these modules; absence alone is not a positive control.",
    "CTRL-I23": "CTRL-I23::cannot_bind_offline -- model/provider routing is a binding-registry field, not code.",
}


def main():
    with open(JSON_PATH, encoding="utf-8-sig") as fh:
        doc = json.load(fh)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                            text=True).stdout.strip()
    stamp = "2026-10-19T12:00:00Z"
    touched = []
    for rec in doc["records"]:
        rid = rec["id"]
        if rid in PASS_ROWS:
            ref, check, why = PASS_ROWS[rid]
            rec.update(result="PASS", evidence_ref=ref, tested_commit=commit, tested_at_utc=stamp,
                       notes="Offline ACTIVE/CONTROL probe %s. %s. Subjects: %s." % (check, why, SUBJECTS))
            touched.append(rid)
        elif rid in FAIL_ROWS:
            rec.update(result="FAIL", evidence_ref=P3, tested_commit=commit, tested_at_utc=stamp,
                       notes="Offline carrier-level probe. %s" % FAIL_ROWS[rid])
            touched.append(rid)
        elif rid in NOT_TESTED_ROWS:
            rec["notes"] = NOT_TESTED_ROWS[rid]
            touched.append(rid)
    with open(JSON_PATH, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    fields = ["id", "area", "feature", "expected_behaviour", "sources", "applicability",
              "proof_network", "open_decisions", "execution_proof", "independent_oracle",
              "negative_tests", "prior_evidence", "result", "evidence_ref", "tested_commit",
              "tested_at_utc", "notes"]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for rec in doc["records"]:
            row = dict(rec)
            for k in ("sources", "open_decisions", "negative_tests"):
                row[k] = " | ".join(rec.get(k) or [])
            w.writerow({k: row.get(k, "") for k in fields})
    counts = {}
    for rec in doc["records"]:
        counts[rec["result"]] = counts.get(rec["result"], 0) + 1
    print("COMMIT::%s" % commit)
    print("UPDATED::%s" % ",".join(touched))
    print("COUNTS::%s" % json.dumps(counts, sort_keys=True))
    print("RECORDS::%d" % len(doc["records"]))


if __name__ == "__main__":
    main()
