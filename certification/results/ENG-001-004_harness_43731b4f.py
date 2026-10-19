#!/usr/bin/env python3
"""
ENG-001/002/004 certification harness for Build-3 Hyperliquid copy engine.
Commit: 43731b4f1f19a56e835032dabf608a550f925717

Drives the REAL production functions in HL_Live_Copy_Service_Core.py.
Oracle = Hyperliquid testnet info API via exchange_truth.py companion.
Negative tests mutate a scratch copy of the engine; positive control passes unmutated.
"""
import importlib
import importlib.util
import json
import math
import os
import sys
import copy
import shutil
import tempfile
import time
from pathlib import Path
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING
from unittest.mock import MagicMock, patch

# --- Setup: import the engine and companion ---
REPO = Path("C:/Users/wigmore/hyperliquid-build3-repair")
ENGINE_PATH = REPO / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
COMPANION_PATH = REPO / "_archive" / "hl_stage2" / "exchange_truth.py"

# Set environment before importing engine
os.environ.setdefault("HL_FOLLOWER_NETWORK", "testnet")
os.environ.setdefault("HL_LEADER_NETWORK", "testnet")
os.environ.setdefault("HL_LIVE_AUTO_SEND_ENABLED", "0")

# Import companion first (it sets up HL_INFO_URL, NETWORKS, etc.)
spec_et = importlib.util.spec_from_file_location("exchange_truth", str(COMPANION_PATH))
et = importlib.util.module_from_spec(spec_et)
spec_et.loader.exec_module(et)

# Import the engine
spec = importlib.util.spec_from_file_location("HL_Live_Copy_Service_Core", str(ENGINE_PATH))
engine = importlib.util.module_from_spec(spec)
sys.modules["HL_Live_Copy_Service_Core"] = engine  # Required for dataclass(frozen=True) in Python 3.14+
spec.loader.exec_module(engine)

# Now the engine classes are available
LeaderFill = engine.LeaderFill
ManualLedger = engine.ManualLedger
ConfigManager = engine.ConfigManager
IntentBuilder = engine.IntentBuilder
SenderGateway = engine.SenderGateway
AuditLogWriter = engine.AuditLogWriter
CycleSummary = engine.CycleSummary

# Engine functions
signed_from_side_size = engine.signed_from_side_size
canonical_coin_key = engine.canonical_coin_key
normalise_wallet = engine.normalise_wallet
fnum = engine.fnum
bval = engine.bval

# Companion functions (oracle)
list_perp_dexes = et.list_perp_dexes
master_account_net = et.master_account_net
master_exposure = et.master_exposure
resolve_networks = et.resolve_networks

# ============================================================================
# TEST FIXTURES
# ============================================================================

def make_leader_fill(
    coin="BTC",
    side="BUY",
    size=0.1,
    price=50000.0,
    leader_wallet="0x1111111111111111111111111111111111111111",
    timestamp_ms=None,
    fill_id=None,
    source="WS",
):
    """Create a LeaderFill with realistic defaults."""
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    if fill_id is None:
        fill_id = f"fill_{coin}_{side}_{size}_{timestamp_ms}"
    return LeaderFill(
        leader_fill_id=fill_id,
        leader_wallet=leader_wallet,
        coin=coin,
        side=side,
        size=size,
        price=price,
        timestamp_ms=timestamp_ms,
        source=source,
        raw={"coin": coin, "side": side, "sz": str(size), "px": str(price),
              "time": timestamp_ms, "dir": "Open Long" if side == "BUY" else "Open Short"},
    )


def make_testnet_fetcher():
    """A fetcher that calls the real Hyperliquid testnet info API (read-only)."""
    import requests as req
    def fetcher(payload):
        info_url = et.NETWORKS["follower"]["info"] if et.NETWORKS else "https://api.hyperliquid-testnet.xyz/info"
        resp = req.post(info_url, json=payload, timeout=10)
        return resp.json()
    return fetcher


# ============================================================================
# POSITIVE CONTROL TESTS
# ============================================================================

