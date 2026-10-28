"""Scratch-only proofs for apply_hotfix state invariants and swap outcomes.

Why this file looks the way it does - each rule is a defect the previous revision had:

1. It must COMPILE AND RUN. The previous revision nested an eleven-manager ``with`` block
   inside a ``for`` inside a function and died with
   ``SyntaxError: too many statically nested blocks`` on CPython 3.11, so not one of its
   assertions ever executed. Patches now go through ``contextlib.ExitStack``.
2. Assertions bind to OBSERVABLE OUTCOMES - a launch spec that was or was not restored, a
   pointer file, an on-disk swap record, an exit code, a printed verdict - not to
   "function X was called".
3. Every load-bearing guard has a NON-VACUITY control: a scratch mutation of
   ``apply_hotfix.py`` that removes the guard must make the same assertion go RED. The
   mutation is applied to a temporary copy only; the committed helper is never edited.
"""
import csv
import importlib.util
import io
import json
import shutil
import sys
import tempfile
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("apply_hotfix", HERE / "apply_hotfix.py")
HOTFIX = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules.setdefault("apply_hotfix", HOTFIX)
SPEC.loader.exec_module(HOTFIX)

BASELINE = {
    "anchor_sha256": "anchor", "anchor_t0_ms": 1,
    "live_config_sha256": "config", "live_config_semantic_sha256": "config_semantic",
    "manual_live_positions_sha256": "manual", "xyz_position_state_sha256": "xyz",
    "user_owned_sha256": "user",
}
OLD_SHA, NEW_SHA = "a" * 40, "b" * 40


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mutated_copy(root, name, old, new):
    """Copy the committed helper to scratch, apply one textual mutation, import it."""
    target = root / ("mut_" + name)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(HERE / "stop_pair.py", target / "stop_pair.py")
    source = (HERE / "apply_hotfix.py").read_text(encoding="utf-8")
    if old not in source:
        raise AssertionError("mutation anchor not found: " + old)
    (target / "apply_hotfix.py").write_text(source.replace(old, new, 1), encoding="utf-8")
    return load_module(target / "apply_hotfix.py", "apply_hotfix_" + name)


def make_pair(root, name="pair"):
    pair = root / name
    state = pair / "run8" / "state_scratch"
    state.mkdir(parents=True)
    (state / "PAIR_START_ANCHOR.json").write_text(json.dumps({"t0_ms": 1}), encoding="utf-8")
    (state / "live_config.json").write_text(
        json.dumps({"wallets": {"live": {"mode": "LIVE"}, "user": {"mode": "USER"}}}), encoding="utf-8")
    (pair / "CURRENT_AUDIT_DIR").write_text(str(state), encoding="utf-8")
    old_root, new_root = pair / "old", pair / "new"
    old_root.mkdir()
    new_root.mkdir()
    source = pair / "source.csv"
    source.write_text("leader_fill_id,time\n", encoding="utf-8")
    env = {"HL_LIVE_AUDIT_DIR": str(state), "HL_LIVE_SOURCE_FILLS": str(source)}
    spec = {"cwd": str(old_root / "_archive" / "hl_stage2"),
            "script": str(old_root / "_archive" / "hl_stage2" / HOTFIX.TARGET),
            "build_sha": OLD_SHA, "env": dict(env)}
    launch_env = pair / "core_launch_env.json"
    launch_env.write_text(json.dumps(spec), encoding="utf-8")
    return {"pair": pair, "state": state, "old": old_root, "new": new_root, "source": source,
            "spec": spec, "launch_env": launch_env, "last_swap": pair / "last_swap.json"}


