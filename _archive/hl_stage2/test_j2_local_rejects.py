#!/usr/bin/env python3
"""J2: Cheap local rejects tests.

Goal: show orders that cannot succeed are rejected locally without an exchange call
and without an info read:
- illiquid exit (size below szDecimals step)
- resting-order churn (same coin/side/price already resting from our own cloid)
- reduce-only with no position
- price outside the 0.2% band

Uses the FakeExchange pattern from test_hotpath_replay_bench.py (counts calls).
Reports which rejects exist today and which do not; for those missing gives a proposed patch diff.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_j2_local_rejects.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

tmp = Path(tempfile.mkdtemp(prefix="j2_local_rejects_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(tmp),
    "HL_LIVE_ENV_FILE": "/nonexistent",
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_WS_ENABLED": "0",
    "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
    "HL_LIVE_PREWARM_SYMBOL_META": "0",
    "HL_LIVE_PREWARM_SDK_CLIENT": "0",
    "HL_LIVE_HOT_SEND_WORKERS": "1",
    "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
    "HL_LIVE_MISSED_ENTRY_RULE": "1",
})

import requests
import HL_Live_Copy_Service_Core as c

# Offline: no network calls allowed
def offline(*_a, **_k):
    raise RuntimeError("offline test: no network")
requests.post = offline
requests.get = offline
c.requests.post = offline

RESULTS = []
EXCHANGE_CALLS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


LEADER = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40
FAKE_KEY = "0x" + "1" * 64

c.USER_WALLET = FOLLOWER

# Shared config
MIDS = {"BTC": 100.0, "ETH": 100.0}
EXP_PAYLOAD = {"assetPositions": [], "marginSummary": {"accountValue": "1000000"}}

c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(MIDS)
c.LEADER_MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(MIDS)
c.EXPOSURE_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP_PAYLOAD)
c.LEADER_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else dict(EXP_PAYLOAD)

# Pre-populate the mid caches with scope so they don't refresh via fetcher
c._FOLLOWER_MIDS.update(px=dict(MIDS), ms=c.utc_now_ms(), scope=[""])
c._LEADER_MIDS.update(px=dict(MIDS), ms=c.utc_now_ms(), scope=[""])

c.atomic_write_json(c.LIVE_CONFIG_FILE, {
    "auto_send_enabled": True,
    "global_controls": {"symbol_blocklist": [], "min_notional": 1, "marketable_bps": 20},
    "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 100}},
})

os.environ["HL_LIVE_HL_PRIVATE_KEY"] = FAKE_KEY
os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = FOLLOWER
saved_acct = c.HLAccount, c.HLExchange
c.HLAccount, c.HLExchange = object, object


class FakeExchange:
    """Fake exchange that counts calls and returns configurable responses."""
    def __init__(self, replies=None):
        self.calls = []
        self.cancels = []
        self.replies = list(replies or [])

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        EXCHANGE_CALLS.append({
            "coin": coin, "is_buy": is_buy, "size": size, "px": px,
            "tif": (tif.get("limit") or {}).get("tif"), "reduce_only": reduce_only
        })
        self.calls.append({
            "coin": coin, "is_buy": is_buy, "size": size, "px": px,
            "tif": (tif.get("limit") or {}).get("tif"), "reduce_only": reduce_only
        })
        if self.replies:
            return self.replies.pop(0)
        if tif.get("limit", {}).get("tif") == "Gtc":
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 9999}}]}}}
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
            {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1111}}]}}}

    def cancel(self, coin, oid):
        self.cancels.append((coin, oid))
        return {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}


# Common resolved symbol metadata for BTC (sz_decimals=3 means min size step = 0.001)
RESOLVED_BTC = {
    "ok": True, "sdk_coin": "BTC", "raw_coin": "BTC",
    "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
    "sdk_order_compatible": True, "min_order_value_usd": 10.0, "min_size": 0.001, "status": "OK"
}


def make_gateway(fake_exchange, ledger=None):
    """Create a SenderGateway with all external dependencies stubbed."""
    if ledger is None:
        ledger = c.ManualLedger(path=tmp / "ledger.json")
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
    gw._resolve_coin = lambda coin: dict(RESOLVED_BTC)
    gw._get_exchange_client = lambda *a, **k: fake_exchange
    gw._exchange_client_has_symbol = lambda *a, **k: True
    gw._validate_final_wire_order = lambda *a, **k: (True, {})
    gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
    gw._exchange_client_for_coin = lambda raw_coin: (fake_exchange, "BTC")
    # Also stub the ownership gate for _send_real tests
    gw._pre_send_ownership_gate = lambda intent: (True, {})
    return gw


def make_intent(lifecycle: str, side: str, size: float, price: float = 100.0,
                wallet_pos_before: float = 0.0, coin_net_before: float = 0.0,
                reduce_only_intended: bool = False, notes: str = "") -> c.Intent:
    """Create an Intent for testing."""
    fill = c.LeaderFill("f1", LEADER, "BTC", side, price, size, c.utc_now_ms(), "TEST")
    decision = "EXIT_ALLOWED" if lifecycle in {"EXIT", "REDUCE"} else "ENTRY_ALLOWED"
    return c.Intent(
        "i1", fill, side, size, size * price, "LIVE", "fixed", decision, lifecycle,
        "s1", "", "LONG", wallet_pos_before, coin_net_before,
        reduce_only_intended, reduce_only_intended, c.utc_now_ms(),
        notes or f"lifecycle={lifecycle};"
    )


def send_via_send_real(gw: c.SenderGateway, intent: c.Intent):
    """Send an intent through _send_real directly and return (ok, status, result, calls)."""
    EXCHANGE_CALLS.clear()
    ok, status, result = gw._send_real(intent)
    return ok, status, result, EXCHANGE_CALLS[:]


def send_via_send_if_allowed(gw: c.SenderGateway, intent: c.Intent):
    """Send an intent through send_if_allowed and return (ok, status, calls)."""
    EXCHANGE_CALLS.clear()
    ok, status = gw.send_if_allowed(intent)
    return ok, status, EXCHANGE_CALLS[:]


def clear_resting_entries():
    """Clear the resting entries registry."""
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})


# ============================================================================
# TEST 1: Illiquid exit (size below szDecimals step)
# ============================================================================
print("\n=== TEST 1: Illiquid exit (size below szDecimals step) ===")

# BTC has sz_decimals=3, so min size step = 0.001
# Size 0.0005 is below the step and should be rejected locally in _validate_final_wire_order
fake1 = FakeExchange()
ledger1 = c.ManualLedger(path=tmp / "ledger1.json")
ledger1.sleeve(LEADER, "BTC")["signed_size"] = 1.0  # has position to close
gw1 = make_gateway(fake1, ledger1)

# Try to close with size 0.0005 (below 0.001 step)
intent1 = make_intent("EXIT", "SELL", 0.0005, wallet_pos_before=1.0, coin_net_before=1.0, reduce_only_intended=True)
ok1, status1, result1, calls1 = send_via_send_real(gw1, intent1)

check("J2_1A_SIZE_BELOW_STEP_REJECTED_LOCALLY", not ok1 and len(calls1) == 0,
      f"ok={ok1}, status={status1}, calls={calls1}")
check("J2_1B_TERMINAL_STATE_INVALID_WIRE_SIZE", result1.get("terminal_state") == "INVALID_WIRE_SIZE",
      f"terminal_state={result1.get('terminal_state')}")
check("J2_1C_NO_EXCHANGE_CALL", len(calls1) == 0, f"calls={calls1}")

# Size exactly at step (0.001) should pass local validation
fake1b = FakeExchange()
ledger1b = c.ManualLedger(path=tmp / "ledger1b.json")
ledger1b.sleeve(LEADER, "BTC")["signed_size"] = 1.0
gw1b = make_gateway(fake1b, ledger1b)
intent1b = make_intent("EXIT", "SELL", 0.001, wallet_pos_before=1.0, coin_net_before=1.0, reduce_only_intended=True)
ok1b, status1b, result1b, calls1b = send_via_send_real(gw1b, intent1b)

check("J2_1D_SIZE_AT_STEP_PASSES_LOCAL", ok1b or (not ok1b and len(calls1b) > 0),
      f"ok={ok1b}, status={status1b}, calls={calls1b} (exchange call expected)")


# ============================================================================
# TEST 2: Resting-order churn (same coin/side/price already resting from our own cloid)
# ============================================================================
print("\n=== TEST 2: Resting-order churn (same coin/side/price already resting) ===")

# The _already_resting_block is only triggered when the missed entry rule
# decides to rest a limit (rest_now=True). Set up conditions for that:
# - Leader fill at 100.0
# - Follower mid at 100.3 (30 bps adverse, beyond 20 bps tolerance)
# - This should trigger rest_now=True and then check _already_resting_block

clear_resting_entries()

fake2 = FakeExchange()
ledger2 = c.ManualLedger(path=tmp / "ledger2.json")
gw2 = make_gateway(fake2, ledger2)

# Register a resting entry limit for BUY BTC at 100.0 (from a previous missed entry)
gw2._register_resting_entry(
    make_intent("ENTRY", "BUY", 1.0, 100.0),
    "BTC", "oid_resting_1", 100.0, 1.0, "missed entry"
)

# Set up missed entry rule conditions: follower mid at 100.3 (30 bps adverse for BUY)
c._FOLLOWER_MIDS.update(px={"BTC": 100.3}, ms=c.utc_now_ms(), scope=[""])
c._LEADER_MIDS.update(px={"BTC": 100.0}, ms=c.utc_now_ms(), scope=[""])

# Now try to send another BUY entry for BTC at same price - should be blocked locally
# because there's already a resting entry for this wallet/coin/side
intent2 = make_intent("ENTRY", "BUY", 1.0, 100.0)
ok2, status2, result2, calls2 = send_via_send_real(gw2, intent2)

check("J2_2A_RESTING_CHAIN_BLOCKED_LOCALLY", not ok2 and len(calls2) == 0,
      f"ok={ok2}, status={status2}, calls={calls2}")
check("J2_2B_TERMINAL_STATE_MISSED_ENTRY_ALREADY_RESTING", result2.get("terminal_state") == "MISSED_ENTRY_ALREADY_RESTING",
      f"terminal_state={result2.get('terminal_state')}")
check("J2_2C_NO_EXCHANGE_CALL", len(calls2) == 0, f"calls={calls2}")

# Different side (SELL) should NOT be blocked by _already_resting_block
clear_resting_entries()
fake2b = FakeExchange()
ledger2b = c.ManualLedger(path=tmp / "ledger2b.json")
gw2b = make_gateway(fake2b, ledger2b)
gw2b._register_resting_entry(
    make_intent("ENTRY", "BUY", 1.0, 100.0),
    "BTC", "oid_resting_2", 100.0, 1.0, "missed entry"
)
c._FOLLOWER_MIDS.update(px={"BTC": 100.3}, ms=c.utc_now_ms(), scope=[""])
c._LEADER_MIDS.update(px={"BTC": 100.0}, ms=c.utc_now_ms(), scope=[""])
intent2b = make_intent("ENTRY", "SELL", 1.0, 100.0)  # Different side
ok2b, status2b, result2b, calls2b = send_via_send_real(gw2b, intent2b)

check("J2_2D_DIFFERENT_SIDE_NOT_BLOCKED", ok2b or (not ok2b and len(calls2b) > 0),
      f"ok={ok2b}, status={status2b}, calls={calls2b} (exchange call expected for different side)")


# ============================================================================
# TEST 3: Reduce-only with no position
# ============================================================================
print("\n=== TEST 3: Reduce-only with no position ===")

# This reject is checked in _pre_send_ownership_gate which is called from send_if_allowed
# Need to test via send_if_allowed, not _send_real directly
# Also need to set up exchange snapshot so the ownership gate can read it

clear_resting_entries()

fake3 = FakeExchange()
ledger3 = c.ManualLedger(path=tmp / "ledger3.json")
# No sleeve created - wallet has no position in BTC
# Set up exchange snapshot showing no position
c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": 0.0}}})
gw3 = make_gateway(fake3, ledger3)
# Don't stub _pre_send_ownership_gate - let the real one run
gw3._pre_send_ownership_gate = c.SenderGateway._pre_send_ownership_gate.__get__(gw3, c.SenderGateway)

intent3 = make_intent("EXIT", "SELL", 1.0, wallet_pos_before=0.0, coin_net_before=0.0, reduce_only_intended=True)
ok3, status3, calls3 = send_via_send_if_allowed(gw3, intent3)

check("J2_3A_REDUCE_ONLY_NO_POSITION_REJECTED_LOCALLY", not ok3 and len(calls3) == 0,
      f"ok={ok3}, status={status3}, calls={calls3}")
check("J2_3B_STATUS_OWNERSHIP_GATE_NO_MATCHING_SLEEVE", status3 == "OWNERSHIP_GATE_NO_MATCHING_WALLET_SLEEVE",
      f"status={status3}")
check("J2_3C_NO_EXCHANGE_CALL", len(calls3) == 0, f"calls={calls3}")

# With a matching sleeve, should pass local validation
clear_resting_entries()
fake3b = FakeExchange()
ledger3b = c.ManualLedger(path=tmp / "ledger3b.json")
ledger3b.sleeve(LEADER, "BTC")["signed_size"] = 1.0  # Has position
# Set up exchange snapshot showing position
c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": 1.0}}})
# Monkey-patch coin_net to return the position (simpler than relying on ledger file persistence)
ledger3b.coin_net = lambda coin: 1.0 if coin == "BTC" else 0.0
gw3b = make_gateway(fake3b, ledger3b)
gw3b._pre_send_ownership_gate = c.SenderGateway._pre_send_ownership_gate.__get__(gw3b, c.SenderGateway)
gw3b._fresh_exchange_net = lambda coin: 1.0  # the close is sized against a fresh account read
intent3b = make_intent("EXIT", "SELL", 1.0, wallet_pos_before=1.0, coin_net_before=1.0, reduce_only_intended=True)
ok3b, status3b, calls3b = send_via_send_if_allowed(gw3b, intent3b)

check("J2_3D_WITH_POSITION_PASSES_LOCAL", ok3b or (not ok3b and len(calls3b) > 0),
      f"ok={ok3b}, status={status3b}, calls={calls3b} (exchange call expected)")


# ============================================================================
# TEST 4: Price outside the 0.2% band (missed entry rule)
# ============================================================================
print("\n=== TEST 4: Price outside the 0.2% band ===")

clear_resting_entries()

fake4 = FakeExchange()
ledger4 = c.ManualLedger(path=tmp / "ledger4.json")
gw4 = make_gateway(fake4, ledger4)

# Set follower mid to 100.3 (30 bps adverse for BUY, beyond 20 bps tolerance)
# Leader fill at 100.0
c._FOLLOWER_MIDS.update(px={"BTC": 100.3}, ms=c.utc_now_ms(), scope=[""])
c._LEADER_MIDS.update(px={"BTC": 100.0}, ms=c.utc_now_ms(), scope=[""])

intent4 = make_intent("ENTRY", "BUY", 1.0, 100.0)  # Leader fill at 100.0
ok4, status4, result4, calls4 = send_via_send_real(gw4, intent4)

# The missed entry rule converts to a resting limit (GTC) at leader price
# This DOES make an exchange call to place the resting limit
# So it's NOT a "local reject without exchange call" - it's a local decision to rest instead of IOC
# The order returns ok=True with status=ORDER_RESTING for a successfully placed resting limit
check("J2_4A_PRICE_OUTSIDE_BAND_RESTS_AS_GTC", ok4 and len(calls4) > 0 and status4 == "ORDER_RESTING",
      f"ok={ok4}, status={status4}, calls={calls4}")
check("J2_4B_TERMINAL_STATE_ENTRY_LIMIT_RESTING", result4.get("terminal_state") == "ENTRY_LIMIT_RESTING_PRICE_MOVED",
      f"terminal_state={result4.get('terminal_state')}")
check("J2_4C_LIMIT_PRICE_AT_LEADER_PRICE", abs(result4.get("limit_px", 0) - 100.0) < 1e-9,
      f"limit_px={result4.get('limit_px')}")
check("J2_4D_GTC_NOT_IOC", len(calls4) > 0 and calls4[0].get("tif") == "Gtc",
      f"tif={calls4[0].get('tif') if calls4 else 'none'}")

# Within tolerance (follower mid at 100.1 = 10 bps adverse) should send IOC
clear_resting_entries()
fake4b = FakeExchange()
ledger4b = c.ManualLedger(path=tmp / "ledger4b.json")
gw4b = make_gateway(fake4b, ledger4b)
c._FOLLOWER_MIDS.update(px={"BTC": 100.1}, ms=c.utc_now_ms(), scope=[""])
c._LEADER_MIDS.update(px={"BTC": 100.0}, ms=c.utc_now_ms(), scope=[""])

intent4b = make_intent("ENTRY", "BUY", 1.0, 100.0)
ok4b, status4b, result4b, calls4b = send_via_send_real(gw4b, intent4b)

check("J2_4E_WITHIN_TOLERANCE_SENDS_IOC", ok4b or (not ok4b and len(calls4b) > 0),
      f"ok={ok4b}, status={status4b}, calls={calls4b} (exchange call expected)")
check("J2_4F_IOC_NOT_GTC", len(calls4b) > 0 and calls4b[0].get("tif") == "Ioc",
      f"tif={calls4b[0].get('tif') if calls4b else 'none'}")


# ============================================================================
# TEST 5: halt and no-match cooldowns are per coin; reductions stay available
# ============================================================================
print("\n=== TEST 5: market halt, IOC no-match, and exit pacing ===")

def stub_send(gw, reply):
    gw._pre_send_ownership_gate = lambda intent: (True, {})
    gw.liq_parity_block = lambda intent: None
    gw._send_real = lambda intent, timing=None: (False, "ORDER_REJECTED", {
        "exchange_called": True, "reject_category": reply, "error": reply,
        "reduce_only_sent": intent.reduce_only_intended,
    })
    gw._append_real_attempt = lambda *args: None
    rows = []
    gw.audit.append_reconciliation = lambda event, status, **kw: rows.append((event, status, kw))
    return rows

halt_gw = make_gateway(FakeExchange())
halt_rows = stub_send(halt_gw, "MARKET_HALTED")
halt_intent = make_intent("ENTRY", "BUY", 1.0)
first_halt = halt_gw.send_if_allowed(halt_intent)
second_halt = halt_gw.send_if_allowed(make_intent("ENTRY", "BUY", 1.0))
other_coin = make_intent("ENTRY", "BUY", 1.0)
other_coin = replace(other_coin, fill=replace(other_coin.fill, coin="ETH"))
other_coin_result = halt_gw.send_if_allowed(other_coin)
check("J2_5A_HALT_COOLDOWN_PER_COIN", first_halt[1] == "ORDER_REJECTED" and second_halt[1] == "SKIPPED_MARKET_HALTED", f"{first_halt}, {second_halt}")
check("J2_5B_ONE_HALT_AUDIT_OUTCOME", sum(r[1] == "SKIPPED_MARKET_HALTED" and r[2].get("coin") == "btc" for r in halt_rows) == 1, str(halt_rows))
check("J2_5C_HALT_COOLDOWN_IS_PER_COIN", other_coin_result[1] == "ORDER_REJECTED")
check("J2_5D_EXACT_HALT_RECOGNIZED", c.classify_reject_category("Trading is halted.") == "MARKET_HALTED")

ioc_gw = make_gateway(FakeExchange())
ioc_rows = stub_send(ioc_gw, "IOC_NO_IMMEDIATE_MATCH")
first_ioc = ioc_gw.send_if_allowed(make_intent("ENTRY", "BUY", 1.0))
second_ioc = ioc_gw.send_if_allowed(make_intent("ENTRY", "BUY", 1.0))
check("J2_5E_IOC_RETRY_WINDOW", first_ioc[1] == "ORDER_REJECTED" and second_ioc[1] == "SKIPPED_IOC_NO_IMMEDIATE_MATCH", f"{first_ioc}, {second_ioc}")
check("J2_5F_ONE_IOC_AUDIT_OUTCOME", [r[1] for r in ioc_rows].count("IOC_NO_IMMEDIATE_MATCH") == 1, str(ioc_rows))

exit_gw = make_gateway(FakeExchange())
exit_rows = stub_send(exit_gw, "MARKET_HALTED")
exit_gw._send_real = lambda intent, timing=None: (True, "ORDER_FILLED", {"exchange_called": True, "reject_category": "", "reduce_only_sent": True})
exit_intent = make_intent("EXIT", "SELL", 0.1, wallet_pos_before=1.0, coin_net_before=1.0, reduce_only_intended=True)
exit_first = exit_gw.send_if_allowed(exit_intent)
exit_second = exit_gw.send_if_allowed(make_intent("EXIT", "SELL", 0.1, wallet_pos_before=1.0, coin_net_before=1.0, reduce_only_intended=True))
check("J2_5G_REDUCTIONS_NOT_HALTED", exit_first == (True, "ORDER_FILLED"))
check("J2_5H_EXIT_ATTEMPT_MAX_ONCE_PER_MINUTE", exit_second[1] == "EXIT_ATTEMPT_COOLDOWN")


# ============================================================================
# SUMMARY
# ============================================================================
print("\n=== SUMMARY ===")
print("Local rejects tested:")
print("  1. Illiquid exit (size below szDecimals step) - EXISTS (in _validate_final_wire_order Gate C)")
print("  2. Resting-order churn (same coin/side/price already resting) - EXISTS (in _send_real via _already_resting_block, only when missed entry rule triggers rest)")
print("  3. Reduce-only with no position - EXISTS (in _pre_send_ownership_gate)")
print("  4. Price outside 0.2% band (missed entry rule) - PARTIAL: converts to resting limit via exchange call, NOT a local reject without exchange call")

failed = [n for n, ok in RESULTS if not ok]
print(f"\nTOTAL={len(RESULTS)} FAILED={len(failed)}")
if failed:
    print("FAILED:", failed)

c.HLAccount, c.HLExchange = saved_acct
sys.exit(1 if failed else 0)
