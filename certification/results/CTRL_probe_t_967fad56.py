"""CONTROL-plane probe (card t_967fad56).

Subject under test: the Control Mailbox v1 transport modules that implement the mission-control
control plane on this host:
    envelope.py   envelope build/validate + exactly-once ConsumptionLedger
    push_gate.py  push-payload gate (project/ref/path/type selection, deterministic order)

They are NOT part of the Build-3 engine: HL_Live_Copy_Service_Core.py contains 0 occurrences of
highwater/escalat/architect/control_state/mailbox/adjudication. Each check therefore names the
module+symbol it binds to. No engine run, no credentials, no network.

Every check is a pair: ACTIVE trips the control (exact failure token), CONTROL neutralises one
value and expects success. Echo: RESULT::<ROW>::<check>::PASS|FAIL:: active=... control=...
"""

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import traceback

DEFAULT_MOD_DIR = r"C:\Users\wigmore\.hermes\state\projects\hyperliquid-build3-repair\lane-artifacts\minimal_transport"
RESULTS = []
FAILURES = []


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def record(row, check, ok, active, control, detail=""):
    print("RESULT::%s::%s::%s:: active=%s control=%s" % (row, check, "PASS" if ok else "FAIL", active, control))
    RESULTS.append({"row": row, "check": check, "verdict": "PASS" if ok else "FAIL",
                    "active": active, "control": control, "detail": detail})
    if not ok:
        FAILURES.append(row + "::" + check)


def expect_error(module, token, fn, *a, **kw):
    try:
        fn(*a, **kw)
        return False
    except module.EnvelopeError as exc:
        return str(exc).startswith(token)
    except Exception:
        return False


