"""Scratch-only timestamp rules for apply_hotfix state invariants."""
import importlib.util
import json
import csv
import io
import tempfile
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("apply_hotfix", HERE / "apply_hotfix.py")
HOTFIX = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(HOTFIX)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="hotfix-invariant-") as tmp:
        root = Path(tmp)
        manual = root / "manual_live_positions.json"
        xyz = root / "xyz_position_state.json"
        config = root / "live_config.json"
        manual.write_text(json.dumps({"BTC": {"signed_size": 1, "last_updated_at": "before"}}), encoding="utf-8")
        manual_before = HOTFIX.digest_json(manual, manual.name)
        manual.write_text(json.dumps({"BTC": {"signed_size": 1, "last_updated_at": "after"}}), encoding="utf-8")
        assert HOTFIX.digest_json(manual, manual.name) == manual_before

        xyz.write_text(json.dumps({"updated_at": "before", "updated_at_ms": 1, "positions_by_coin": {"BTC": 1}}), encoding="utf-8")
        xyz_before = HOTFIX.digest_json(xyz, xyz.name)
        xyz.write_text(json.dumps({"updated_at": "after", "updated_at_ms": 2, "positions_by_coin": {"BTC": 1}}), encoding="utf-8")
        assert HOTFIX.digest_json(xyz, xyz.name) == xyz_before

        config.write_text(json.dumps({"wallets": {"user": {"mode": "USER", "sleeve": 1}}}), encoding="utf-8")
        config_before = HOTFIX.digest_json(config, config.name)
        raw_before = config.read_bytes()
        config.write_text(json.dumps({"wallets": {"user": {"sleeve": 1, "mode": "USER"}}}, indent=4), encoding="utf-8")
        assert config.read_bytes() != raw_before
        assert HOTFIX.digest_json(config, config.name) == config_before
        config.write_text(json.dumps({"wallets": {"user": {"mode": "USER", "sleeve": 2}}}), encoding="utf-8")
        assert HOTFIX.digest_json(config, config.name) != config_before

        assert HOTFIX.user_owned_digest({"wallets": {"user": {"mode": "USER", "sleeve": 1}}}) != \
               HOTFIX.user_owned_digest({"wallets": {"user": {"mode": "USER", "sleeve": 2}}})

        state = root / "run8" / "state_scratch"
        append_only = state / "append_only"
        append_only.mkdir(parents=True)
        (state / "clean_core_runtime_state.json").write_text(
            json.dumps({"last_leader_poll_cursor_ms": {"0xwallet": 149}}), encoding="utf-8")
        (state / "live_integrity_status.json").write_text(json.dumps({
            "hard_copy_invariant": {"historical_unresolved_active_red_count": 0},
            "counts": {"open_late_fill_incidents": 0},
        }), encoding="utf-8")
        with (append_only / "order_intents.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["created_at_ms", "leader_fill_id"])
            writer.writeheader()
            writer.writerow({"created_at_ms": 121, "leader_fill_id": "fill-1"})
        with (append_only / "send_attempts.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["created_at_ms", "wallet", "leader_fill_id"])
            writer.writeheader()
        source = root / "raw_live_fills.csv"
        with source.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["leader_fill_id", "user", "coin", "side", "px", "sz", "time"])
            writer.writeheader()
            writer.writerow({"leader_fill_id": "fill-1", "user": "leader", "coin": "BTC",
                             "side": "B", "px": "1", "sz": "1", "time": 120})
        baseline = {"anchor_sha256": "anchor", "anchor_t0_ms": 1, "live_config_sha256": "config", "live_config_semantic_sha256": "config_semantic",
                    "manual_live_positions_sha256": "manual", "xyz_position_state_sha256": "xyz",
                    "user_owned_sha256": "user"}
        with patch.object(HOTFIX, "snapshot_state", return_value=baseline):
            try:
                HOTFIX.replay_proof(state, baseline, set(), source, 100, 150, ["0xwallet"])
            except HOTFIX.HotfixError as exc:
                assert "not caught up" in str(exc)
            else:
                raise AssertionError("poll cursor before the first healthy cycle must not pass")
            runtime = json.loads((state / "clean_core_runtime_state.json").read_text(encoding="utf-8"))
            runtime["last_leader_poll_cursor_ms"]["0xwallet"] = 150
            (state / "clean_core_runtime_state.json").write_text(json.dumps(runtime), encoding="utf-8")
            proof = HOTFIX.replay_proof(state, baseline, set(), source, 100, 150, ["0xwallet"])
            assert proof == {"gap_fills": 1, "gap_intent_rows": 1, "duplicate_attempts": 0,
                             "unresolved": 0, "cursors_caught_up": 1}
            with patch.object(HOTFIX, "snapshot_state", return_value=dict(baseline, live_config_sha256="raw_changed")):
                HOTFIX.replay_proof(state, baseline, set(), source, 100, 150, ["0xwallet"])
            with patch.object(HOTFIX, "snapshot_state",
                              return_value=dict(baseline, live_config_semantic_sha256="semantic_changed")):
                try:
                    HOTFIX.replay_proof(state, baseline, set(), source, 100, 150, ["0xwallet"])
                except HOTFIX.HotfixError as exc:
                    assert "live_config_semantic_sha256" in str(exc)
                else:
                    raise AssertionError("semantic live config change must fail")
            with (append_only / "send_attempts.csv").open("a", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=["created_at_ms", "wallet", "leader_fill_id"])
                writer.writerow({"created_at_ms": 130, "wallet": "0xwallet", "leader_fill_id": "fill-1"})
            try:
                HOTFIX.replay_proof(state, baseline, {("0xwallet", "fill-1")}, source, 100, 150,
                                    ["0xwallet"])
            except HOTFIX.HotfixError as exc:
                assert "another send attempt" in str(exc)
            else:
                raise AssertionError("previously-sent gap fill must not pass")
        _scratch_swap_flow(root)
        _scratch_failure_flow(root)
    print("RESULT::APPLY_HOTFIX_TIMESTAMP_RULES_PASS")
    print("RESULT::APPLY_HOTFIX_REPLAY_PROOF_PASS")
    print("RESULT::APPLY_HOTFIX_SWAP_FLOW_PASS")
    print("RESULT::APPLY_HOTFIX_CONFIG_SEMANTIC_GATE_PASS")


def _scratch_swap_flow(root: Path) -> None:
    root = root / "swap_flow"
    root.mkdir()
    run = root / "run8"
    state = run / "state_scratch"
    state.mkdir(parents=True)
    (state / "PAIR_START_ANCHOR.json").write_text(json.dumps({"t0_ms": 1}), encoding="utf-8")
    config = {"wallets": {"live": {"mode": "LIVE"}, "user": {"mode": "USER"}}}
    (state / "live_config.json").write_text(json.dumps(config), encoding="utf-8")
    (root / "CURRENT_AUDIT_DIR").write_text(str(state), encoding="utf-8")
    old_root, new_root = root / "old", root / "new"
    old_root.mkdir()
    new_root.mkdir()
    source = root / "source.csv"
    source.write_text("leader_fill_id,time\n", encoding="utf-8")
    spec = {"env": {"HL_LIVE_AUDIT_DIR": str(state), "HL_LIVE_SOURCE_FILLS": str(source)}}
    identity = {"pid": 1234}
    old_sha, new_sha = "a" * 40, "b" * 40
    baseline = {"anchor_sha256": "anchor", "anchor_t0_ms": 1, "live_config_sha256": "config", "live_config_semantic_sha256": "config_semantic",
                "manual_live_positions_sha256": "manual", "xyz_position_state_sha256": "xyz",
                "user_owned_sha256": "user"}
    events: list[str] = []
    output = io.StringIO()

    with patch.object(HOTFIX, "launch_spec", return_value=(spec, dict(spec["env"]), state)), \
            patch.object(HOTFIX, "validate_pair", side_effect=[(identity, old_root, old_sha, 5678),
                                                                   (identity, old_root, old_sha, 5678)]), \
            patch.object(HOTFIX, "checkout_info", return_value=(new_root, new_sha)), \
            patch.object(HOTFIX, "precompile", side_effect=lambda _path: events.append("precompile")), \
            patch.object(HOTFIX, "snapshot_state", return_value=baseline), \
            patch.object(HOTFIX, "sent_keys", return_value=set()), \
            patch.object(HOTFIX, "stop_pair", side_effect=lambda *_args: events.append("stop")), \
            patch.object(HOTFIX, "rewrite_launch_spec", side_effect=lambda *_args: events.append("rewrite")), \
            patch.object(HOTFIX, "start_pair", side_effect=lambda *_args: (events.append("start") or
                                                                              {"pair": "STARTED", "engine_pid": 4321})), \
            patch.object(HOTFIX, "tracked_start_ui", side_effect=lambda *_args: events.append("track-ui")), \
            patch.object(HOTFIX, "save_swap_record", side_effect=lambda *_args: events.append("save-record")), \
            patch.object(HOTFIX, "first_healthy_cycle", side_effect=lambda _s, _p, after: (after + 12_345, {})), \
            patch.object(HOTFIX, "replay_proof", return_value={"gap_fills": 0, "gap_intent_rows": 0,
                                                                "duplicate_attempts": 0, "unresolved": 0,
                                                                "cursors_caught_up": 1}):
        with redirect_stdout(output):
            result = HOTFIX.perform_swap(new_root, new_sha, 8031, False)

    assert result == 0
    assert events == ["precompile", "stop", "rewrite", "start", "track-ui", "save-record"]
    assert "deactivation_to_healthy_ms   12345 / 20000" in output.getvalue()
    assert "HOTFIX SWAP PASS" in output.getvalue()


def _scratch_failure_flow(root: Path) -> None:
    """Injection proof: ambiguity before confirmed stop never triggers another control action;
    later metadata/pointer/start/track/proof failures restore the original pair."""
    from unittest.mock import Mock
    root = root / "failure_flow"
    state = root / "run8" / "state_scratch"
    state.mkdir(parents=True)
    (state / "live_config.json").write_text(
        json.dumps({"wallets": {"live": {"mode": "LIVE"}}}), encoding="utf-8")
    (root / "CURRENT_AUDIT_DIR").write_text(str(state), encoding="utf-8")
    source = root / "source.csv"
    source.write_text("leader_fill_id,time\\n", encoding="utf-8")
    old_root, new_root = root / "old", root / "new"
    old_root.mkdir()
    new_root.mkdir()
    old_sha, new_sha = "a" * 40, "b" * 40
    spec = {"env": {"HL_LIVE_AUDIT_DIR": str(state), "HL_LIVE_SOURCE_FILLS": str(source)}}
    baseline = {"anchor_sha256": "a", "anchor_t0_ms": 1,
                "live_config_semantic_sha256": "config",
                "manual_live_positions_sha256": "manual",
                "xyz_position_state_sha256": "xyz", "user_owned_sha256": "user"}
    for failed_at in ("stop", "rewrite", "pointer", "start", "track", "proof"):
        events = []
        def action(name, result=None):
            def fn(*args, **kwargs):
                events.append(name)
                if name == failed_at:
                    raise HOTFIX.HotfixError("injected " + name)
                return result
            return fn

        with patch.object(HOTFIX, "launch_spec", return_value=(spec.copy(), dict(spec["env"]), state)), \\
                patch.object(HOTFIX, "validate_pair", return_value=({"pid": 1234}, old_root, old_sha, 5678)), \\
                patch.object(HOTFIX, "checkout_info", return_value=(new_root, new_sha)), \\
                patch.object(HOTFIX, "precompile"), \\
                patch.object(HOTFIX, "snapshot_state", return_value=baseline), \\
                patch.object(HOTFIX, "backup_state", return_value=root / "backup"), \\
                patch.object(HOTFIX, "sent_keys", return_value=set()), \\
                patch.object(HOTFIX, "stop_pair", side_effect=action("stop")), \\
                patch.object(HOTFIX, "rewrite_launch_spec", side_effect=action("rewrite")), \\
                patch.object(HOTFIX, "atomic_text", side_effect=action("pointer")), \\
                patch.object(HOTFIX, "start_pair", side_effect=action("start", {"engine_pid": 4321})), \\
                patch.object(HOTFIX, "tracked_start_ui", side_effect=action("track")), \\
                patch.object(HOTFIX, "first_healthy_cycle", side_effect=lambda _s, _p, after: (after + 12345, {})), \\
                patch.object(HOTFIX, "replay_proof", side_effect=action("proof", {"gap_fills": 0, "gap_intent_rows": 0, "duplicate_attempts": 0, "unresolved": 0, "cursors_caught_up": 1})), \\
                patch.object(HOTFIX, "save_swap_record"), \\
                patch.object(HOTFIX.SP, "pids", return_value=[]), \\
                patch.object(HOTFIX.SP, "listener", return_value=None), \\
                patch.object(HOTFIX.time, "sleep"):
            try:
                HOTFIX.perform_swap(new_root, new_sha, 8031, False)
            except HOTFIX.HotfixError as exc:
                if failed_at == "stop":
                    assert "injected stop" in str(exc)
                    assert events == ["stop"], events
                else:
                    assert "previous pair restored" in str(exc), (failed_at, exc)
                    assert events.count("start") >= 1, events
            else:
                raise AssertionError("injected failure unexpectedly passed: " + failed_at)


if __name__ == "__main__":
    main()