def swap_stack(module, pair, gap_ms, events, precompile=None, rewrite=None, pointer=None,
               start=None, track=None, proof=None):
    stack = ExitStack()
    real_save = module.save_swap_record

    def save_record(*args, **kwargs):
        events.append("save-record")
        return real_save(*args, **kwargs)

    stack.enter_context(patch.object(module, "save_swap_record", side_effect=save_record))
    stack.enter_context(patch.object(module, "LAUNCH_ENV", pair["launch_env"]))
    stack.enter_context(patch.object(module, "LAST_SWAP", pair["last_swap"]))
    stack.enter_context(patch.object(module, "launch_spec", return_value=(
        dict(pair["spec"]), dict(pair["spec"]["env"]), pair["state"])))
    stack.enter_context(patch.object(module, "validate_pair", return_value=(
        {"pid": 1234}, pair["old"], OLD_SHA, 5678)))
    stack.enter_context(patch.object(module, "checkout_info", return_value=(pair["new"], NEW_SHA)))
    stack.enter_context(patch.object(module, "precompile", side_effect=(
        precompile or (lambda _p: events.append("precompile")))))
    stack.enter_context(patch.object(module, "snapshot_state", return_value=dict(BASELINE)))
    stack.enter_context(patch.object(module, "sent_keys", return_value=set()))
    stack.enter_context(patch.object(module, "backup_state", return_value=pair["pair"] / "backup"))
    stack.enter_context(patch.object(module, "stop_pair", side_effect=(
        lambda *_a: events.append("stop"))))
    stack.enter_context(patch.object(module, "rewrite_launch_spec", side_effect=(
        rewrite or (lambda *_a: events.append("rewrite")))))
    stack.enter_context(patch.object(module, "atomic_text", side_effect=(
        pointer or (lambda *_a: events.append("pointer")))))
    stack.enter_context(patch.object(module, "start_pair", side_effect=(
        start or (lambda *_a: (events.append("start"),
                               {"pair": "STARTED", "engine_pid": 4321})[1]))))
    stack.enter_context(patch.object(module, "tracked_start_ui", side_effect=(
        track or (lambda *_a: events.append("track-ui")))))
    stack.enter_context(patch.object(module, "first_healthy_cycle", side_effect=(
        lambda _s, _p, after: (after + gap_ms, {}))))
    stack.enter_context(patch.object(module, "replay_proof", side_effect=(
        proof or (lambda *_a: {"gap_fills": 0, "gap_intent_rows": 0, "duplicate_attempts": 0,
                               "unresolved": 0, "cursors_caught_up": 1, "merged_buckets": 0,
                               "buckets": 0, "failed_buckets": 0}))))
    stack.enter_context(patch.object(module.SP, "pids", return_value=[]))
    stack.enter_context(patch.object(module.SP, "listener", return_value=None))
    stack.enter_context(patch.object(module.time, "sleep"))
    return stack


def run_swap(module, pair, gap_ms, events=None, **kwargs):
    if events is None:
        events = []
    output = io.StringIO()
    with swap_stack(module, pair, gap_ms, events, **kwargs), redirect_stdout(output):
        try:
            result = module.perform_swap(pair["new"], NEW_SHA, 8031, False)
        except module.HotfixError as exc:
            return {"raised": exc, "events": events, "output": output.getvalue(), "result": None}
    return {"raised": None, "events": events, "output": output.getvalue(), "result": result}


