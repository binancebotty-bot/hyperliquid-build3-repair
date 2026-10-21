"""Startup entry gates must not trap owned closes, including legacy decision-less exits."""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import threading

tmp = Path(tempfile.mkdtemp(prefix="exit_gate_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                   "HL_LIVE_MOCK_SEND": "0"})
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as c

checks = []


def check(name, ok):
    checks.append((name, bool(ok)))
    print(f"RESULT::{name}_{'PASS' if ok else 'FAIL'}")


now = c.utc_now_ms()
fill = c.LeaderFill("close-1", "0x" + "d" * 40, "BTC", "SELL", 100.0, 1.0, now,
                    "WS_CAPTURED", raw={"dir": "Close Long"})
exit_intent = c.Intent("exit-1", fill, "SELL", 1.0, 100.0, "LIVE", "PROPORTIONAL", None, "EXIT",
                       "sleeve-a", "position-a", "LONG", 1.0, 0.0, True, False, now, "lifecycle=EXIT")
entry_fill = c.LeaderFill("entry-1", "0x" + "e" * 40, "BTC", "BUY", 100.0, 1.0, now,
                          "WS_CAPTURED", raw={"dir": "Open Long"})
entry_intent = c.Intent("entry-1", entry_fill, "BUY", 1.0, 100.0, "LIVE", "PROPORTIONAL", "ENTRY_ALLOWED",
                        "ENTRY", "sleeve-b", "position-b", "FLAT", 0.0, 0.0, False, False, now,
                        "lifecycle=ENTRY")

# Other leaders' opposing sleeves net to flat. The existing close planner should send this owned exit
# without reduce-only so the account reaches the sleeves' new net target.
net_ledger = SimpleNamespace(coin_net=lambda coin: 0.0)
net_sender = SimpleNamespace(ledger=net_ledger, _fresh_exchange_net=lambda coin: 0.0,
                             _floor_wire_size=lambda size, decimals: round(size, decimals),
                             _reduce_only_for_intent=c.SenderGateway._reduce_only_for_intent)
close_plan = c.SenderGateway._close_wire_plan(net_sender, exit_intent, 1.0, 3, lambda size: True)
check("ZERO_NET_CLOSE_USES_EXISTING_NETTING_RULE", close_plan == (False, 1.0, ""))

sender = object.__new__(c.SenderGateway)
sender.cfg = SimpleNamespace(master_switch_now=lambda: True, send_mode_now=lambda: "ON", liq_parity_enabled=lambda: False)
sender.sender_key_invalid = ""
sender._market_halted_until_ms = {}
sender._ioc_no_match_until_ms = {}
sender._pending_exit_lock = threading.RLock()
sender._last_exit_attempt_ms = {}
sender._base_timing = lambda intent: {}
sender._pre_send_ownership_gate = lambda intent: (True, {})
sender._mark_pending_exit = lambda intent: None
sender._pending_exit_blocked = lambda intent: (False, "")
sender._clear_pending_exit = lambda intent: None
sender._send_real = lambda intent, timing: (True, "OFFLINE_SEND_STUB", {})

exit_result = sender.send_if_allowed(exit_intent, "STARTUP_ORPHAN_CHECK_PENDING")
check("DECISION_NONE_CLOSE_LONG_PASSES_HELD_STARTUP_GATE", exit_result == (True, "OFFLINE_SEND_STUB"))
entry_result = sender.send_if_allowed(entry_intent, "STARTUP_ORPHAN_CHECK_PENDING")
check("COMPANION_ENTRY_REMAINS_BLOCKED", entry_result == (False, "ENTRY_BLOCKED_STARTUP_ORPHAN_CHECK_PENDING"))

failed = [name for name, ok in checks if not ok]
print(f"TOTAL={len(checks)} FAILED={len(failed)}")
raise SystemExit(1 if failed else 0)