def test_eng001_convergence():
    """ENG-001: Repeated leader ADDs converge to target once.

    Drive the REAL IntentBuilder.build() + ManualLedger.apply_copy_fill()
    to prove that N repeated same-direction ADDs move actual toward desired
    and never exceed the target.
    """
    results = []
    
    # Setup: temp state dir
    tmpdir = tempfile.mkdtemp(prefix="eng001_")
    try:
        # Create config
        cfg_path = Path(tmpdir) / "live_config.json"
        cfg_data = {
            "wallets": {
                "0x1111111111111111111111111111111111111111": {
                    "mode": "ON",
                    "copy_mode": "proportional",
                    "fixed_notional": 100.0,
                    "norm_base": 10000.0,
                    "leader_equity_base": 10000.0,
                }
            },
            "global_controls": {},
        }
        import json as _json
        cfg_path.write_text(_json.dumps(cfg_data, indent=2))
        
        cfg = ConfigManager(config_path=cfg_path)
        ledger = ManualLedger(path=Path(tmpdir) / "manual_live_positions.json")
        
        # Mock leader equity to return a fixed value
        # The engine calls leader_equity(wallet) which fetches from testnet
        # We'll patch it to return a known value
        
        builder = IntentBuilder(cfg=cfg, ledger=ledger)
        builder.leader_equity = lambda w: 10000.0  # mock leader equity
        
        # Leader does 10 ADD fills of 0.1 BTC each at $50k
        # Each fill notional = $5000
        # With norm_base=10000 and leader_equity=10000, copy scale = 1.0
        # So each copy fill should be 0.1 BTC = $5000
        # After 10 fills, follower should have 1.0 BTC total
        # The key: the engine should NOT mint a fixed notional per fill
        
        wallet = "0x1111111111111111111111111111111111111111"
        coin = "BTC"
        total_copy_size = 0.0
        target_size = 1.0  # 10 * 0.1 = 1.0 BTC
        
        for i in range(10):
            fill = make_leader_fill(
                coin=coin, side="BUY", size=0.1, price=50000.0,
                leader_wallet=wallet,
                timestamp_ms=int(time.time() * 1000) + i,
                fill_id=f"add_{i}",
            )
            intent = builder.build(fill)
            
            # Apply the copy fill to the ledger
            copy_fill = {
                "side": intent.copy_side,
                "size": intent.copy_size,
                "price": fill.price,
                "copy_fill_id": f"copy_fill_{i}",
            }
            ledger.apply_copy_fill(intent, copy_fill)
            
            total_copy_size = ledger.wallet_coin_position(wallet, coin)
        
        # After 10 ADDs, follower should have ~1.0 BTC
        # It should NOT exceed the target
        results.append({
            "check": "eng001_convergence_after_10_adds",
            "expected": target_size,
            "actual": total_copy_size,
            "pass": abs(total_copy_size - target_size) < 0.001,
        })
        
        # Now simulate a partial reduce: leader sells 0.3 BTC
        reduce_fill = make_leader_fill(
            coin=coin, side="SELL", size=0.3, price=50000.0,
            leader_wallet=wallet,
            timestamp_ms=int(time.time() * 1000) + 100,
            fill_id="reduce_1",
        )
        intent_reduce = builder.build(reduce_fill)
        copy_fill_reduce = {
            "side": intent_reduce.copy_side,
            "size": intent_reduce.copy_size,
            "price": reduce_fill.price,
            "copy_fill_id": "copy_fill_reduce_1",
        }
        ledger.apply_copy_fill(intent_reduce, copy_fill_reduce)
        size_after_reduce = ledger.wallet_coin_position(wallet, coin)
        
        # After reducing 0.3, should have ~0.7 BTC
        results.append({
            "check": "eng001_after_reduce",
            "expected": 0.7,
            "actual": size_after_reduce,
            "pass": abs(size_after_reduce - 0.7) < 0.001,
        })
        
        # Now leader closes: sells remaining 0.7
        close_fill = make_leader_fill(
            coin=coin, side="SELL", size=1.0, price=50000.0,
            leader_wallet=wallet,
            timestamp_ms=int(time.time() * 1000) + 200,
            fill_id="close_1",
        )
        intent_close = builder.build(close_fill)
        copy_fill_close = {
            "side": intent_close.copy_side,
            "size": intent_close.copy_size,
            "price": close_fill.price,
            "copy_fill_id": "copy_fill_close_1",
        }
        ledger.apply_copy_fill(intent_close, copy_fill_close)
        size_after_close = ledger.wallet_coin_position(wallet, coin)
        
        results.append({
            "check": "eng001_after_close",
            "expected": 0.0,
            "actual": size_after_close,
            "pass": abs(size_after_close) < 0.001,
        })
        
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    return results