def check_timestamp_and_digest_rules(root):
    manual = root / "manual_live_positions.json"
    xyz = root / "xyz_position_state.json"
    config = root / "live_config.json"
    manual.write_text(json.dumps({"BTC": {"signed_size": 1, "last_updated_at": "before"}}), encoding="utf-8")
    manual_before = HOTFIX.digest_json(manual, manual.name)
    manual.write_text(json.dumps({"BTC": {"signed_size": 1, "last_updated_at": "after"}}), encoding="utf-8")
    assert HOTFIX.digest_json(manual, manual.name) == manual_before

    xyz.write_text(json.dumps({"updated_at": "before", "updated_at_ms": 1,
                               "positions_by_coin": {"BTC": 1}}), encoding="utf-8")
    xyz_before = HOTFIX.digest_json(xyz, xyz.name)
    xyz.write_text(json.dumps({"updated_at": "after", "updated_at_ms": 2,
                               "positions_by_coin": {"BTC": 1}}), encoding="utf-8")
    assert HOTFIX.digest_json(xyz, xyz.name) == xyz_before

    config.write_text(json.dumps({"wallets": {"user": {"mode": "USER", "sleeve": 1}}}), encoding="utf-8")
    config_before = HOTFIX.digest_json(config, config.name)
    raw_before = config.read_bytes()
    config.write_text(json.dumps({"wallets": {"user": {"sleeve": 1, "mode": "USER"}}}, indent=4),
                      encoding="utf-8")
    assert config.read_bytes() != raw_before, "raw-only rewrite must change bytes"
    assert HOTFIX.digest_json(config, config.name) == config_before, "key order/indent is not semantic"
    config.write_text(json.dumps({"wallets": {"user": {"mode": "USER", "sleeve": 2}}}), encoding="utf-8")
    assert HOTFIX.digest_json(config, config.name) != config_before, "sleeve change must be semantic"

    assert HOTFIX.user_owned_digest({"wallets": {"user": {"mode": "USER", "sleeve": 1}}}) != \
           HOTFIX.user_owned_digest({"wallets": {"user": {"mode": "USER", "sleeve": 2}}})
    assert HOTFIX.user_owned_digest({"wallets": {"live": {"mode": "LIVE", "sleeve": 9},
                                                 "user": {"mode": "USER", "sleeve": 1}}}) == \
           HOTFIX.user_owned_digest({"wallets": {"user": {"mode": "USER", "sleeve": 1}}}), \
        "LIVE wallet churn must not move the USER-owned digest"


def _replay_fixture(root, source):
    state = root / "state"
    append_only = state / "append_only"
    append_only.mkdir(parents=True)
    (state / "clean_core_runtime_state.json").write_text(
        json.dumps({"last_leader_poll_cursor_ms": {"0xwallet": 149}}), encoding="utf-8")
    (state / "live_integrity_status.json").write_text(json.dumps({
        "hard_copy_invariant": {"historical_unresolved_active_red_count": 0},
        "counts": {"open_late_fill_incidents": 0}}), encoding="utf-8")
    # Bucket coverage keys intents by (wallet, coin, side, interval), so the fixture must
    # carry the same provenance columns production writes - a two-column stub cannot prove
    # coverage and would fail for the wrong reason.
    (append_only / "order_intents.csv").write_text(
        "created_at_ms,leader_fill_id,leader_wallet,coin,leader_side,leader_notional,"
        "leader_fill_timestamp_ms\n121,fill-1,leader,BTC,B,1,120\n", encoding="utf-8")
    (append_only / "send_attempts.csv").write_text("created_at_ms,wallet,leader_fill_id\n",
                                                    encoding="utf-8")
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["leader_fill_id", "user", "coin", "side",
                                                    "px", "sz", "time"])
        writer.writeheader()
        writer.writerow({"leader_fill_id": "fill-1", "user": "leader", "coin": "BTC",
                         "side": "B", "px": "1", "sz": "1", "time": 120})
    return state


