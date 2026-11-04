#!/usr/bin/env python3
"""C7C fix-up standalone regression, no live orders. Run: python test_core_c7c_fixup_standalone.py."""
import os
import sys
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TMP = Path(tempfile.mkdtemp(prefix="c7c_fixup_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(TMP),
    "HL_LIVE_ENV_FILE": str(TMP / "none.env"),
    "HL_LEADER_NETWORK": "testnet",
    "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_HL_PRIVATE_KEY": "0x" + "1" * 64,
    "HL_LIVE_MOCK_SEND": "0",
})
import HL_Live_Copy_Service_Core as c  # noqa: E402

RESULTS = []
LEADER = "0x" + "a" * 40


def check(name, passed, detail=""):
    RESULTS.append((name, bool(passed)))
    print("RESULT::%s_%s%s" % (name, "PASS" if passed else "FAIL",
          (" | " + str(detail)[:150]) if not passed else ""))


def exit_intent(label):
    fill = c.LeaderFill("f-" + label, LEADER, "BTC", "BUY", 100.0, 0.1,
                        c.utc_now_ms(), "TEST")
    return c.Intent("i-" + label, fill, "BUY", 0.1, 10.0, "CLO", "fixed",
                    "EXIT_ALLOWED", "EXIT", "sleeve-BTC", "position-BTC",
                    "SHORT", -0.1, -0.1, True, True, c.utc_now_ms(),
                    "lifecycle=EXIT;")


