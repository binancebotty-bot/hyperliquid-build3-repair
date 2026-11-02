#!/usr/bin/env python3
"""Offline source-backed regression for ExchangeReconciler /info envelope validation.

Run: python test_core_snapshot_envelope.py
     python test_core_snapshot_envelope.py --mutation-check
The Core module is NEVER imported or executed at top level. Only two methods
are extracted from its AST, executed with injected fake /info transport and
stubbed persistence, so no keys, files, running engine, or sockets are used.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Dict, Tuple
import unittest

CORE = Path(os.environ.get("SNAPSHOT_CORE_SOURCE", Path(__file__).with_name("HL_Live_Copy_Service_Core.py")))


class FakeResponse:
    def __init__(self, body: Any, status_code: int = 200):
        self.body, self.status_code = body, status_code

    def json(self) -> Any:
        return self.body


class FakeRequests:
    def __init__(self, replies: Dict[str, FakeResponse]):
        self.replies = replies
        self.calls = []

    def post(self, url: str, *, json: Dict[str, Any], timeout: float) -> FakeResponse:
        assert url == "fake://info" and json["type"] == "clearinghouseState"
        assert json["user"] == "test-wallet" and timeout == 1
        dex = json.get("dex", "")
        self.calls.append(dex)
        return self.replies[dex]


def source_backed_reconciler(path: Path, replies: Dict[str, FakeResponse], dexes: Tuple[str, ...]):
    """Compile only the two production methods; all dependencies are test fakes."""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    original = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "ExchangeReconciler")
    names = {"fetch_snapshot", "_positions_from_snapshot"}
    methods = [n for n in original.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {m.name for m in methods} == names, "Core method binding changed"
    cls = ast.ClassDef(name="ExchangeReconciler", bases=[], keywords=[], body=methods, decorator_list=[])
    unit = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    requests = FakeRequests(replies)
    writes, history, errors = [], [], []
    ns = {
        "Tuple": Tuple, "Dict": Dict, "Any": Any,
        "USER_WALLET": "test-wallet", "requests": requests,
        "HL_INFO_URL": "fake://info", "HTTP_TIMEOUT_SEC": 1,
        "follower_dex_scope": lambda: list(dexes),
        "xyz_state_positions": lambda include_zero=False: {},
        "canonical_coin_key": lambda x: str(x or "").strip().upper(),
        "fnum": lambda v, default=0.0: float(v) if v not in (None, "") else default,
        "utc_now_iso": lambda: "2026-11-02T00:00:00Z", "utc_now_ms": lambda: 0,
        "EXCHANGE_ACCOUNT_SNAPSHOT_FILE": "unused-in-test",
        "atomic_write_json": lambda path, snapshot: writes.append(snapshot),
        "append_account_history_point": lambda snapshot: history.append(snapshot),
        "log_error": lambda *args: errors.append(args),
    }
    exec(compile(unit, str(path), "exec"), ns)
    reconciler = ns["ExchangeReconciler"]()
    reconciler._xyz_positions_from_app_snapshot = lambda: {}
    return reconciler, requests, writes, history, errors


class SnapshotEnvelopeTests(unittest.TestCase):
    def check_case(self, label: str, replies: Dict[str, FakeResponse], *, accept: bool,
                   expected_positions: Dict[str, float] | None = None, dexes: Tuple[str, ...] = ("",)):
        reconciler, requests, writes, history, errors = source_backed_reconciler(CORE, replies, dexes)
        snapshot, status = reconciler.fetch_snapshot()
        flat = isinstance(snapshot.get("positions_by_coin"), dict) and not snapshot["positions_by_coin"]
        print(f"CASE {label}: status={status} flat={flat} calls={','.join(requests.calls)} writes={len(writes)}", flush=True)
        if accept:
            self.assertEqual(status, "SNAPSHOT_OK", label)
            self.assertEqual(snapshot["positions_by_coin"], expected_positions, label)
            self.assertEqual(len(writes), 1, label)
            self.assertEqual(len(history), 1, label)
        else:
            # An unknown exchange state must never be endorsed as an empty exchange account.
            self.assertNotEqual(status, "SNAPSHOT_OK", label)
            self.assertFalse(flat, f"{label}: malformed/failed read masqueraded as flat")
            self.assertFalse(writes, f"{label}: persisted invalid snapshot")
            self.assertFalse(history, f"{label}: wrote invalid equity history")

    def test_malformed_asset_positions_dict(self):
        self.check_case("MALFORMED_DICT", {"": FakeResponse({"assetPositions": "invalid-string"})}, accept=False)

    def test_http_429_error_dict(self):
        self.check_case("HTTP_429_ERROR_BODY", {"": FakeResponse({"error": "rate limit"}, 429)}, accept=False)

    def test_http_500_error_dict(self):
        self.check_case("HTTP_500_ERROR_BODY", {"": FakeResponse({"error": "server error"}, 500)}, accept=False)

    def test_empty_dict(self):
        self.check_case("EMPTY_DICT", {"": FakeResponse({})}, accept=False)

    def test_missing_named_dex(self):
        self.check_case("MISSING_NAMED_DEX", {"": FakeResponse({"assetPositions": []}), "xyz": FakeResponse([], 200)},
                        accept=False, dexes=("", "xyz"))

    def test_valid_empty_asset_positions(self):
        self.check_case("VALID_EMPTY_ASSET_POSITIONS", {"": FakeResponse({"assetPositions": []})},
                        accept=True, expected_positions={})

    def test_valid_nonempty_asset_positions(self):
        self.check_case("VALID_NONEMPTY_ASSET_POSITIONS", {"": FakeResponse({"assetPositions": [
            {"position": {"coin": "BTC", "szi": "2.5"}},
        ]})}, accept=True, expected_positions={"BTC": 2.5})


def mutate_within_method(source: str, method: str, before: str, after: str) -> str:
    """Exactly one site in exactly one method, with no engine file modification."""
    ast_tree = ast.parse(source)
    owner = next(n for n in ast_tree.body if isinstance(n, ast.ClassDef) and n.name == "ExchangeReconciler")
    function = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == method)
    lines = source.splitlines(keepends=True)
    span = "".join(lines[function.lineno - 1:function.end_lineno])
    assert span.count(before) == 1, f"mutation site drift: {method}/{before}"
    lines[function.lineno - 1:function.end_lineno] = [span.replace(before, after, 1)]
    return "".join(lines)


def mutation_check() -> int:
    source = CORE.read_text(encoding="utf-8-sig")
    mutations = [
        ("M1_REJECT_VALID_DICT", "fetch_snapshot", "if isinstance(data, dict):", "if False:"),
        ("M2_DROP_POSITION_ROWS", "_positions_from_snapshot", "for item in data.get(\"assetPositions\") or []:", "for item in []:"),
    ]
    with tempfile.TemporaryDirectory(prefix="snapshot_core_mutants_") as d:
        temp = Path(d) / "HL_Live_Copy_Service_Core.py"
        cmd = [sys.executable, str(Path(__file__).resolve()), "--positive-only"]
        env = {**os.environ, "SNAPSHOT_CORE_SOURCE": str(temp)}
        temp.write_text(source, encoding="utf-8")
        baseline = subprocess.run(cmd, env=env, text=True, capture_output=True, timeout=30)
        print(f"MUTANT BASELINE_POSITIVE returncode={baseline.returncode}", flush=True)
        if baseline.returncode:
            print(baseline.stdout + baseline.stderr)
            return 1
        for label, method, before, after in mutations:
            temp.write_text(mutate_within_method(source, method, before, after), encoding="utf-8")
            result = subprocess.run(cmd, env=env, text=True, capture_output=True, timeout=30)
            killed = result.returncode != 0
            print(f"MUTANT {label} killed={killed} returncode={result.returncode}", flush=True)
            print("\n".join(line for line in result.stdout.splitlines() if line.startswith("CASE ")))
            if not killed:
                return 1
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--mutation-check"]:
        sys.exit(mutation_check())
    positive_only = sys.argv[1:] == ["--positive-only"]
    if sys.argv[1:] and not positive_only:
        raise SystemExit("usage: python test_core_snapshot_envelope.py [--positive-only|--mutation-check]")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SnapshotEnvelopeTests)
    if positive_only:
        suite = unittest.TestSuite([SnapshotEnvelopeTests("test_valid_empty_asset_positions"),
                                    SnapshotEnvelopeTests("test_valid_nonempty_asset_positions")])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