def check_replay_proof(root, source):
    state = _replay_fixture(root, source)

    def expect_error(fragment, **snapshot):
        with patch.object(HOTFIX, "snapshot_state", return_value=dict(BASELINE, **snapshot)):
            try:
                HOTFIX.replay_proof(state, BASELINE, set(), source, 100, 150, ["0xwallet"])
            except HOTFIX.HotfixError as exc:
                assert fragment in str(exc), (fragment, str(exc))
            else:
                raise AssertionError("guard did not fire: " + fragment)

    with patch.object(HOTFIX, "snapshot_state", return_value=BASELINE):
        try:
            HOTFIX.replay_proof(state, BASELINE, set(), source, 100, 150, ["0xwallet"])
        except HOTFIX.HotfixError as exc:
            assert "not caught up" in str(exc), exc
        else:
            raise AssertionError("poll cursor before the first healthy cycle must not pass")
        runtime = json.loads((state / "clean_core_runtime_state.json").read_text(encoding="utf-8"))
        runtime["last_leader_poll_cursor_ms"]["0xwallet"] = 150
        (state / "clean_core_runtime_state.json").write_text(json.dumps(runtime), encoding="utf-8")
        proof = HOTFIX.replay_proof(state, BASELINE, set(), source, 100, 150, ["0xwallet"])
        assert proof == {"gap_fills": 1, "gap_intent_rows": 1, "duplicate_attempts": 0,
                         "unresolved": 0, "cursors_caught_up": 1,
                         "proof_label": "bucket-level coverage", "buckets": 1,
                         "bucket_width_ms": HOTFIX.BUCKET_WIDTH_MS,
                         "bucket_provenance": "leader_fill_time",
                         "failed_buckets": 0, "merged_buckets": 0}, proof
        expect_error("live_config_semantic_sha256", live_config_semantic_sha256="semantic_changed")
        expect_error("same-state invariant changed: user_owned_sha256", user_owned_sha256="user_changed")
    with (state / "append_only" / "send_attempts.csv").open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["created_at_ms", "wallet", "leader_fill_id"])
        writer.writerow({"created_at_ms": 130, "wallet": "0xwallet", "leader_fill_id": "fill-1"})
    with patch.object(HOTFIX, "snapshot_state", return_value=BASELINE):
        try:
            HOTFIX.replay_proof(state, BASELINE, {("0xwallet", "fill-1")}, source, 100, 150, ["0xwallet"])
        except HOTFIX.HotfixError as exc:
            assert "another send attempt" in str(exc)
        else:
            raise AssertionError("previously-sent gap fill must not pass")


def check_mutation_semantic_config_guard(root, source):
    """NEGATIVE CONTROL: drop the semantic key from the invariant loop; the check must go green."""
    state = _replay_fixture(root / "mut_sem", source)
    runtime = json.loads((state / "clean_core_runtime_state.json").read_text(encoding="utf-8"))
    runtime["last_leader_poll_cursor_ms"]["0xwallet"] = 150
    (state / "clean_core_runtime_state.json").write_text(json.dumps(runtime), encoding="utf-8")
    drifted = dict(BASELINE, live_config_semantic_sha256="semantic_changed")

    def outcome(module):
        with patch.object(module, "snapshot_state", return_value=drifted):
            try:
                module.replay_proof(state, BASELINE, set(), source, 100, 150, ["0xwallet"])
            except module.HotfixError as exc:
                return "RAISED:" + str(exc)
        return "PASSED"

    assert outcome(HOTFIX) == "RAISED:same-state invariant changed: live_config_semantic_sha256"
    mutant = mutated_copy(root, "no_semantic_key",
                          'for key in ("anchor_sha256", "anchor_t0_ms", "live_config_semantic_sha256",',
                          'for key in ("anchor_sha256", "anchor_t0_ms",')
    assert outcome(mutant) == "PASSED", "mutation control failed: semantic guard is not load-bearing"


def check_swap_pass_and_boundary(root):
    """Outcome-bound: exit code, printed verdict, call order, and the on-disk swap record."""
    for gap_ms, expected in ((12_345, 0), (19_999, 0), (20_000, 1), (45_000, 1)):
        pair = make_pair(root, "gap_%d" % gap_ms)
        out = run_swap(HOTFIX, pair, gap_ms)
        assert out["raised"] is None, out["raised"]
        assert out["result"] == expected, (gap_ms, out["result"])
        assert ("HOTFIX SWAP PASS" in out["output"]) == (gap_ms < 20_000), (gap_ms, out["output"][-300:])
        assert ("FAIL: pair downtime" in out["output"]) == (gap_ms >= 20_000), (gap_ms, out["output"][-300:])
        assert "deactivation_to_healthy_ms   %d / 20000" % gap_ms in out["output"]
        assert out["events"] == ["precompile", "stop", "rewrite", "pointer", "start", "track-ui",
                                 "save-record"], out["events"]
        record = json.loads(pair["last_swap"].read_text(encoding="utf-8"))
        assert record["previous_sha"] == OLD_SHA and record["current_sha"] == NEW_SHA, record
        assert record["current_checkout"] == str(pair["new"]), record
        assert Path(record["state_dir"]) == pair["state"], record
        # C7-DIR-43(4): the coverage proof must be persisted to its own file beside the swap
        # record, carrying merged_buckets, without touching audited state or ledgers.
        proof_path = pair["last_swap"].with_name(pair["last_swap"].stem + "_proof.json")
        assert proof_path.is_file(), "coverage proof must be persisted beside the swap record"
        proof_doc = json.loads(proof_path.read_text(encoding="utf-8"))
        assert "proof" in proof_doc and "saved_at" in proof_doc, proof_doc
        assert "merged_buckets" in proof_doc["proof"], proof_doc["proof"]