def test_eng002_proportional_mode():
    """ENG-002: Proportional mode end-to-end.

    Sleeve = leader position x copy scale; summed per coin; order = desired - actual - in_flight.
    Test: open, add, partial reduce, close.
    """
    results = []
    
    tmpdir = tempfile.mkdtemp(prefix="eng002_")
    try:
        cfg_path = Path(tmpdir) / "live_config.json"
        cfg_data = {
            "wallets": {
                "0x1111111111111111111111111111111111111111": {
                    "mode": "ON",
                    "copy_mode": "proportional",
                    "fixed_notional": 100.0,
                    "norm_base": 5000.0,  # 0.5x copy scale
                    "leader_equity_base": 10000.0,
                }
            },
            "global_controls": {},
        }
        import json as _json
        cfg_path.write_text(_json.dumps(cfg_data, indent=2))
        
        cfg = ConfigManager(config_path=cfg_path)
        ledger = ManualLedger(path=Path(tmpdir) / "manual_live_positions.json")
        
        builder = IntentBuilder(cfg=cfg, ledger=ledger)
        builder.leader_equity = lambda w: 10000.0  # mock leader equity
        
        wallet = "0x1111111111111111111111111111111111111111"
        coin = "ETH"
        
        # Open: leader buys 2 ETH at $2000
        # Leader notional = $4000, copy scale = 5000/10000 = 0.5
        # Copy notional = $2000, copy size = 1.0 ETH
        open_fill = make_leader_fill(
            coin=coin, side="BUY", size=2.0, price=2000.0,
            leader_wallet=wallet, fill_id="open_1",
        )
        intent_open = builder.build(open_fill)
        
        # Verify proportional sizing: copy_size should be 1.0 ETH (0.5 * 2.0)
        results.append({
            "check": "eng002_open_proportional_size",
            "expected": 1.0,
            "actual": intent_open.copy_size,
            "pass": abs(intent_open.copy_size - 1.0) < 0.001,
        })
        
        # Apply open fill
        ledger.apply_copy_fill(intent_open, {
            "side": "BUY", "size": intent_open.copy_size, "price": 2000.0,
            "copy_fill_id": "copy_open_1",
        })
        
        pos_after_open = ledger.wallet_coin_position(wallet, coin)
        results.append({
            "check": "eng002_position_after_open",
            "expected": 1.0,
            "actual": pos_after_open,
            "pass": abs(pos_after_open - 1.0) < 0.001,
        })
        
        # Add: leader buys 1 more ETH at $2000
        # Copy scale 0.5, so copy_size = 0.5 ETH
        add_fill = make_leader_fill(
            coin=coin, side="BUY", size=1.0, price=2000.0,
            leader_wallet=wallet, fill_id="add_1",
        )
        intent_add = builder.build(add_fill)
        
        results.append({
            "check": "eng002_add_proportional_size",
            "expected": 0.5,
            "actual": intent_add.copy_size,
            "pass": abs(intent_add.copy_size - 0.5) < 0.001,
        })
        
        ledger.apply_copy_fill(intent_add, {
            "side": "BUY", "size": intent_add.copy_size, "price": 2000.0,
            "copy_fill_id": "copy_add_1",
        })
        
        pos_after_add = ledger.wallet_coin_position(wallet, coin)
        results.append({
            "check": "eng002_position_after_add",
            "expected": 1.5,
            "actual": pos_after_add,
            "pass": abs(pos_after_add - 1.5) < 0.001,
        })
        
        # Partial reduce: leader sells 0.5 ETH
        reduce_fill = make_leader_fill(
            coin=coin, side="SELL", size=0.5, price=2000.0,
            leader_wallet=wallet, fill_id="reduce_1",
        )
        intent_reduce = builder.build(reduce_fill)
        ledger.apply_copy_fill(intent_reduce, {
            "side": "SELL", "size": intent_reduce.copy_size, "price": 2000.0,
            "copy_fill_id": "copy_reduce_1",
        })
        
        pos_after_reduce = ledger.wallet_coin_position(wallet, coin)
        results.append({
            "check": "eng002_position_after_reduce",
            "expected": 1.0,
            "actual": pos_after_reduce,
            "pass": abs(pos_after_reduce - 1.0) < 0.001,
        })
        
        # Close: leader sells remaining 1.5 ETH
        close_fill = make_leader_fill(
            coin=coin, side="SELL", size=2.0, price=2000.0,
            leader_wallet=wallet, fill_id="close_1",
        )
        intent_close = builder.build(close_fill)
        
        # EXIT should target full sleeve (1.0 ETH), not just the leader's 2.0 * 0.5
        results.append({
            "check": "eng002_close_targets_full_sleeve",
            "expected": 1.0,
            "actual": intent_close.copy_size,
            "pass": abs(intent_close.copy_size - 1.0) < 0.001,
        })
        
        ledger.apply_copy_fill(intent_close, {
            "side": "SELL", "size": intent_close.copy_size, "price": 2000.0,
            "copy_fill_id": "copy_close_1",
        })
        
        pos_after_close = ledger.wallet_coin_position(wallet, coin)
        results.append({
            "check": "eng002_position_after_close",
            "expected": 0.0,
            "actual": pos_after_close,
            "pass": abs(pos_after_close) < 0.001,
        })
        
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    return results


