#!/usr/bin/env python3
"""Edge-case tests for ops/testnet_startup.py"""
import unittest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

from testnet_startup import (
    norm_path,
    verify_authorization_order,
    check_source,
    prepare_account,
    stop_core_process,
    record_shutdown_record,
    retire_legacy_watchdog,
    process_start_ms,
    evaluate_flatness,
)


class TestNormPath(unittest.TestCase):
    def test_norm_path_windows(self):
        # Windows paths with mixed separators
        result = norm_path("C:\\Users\\test/../test")
        self.assertEqual(result.lower(), "c:\\users\\test".lower())


class TestEvaluateFlatness(unittest.TestCase):
    def test_flat_positions_no_orders(self):
        positions = {"BTC": "0.0"}
        orders = []
        documented = {}
        errors, detail = evaluate_flatness(positions, orders, documented)
        self.assertEqual(errors, [])
        self.assertTrue(detail["positions_pass"])
        self.assertTrue(detail["cancel_all_done"])

    def test_non_flat_position_not_documented(self):
        positions = {"BTC": "1.0"}
        orders = []
        documented = {}
        errors, detail = evaluate_flatness(positions, orders, documented)
        self.assertIn("POSITION_NOT_FLAT_OR_DOCUMENTED", errors)

    def test_non_flat_position_documented(self):
        positions = {"BTC": "1.0"}
        orders = []
        documented = {"BTC": "1.0"}
        errors, detail = evaluate_flatness(positions, orders, documented)
        self.assertEqual(errors, [])

    def test_resting_orders_exist(self):
        positions = {"BTC": "0.0"}
        orders = [{"coin": "BTC", "side": "buy"}]
        documented = {}
        errors, detail = evaluate_flatness(positions, orders, documented)
        self.assertIn("CANCEL_ALL_NOT_VERIFIED", errors)


class TestVerifyAuthorizationOrder(unittest.TestCase):
    def _make_comment_response(self, body, author="binancebotty-bot", created_at="2026-10-24T00:00:01Z"):
        """Create a mock GitHub comment response with valid JSON."""
        import json
        comment = {
            "issue_url": "https://api.github.com/repos/binancebotty-bot/hyperliquid-build3-repair/issues/81",
            "user": {"login": author},
            "created_at": created_at,
            "body": body
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(comment).encode('utf-8')
        mock_response.__enter__ = lambda self: self
        mock_response.__exit__ = lambda *args: None
        return mock_response

    def _make_spec(self):
        """Create a spec dict with source_sha for testing."""
        return {"source_sha": "a" * 40}

    def _make_state_dir(self):
        """Create a temporary state directory for testing."""
        return Path(tempfile.mkdtemp())

    @patch("testnet_startup.urlopen")
    @patch("testnet_startup.subprocess.run")
    def test_valid_cutover_order(self, mock_run, mock_urlopen):
        mock_urlopen.return_value = self._make_comment_response(
            body=f"CUTOVER ORDER {'a' * 40}\nSome other text\nSHA: {'a' * 40}"
        )
        mock_run.return_value = MagicMock(stdout="1700000000")
        spec = self._make_spec()
        state_dir = self._make_state_dir()
        result = verify_authorization_order("1234567890", "a" * 40, spec, state_dir)
        self.assertTrue(result)

    @patch("testnet_startup.urlopen")
    @patch("testnet_startup.subprocess.run")
    def test_invalid_author_not_controller(self, mock_run, mock_urlopen):
        mock_urlopen.return_value = self._make_comment_response(
            author="not-controller",
            body="CUTOVER ORDER aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        )
        mock_run.return_value = MagicMock(stdout="1700000000")
        spec = self._make_spec()
        state_dir = self._make_state_dir()
        result = verify_authorization_order("1234567890", "a" * 40, spec, state_dir)
        self.assertFalse(result)

    @patch("testnet_startup.urlopen")
    @patch("testnet_startup.subprocess.run")
    def test_crlf_line_ending_in_body(self, mock_run, mock_urlopen):
        mock_urlopen.return_value = self._make_comment_response(
            body=f"NOT A CUTOVER ORDER\r\nCUTOVER ORDER {'a' * 40}\r\nEND\nSHA: {'a' * 40}"
        )
        mock_run.return_value = MagicMock(stdout="1700000000")
        spec = self._make_spec()
        state_dir = self._make_state_dir()
        result = verify_authorization_order("1234567890", "a" * 40, spec, state_dir)
        self.assertTrue(result)

    @patch("testnet_startup.urlopen")
    @patch("testnet_startup.subprocess.run")
    def test_not_cutover_order_substring(self, mock_run, mock_urlopen):
        mock_urlopen.return_value = self._make_comment_response(
            body="NOT A CUTOVER ORDER"
        )
        mock_run.return_value = MagicMock(stdout="1700000000")
        spec = self._make_spec()
        state_dir = self._make_state_dir()
        result = verify_authorization_order("1234567890", "a" * 40, spec, state_dir)
        self.assertFalse(result)


class TestCheckSource(unittest.TestCase):
    @patch("testnet_startup.subprocess.run")
    def test_merge_commit_rejected(self, mock_run):
        mock_run.return_value = MagicMock(stdout="commit_sha parent1 parent2")
        spec = {"source_sha": "a" * 40, "checkout_root": "/tmp"}
        with self.assertRaises(ValueError) as ctx:
            check_source(spec)
        self.assertIn("has 2 parents", str(ctx.exception))

    @patch("testnet_startup.subprocess.run")
    def test_single_parent_accepted(self, mock_run):
        mock_run.side_effect = [
            MagicMock(stdout="commit_sha parent1"),  # rev-list --parents
            MagicMock(stdout="a" * 40),  # checkout_root rev-parse
        ]
        spec = {"source_sha": "a" * 40, "checkout_root": "/tmp"}
        with patch("testnet_startup.Path.exists", return_value=True):
            result = check_source(spec)
            self.assertEqual(result, "a" * 40)


class TestStopCoreProcess(unittest.TestCase):
    @patch("testnet_startup.Path.is_file")
    @patch("testnet_startup.read_json")
    @patch("testnet_startup.process_start_ms")
    def test_stop_already_stopped(self, mock_process_start_ms, mock_read_json, mock_is_file):
        mock_is_file.return_value = True
        mock_read_json.return_value = {"process_id": 1234, "started_at_ms": 1000}
        mock_process_start_ms.return_value = None  # Already stopped
        
        result = stop_core_process({}, Path("/tmp"), dry_run=False)
        self.assertEqual(result, 0)


class TestRecordShutdownRecord(unittest.TestCase):
    def test_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_dir = Path(tmpdir)
            result = record_shutdown_record({}, state_dir, 1234, 1000, True)
            self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()