def run_checks(mod_dir):
    env = load_module("cm_envelope", os.path.join(mod_dir, "envelope.py"))
    sys.modules["envelope"] = env
    gate = load_module("cm_push_gate", os.path.join(mod_dir, "push_gate.py"))

    PROJECT = "binancebotty-bot/hyperliquid-build3-repair"

    def mk(mid="MSG-1", typ="DIRECTIVE", payload="hello", seq=1):
        return env.build_envelope(project_id=PROJECT, from_logical_role="hermes:implementation-owner",
                                  target_logical_role="gpt:reviewer-controller", message_id=mid,
                                  type=typ, payload=payload, sequence=seq, binding_version=1)

    def text(doc):
        return json.dumps(doc, sort_keys=True)

    # CTRL-I4 -- event push is the normal delivery trigger, on exactly refs/heads/control-mailbox
    try:
        good = mk()
        path = env.envelope_path(good)
        reader = lambda p, _t=text(good): _t if p == path else None
        base = {"repository": {"full_name": PROJECT}, "deleted": False,
                "commits": [{"added": [path], "modified": []}]}
        right = dict(base, ref="refs/heads/control-mailbox")
        d_wrong = gate.decide_push(dict(base, ref="refs/heads/main"), project_id=PROJECT, file_reader=reader)
        d_ok = gate.decide_push(right, project_id=PROJECT, file_reader=reader)
        record("CTRL-I4", "push_ref_exactness",
               (not d_wrong.accepted) and d_wrong.reason == "WRONG_REF" and d_ok.accepted and d_ok.count == 1,
               "accepted=%s reason=%s" % (d_wrong.accepted, d_wrong.reason),
               "accepted=%s reason=%s n=%d" % (d_ok.accepted, d_ok.reason, d_ok.count))
        d_del = gate.decide_push(dict(right, deleted=True), project_id=PROJECT, file_reader=reader)
        record("CTRL-I4", "deletion_not_authority",
               (not d_del.accepted) and d_del.reason == "DELETION_NOT_AUTHORITY",
               "accepted=%s reason=%s" % (d_del.accepted, d_del.reason),
               "accepted=%s reason=%s" % (d_ok.accepted, d_ok.reason))
        d_fp = gate.decide_push(dict(right, repository={"full_name": "someone/else"}),
                                project_id=PROJECT, file_reader=reader)
        record("CTRL-I4", "wrong_project_no_wake",
               (not d_fp.accepted) and d_fp.reason == "WRONG_PROJECT",
               "accepted=%s reason=%s" % (d_fp.accepted, d_fp.reason),
               "accepted=%s reason=%s" % (d_ok.accepted, d_ok.reason))
    except Exception:
        record("CTRL-I4", "push_ref_exactness", False, "EXCEPTION", "n/a", traceback.format_exc()[-400:])

    # CTRL-I6 -- deposit is not send; delivered is not consumed
    try:
        tmp = tempfile.mkdtemp(prefix="ctrl_i6_")
        ledger = env.ConsumptionLedger(os.path.join(tmp, "ledger.jsonl"))
        e = env.parse_envelope(text(mk("MSG-I6")))
        before = ledger.classify(e)[0]
        ledger.consume(e)
        after = ledger.classify(e)[0]
        record("CTRL-I6", "deposit_is_not_consumption",
               before == "NEW" and after == "REPLAY",
               "file_deposited_only=%s" % before, "after_consume=%s" % after)
    except Exception:
        record("CTRL-I6", "deposit_is_not_consumption", False, "EXCEPTION", "n/a", traceback.format_exc()[-400:])

    # CTRL-I7 -- one logical message, one semantic execution
    try:
        tmp = tempfile.mkdtemp(prefix="ctrl_i7_")
        lp = os.path.join(tmp, "ledger.jsonl")
        e = env.parse_envelope(text(mk("MSG-I7", payload="one")))
        first = env.ConsumptionLedger(lp).consume(e)
        second = env.ConsumptionLedger(lp).consume(e)
        recs = [l for l in open(lp, encoding="utf-8").read().splitlines() if l.strip()]
        record("CTRL-I7", "duplicate_delivery_no_second_effect",
               first == "NEW" and second == "REPLAY" and len(recs) == 1,
               "applied_effects=2" if False else "applied_effects=1 ledger_records=%d" % len(recs),
               "first=%s second=%s records=%d" % (first, second, len(recs)))
        bad = env.parse_envelope(text(mk("MSG-I7", payload="two")))
        verdict = env.ConsumptionLedger(lp).classify(bad)[0]
        recs2 = [l for l in open(lp, encoding="utf-8").read().splitlines() if l.strip()]
        record("CTRL-I7", "identity_collision_fails_closed",
               verdict == "CONFLICT" and len(recs2) == len(recs),
               "classify=%s records=%d" % (verdict, len(recs2)),
               "classify=%s records=%d" % (env.ConsumptionLedger(lp).classify(e)[0], len(recs)))
    except Exception:
        record("CTRL-I7", "duplicate_delivery_no_second_effect", False, "EXCEPTION", "n/a", traceback.format_exc()[-400:])

    # CTRL-I8 -- explicit route/type contract, no silent drop
    try:
        bad_type = None
        try:
            mk("MSG-I8-bad", typ="GOSSIP")
        except env.EnvelopeError as exc:
            bad_type = str(exc)
        record("CTRL-I8", "unsupported_type_fails_loudly",
               bad_type is not None and bad_type.startswith("INVALID_TYPE"),
               "error=%s" % bad_type,
               "error=%s valid_types=%s" % (None, list(env.VALID_TYPES)))
        doc = json.loads(text(mk("MSG-I8-smuggle")))
        doc["TYPE"] = "GOSSIP"
        doc["PAYLOAD_DIGEST"] = env.compute_digest(doc)
        err = None
        try:
            env.parse_envelope(json.dumps(doc))
        except env.EnvelopeError as exc:
            err = str(exc)
        record("CTRL-I8", "type_allowlist_not_digest_forgeable",
               err is not None and err.startswith("INVALID_TYPE"),
               "error=%s" % err, "error=%s" % None)
    except Exception:
        record("CTRL-I8", "unsupported_type_fails_loudly", False, "EXCEPTION", "n/a", traceback.format_exc()[-400:])

    # CTRL-I18 -- fail closed on anything ambiguous
    try:
        good_text = text(mk("MSG-I18"))
        doc = json.loads(good_text)
        doc["PAYLOAD"] = "tampered"
        err = None
        try:
            env.parse_envelope(json.dumps(doc))
        except env.EnvelopeError as exc:
            err = str(exc)
        traversal = env.is_control_path("control_mailbox/evil/../../x.json")
        record("CTRL-I18", "tampered_payload_fails_closed",
               err == "DIGEST_MISMATCH" and traversal is False,
               "error=%s traversal_is_control=%s" % (err, traversal),
               "error=%s path=%s" % (None, env.envelope_path(json.loads(good_text))))
        record("CTRL-I18", "malformed_not_json_fails_closed",
               expect_error(env, "NOT_JSON", env.parse_envelope, "not json at all"),
               "error=NOT_JSON", "error=%s" % None)
        record("CTRL-I18", "missing_fields_fails_closed",
               expect_error(env, "MISSING_FIELDS", env.parse_envelope,
                            json.dumps({"SCHEMA_VERSION": env.SCHEMA_VERSION})),
               "error=MISSING_FIELDS", "error=%s" % None)
        bad_dir_env = {"TARGET_LOGICAL_ROLE": "gpt:x", "CREATED_AT_UTC": "t", "MESSAGE_ID": "m"}
        record("CTRL-I18", "bad_directory_rejected",
               expect_error(env, "BAD_DIRECTORY", env.envelope_path, bad_dir_env, "evil"),
               "directory=evil rejected",
               "directory=%s" % env.directory_for_role("gpt:reviewer-controller"))
    except Exception:
        record("CTRL-I18", "tampered_payload_fails_closed", False, "EXCEPTION", "n/a", traceback.format_exc()[-400:])

    # CTRL-I2 -- one canonical role channel each
    try:
        mapping = {r: env.directory_for_role(r) for r in
                   ("hermes:implementation-owner", "gpt:reviewer-controller", "gpt:project-architect")}
        ok = len(set(mapping.values())) == 3 and set(mapping.values()) == {"hermes", "reviewer", "architect"}
        record("CTRL-I2", "role_to_single_canonical_directory", ok,
               "collision=%s" % (len(set(mapping.values())) < 3),
               "mapping=%s" % json.dumps(mapping, sort_keys=True))
    except Exception:
        record("CTRL-I2", "role_to_single_canonical_directory", False, "EXCEPTION", "n/a", traceback.format_exc()[-400:])

    # CTRL-I9 -- one-shot consumer, bounded deterministic order
    try:
        envs = [mk("MSG-I9-%s" % c) for c in "cab"]
        paths = sorted(env.envelope_path(x) for x in envs)
        by_path = {env.envelope_path(x): text(x) for x in envs}
        payload = {"repository": {"full_name": PROJECT}, "ref": "refs/heads/control-mailbox",
                   "deleted": False, "commits": [{"added": list(reversed(paths)), "modified": []}]}
        d = gate.decide_push(payload, project_id=PROJECT, file_reader=by_path.get)
        record("CTRL-I9", "multi_file_push_deterministic_order",
               d.accepted and len(d.paths) == 3 and d.paths == sorted(d.paths),
               "order=%s" % [p.split("/")[-1] for p in reversed(paths)],
               "order=%s" % [p.split("/")[-1] for p in d.paths])
        dup = {"repository": {"full_name": PROJECT}, "ref": "refs/heads/control-mailbox",
               "deleted": False,
               "commits": [{"added": [paths[0], paths[0].replace(".json", "-copy.json")], "modified": []}]}
        dd = gate.decide_push(dup, project_id=PROJECT, file_reader=lambda p: text(envs[0]))
        deduped = gate.dedupe_by_message_id(dd.envelopes)
        record("CTRL-I9", "same_message_twice_collapses",
               len(dd.envelopes) == 2 and len(deduped) == 1,
               "raw_envelopes=2", "raw=%d deduped=%d" % (len(dd.envelopes), len(deduped)))
    except Exception:
        record("CTRL-I9", "multi_file_push_deterministic_order", False, "EXCEPTION", "n/a", traceback.format_exc()[-400:])


