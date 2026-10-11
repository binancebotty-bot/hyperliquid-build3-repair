#!/usr/bin/env python3
"""Dust rule (Boss): a sub-minimum order is sent ONLY when it is a reduce-only EXIT that closes the account's WHOLE
position in the coin; every other sub-minimum order is blocked as DUST_BELOW_MIN_NOTIONAL (a diff, never silently lost).
Drives the engine's real final wire gate (SenderGateway._validate_final_wire_order).
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_dust_rules.py"""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
tmp = Path(tempfile.mkdtemp(prefix="dust_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LEADER_NETWORK": "testnet",
                   "HL_FOLLOWER_NETWORK": "testnet"})
import HL_Live_Copy_Service_Core as c
R = []
def check(n, ok, d=""):
    R.append(bool(ok)); print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))
A = "0x" + "a" * 40
c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {}, "wallets": {A: {"enabled": True, "mode": "ON"}}})
MIN = c.DEFAULT_MIN_NOTIONAL
resolved = {"ok": True, "sdk_coin": "BTC", "raw_coin": "BTC", "min_order_value_usd": MIN}
def gw(exchange_net):
    led = c.ManualLedger(path=tmp / "led.json")
    g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), led)
    led.coin_net = lambda k: exchange_net
    c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": exchange_net}}})
    return g
def intent(lifecycle, side, size):
    fill = c.LeaderFill("f", A, "BTC", side, 100.0, size, c.utc_now_ms(), "T")
    reduce = lifecycle in {"EXIT", "REDUCE"}
    return c.Intent("i", fill, side, size, size * 100.0, "ON", "fixed", "EXIT_ALLOWED" if reduce else "ENTRY_ALLOWED", lifecycle,
                    "s", "", "LONG", 1.0, 1.0, reduce, reduce, c.utc_now_ms(), "lifecycle=%s;" % lifecycle)
def gate(g, it, size, px=100.0):
    ok, info = g._validate_final_wire_order(it, dict(resolved), "BTC", size, px, {})
    return ok, str(info.get("terminal_state", ""))
tiny = MIN / 100.0 / 2          # notional MIN/2 at price 100
# (a) sub-min ENTRY blocked
ok, ts = gate(gw(0.0), intent("ENTRY", "BUY", tiny), tiny)
check("A_SUBMIN_ENTRY_BLOCKED_AS_DUST", ok is False and ts == "DUST_BELOW_MIN_NOTIONAL", (ok, ts))
# (b) sub-min ADD blocked
ok, ts = gate(gw(1.0), intent("ADD", "BUY", tiny), tiny)
check("B_SUBMIN_ADD_BLOCKED_AS_DUST", ok is False and ts == "DUST_BELOW_MIN_NOTIONAL", (ok, ts))
# (c) sub-min EXIT that is NOT the whole account position: blocked
ok, ts = gate(gw(1.0), intent("EXIT", "SELL", tiny), tiny)
check("C_SUBMIN_PARTIAL_EXIT_BLOCKED_AS_DUST", ok is False and ts == "DUST_BELOW_MIN_NOTIONAL", (ok, ts))
# (d) sub-min EXIT that closes the WHOLE account position: sent
ok, ts = gate(gw(tiny), intent("EXIT", "SELL", tiny), tiny)
check("D_SUBMIN_WHOLE_POSITION_CLOSE_SENT", ok is True, (ok, ts))
# (e) same but the ledger disagrees with the exchange: blocked (not provably whole)
g = gw(tiny); g.ledger.coin_net = lambda k: tiny * 3
ok, ts = gate(g, intent("EXIT", "SELL", tiny), tiny)
check("E_LEDGER_EXCHANGE_DISAGREE_BLOCKED", ok is False and ts == "DUST_BELOW_MIN_NOTIONAL", (ok, ts))
# (f) a sub-min close on the wrong side (would flip / open): blocked
ok, ts = gate(gw(tiny), intent("EXIT", "BUY", tiny), tiny)
check("F_WRONG_SIDE_NEVER_A_DUST_CLOSE", ok is False, (ok, ts))
# (g) boundary: exactly the minimum passes, one cent below does not (entry)
size_min = MIN / 100.0
ok_at, _ = gate(gw(0.0), intent("ENTRY", "BUY", size_min), size_min)
ok_below, _ = gate(gw(0.0), intent("ENTRY", "BUY", size_min - 0.0001), size_min - 0.0001)
check("G_BOUNDARY_AT_MIN_PASSES_BELOW_BLOCKED", ok_at is True and ok_below is False, (ok_at, ok_below))
# (h) kill switch restores the old block
os.environ["HL_LIVE_DUST_CLOSE_ATTEMPT"] = "0"
ok, ts = gate(gw(tiny), intent("EXIT", "SELL", tiny), tiny)
os.environ.pop("HL_LIVE_DUST_CLOSE_ATTEMPT")
check("H_KILL_SWITCH_BLOCKS_WHOLE_POSITION_DUST", ok is False and ts == "DUST_BELOW_MIN_NOTIONAL", (ok, ts))
# (i) several leaders on one coin: the ACCOUNT position decides (a leader's sleeve being small does not make a close "whole")
g = gw(2 * tiny)                       # account holds 2x: closing tiny is partial even if one sleeve holds only tiny
ok, ts = gate(g, intent("EXIT", "SELL", tiny), tiny)
check("I_ACCOUNT_POSITION_NOT_SLEEVE_DECIDES", ok is False and ts == "DUST_BELOW_MIN_NOTIONAL", (ok, ts))
print("TOTAL=%d FAILED=%d" % (len(R), R.count(False))); sys.exit(1 if False in R else 0)