def check_mutation_gap_threshold(root):
    """NEGATIVE CONTROL: with a huge MAX_GAP_MS the same 20 s case must silently pass."""
    real = run_swap(HOTFIX, make_pair(root, "mut_gap_real"), 20_000)
    assert real["result"] == 1, ("unmutated 20s gap must fail", real["result"])
    mutant = mutated_copy(root, "huge_gap", "MAX_GAP_MS = 20_000", "MAX_GAP_MS = 10 ** 9")
    mutated = run_swap(mutant, make_pair(root, "mut_gap_wide"), 20_000)
    assert mutated["result"] == 0, ("mutation control failed: gap bound is not load-bearing",
                                    mutated["result"])


def check_precompile_failure_never_stops_the_pair(root):
    """A failing preflight must leave the running pair completely untouched."""
    pair = make_pair(root, "precompile_fail")
    before = pair["launch_env"].read_bytes()
    pointer_before = (pair["pair"] / "CURRENT_AUDIT_DIR").read_bytes()

    def boom(_path):
        raise HOTFIX.HotfixError("precompile failed: injected")

    out = run_swap(HOTFIX, pair, 12_345, precompile=boom)
    assert isinstance(out["raised"], HOTFIX.HotfixError), out["raised"]
    assert out["events"] == [], ("nothing may be stopped/started before preflight", out["events"])
    assert pair["launch_env"].read_bytes() == before, "launch spec must be byte-identical"
    assert (pair["pair"] / "CURRENT_AUDIT_DIR").read_bytes() == pointer_before, "pointer must be untouched"
    assert not pair["last_swap"].exists(), "no swap record may be written by a preflight failure"


def check_ambiguous_stop_isolated(root):
    """An unproven stop must not trigger any further control action on either process."""
    pair = make_pair(root, "ambiguous_stop")
    before = pair["launch_env"].read_bytes()
    events = []
    output = io.StringIO()

    def stop_ambiguous(*_args):
        raise HOTFIX.HotfixError("post-stop identity check failed: pair state ambiguous; check whether "
                                 "pair is down and use --rollback only after operator verification")

    stack = swap_stack(HOTFIX, pair, 12_345, events)
    stack.enter_context(patch.object(HOTFIX, "stop_pair", side_effect=stop_ambiguous))
    with stack, redirect_stdout(output):
        try:
            HOTFIX.perform_swap(pair["new"], NEW_SHA, 8031, False)
        except HOTFIX.HotfixError as exc:
            message = str(exc)
        else:
            raise AssertionError("an ambiguous stop must not be treated as success")
    assert "rewrite" not in events and "pointer" not in events and "start" not in events, events
    assert "ambiguous" in message or "could not be restored" in message, message
    assert pair["launch_env"].read_bytes() == before, "launch spec must survive an ambiguous stop"