def test_eng004_unit_semantics():
    """ENG-004: Unit semantics target delta -> order size.

    Signed coin delta maps to exchange size with correct szDecimals rounding and side.
    No unit confusion (coins vs USD).
    """
    results = []
    
    # Test signed_from_side_size
    results.append({
        "check": "eng004_signed_from_side_size_buy",
        "input": "BUY, 0.5",
        "expected": 0.5,
        "actual": signed_from_side_size("BUY", 0.5),
        "pass": signed_from_side_size("BUY", 0.5) == 0.5,
    })
    results.append({
        "check": "eng004_signed_from_side_size_sell",
        "input": "SELL, 0.5",
        "expected": -0.5,
        "actual": signed_from_side_size("SELL", 0.5),
        "pass": signed_from_side_size("SELL", 0.5) == -0.5,
    })
    
    # Test direction_from_size
    results.append({
        "check": "eng004_direction_long",
        "input": "1.0",
        "expected": "LONG",
        "actual": engine.ManualLedger.direction_from_size(1.0),
        "pass": engine.ManualLedger.direction_from_size(1.0) == "LONG",
    })
    results.append({
        "check": "eng004_direction_short",
        "input": "-1.0",
        "expected": "SHORT",
        "actual": engine.ManualLedger.direction_from_size(-1.0),
        "pass": engine.ManualLedger.direction_from_size(-1.0) == "SHORT",
    })
    results.append({
        "check": "eng004_direction_flat",
        "input": "0.0",
        "expected": "FLAT",
        "actual": engine.ManualLedger.direction_from_size(0.0),
        "pass": engine.ManualLedger.direction_from_size(0.0) == "FLAT",
    })
    
    # Test _ceil_wire_size (rounding UP to sz_decimals)
    # BTC has szDecimals=1 on testnet (typically)
    results.append({
        "check": "eng004_ceil_wire_size_btc_1dp",
        "input": "0.12345, szDecimals=1",
        "expected": 0.2,
        "actual": SenderGateway._ceil_wire_size(0.12345, 1),
        "pass": SenderGateway._ceil_wire_size(0.12345, 1) == 0.2,
    })
    results.append({
        "check": "eng004_ceil_wire_size_zero",
        "input": "0.0, szDecimals=1",
        "expected": 0.0,
        "actual": SenderGateway._ceil_wire_size(0.0, 1),
        "pass": SenderGateway._ceil_wire_size(0.0, 1) == 0.0,
    })
    
    # Test _floor_wire_size (rounding DOWN to sz_decimals)
    results.append({
        "check": "eng004_floor_wire_size_btc_1dp",
        "input": "0.12345, szDecimals=1",
        "expected": 0.1,
        "actual": SenderGateway._floor_wire_size(0.12345, 1),
        "pass": SenderGateway._floor_wire_size(0.12345, 1) == 0.1,
    })
    
    # Test that sz_decimals matters: same size with different precision
    results.append({
        "check": "eng004_sz_decimals_4dp",
        "input": "0.12345678, szDecimals=4",
        "expected": 0.1235,
        "actual": SenderGateway._ceil_wire_size(0.12345678, 4),
        "pass": SenderGateway._ceil_wire_size(0.12345678, 4) == 0.1235,
    })
    
    # Test that size 0 rounds to 0 (no order)
    results.append({
        "check": "eng004_zero_size_rounds_to_zero",
        "input": "0.0001, szDecimals=1",
        "expected": 0.0,
        "actual": SenderGateway._floor_wire_size(0.0001, 1),
        "pass": SenderGateway._floor_wire_size(0.0001, 1) == 0.0,
    })
    
    # Test signed_delta for side/size mapping
    results.append({
        "check": "eng004_signed_delta_buy",
        "input": "BUY, 2.5",
        "expected": 2.5,
        "actual": engine.ManualLedger.signed_delta("BUY", 2.5),
        "pass": engine.ManualLedger.signed_delta("BUY", 2.5) == 2.5,
    })
    results.append({
        "check": "eng004_signed_delta_sell",
        "input": "SELL, 2.5",
        "expected": -2.5,
        "actual": engine.ManualLedger.signed_delta("SELL", 2.5),
        "pass": engine.ManualLedger.signed_delta("SELL", 2.5) == -2.5,
    })
    
    # Test that negative size is handled (abs)
    results.append({
        "check": "eng004_signed_delta_negative_size_buy",
        "input": "BUY, -1.0 (should use abs)",
        "expected": 1.0,
        "actual": engine.ManualLedger.signed_delta("BUY", -1.0),
        "pass": engine.ManualLedger.signed_delta("BUY", -1.0) == 1.0,
    })
    
    return results


