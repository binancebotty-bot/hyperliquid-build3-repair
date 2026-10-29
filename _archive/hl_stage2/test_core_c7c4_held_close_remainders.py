#!/usr/bin/env python3
"""C7C commit 4: offline held-close and whole-account dust regressions.
Standalone process: python test_core_c7c4_held_close_remainders.py
Writes TOTAL/FAILED and exits nonzero on any failure. No network or real orders.
"""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
TMP = Path(tempfile.mkdtemp(prefix="c7c4_dust_"))
os.environ.update({
    "HL_LIVE_AUDIT_DIR": str(TMP), "HL_LIVE_ENV_FILE": str(TMP / "missing.env"),
    "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
    "HL_LIVE_DUST_CLOSE_ATTEMPT": "1",
})
import HL_Live_Copy_Service_Core as core  # noqa: E402

RESULTS = []
WALLET = "0x" + "a" * 40
COIN = "near"
PX = 3.2
RESOLVED = {"ok": True, "raw_coin": "NEAR", "sdk_coin": "NEAR",
            "min_order_value_usd": 10.0}


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("RESULT::%s_%s%s" % (
        name, "PASS" if ok else "FAIL", (" | " + str(detail)[:220]) if not ok else ""))


class Ledger:
    def __init__(self, size):
        self.size = size
        self.data = {"by_wallet": {WALLET: {COIN: {
            "coin": COIN, "signed_size": size}}}}

    def coin_net(self, coin):
        return self.size

    def change(self, size):
        self.size = size
        self.data["by_wallet"][WALLET][COIN]["signed_size"] = size


class OrderSpy:
    def __init__(self):
        self.calls = []

    def order(self, *args, **kw):
        self.calls.append((args, kw))
        return {"status": "ok", "response": {"type": "order", "data": {
            "statuses": [{"filled": {"totalSz": str(args[2]),
                                     "avgPx": str(args[3]), "oid": 31}}]}}}


def intent(i, size=0.1):
    fill = core.LeaderFill("f-%s" % i, WALLET, "NEAR", "SELL",
                           PX, size, core.utc_now_ms(), "TEST")
    return core.Intent("close-%s" % i, fill, "SELL", size, size * PX,
                       "CLO", "fixed", "EXIT_ALLOWED", "EXIT",
                       core.ManualLedger.sleeve_id(WALLET, "NEAR"), "pos",
                       "LONG", 4.0, 4.0, True, True,
                       core.utc_now_ms(), "lifecycle=EXIT;")


def gateway(owned, exchange):
    g = core.SenderGateway.__new__(core.SenderGateway)
    g.ledger = Ledger(owned)
    g.cfg = SimpleNamespace(min_notional=lambda: 10.0)
    g._exchange_net_for_test = exchange
    g._persisted_exchange_positions = lambda: ({COIN: g._exchange_net_for_test}, "")
    g._fresh_exchange_net = lambda coin: g._exchange_net_for_test
    g._close_proof_account_ok = lambda: True
    g._master_gate_reason = lambda *args: ""
    g._reserve_exchange_order_slot = lambda **kw: core.utc_now_ms()
    g._note_sender_key_rejection = lambda response: None
    return g


def fake_wire(g, spy, it, size, timing):
    # Exercise the actual one-call gate, not a mock replacing _place_order.
    with patch.object(core, "_open_orders_send_begin", lambda: None), \
         patch.object(core, "_open_orders_send_end", lambda: None):
        response = g._place_order(spy, "NEAR", False, size, PX, "Ioc",
                                  True, timing, "exchange_call_started_ms",
                                  bypass_rate_limit_cooldown=True,
                                  intent=it, path="send_other")
    g._mark_held_close_sent(timing, it)
    return response


