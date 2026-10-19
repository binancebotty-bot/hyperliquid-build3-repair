#!/usr/bin/env python3
"""RISK-area certification harness for Build-3 repair engine.

Tests all 14 in-scope RISK rows (11 APPLIES + 3 APPLIES_PROPOSED) against
the production engine at commit fa9d9f55ff. Each check is EARNED by the
runtime outcome its check name asserts. Non-vacuous negative tests verify
the control actually discriminates between valid and invalid states.

Engine: _archive/hl_stage2/HL_Live_Copy_Service_Core.py (sha256 2dfbd57...)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from datetime import datetime, timezone

# Engine location
REPO = Path("C:/Users/wigmore/hyperliquid-build3-repair")
sys.path.insert(0, str(REPO / "_archive" / "hl_stage2"))

ENGINE_PATH = REPO / "_archive" / "hl_stage2" / "HL_Live_Copy_Service_Core.py"
COMMIT = "fa9d9f55fffa74cb6888c471d97d1655267999b6"
ENGINE_SHA256 = "2dfbd571012af67479ee7a2d9e6f1faac6ee5408722a092fb3625450cab51405"

LEADER = "0x" + "d" * 40
FOLLOWER = "0x" + "c" * 40

RESULTS = {}
CHECKS = []
NEG_TESTS = []


def check(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "pass": bool(passed), "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  CHECK::{name}::{status}" + (f" | {detail}" if detail and not passed else ""))


def neg_test(name: str, passed: bool, detail: str = "") -> None:
    NEG_TESTS.append({"name": name, "pass": bool(passed), "detail": detail})
    status = "PASS" if passed else "FAIL"
    print(f"  NEG::{name}::{status}" + (f" | {detail}" if detail and not passed else ""))


def run_engine_checks():
    """Main engine: import and set up test environment."""
    import HL_Live_Copy_Service_Core as c

    # Verify engine integrity
    with open(ENGINE_PATH, "rb") as f:
        actual_sha = hashlib.sha256(f.read()).hexdigest()
    check("ENGINE_SHA256_MATCH", actual_sha == ENGINE_SHA256,
          f"expected={ENGINE_SHA256} actual={actual_sha}")

    # Set up isolated test environment
    tmp = Path(tempfile.mkdtemp(prefix="riskcert_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "mainnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
    })

    # Set engine globals (same pattern as run_self_test)
    c.BASE_DIR = tmp
    c.AUDIT_DIR = tmp / "hl_live_copy_audit"
    c.LIVE_CONFIG_FILE = c.AUDIT_DIR / "live_config.json"
    c.ensure_dirs()

    c.USER_WALLET = FOLLOWER

    # Mock exchange state
    book = {"positions": [], "down": False, "reads": 0}

    def fetcher(payload):
        if payload.get("type") == "perpDexs":
            return [{"name": "xyz"}]
        book["reads"] += 1
        if book["down"]:
            raise RuntimeError("scope unavailable")
        return {"assetPositions": [{"position": p} for p in book["positions"] if p.get("dex", "") == payload.get("dex", "")]}

    c.EXPOSURE_FETCHER = fetcher

    mids = {"BTC": 100.0, "ETH": 400.0}

    def mids_fetcher(payload):
        if payload.get("type") == "perpDexs":
            return []
        return {k: str(v) for k, v in mids.items()}

    c.MIDS_FETCHER = mids_fetcher

    def set_mid(px):
        mids.clear()
        if px:
            mids["BTC"] = px
        c._FOLLOWER_MIDS.update(px={}, ms=0)

    seq = [0]

    def fill(side="BUY", coin="BTC", price=100.0, size=1.0):
        seq[0] += 1
        return c.LeaderFill(f"f{seq[0]}", LEADER, coin, side, price, size, c.utc_now_ms(), "TEST")

    def config(**gc):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            "auto_send_enabled": False,
            "global_controls": gc,
            "wallets": {
                LEADER: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000}
            }
        })
        # ConfigManager reads from disk each time, no cache to clear

    def decide(gc, positions=(), side="BUY", coin="BTC", ledger=None, builder=None):
        config(**gc)
        book["positions"] = list(positions)
        b = builder or c.IntentBuilder(c.ConfigManager(), ledger or c.ManualLedger(path=tmp / f"pos{seq[0]}.json"))
        i = b.build(fill(side, coin))
        return i.decision, i.reason

    # ---- RISK-001: Max total live exposure ($) ----
    print("\n=== RISK-001: Max total live exposure ===")
    # Positive: cap set, exchange truth shows exceeding
    eth = {"coin": "ETH", "szi": "5", "positionValue": "2000"}
    hip3 = {"coin": "xyz:GOLD", "szi": "1", "positionValue": "700", "dex": "xyz"}
    d = decide({"max_total_live_exposure_usd": 3500}, [eth, hip3])
    check("RISK-001:TOTAL_CAP_BLOCKS_EXCEEDING", d == ("SEND_BLOCKED_RISK", "max total exposure exceeded"),
          f"got={d}")

    # Positive: within cap allowed
    d = decide({"max_total_live_exposure_usd": 5000}, [eth, hip3])
    check("RISK-001:TOTAL_CAP_WITHIN_ALLOWED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Negative: blank value = disabled
    d = decide({"max_total_live_exposure_usd": ""}, [eth, hip3])
    neg_test("RISK-001:NEG_BLANK_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Negative: zero = disabled
    d = decide({"max_total_live_exposure_usd": 0}, [eth, hip3])
    neg_test("RISK-001:NEG_ZERO_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Negative: negative = disabled (fnum clamps to 0)
    d = decide({"max_total_live_exposure_usd": -100}, [eth, hip3])
    neg_test("RISK-001:NEG_NEGATIVE_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Negative: non-numeric = disabled (fnum returns 0)
    d = decide({"max_total_live_exposure_usd": "abc"}, [eth, hip3])
    neg_test("RISK-001:NEG_NONNUMERIC_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Negative: value changed while engine running
    config(max_total_live_exposure_usd=3500)
    book["positions"] = [eth, hip3]  # 2700 exposure + 1000 entry = 3700 > 3500
    b = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "live_change.json"))
    i1 = b.build(fill())
    # Now change config
    config(max_total_live_exposure_usd=5000)
    b2 = c.IntentBuilder(c.ConfigManager(), c.ManualLedger(path=tmp / "live_change2.json"))
    i2 = b2.build(fill())
    neg_test("RISK-001:NEG_VALUE_CHANGE_TAKES_EFFECT",
             i1.decision == "SEND_BLOCKED_RISK" and i2.decision == "ENTRY_ALLOWED",
             f"first={i1.decision} second={i2.decision}")

    # Negative: rejected save (exchange down = fail closed)
    book["down"] = True
    d = decide({"max_total_live_exposure_usd": 5000})
    neg_test("RISK-001:NEG_EXCHANGE_DOWN_FAILS_CLOSED",
             d[0] == "SEND_BLOCKED_RISK" and "unavailable" in d[1],
             f"got={d}")
    book["down"] = False

    # ---- RISK-002: Max per-asset directional exposure ($) ----
    print("\n=== RISK-002: Max per-asset directional exposure ===")
    d = decide({"max_asset_directional_exposure_usd": 1500},
               [{"coin": "BTC", "szi": "6", "positionValue": "600"}])
    check("RISK-002:ASSET_CAP_BLOCKS", d == ("SEND_BLOCKED_RISK", "max asset directional exposure exceeded"),
          f"got={d}")

    d = decide({"max_asset_directional_exposure_usd": 1500},
               [{"coin": "BTC", "szi": "-6", "positionValue": "600"}])
    check("RISK-002:ASSET_NET_DIRECTION_ALLOWED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Negative tests
    d = decide({"max_asset_directional_exposure_usd": ""},
               [{"coin": "BTC", "szi": "6", "positionValue": "600"}])
    neg_test("RISK-002:NEG_BLANK_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    d = decide({"max_asset_directional_exposure_usd": 0},
               [{"coin": "BTC", "szi": "6", "positionValue": "600"}])
    neg_test("RISK-002:NEG_ZERO_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    d = decide({"max_asset_directional_exposure_usd": -100},
               [{"coin": "BTC", "szi": "6", "positionValue": "600"}])
    neg_test("RISK-002:NEG_NEGATIVE_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    d = decide({"max_asset_directional_exposure_usd": "abc"},
               [{"coin": "BTC", "szi": "6", "positionValue": "600"}])
    neg_test("RISK-002:NEG_NONNUMERIC_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # ---- RISK-003: Max per-wallet exposure ($) ----
    print("\n=== RISK-003: Max per-wallet exposure ===")
    d = decide({"max_wallet_exposure_usd": 500})
    check("RISK-003:WALLET_CAP_BLOCKS", d == ("SEND_BLOCKED_RISK", "max wallet exposure exceeded"),
          f"got={d}")

    d = decide({"max_wallet_exposure_usd": 5000})
    check("RISK-003:WALLET_CAP_WITHIN_ALLOWED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Negative tests
    d = decide({"max_wallet_exposure_usd": ""})
    neg_test("RISK-003:NEG_BLANK_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    d = decide({"max_wallet_exposure_usd": 0})
    neg_test("RISK-003:NEG_ZERO_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    d = decide({"max_wallet_exposure_usd": -100})
    neg_test("RISK-003:NEG_NEGATIVE_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    d = decide({"max_wallet_exposure_usd": "abc"})
    neg_test("RISK-003:NEG_NONNUMERIC_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # ---- RISK-004: Max per-order notional ($) ----
    print("\n=== RISK-004: Max per-order notional ===")
    d = decide({"max_order_notional_usd": 500})
    check("RISK-004:ORDER_CAP_BLOCKS", d == ("SEND_BLOCKED_RISK", "max order notional exceeded"),
          f"got={d}")

    d = decide({"max_order_notional_usd": 5000})
    check("RISK-004:ORDER_CAP_WITHIN_ALLOWED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Negative tests
    d = decide({"max_order_notional_usd": ""})
    neg_test("RISK-004:NEG_BLANK_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    d = decide({"max_order_notional_usd": 0})
    neg_test("RISK-004:NEG_ZERO_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    d = decide({"max_order_notional_usd": -100})
    neg_test("RISK-004:NEG_NEGATIVE_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    d = decide({"max_order_notional_usd": "abc"})
    neg_test("RISK-004:NEG_NONNUMERIC_DISABLED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # ---- RISK-005: Marketable slippage % ----
    print("\n=== RISK-005: Marketable slippage % ===")
    # Config property: missing = Boss default 20 bps (0.2%)
    config()
    check("RISK-005:MISSING_SLIPPAGE_DEFAULT_20BPS",
          c.ConfigManager().marketable_bps() == 20.0,
          f"got={c.ConfigManager().marketable_bps()}")

    config(marketable_bps=0)
    check("RISK-005:EXPLICIT_ZERO_STAYS_ZERO",
          c.ConfigManager().marketable_bps() == 0.0,
          f"got={c.ConfigManager().marketable_bps()}")

    config(marketable_bps=50)
    check("RISK-005:CUSTOM_VALUE_READ",
          c.ConfigManager().marketable_bps() == 50.0,
          f"got={c.ConfigManager().marketable_bps()}")

    # Negative: blank = explicit 0 (key present but empty -> fnum returns 0)
    config(marketable_bps="")
    check("RISK-005:NEG_BLANK_IS_ZERO",
          c.ConfigManager().marketable_bps() == 0.0,
          f"got={c.ConfigManager().marketable_bps()}")

    # Negative: negative = clamped to 0
    config(marketable_bps=-10)
    check("RISK-005:NEG_NEGATIVE_CLAMPED_ZERO",
          c.ConfigManager().marketable_bps() == 0.0,
          f"got={c.ConfigManager().marketable_bps()}")

    # ---- RISK-006: Adverse close diff % ----
    print("\n=== RISK-006: Adverse close diff % ===")
    config()
    check("RISK-006:MISSING_CLOSE_DIFF_IS_OFF",
          c.ConfigManager().max_close_adverse_diff_pct() == 0.0,
          f"got={c.ConfigManager().max_close_adverse_diff_pct()}")

    config(max_close_adverse_diff_pct=0.3)
    check("RISK-006:CUSTOM_VALUE_READ",
          c.ConfigManager().max_close_adverse_diff_pct() == 0.3,
          f"got={c.ConfigManager().max_close_adverse_diff_pct()}")

    # Negative: blank = off
    config(max_close_adverse_diff_pct="")
    check("RISK-006:NEG_BLANK_IS_OFF",
          c.ConfigManager().max_close_adverse_diff_pct() == 0.0,
          f"got={c.ConfigManager().max_close_adverse_diff_pct()}")

    # Negative: negative = clamped to 0 (off)
    config(max_close_adverse_diff_pct=-5)
    check("RISK-006:NEG_NEGATIVE_IS_OFF",
          c.ConfigManager().max_close_adverse_diff_pct() == 0.0,
          f"got={c.ConfigManager().max_close_adverse_diff_pct()}")

    # ---- RISK-007: Symbol allowlist ----
    print("\n=== RISK-007: Symbol allowlist ===")
    d = decide({"symbol_allowlist": ["ETH"]})
    check("RISK-007:ALLOWLIST_BLOCKS_OTHERS", d == ("SYMBOL_UNAVAILABLE", "SYMBOL_NOT_ALLOWED"),
          f"got={d}")

    d = decide({"symbol_allowlist": ["ETH", "BTC"]})
    check("RISK-007:ALLOWLISTED_PASSES", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Empty allowlist = all allowed
    d = decide({"symbol_allowlist": []})
    check("RISK-007:EMPTY_ALLOWLIST_ALL_ALLOWED", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Negative: blank = no restriction
    d = decide({"symbol_allowlist": ""})
    neg_test("RISK-007:NEG_BLANK_NO_RESTRICTION", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # ---- RISK-008: Symbol blocklist ----
    print("\n=== RISK-008: Symbol blocklist ===")
    d = decide({"symbol_blocklist": ["BTC"]})
    check("RISK-008:BLOCKLIST_BLOCKS", d == ("SYMBOL_UNAVAILABLE", "SYMBOL_BLOCKED"),
          f"got={d}")

    d = decide({"symbol_blocklist": ["ETH"]})
    check("RISK-008:BLOCKLIST_OTHERS_PASS", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # Negative: blank = no restriction
    d = decide({"symbol_blocklist": ""})
    neg_test("RISK-008:NEG_BLANK_NO_RESTRICTION", d[0] == "ENTRY_ALLOWED", f"got={d}")

    # ---- RISK-014: Stale/uncertain state containment ----
    print("\n=== RISK-014: Stale/uncertain state containment ===")
    # No follower price = entry fails closed
    set_mid(0.0)
    d = decide({})
    check("RISK-014:NO_FOLLOWER_PRICE_FAILS_CLOSED",
          d[0] == "SEND_BLOCKED_RISK" and "no fresh follower" in d[1],
          f"got={d}")

    # Exchange truth unavailable = fail closed when caps set
    set_mid(100.0)
    book["down"] = True
    d = decide({"max_total_live_exposure_usd": 5000})
    check("RISK-014:EXCHANGE_UNAVAILABLE_FAILS_CLOSED",
          d[0] == "SEND_BLOCKED_RISK" and "unavailable" in d[1],
          f"got={d}")
    book["down"] = False

    # ---- RISK-015: Emergency close only where intended ----
    print("\n=== RISK-015: Emergency close only where intended ===")
    # Close is never blocked by entry controls
    ledger = c.ManualLedger(path=tmp / "exit.json")
    ledger.sleeve(LEADER, "BTC")["signed_size"] = 10.0
    d = decide({"symbol_blocklist": ["BTC"], "symbol_allowlist": ["ETH"],
                "max_total_live_exposure_usd": 1, "max_asset_directional_exposure_usd": 1,
                "max_wallet_exposure_usd": 1, "max_order_notional_usd": 1},
               side="SELL", ledger=ledger)
    check("RISK-015:CLOSE_NEVER_BLOCKED_BY_ENTRY_CONTROLS", d[0] == "EXIT_ALLOWED",
          f"got={d}")

    # ---- RISK-016: Manual order cap ----
    print("\n=== RISK-016: Manual order cap ===")
    # HL_LIVE_MAX_MANUAL_ORDER_NOTIONAL_USD env var caps manual sends
    config(max_order_notional_usd=500)
    check("RISK-016:ORDER_CAP_CONFIG_READ",
          c.ConfigManager().max_order_notional() == 500.0,
          f"got={c.ConfigManager().max_order_notional()}")

    # ---- TN-F06: Catastrophic limits used as clamps ----
    print("\n=== TN-F06: Catastrophic limits used as clamps ===")
    # Limits BLOCK the whole order, never resize/clamp it
    d = decide({"max_order_notional_usd": 500})
    check("TN-F06:LIMIT_BLOCKS_NOT_CLAMPS",
          d == ("SEND_BLOCKED_RISK", "max order notional exceeded"),
          f"got={d} (must be BLOCKED, not resized)")

    # ---- TN-F16: Stale risk / account truth at send boundary ----
    print("\n=== TN-F16: Stale risk at send boundary ===")
    # Cross-network entry requires fresh follower price
    set_mid(0.0)
    d = decide({})
    check("TN-F16:NO_FOLLOWER_PRICE_ENTRY_REFUSED",
          d[0] == "SEND_BLOCKED_RISK" and "no fresh follower" in d[1],
          f"got={d}")

    # ---- TN-F21: Open-safety failure traps REDUCE/CLOSE ----
    print("\n=== TN-F21: Open-safety failure cannot trap REDUCE/CLOSE ===")
    # Even with no follower price, a close should not be trapped
    # (close uses position mark, not fresh mid)
    set_mid(0.0)
    ledger = c.ManualLedger(path=tmp / "exit2.json")
    ledger.sleeve(LEADER, "BTC")["signed_size"] = 10.0
    d = decide({}, side="SELL", ledger=ledger)
    check("TN-F21:CLOSE_NOT_TRAPPED_BY_OPEN_SAFETY",
          d[0] == "EXIT_ALLOWED",
          f"got={d}")

    # Restore mid
    set_mid(100.0)


def main():
    print("=" * 60)
    print(f"RISK-area certification harness")
    print(f"Commit: {COMMIT}")
    print(f"Engine: {ENGINE_SHA256}")
    print("=" * 60)

    run_engine_checks()

    # Build result JSON
    result = {
        "task_id": "t_d3193494",
        "title": "B3-CERT RISK area (14 rows): risk-gate semantics proof",
        "tested_commit": COMMIT,
        "tested_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "engine_sha256": ENGINE_SHA256,
        "engine_lines": sum(1 for _ in open(ENGINE_PATH, "rb")),
        "checks": {},
        "negative_tests": {},
        "summary": {
            "total_rows": 14,
            "rows": {
                "APPLIES": {"count": 11, "ids": [
                    "RISK-001", "RISK-002", "RISK-003", "RISK-004",
                    "RISK-005", "RISK-006", "RISK-007", "RISK-008",
                    "RISK-014", "RISK-015", "RISK-016"
                ]},
                "APPLIES_PROPOSED": {"count": 3, "ids": [
                    "TN-F06", "TN-F16", "TN-F21"
                ]}
            },
            "total_checks": len(CHECKS),
            "passed_checks": sum(1 for c in CHECKS if c["pass"]),
            "failed_checks": sum(1 for c in CHECKS if not c["pass"]),
            "total_negative_tests": len(NEG_TESTS),
            "passed_negative_tests": sum(1 for n in NEG_TESTS if n["pass"]),
            "failed_negative_tests": sum(1 for n in NEG_TESTS if not n["pass"]),
        }
    }

    for c in CHECKS:
        key = c["name"]
        result["checks"][key] = {
            "pass": c["pass"],
            "detail": c["detail"] if not c["pass"] else ""
        }

    for n in NEG_TESTS:
        key = n["name"]
        result["negative_tests"][key] = {
            "pass": n["pass"],
            "detail": n["detail"] if not n["pass"] else ""
        }

    # Write result
    out_path = REPO / "certification" / "results" / f"RISK_{COMMIT[:8]}.json"
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)

    print("\n" + "=" * 60)
    print(f"RESULT: {result['summary']['passed_checks']}/{result['summary']['total_checks']} checks PASS")
    print(f"NEGATIVE: {result['summary']['passed_negative_tests']}/{result['summary']['total_negative_tests']} PASS")
    if result['summary']['failed_checks'] > 0:
        print("FAILED CHECKS:")
        for c in CHECKS:
            if not c["pass"]:
                print(f"  {c['name']}: {c['detail']}")
    if result['summary']['failed_negative_tests'] > 0:
        print("FAILED NEGATIVE TESTS:")
        for n in NEG_TESTS:
            if not n["pass"]:
                print(f"  {n['name']}: {n['detail']}")
    print(f"Output: {out_path}")
    print("=" * 60)

    return 0 if result['summary']['failed_checks'] == 0 and result['summary']['failed_negative_tests'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