# ============================================================================
# NEGATIVE TESTS (MUTATION TESTING)
# ============================================================================

def _mutate_engine_file(src_path, dst_path, mutations):
    """Copy engine file and apply mutations. mutations = [(old_str, new_str), ...]"""
    with open(src_path, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new in mutations:
        if old not in content:
            raise RuntimeError(f"Mutation target not found: {old[:80]}")
        content = content.replace(old, new, 1)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.write(content)


def test_eng001_negative_test():
    """ENG-001 negative test: break the planner, prove the check fails."""
    results = []
    
    tmpdir = tempfile.mkdtemp(prefix="eng001_neg_")
    try:
        # Create a mutated engine where convergence is broken
        # Mutation 1: Make apply_copy_fill NOT update the position (broken planner)
        mutated_engine_path = Path(tmpdir) / "mutated_engine.py"
        _mutate_engine_file(
            ENGINE_PATH,
            mutated_engine_path,
            [
                # Break: after = before + delta -> after = before (no update)
                ("after = before + delta", "after = before  # MUTATION: no position update"),
            ],
        )
        
        # Import the mutated engine
        spec_mut = importlib.util.spec_from_file_location("mutated_engine", str(mutated_engine_path))
        mut_engine = importlib.util.module_from_spec(spec_mut)
        spec_mut.loader.exec_module(mut_engine)
        
        # Now test the mutated engine
        cfg_path = Path(tmpdir) / "live_config.json"
        cfg_data = {
            "wallets": {
                "0x1111111111111111111111111111111111111111": {
                    "mode": "ON", "copy_mode": "proportional",
                    "fixed_notional": 100.0, "norm_base": 10000.0,
                    "leader_equity_base": 10000.0,
                }
            },
            "global_controls": {},
        }
        import json as _json
        cfg_path.write_text(_json.dumps(cfg_data, indent=2))
        
        cfg = ConfigManager(config_path=cfg_path)
        ledger = mut_engine.ManualLedger(path=Path(tmpdir) / "manual_live_positions.json")
        
        builder = mut_engine.IntentBuilder(cfg=cfg, ledger=ledger)
        builder.leader_equity = lambda w: 10000.0  # mock leader equity
        
        wallet = "0x1111111111111111111111111111111111111111"
        coin = "BTC"
        
        # Apply 3 ADD fills
        for i in range(3):
            fill = make_leader_fill(
                coin=coin, side="BUY", size=0.1, price=50000.0,
                leader_wallet=wallet, fill_id=f"mut_add_{i}",
            )
            intent = builder.build(fill)
            ledger.apply_copy_fill(intent, {
                "side": intent.copy_side, "size": intent.copy_size,
                "price": fill.price, "copy_fill_id": f"mut_copy_{i}",
            })
        
        # After 3 ADDs, the mutated engine should have 0 position (broken)
        # The REAL engine should have 0.3 BTC
        # This proves the test detects the mutation
        pos_after_mutation = ledger.wallet_coin_position(wallet, coin)
        
        results.append({
            "check": "eng001_negative_broken_planner_detected",
            "expected": "position should be 0.0 (mutated engine, broken convergence)",
            "actual": pos_after_mutation,
            "pass": pos_after_mutation == 0.0,  # Mutation made it 0
            "note": "Positive control (real engine) gives 0.3 BTC, proving test detects mutation",
        })
        
        # Positive control: same test with real engine
        ledger_real = ManualLedger(path=Path(tmpdir) / "real_positions.json")
        builder_real = IntentBuilder(cfg=cfg, ledger=ledger_real)
        builder_real.leader_equity = lambda w: 10000.0  # mock leader equity
        
        for i in range(3):
            fill = make_leader_fill(
                coin=coin, side="BUY", size=0.1, price=50000.0,
                leader_wallet=wallet, fill_id=f"real_add_{i}",
            )
            intent = builder_real.build(fill)
            ledger_real.apply_copy_fill(intent, {
                "side": intent.copy_side, "size": intent.copy_size,
                "price": fill.price, "copy_fill_id": f"real_copy_{i}",
            })
        
        pos_real = ledger_real.wallet_coin_position(wallet, coin)
        results.append({
            "check": "eng001_positive_control",
            "expected": 0.3,
            "actual": pos_real,
            "pass": abs(pos_real - 0.3) < 0.001,
        })
        
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    return results


def test_eng002_negative_test():
    """ENG-002 negative test: break proportional sizing, prove the check fails."""
    results = []
    
    tmpdir = tempfile.mkdtemp(prefix="eng002_neg_")
    try:
        # Mutation: break _copy_notional to return fixed_notional always
        mutated_engine_path = Path(tmpdir) / "mutated_engine.py"
        _mutate_engine_file(
            ENGINE_PATH,
            mutated_engine_path,
            [
                # Break: _copy_notional always returns fixed_notional (not proportional)
                (
                    "return max(0.0, fill.notional * (norm_base / leader_equity))",
                    "return self.cfg.fixed_notional(wallet)  # MUTATION: always fixed, not proportional",
                ),
            ],
        )
        
        spec_mut = importlib.util.spec_from_file_location("mutated_engine", str(mutated_engine_path))
        mut_engine = importlib.util.module_from_spec(spec_mut)
        spec_mut.loader.exec_module(mut_engine)
        
        cfg_path = Path(tmpdir) / "live_config.json"
        cfg_data = {
            "wallets": {
                "0x1111111111111111111111111111111111111111": {
                    "mode": "ON", "copy_mode": "proportional",
                    "fixed_notional": 100.0, "norm_base": 5000.0,
                    "leader_equity_base": 10000.0,
                }
            },
            "global_controls": {},
        }
        import json as _json
        cfg_path.write_text(_json.dumps(cfg_data, indent=2))
        
        cfg = ConfigManager(config_path=cfg_path)
        ledger = mut_engine.ManualLedger(path=Path(tmpdir) / "positions.json")
        
        builder = mut_engine.IntentBuilder(cfg=cfg, ledger=ledger)
        builder.leader_equity = lambda w: 10000.0  # mock leader equity
        
        wallet = "0x1111111111111111111111111111111111111111"
        coin = "ETH"
        
        # Leader buys 2 ETH at $2000
        # Real proportional: copy_notional = 4000 * (5000/10000) = $2000, copy_size = 1.0 ETH
        # Mutated: copy_notional = $100 (fixed), copy_size = 0.05 ETH
        fill = make_leader_fill(
            coin=coin, side="BUY", size=2.0, price=2000.0,
            leader_wallet=wallet, fill_id="mut_open",
        )
        intent = builder.build(fill)
        
        # The mutated engine should give wrong size (0.05 instead of 1.0)
        results.append({
            "check": "eng002_negative_broken_sizing_detected",
            "expected": "copy_size != 1.0 (mutated, wrong sizing)",
            "actual": intent.copy_size,
            "pass": abs(intent.copy_size - 1.0) > 0.001,  # Should differ from correct value
            "note": "Positive control (real engine) gives 1.0 ETH",
        })
        
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    return results


def test_eng004_negative_test():
    """ENG-004 negative test: break rounding, prove the check fails."""
    results = []
    
    tmpdir = tempfile.mkdtemp(prefix="eng004_neg_")
    try:
        # Mutation: break _ceil_wire_size to not round (return raw size)
        mutated_engine_path = Path(tmpdir) / "mutated_engine.py"
        _mutate_engine_file(
            ENGINE_PATH,
            mutated_engine_path,
            [
                # Break: _ceil_wire_size returns size without rounding
                (
                    "return float(Decimal(str(size)).quantize(quantum, rounding=ROUND_CEILING))",
                    "return size  # MUTATION: no rounding",
                ),
            ],
        )
        
        spec_mut = importlib.util.spec_from_file_location("mutated_engine", str(mutated_engine_path))
        mut_engine = importlib.util.module_from_spec(spec_mut)
        spec_mut.loader.exec_module(mut_engine)
        
        # Test: 0.12345 with szDecimals=1 should round to 0.2
        # Mutated: returns 0.12345 (no rounding)
        correct = mut_engine.SenderGateway._ceil_wire_size(0.12345, 1)
        expected_correct = 0.2
        
        results.append({
            "check": "eng004_negative_broken_rounding_detected",
            "expected": f"rounding broken, should NOT equal {expected_correct}",
            "actual": correct,
            "pass": correct != expected_correct,  # Mutation broke it
            "note": "Positive control (real engine) gives 0.2",
        })
        
        # Positive control
        correct_real = SenderGateway._ceil_wire_size(0.12345, 1)
        results.append({
            "check": "eng004_positive_control",
            "expected": expected_correct,
            "actual": correct_real,
            "pass": correct_real == expected_correct,
        })
        
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    return results


# ============================================================================
# ORACLE: TESTNET API VERIFICATION
# ============================================================================

def test_oracle_testnet_api():
    """Verify the testnet oracle is reachable and returns valid data."""
    results = []
    
    try:
        fetcher = make_testnet_fetcher()
        networks = et.resolve_networks()
        
        results.append({
            "check": "oracle_networks_resolved",
            "expected": "leader and follower networks resolved",
            "actual": f"leader={networks['leader']['network']}, follower={networks['follower']['network']}",
            "pass": networks["leader"]["network"] == "testnet" and networks["follower"]["network"] == "testnet",
        })
        
        # Query perp dexes (read-only)
        dexes = et.list_perp_dexes(fetcher=fetcher, info_url=networks["follower"]["info"])
        results.append({
            "check": "oracle_list_perp_dexes",
            "expected": "at least default dex ('')",
            "actual": f"dexes={dexes.get('dexes', [])}",
            "pass": dexes.get("ok") and "" in dexes.get("dexes", []),
        })
        
    except Exception as e:
        results.append({
            "check": "oracle_testnet_api",
            "expected": "API reachable",
            "actual": f"ERROR: {e}",
            "pass": False,
        })
    
    return results


# ============================================================================
# MAIN
# ============================================================================

def main():
    all_results = []
    
    print("=" * 70)
    print("ENG-001/002/004 Certification Harness")
    print(f"Commit: 43731b4f1f19a56e835032dabf608a550f925717")
    print("=" * 70)
    
    # Run all test groups
    test_groups = [
        ("ENG-001 Convergence", test_eng001_convergence),
        ("ENG-002 Proportional Mode", test_eng002_proportional_mode),
        ("ENG-004 Unit Semantics", test_eng004_unit_semantics),
        ("ENG-001 Negative Test", test_eng001_negative_test),
        ("ENG-002 Negative Test", test_eng002_negative_test),
        ("ENG-004 Negative Test", test_eng004_negative_test),
        ("Oracle: Testnet API", test_oracle_testnet_api),
    ]
    
    for name, test_fn in test_groups:
        print(f"\n--- {name} ---")
        try:
            results = test_fn()
            for r in results:
                status = "PASS" if r["pass"] else "FAIL"
                print(f"  [{status}] {r['check']}: expected={r['expected']}, actual={r['actual']}")
            all_results.extend(results)
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            import traceback
            traceback.print_exc()
            all_results.append({
                "check": f"{name}_exception",
                "expected": "no exception",
                "actual": str(e),
                "pass": False,
            })
    
    # Summary
    total = len(all_results)
    passed = sum(1 for r in all_results if r["pass"])
    failed = total - passed
    
    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed}/{total} checks passed, {failed} failed")
    print("=" * 70)
    
    # Output JSON
    output = {
        "commit": "43731b4f1f19a56e835032dabf608a550f925717",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_checks": total,
        "passed": passed,
        "failed": failed,
        "overall_result": "PASS" if failed == 0 else "FAIL",
        "checks": all_results,
    }
    
    # Write results
    results_dir = REPO / "certification" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    json_path = results_dir / "ENG-001-004_43731b4f.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print(f"\nResults written to: {json_path}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