def run():
    core.atomic_write_json(core.HELD_CLOSE_REMAINDERS_FILE, {})
    core.atomic_write_json(core.CLOSE_ESCALATIONS_FILE, {})
    g = gateway(4.0, 4.0)
    spy = OrderSpy()
    held_first = None
    total_sent = 0.0
    for n in range(40):
        it = intent(n)
        timing = {}
        size, block = g._prepare_held_close(it, RESOLVED, PX, 0.1, timing)
        if n == 0:
            held_first = (size, block)
        if block is not None:
            continue
        permitted, _ = g._validate_final_wire_order(
            it, RESOLVED, "NEAR", size, PX, timing)
        if permitted:
            fake_wire(g, spy, it, size, timing)
            total_sent += size
    check("A_FORTY_POINT_ONE_REMAINDERS_AGGREGATE_TO_ONE_SEND",
          len(spy.calls) == 1 and total_sent * PX >= 10.0,
          (len(spy.calls), total_sent, total_sent * PX))
    check("A_OWNED_BATCH_DOES_NOT_OVERSIZE_THE_EXCHANGE_POSITION",
          total_sent <= 4.0 and all(c[0][2] <= 4.0 for c in spy.calls),
          spy.calls)
    check("E_HELD_ROW_HAS_COIN_SIZE_NOTIONAL_AND_AGE",
          held_first is not None and held_first[1] is not None
          and any(row.get("coin") == "near" and row.get("size") == 0.1
                  and abs(row.get("notional", 0.0) - 0.32) < 1e-8
                  and isinstance(row.get("age_ms"), int)
                  for row in core.load_json(core.HELD_CLOSE_REMAINDERS_FILE, {}).values()),
          core.load_json(core.HELD_CLOSE_REMAINDERS_FILE, {}))

    # Whole account net exactly 0.1: venue exempts minimum only for reduce-only whole close.
    core.atomic_write_json(core.HELD_CLOSE_REMAINDERS_FILE, {})
    one = gateway(0.1, 0.1)
    one_spy = OrderSpy()
    it = intent("whole", 0.1)
    timing = {}
    whole_sz, blocked = one._prepare_held_close(it, RESOLVED, PX, 0.1, timing)
    ok, _ = one._validate_final_wire_order(it, RESOLVED, "NEAR", whole_sz, PX, timing)
    if blocked is None and ok:
        fake_wire(one, one_spy, it, whole_sz, timing)
    check("B_SUBTEN_EXACT_WHOLE_EXCHANGE_POSITION_SENT",
          blocked is None and ok and len(one_spy.calls) == 1
          and one_spy.calls[0][0][2] == 0.1,
          (blocked, ok, one_spy.calls))

    # Flat proof requires BOTH the engine ledger and the account flat. It removes
    # each previously held row and any associated red close escalation.
    core.atomic_write_json(core.HELD_CLOSE_REMAINDERS_FILE, {})
    for i in range(4):
        g._prepare_held_close(intent("flat-%d" % i), RESOLVED, PX, 0.1, {})
    key = WALLET + "::" + COIN
    core.atomic_write_json(core.CLOSE_ESCALATIONS_FILE, {
        key: {"state": "OPEN", "wallet": WALLET, "coin": COIN,
              "reason": "DUST_BELOW_MIN_NOTIONAL"}})
    g.ledger.change(0.0)
    g._exchange_net_for_test = 0.0
    cleared = g.clear_close_escalations()
    check("C_LEADER_AND_EXCHANGE_FLAT_REMAINDER_EXACTLY_ZERO",
          not core.load_json(core.HELD_CLOSE_REMAINDERS_FILE, {})
          and g.ledger.coin_net(COIN) == 0.0 and g._exchange_net_for_test == 0.0)
    check("C_FLAT_HAS_NO_OPEN_RED_FLAG_OR_LEFTOVER_ROW",
          cleared == 1 and not core.load_json(core.CLOSE_ESCALATIONS_FILE, {})
          and not core.load_json(core.HELD_CLOSE_REMAINDERS_FILE, {}),
          (cleared, core.load_json(core.CLOSE_ESCALATIONS_FILE, {})))

    # Exchange exposure not in the engine's ledger is treated as user-managed.
    # Even when 40 close fragments total more than $10, refuse any oversize/adoption.
    core.atomic_write_json(core.HELD_CLOSE_REMAINDERS_FILE, {})
    user = gateway(4.0, 4.5)
    user_spy = OrderSpy()
    user_result = []
    for n in range(40):
        it = intent("user-%d" % n)
        timing = {}
        sz, blocked = user._prepare_held_close(it, RESOLVED, PX, 0.1, timing)
        user_result.append(blocked is not None)
        if blocked is not None:
            user._open_close_escalation(it, "DUST_BELOW_MIN_NOTIONAL")
        else:
            allowed, _ = user._validate_final_wire_order(it, RESOLVED, "NEAR", sz, PX, timing)
            if allowed:
                fake_wire(user, user_spy, it, sz, timing)
    check("D_USER_MANAGED_RESIDUAL_NEVER_ADOPTED_OR_CLOSED",
          len(user_spy.calls) == 0 and all(user_result)
          and user._exchange_net_for_test == 4.5 and user.ledger.coin_net(COIN) == 4.0,
          (user_result.count(True), user._exchange_net_for_test))
    no_clear = user.clear_close_escalations()
    red = core.load_json(core.CLOSE_ESCALATIONS_FILE, {})
    check("D_UNEXPLAINED_RESIDUAL_STAYS_HELD_AND_RED",
          len(core.load_json(core.HELD_CLOSE_REMAINDERS_FILE, {})) == 40
          and no_clear == 0 and red.get(WALLET + "::" + COIN, {}).get("state") == "OPEN",
          (no_clear, red))
    failed = sum(not success for _, success in RESULTS)
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as exc:
        check("C7C4_STANDALONE_UNHANDLED_EXCEPTION", False, repr(exc))
        print("TOTAL=%d FAILED=%d" % (len(RESULTS),
              sum(not success for _, success in RESULTS)))
        sys.exit(1)