class OrderSpy:
    def __init__(self):
        self.calls = []

    def order(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return {"status": "ok", "response": {"type": "order", "data": {
            "statuses": [{"filled": {"totalSz": "0.1", "avgPx": "100",
                                     "oid": 7}}]}}}


def gateway(spy):
    g = c.SenderGateway.__new__(c.SenderGateway)
    g.cfg = SimpleNamespace(
        master_switch_now=lambda: True,
        send_mode_now=lambda: "ON",
        liq_parity_enabled=lambda: False,
        marketable_bps=lambda: 20.0,
        max_close_adverse_diff_pct=lambda: 0.0,
        min_notional=lambda: 1.0,
        max_order_notional=lambda: 1000.0)
    g.sender_key_invalid = ""
    g.ledger = None
    g._pending_exit_lock = threading.Lock()
    g._pending_exit_guard = {}
    g._last_exit_attempt_ms = {}
    g._pre_send_ownership_gate = lambda it: (True, {})
    g._send_time_wallet_mode_block = lambda *a: None
    g.leader_reduced_since = lambda *a: 0
    g._base_timing = lambda it: {}
    g._append_local_block_reconciliation = lambda *a: None
    g._append_mock_attempt = lambda *a: None
    g._append_real_attempt = lambda *a: None
    g.signal_ambiguous_send_attempt_written = lambda *a: None
    g._report_post_send_bookkeeping_error = lambda *a: None
    g._journal_authorised_close_refusal = lambda *a: None
    g._resolve_coin = lambda coin: {
        "ok": True, "sdk_coin": "BTC", "sz_decimals": 3,
        "price_max_decimals": 2, "perp_dexs": [""],
        "sdk_order_compatible": True, "min_order_value_usd": 1.0,
        "min_size": 0.0, "status": "OK"}
    g._get_exchange_client = lambda *a, **kw: spy
    g._exchange_client_has_symbol = lambda *a: True
    g._validate_final_wire_order = lambda *a: (True, {})
    g._pre_exchange_asset_safety = lambda *a: (True, {})
    g._withdraw_standing_close = lambda ex, it, size, dec, timing: (size, None)
    g._ensure_margin_mode = lambda *a: None
    g._close_wire_plan = lambda it, size, dec, min_ok, timing: (True, size, "")
    g._effective_symbol_min_notional = lambda *a: 1.0
    g._master_gate_reason = lambda *a: ""
    g._note_sender_key_rejection = lambda *a: None
    g._note_exchange_rate_limit = lambda *a: None
    return g


def run():
    spy = OrderSpy()
    g = gateway(spy)
    g._reserve_exchange_order_slot = (
        lambda **kw: (_ for _ in ()).throw(RuntimeError("slot fail")))
    with patch.object(c, "HLAccount", object), patch.object(c, "HLExchange", object):
        with patch.object(c, "wait_intent_durable", lambda *a, **kw: None):
            first = g.send_if_allowed(exit_intent("slot-failure"))
    check("C7C_RESERVE_SLOT_EXCEPTION_ZERO_ORDER_CALLS", len(spy.calls) == 0, spy.calls)
    check("C7C_RESERVE_SLOT_EXCEPTION_NO_EXIT_STAMP", not g._last_exit_attempt_ms,
          g._last_exit_attempt_ms)
    check("C7C_RESERVE_SLOT_EXCEPTION_RELEASES_GUARD", not g._pending_exit_guard,
          g._pending_exit_guard)
    check("C7C_RESERVE_SLOT_EXCEPTION_DEFINITE_NO_CALL", first == (False, "EXCHANGE_ERROR"), first)

    # The immediately following exit must reach the physical order, not sit in a 30s guard.
    g._reserve_exchange_order_slot = lambda **kw: c.utc_now_ms()
    g._begin_pending_send = lambda *a: None
    with patch.object(c, "HLAccount", object), patch.object(c, "HLExchange", object):
        with patch.object(c, "wait_intent_durable", lambda *a, **kw: None):
            second = g.send_if_allowed(exit_intent("immediately-next"))
    check("C7C_NEXT_EXIT_NOT_PENDING_BLOCKED",
          second[1] != "PENDING_EXIT_GUARD_ACTIVE", second)
    check("C7C_NEXT_EXIT_REACHES_EXCHANGE_ORDER", len(spy.calls) == 1, spy.calls)
    check("C7C_CONFIRMED_EXCHANGE_CALL_STAMPS", bool(g._last_exit_attempt_ms),
          g._last_exit_attempt_ms)
    check("C7C_PHYSICAL_CALL_RETAINS_PENDING_GUARD", bool(g._pending_exit_guard),
          g._pending_exit_guard)

    mock_gateway = gateway(OrderSpy())
    with patch.dict(os.environ, {"HL_LIVE_MOCK_SEND": "1"}):
        mock_result = mock_gateway.send_if_allowed(exit_intent("mock"))
    check("C7C_MOCK_SEND_RELEASES_PENDING",
          mock_result[0] and not mock_gateway._pending_exit_guard, mock_result)
    check("C7C_MOCK_SEND_NEVER_STAMPS", not mock_gateway._last_exit_attempt_ms)

    unresolved = gateway(OrderSpy())
    unresolved._resolve_coin = lambda coin: {"ok": False, "status": "SYMBOL_CACHE_MISS",
                                               "error": "unresolved"}
    absent = unresolved.send_if_allowed(exit_intent("missing-symbol"))
    check("C7C_UNRESOLVED_SYMBOL_RELEASES_PENDING",
          absent[1] == "SEND_NOT_ATTEMPTED_UNSUPPORTED_SYMBOL"
          and not unresolved._pending_exit_guard, absent)
    check("C7C_UNRESOLVED_SYMBOL_NEVER_STAMPS", not unresolved._last_exit_attempt_ms)

    source = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    body = source.split("    def send_if_allowed(", 1)[1].split("\n    def _send_real(", 1)[0]
    check("C7C_ORIGINAL_SEND_BODY_PRESERVED",
          "_pre_send_ownership_gate(intent)" in body
          and "    def _send_if_allowed_impl(" not in source)
    check("C7C_NEW_REFUSAL_ROW_CLASSIFIED",
          c.classify_terminal_row("AUTHORISED_CLOSE_REFUSAL") == "NON_TERMINAL")
    check("C7C_EXIT_TIME_COOLDOWNS_BYPASSED",
          "EXIT_ATTEMPT_COOLDOWN" not in body
          and "bypass_rate_limit_cooldown=lifecycle" in source)
    failures = sum(not passed for _, passed in RESULTS)
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), failures))
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        check("C7C_STANDALONE_EXCEPTION", False, repr(exc))
        print("TOTAL=%d FAILED=%d" % (len(RESULTS),
              sum(not passed for _, passed in RESULTS)))
        sys.exit(1)