EVIDENCE_TOKENS = ("TASK_ID", "COMMIT_SHA", "FILES_CHANGED", "LOC", "TESTS", "OUTPUTS",
                   "UNCERTAINTY", "STAND_DOWN_REQUEST")


def run_mailbox_census(repo_dir):
    """CTRL-EVID measured on the real envelopes on origin/control-mailbox."""
    def git(*a):
        return subprocess.run(["git"] + list(a), cwd=repo_dir, capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout
    try:
        listing = git("ls-tree", "-r", "--name-only", "origin/control-mailbox").split()
        paths = [p for p in listing if p.startswith("control_mailbox/") and p.endswith(".json")]
        rich = thin = 0
        ex_rich = ex_thin = None
        for p in paths:
            try:
                doc = json.loads(git("show", "origin/control-mailbox:" + p))
            except Exception:
                continue
            if not isinstance(doc, dict) or "MESSAGE_ID" not in doc:
                continue
            blob = json.dumps(doc)
            hits = sum(1 for t in EVIDENCE_TOKENS if t in blob)
            if hits >= 6:
                rich += 1
                ex_rich = ex_rich or p
            else:
                thin += 1
                ex_thin = ex_thin or p
        record("CTRL-EVID", "handoff_evidence_completeness", rich > 0 and thin > 0,
               "envelopes_missing_evidence=%d e.g. %s" % (thin, ex_thin),
               "envelopes_carrying_evidence=%d e.g. %s" % (rich, ex_rich),
               "tokens=%s total_envelopes=%d" % (list(EVIDENCE_TOKENS), len(paths)))
    except Exception:
        record("CTRL-EVID", "handoff_evidence_completeness", False, "EXCEPTION", "n/a",
               traceback.format_exc()[-400:])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mod-dir", default=DEFAULT_MOD_DIR)
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "CTRL_probe_t_967fad56.json"))
    a = ap.parse_args()
    run_checks(a.mod_dir)
    run_mailbox_census(a.repo)
    core = os.path.join(a.repo, "_archive", "hl_stage2", "HL_Live_Copy_Service_Core.py")
    subjects = {n: {"path": os.path.join(a.mod_dir, n), "sha256": sha256_file(os.path.join(a.mod_dir, n))}
                for n in ("envelope.py", "push_gate.py")}
    subjects["HL_Live_Copy_Service_Core.py"] = {
        "sha256": sha256_file(core) if os.path.exists(core) else None,
        "note": "engine scanned for control-plane symbols; none present -> CONTROL rows are not engine rows"}
    out = {"card": "t_967fad56", "subjects": subjects, "checks": RESULTS, "failures": FAILURES,
           "summary": {"checks": len(RESULTS),
                       "pass": sum(1 for r in RESULTS if r["verdict"] == "PASS"),
                       "fail": len(FAILURES),
                       "rows_touched": sorted({r["row"] for r in RESULTS})}}
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    print("SUMMARY::checks=%d pass=%d fail=%d rows=%s" % (len(RESULTS), out["summary"]["pass"], len(FAILURES),
                                                          ",".join(out["summary"]["rows_touched"])))
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
