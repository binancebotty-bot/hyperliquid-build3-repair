#!/usr/bin/env python3
"""Offline ownership proof regression for default + xyz DEX; no exchange requests/orders."""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ["HL_LIVE_AUDIT_DIR"] = tempfile.mkdtemp(prefix="xyz_gate_")
os.environ["HL_LIVE_ENV_FILE"] = str(Path(os.environ["HL_LIVE_AUDIT_DIR"]) / "absent.env")
os.environ["HL_LEADER_NETWORK"] = "testnet"
os.environ["HL_FOLLOWER_NETWORK"] = "testnet"
os.environ["HL_LIVE_SCOPE_SWEEP_THREAD"] = "0"
import HL_Live_Copy_Service_Core as c

checks = []
def check(name, condition, detail=""):
    checks.append(bool(condition))
    print("RESULT::%s_%s%s" % (
        name, "PASS" if condition else "FAIL",
        (" | " + str(detail)[:240]) if not condition else ""))

def dex_positions(*positions):
    return {"assetPositions": [{"position": {"coin": coin, "szi": str(sz)}} for coin, sz in positions]}

default = dex_positions(("BTC", 2.0))
xyz = dex_positions(("xyz:ABC", -3.0))
snapshot = {"raw": default, "raw_by_dex": {"": default, "xyz": xyz},
            "positions_by_coin": {"xyz:ABC": 0.0}}  # advisory index must not hide real xyz
def persist(snap):
    with patch.object(c, "load_json", return_value=snap):
        return c.SenderGateway._persisted_exchange_positions()

ex, reason = persist(snapshot)
btc = c.canonical_coin_key("BTC")
xyz_key = c.canonical_coin_key("xyz:ABC")
check("DEFAULT_AND_XYZ_MERGE", not reason and ex.get(btc) == 2.0 and ex.get(xyz_key) == -3.0,
      (ex, reason))
check("DEFAULT_NOT_DOUBLE_COUNTED", ex.get(btc) == 2.0, ex)

snap_no_default = {"raw": default, "raw_by_dex": {"xyz": xyz}}
ex, reason = persist(snap_no_default)
check("DEFAULT_RAW_FALLBACK_WHEN_MISSING_BY_DEX", not reason
      and ex.get(btc) == 2.0 and ex.get(xyz_key) == -3.0, (ex, reason))

ex, reason = persist({"raw": default})
check("LEGACY_DEFAULT_ONLY_STILL_WORKS", not reason and ex == {btc: 2.0}, (ex, reason))

ex, reason = persist({"raw": default, "raw_by_dex": {"": default, "xyz": {}}})
check("MALFORMED_XYZ_FAILS_CLOSED", bool(reason) and not ex and "xyz" in reason, (ex, reason))

# End-to-end ownership gate: a follower XYZ position absent from the manual
# sleeves MUST block an entry, not silently treat exchange net as zero.
gateway = c.SenderGateway.__new__(c.SenderGateway)
gateway.ledger = SimpleNamespace(coin_net=lambda coin: 0.0)
gateway._audit_proof_block_reason = lambda: ""
gateway._manual_sleeves_for_coin = lambda coin: []
intent = SimpleNamespace(
    notes="lifecycle=ENTRY;", copy_side="BUY", copy_size=1.0,
    wallet_position_before=0.0, reduce_only_intended=False,
    fill=SimpleNamespace(coin="xyz:ABC", leader_wallet="0x" + "a" * 40))
with patch.object(c, "load_json", return_value=snapshot):
    allowed, block = gateway._pre_send_ownership_gate(intent)
check("OWNERSHIP_GATE_SEES_UNEXPLAINED_XYZ", not allowed
      and block.get("terminal_state") == "OWNERSHIP_GATE_UNEXPLAINED_EXCHANGE_POSITION"
      and block.get("exchange_net") == -3.0, block)

flat = {"raw": default, "raw_by_dex": {"": default, "xyz": dex_positions()}}
with patch.object(c, "load_json", return_value=flat):
    allowed, block = gateway._pre_send_ownership_gate(intent)
check("FLAT_XYZ_NOT_FALSELY_BLOCKED", allowed, block)

failed = len(checks) - sum(checks)
print("TOTAL=%d FAILED=%d" % (len(checks), failed))
sys.exit(1 if failed else 0)
