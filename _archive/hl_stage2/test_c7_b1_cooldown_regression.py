"""B1: 133 offline ages of the previous exit cannot suppress a new owed close.

No real orders or network calls; the physical sender is stubbed.
Run: python -m pytest _archive/hl_stage2/test_c7_b1_cooldown_regression.py -q
"""
import os
import threading
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

os.environ.setdefault("HL_LIVE_ENV_FILE", "/nonexistent")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import HL_Live_Copy_Service_Core as core


@pytest.mark.parametrize("age_ms", range(133))
def test_b1_previous_close_attempt_never_cools_down_owed_exit(age_ms):
    now = core.utc_now_ms()
    fill = core.LeaderFill("b1-close", "0x" + "d" * 40, "BTC", "SELL", 100.0, 1.0,
                           now, "WS_CAPTURED", raw={"dir": "Close Long"})
    intent = core.Intent("b1-exit", fill, "SELL", 1.0, 100.0,
                         "LIVE", "PROPORTIONAL", None, "EXIT",
                         "b1-sleeve", "b1-position", "LONG", 1.0, 1.0,
                         True, False, now, "lifecycle=EXIT")
    sender = object.__new__(core.SenderGateway)
    sender.cfg = SimpleNamespace(master_switch_now=lambda: True,
                                  send_mode_now=lambda: "ON",
                                  liq_parity_enabled=lambda: False,
                                  wallet_enabled=lambda _: True,
                                  wallet_mode=lambda _: "ON")
    sender.sender_key_invalid = ""
    sender._market_halted_until_ms = {}
    sender._ioc_no_match_until_ms = {}
    sender._margin_reject_until_ms = {}
    sender._pending_exit_lock = threading.RLock()
    sender._last_exit_attempt_ms = {"btc": now - age_ms}
    sender._base_timing = lambda _: {}
    sender._pre_send_ownership_gate = lambda _: (True, {})
    sender._pending_exit_blocked = lambda _: (False, "")
    sender._mark_pending_exit = lambda _: None
    sender._clear_pending_exit = lambda _: None
    recorded = []
    sender._send_real = lambda i, t: (recorded.append(i.intent_id) or True, "OFFLINE_SENT", {})
    assert sender.send_if_allowed(intent) == (True, "OFFLINE_SENT")
    assert recorded == ["b1-exit"]
