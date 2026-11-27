"""Regression tests for testnet symbol eligibility and entry-book filtering."""

import os
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

import HL_Live_Copy_Service_Core as core


class TestnetSymbolEligibilityTests(unittest.TestCase):
    def test_live_testnet_allowlist_excludes_delisted_or_unqualified_assets(self):
        fixture = Path(__file__).resolve().parents[2] / "tools" / "cert" / "fixtures" / "live_config_copy.json"
        config = json.loads(fixture.read_text(encoding="utf-8"))
        cfg = core.ConfigManager(fixture)

        eligible = (
            "BTC ETH SOL NEAR DOGE AVAX PUMP BNB ME SUI INIT AAVE XMR kPEPE ARB ADA OP ZRO PAXG INJ TIA"
        ).split()
        self.assertEqual(config["global_controls"].get("symbol_allowlist"), eligible)
        self.assertEqual(config["global_controls"].get("symbol_blocklist"), [])
        for coin in eligible:
            with self.subTest(coin=coin):
                self.assertEqual(cfg.is_symbol_allowed(coin), (True, ""))
        self.assertEqual(cfg.is_symbol_allowed("DELISTED-ASSET"), (False, "SYMBOL_NOT_ALLOWED"))

    def test_one_sided_or_empty_book_does_not_block_entry(self):
        builder = object.__new__(core.SenderGateway)
        intent = SimpleNamespace(fill=SimpleNamespace(coin="TESTNET-MARKET"))

        for sides in ((1, 0), (0, 1), (0, 0)):
            with self.subTest(sides=sides), patch.dict(
                os.environ, {"HL_LIVE_ONE_SIDED_BOOK_GUARD": "1"}
            ):
                builder._fetch_book_sides = lambda coin, sides=sides: sides
                self.assertEqual(builder._one_sided_book_block(intent), "")


if __name__ == "__main__":
    unittest.main()
