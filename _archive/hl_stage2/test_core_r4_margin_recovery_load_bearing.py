"""Load-bearing R4 recovery regression: real missed-entry decision and wire send.

The negative control replaces only `margin_recovery = cause == ...` with
`margin_recovery = False` in Core.py; this test must fail on that mutation.
Run with PAID_GUARD_ALLOW=1 on the authorised offline host.
"""
import ast
from pathlib import Path
from types import MethodType, SimpleNamespace

from test_core_r4_physical_order_no_call import CORE, ExchangeSpy, build_sender


def test_margin_reject_at_refusal_rests_once_at_leader_price_not_follower(tmp_path):
    # Compile the real production recovery method, not a reimplementation.
    tree = ast.parse(CORE.read_text(encoding="utf-8-sig"))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                 and n.name == "SenderGateway")
    method = next(n for n in owner.body if isinstance(n, ast.FunctionDef)
                  and n.name == "_missed_entry_rest_or_diff")
    method.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))

    sender, updates, events = build_sender(tmp_path, withdrawable=100)
    exchange = ExchangeSpy()
    follower_calls = []
    decision_calls = []
    recovery_calls = []
    leader_price = 70.0
    follower_price = 500.0  # deliberately far away: ordinary path would take
    env = dict(sender._place_order.__func__.__globals__)
    env.update({
        "fnum": lambda value, default=0.0: float(value) if value is not None else default,
        "canonical_coin_key": lambda coin: coin,
        "LEADER_NETWORK": "testnet",
        "FOLLOWER_NETWORK": "testnet",
        "follower_mid": lambda *a, **kw: follower_calls.append((a, kw)) or follower_price,
        "missed_entry_decision": lambda *a, **kw: decision_calls.append((a, kw)) or {
            "ok": True, "take": True, "desired_px": leader_price,
            "cap_px": leader_price, "adverse_bps": 1000.0,
        },
        "classify_operator_action": lambda *a: "WAIT",
        "classify_reject_category": lambda *a: "",
        "SenderGateway": SimpleNamespace(_gate_journal_failures=0),
    })
    exec(compile(module, str(CORE), "exec"), env)
    sender._missed_entry_rest_or_diff = MethodType(env["_missed_entry_rest_or_diff"], sender)

    sender.cfg = SimpleNamespace(marketable_bps=lambda: 25.0)
    sender._base_timing = lambda intent: {}
    sender._resolve_coin = lambda coin: {
        "ok": True, "snapshot_only": False, "sdk_order_compatible": True,
        "price_max_decimals": 2, "sz_decimals": 3,
    }
    sender._floor_wire_size = lambda size, decimals: float(size)
    sender.resting_entry_for = lambda *a: None
    sender._exchange_client_for_coin = lambda coin: (exchange, coin)
    sender._ensure_margin_mode = lambda *a, **kw: None
    sender._fresh_margin_rest_proof = lambda *a: True
    sender._format_limit_px = lambda price, decimals: round(price, decimals)
    sender._px_passive = lambda price, decimals, is_buy: round(price, decimals)
    sender._pre_exchange_asset_safety = lambda *a: (True, {})
    sender._pre_send_ownership_gate = lambda intent: (True, {})
    sender._recovery_send_hooks = lambda intent, tif, order_type, px, size, ro, timing, label: (
        None,
        lambda: timing.__setitem__("send_attempt_id", "attempt-" + intent.intent_id)
                or "attempt-" + intent.intent_id,
    )
    sender._parse_hl_response = lambda response: (True, "ORDER_RESTING", "oid-1", "")
    sender._register_resting_entry = lambda *a: recovery_calls.append(a)

    intent = SimpleNamespace(
        intent_id="margin-recovery-refusal-1", reason="ENTRY",
        copy_side="BUY", copy_size=1.0, reduce_only_intended=False,
        fill=SimpleNamespace(
            coin="BTC", price=leader_price, leader_fill_id="leader-fill-1",
            leader_wallet="0x" + "b" * 40,
        ),
    )
    result = sender._missed_entry_rest_or_diff(intent, "MARGIN_REJECT_AT_REFUSAL")

    assert len(exchange.orders) == 1, (
        "MARGIN_REJECT_AT_REFUSAL must invoke exactly one physical exchange.order; "
        f"got {len(exchange.orders)}: {result}"
    )
    args, kwargs = exchange.orders[0]
    assert args[3] == leader_price, (
        f"MARGIN_REJECT_AT_REFUSAL must wire LEADER price {leader_price}, got {args[3]}"
    )
    assert args[4] == {"limit": {"tif": "Gtc"}}, (
        "MARGIN_REJECT_AT_REFUSAL must rest a GTC, never take via IOC"
    )
    assert result["take"] is False, (
        "MARGIN_REJECT_AT_REFUSAL resting decision must have take=False"
    )
    assert result["limit_px"] == leader_price
    assert result["leader_px"] == leader_price
    assert result["follower_px"] == 0.0, (
        "MARGIN_REJECT_AT_REFUSAL must not price from follower mid"
    )
    assert not follower_calls, "MARGIN_REJECT_AT_REFUSAL must not request follower mid"
    assert not decision_calls, "MARGIN_REJECT_AT_REFUSAL must bypass normal follower-price decision"
    assert result["exchange_called"] is True
    assert len(recovery_calls) == 1
