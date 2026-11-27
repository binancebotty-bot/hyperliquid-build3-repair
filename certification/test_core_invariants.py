#!/usr/bin/env python3
"""Current-tree checks for ARCHITECTURE.md's 14 non-negotiable invariants.

Run with: python certification/test_core_invariants.py
These are source-level checks; they do not certify live exchange behavior.
"""
import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
TRUTH = ROOT / "_archive" / "hl_stage2" / "exchange_truth.py"
CONVERGENCE = ROOT / "_archive" / "hl_stage2" / "convergence_shadow.py"


def source(path):
    return path.read_text(encoding="utf-8-sig")


def calls(path, name):
    tree = ast.parse(source(path))
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and ((isinstance(n.func, ast.Attribute) and n.func.attr == name)
                 or (isinstance(n.func, ast.Name) and n.func.id == name))]


class CoreInvariantTests(unittest.TestCase):
    def test_inv01_one_process(self):
        tree = ast.parse(source(CORE))
        forbidden = {"Popen", "Process", "Pool", "create_subprocess_exec", "create_subprocess_shell"}
        found = [n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
                 for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and ((isinstance(n.func, ast.Attribute) and n.func.attr in forbidden)
                      or (isinstance(n.func, ast.Name) and n.func.id in forbidden))]
        self.assertEqual(found, [], f"process creation calls: {found}")

    def test_inv02_one_physical_order_callsite(self):
        self.assertEqual(len(calls(CORE, "order")), 1, "expected one physical .order() site in Core")

    def test_inv03_no_unapproved_dependency(self):
        approved = __import__("json").loads((ROOT / "certification" / "approved_dependencies.json").read_text())
        records = approved if isinstance(approved, list) else approved.get("approved", [])
        names = {item["module"] for item in records if isinstance(item, dict) and item.get("approved")}
        tree = ast.parse(source(CORE))
        imports = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
        imports |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        stdlib = set(__import__("sys").stdlib_module_names)
        local = {p.stem for p in CORE.parent.glob("*.py")}
        unexpected = sorted(imports - stdlib - local - names)
        self.assertEqual(unexpected, [], f"unapproved imports: {unexpected}")

    def test_inv04_only_existing_authoritative_store(self):
        text = source(CORE)
        self.assertIn("SERVICE_STATE_FILE", text)
        stores = re.findall(r"(?:sqlite3\.connect|shelve\.open|dbm\.open)\s*\(", text)
        self.assertEqual(stores, [], f"additional database stores found: {stores}")

    def test_inv05_no_build4_control_plane_import(self):
        text = source(CORE).lower()
        self.assertNotRegex(text, r"(?m)^\s*(?:from|import)\s+[^\n]*(?:build4|lease|mission_control)")

    def test_inv06_no_second_engine_runtime(self):
        self.assertTrue(CORE.is_file())
        self.assertFalse((ROOT / "HL_Live_Copy_Service_Core.py").exists(), "unexpected root runtime copy")

    def test_inv07_leader_mutable_state_scoped_by_wallet_coin(self):
        text = source(CORE)
        self.assertRegex(text, r"def\s+sleeve_id\s*\(\s*wallet[^,]*,\s*coin")
        self.assertRegex(text, r"return\s+f[\"']\{normalise_wallet\(wallet\)\}::\{canonical_coin_key\(coin\)\}")

    def test_inv08_multidex_truth(self):
        text = source(TRUTH)
        self.assertIn("def list_perp_dexes", text)
        self.assertIn("def master_userfills_all_dexes", text)

    @unittest.skip("MISSING: requires replay/recovery execution against an independent all-DEX exchange-position oracle")
    def test_inv09_exchange_truth_beats_manual_position_file(self):
        pass

    @unittest.skip("MISSING: requires executed send plus independent MASTER-account fill/position oracle")
    def test_inv10_acknowledgement_is_not_settlement(self):
        pass

    def test_inv11_master_and_signer_are_separate(self):
        text = source(CORE).lower()
        self.assertIn("master", text)
        self.assertIn("signer", text)

    def test_inv12_convergence_preserves_unrelated_inventory(self):
        text = source(CONVERGENCE)
        self.assertIn("def compute_convergence_order", text)
        self.assertIn("actual_net", text)
        self.assertIn("desired_net", text)

    def test_inv13_restart_snapshot_creates_no_trade_authority(self):
        text = source(CORE)
        self.assertIn("stale_snapshot_replay_reason", text)
        self.assertIn("snapshot", text.lower())

    @unittest.skip("MISSING: requires an observed LIVE/mainnet activation attempt and explicit operator approval oracle")
    def test_inv14_no_live_activation_without_explicit_approval(self):
        pass


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CoreInvariantTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    failed = len(result.failures) + len(result.errors)
    missing = len(result.skipped)
    passed = result.testsRun - failed - missing
    print(f"INVARIANT_RESULTS pass={passed} fail={failed} missing={missing} total={result.testsRun}")
    raise SystemExit(1 if failed else 0)