def check_single_fault_rollback_restores_state(root):
    """Every post-stop failure must restore the OLD build in the launch spec ON DISK."""
    for failed_at in ("rewrite", "pointer", "start", "track", "proof"):
        pair = make_pair(root, "fault_" + failed_at)
        starts = []
        events = []

        def real_rewrite(spec, build, sha, state, _pair=pair, _events=events):
            _events.append("rewrite")
            spec["build_sha"] = sha
            spec["script"] = str(Path(build) / "_archive" / "hl_stage2" / HOTFIX.TARGET)
            HOTFIX.atomic_json(_pair["launch_env"], spec)

        def real_pointer(path, text, _events=events):
            _events.append("pointer")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text + "\n", encoding="utf-8")

        tripped = []

        def inject(name, real, _events=events, _tripped=tripped):
            def fn(*args, **kwargs):
                _events.append(name)
                if name == failed_at and not _tripped:
                    _tripped.append(name)
                    raise HOTFIX.HotfixError("injected " + name)
                return real(*args, **kwargs)
            return fn

        def start_action(build, sha, *_args, **_kwargs):
            events.append("start")
            starts.append((Path(build), sha))
            if failed_at == "start" and len(starts) == 1:
                raise HOTFIX.HotfixError("injected start")
            return {"engine_pid": 4321}

        def track_action(*_a):
            events.append("track-ui")
            if failed_at == "track" and events.count("track-ui") == 1:
                raise HOTFIX.HotfixError("injected track")
            return None

        out = run_swap(HOTFIX, pair, 12_345, events=events, start=start_action,
                       rewrite=inject("rewrite", real_rewrite),
                       pointer=inject("pointer", real_pointer),
                       track=track_action,
                       proof=inject("proof", lambda *_a: {
                           "gap_fills": 0, "gap_intent_rows": 0, "duplicate_attempts": 0,
                           "unresolved": 0, "cursors_caught_up": 1, "merged_buckets": 0,
                           "buckets": 0, "failed_buckets": 0}))
        assert isinstance(out["raised"], HOTFIX.HotfixError), (failed_at, out["raised"])
        assert "previous pair restored" in str(out["raised"]), (failed_at, str(out["raised"]))
        restored = json.loads(pair["launch_env"].read_text(encoding="utf-8"))
        assert restored["build_sha"] == OLD_SHA, (failed_at, restored)
        assert Path(restored["script"]).parts[-4] == pair["old"].name, (failed_at, restored)
        assert starts and starts[-1] == (pair["old"], OLD_SHA), (failed_at, starts)
        assert (pair["pair"] / "CURRENT_AUDIT_DIR").read_text(encoding="utf-8").strip() == str(pair["state"])


def main():
    with tempfile.TemporaryDirectory(prefix="hotfix-invariant-") as tmp:
        root = Path(tmp)
        raw = root / "raw_live_fills.csv"
        checks = [
            ("APPLY_HOTFIX_TIMESTAMP_RULES", lambda: check_timestamp_and_digest_rules(root)),
            ("APPLY_HOTFIX_REPLAY_PROOF", lambda: check_replay_proof(root / "replay", raw)),
            ("APPLY_HOTFIX_SWAP_PASS_AND_GAP_BOUNDARY", lambda: check_swap_pass_and_boundary(root)),
            ("APPLY_HOTFIX_MUTATION_GAP_THRESHOLD", lambda: check_mutation_gap_threshold(root)),
            ("APPLY_HOTFIX_PRECOMPILE_FAILURE_NEVER_STOPS",
             lambda: check_precompile_failure_never_stops_the_pair(root)),
            ("APPLY_HOTFIX_AMBIGUOUS_STOP_ISOLATED", lambda: check_ambiguous_stop_isolated(root)),
            ("APPLY_HOTFIX_SINGLE_FAULT_ROLLBACK", lambda: check_single_fault_rollback_restores_state(root)),
            ("APPLY_HOTFIX_MUTATION_SEMANTIC_CONFIG_GUARD",
             lambda: check_mutation_semantic_config_guard(root, raw)),
        ]
        failed = 0
        for name, fn in checks:
            try:
                fn()
            except Exception as exc:
                failed += 1
                print("FAIL %s | %r" % (name, exc))
            else:
                print("RESULT::%s_PASS" % name)
        print("TOTAL=%d FAILED=%d" % (len(checks), failed))
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
