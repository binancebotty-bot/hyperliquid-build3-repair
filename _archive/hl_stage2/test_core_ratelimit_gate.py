"""Expectations for the ENTRY/ADD rate-limit recovery's final wire cap gate.

This harness uses a fake exchange and a temporary config/audit directory. It
does not load credentials or open a network connection.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
LEADER = "0x" + "a" * 40


def check(name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append(bool(condition))
    print("RESULT::%s_%s%s" % (name, "PASS" if condition else "FAIL", (" | " + detail) if detail and not condition else ""))


class FakeExchange:
    def __init__(self) -> None:
        self.calls = []

    def order(self, coin, is_buy, size, px, tif, reduce_only=False):
        self.calls.append((coin, is_buy, size, px, tif, reduce_only))
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
            {"resting": {"oid": 12345}}
        ]}}}


def make_intent(c):
    fill = c.LeaderFill(
        "rate-limit-fill", LEADER, "BTC", "BUY", 10.0, 2.0,
        c.utc_now_ms(), "TEST", raw={"dir": "Open Long"},
    )
    return c.Intent(
        intent_id="rate-limit-intent", fill=fill, copy_side="BUY",
        copy_size=2.0, copy_notional=20.0, wallet_mode="ON",
        copy_mode="fixed", decision="ENTRY_ALLOWED", reason="ENTRY",
        sleeve_id="sleeve", position_id="position",
        position_direction_before="", wallet_position_before=0.0,
        coin_net_before=0.0, reduce_only_intended=False,
        reduce_only_sent_planned=False, notes="lifecycle=ENTRY",
    )


def run_case(c, cfg_path: Path, cap: float, send_mode=None):
    config = {"global_controls": {"max_order_notional_usd": cap}}
    if send_mode is not None:
        config["global_controls"]["send_mode"] = send_mode
    cfg_path.write_text(json.dumps(config), encoding="utf-8")
    gateway = c.SenderGateway(c.ConfigManager(config_path=cfg_path), c.AuditLogWriter())
    gateway._pre_exchange_asset_safety = lambda *args, **kwargs: (True, {})
    gateway._fetch_all_mids = lambda: {"BTC": 20.0}  # BUY at leader price rests as GTC
    gateway._already_resting_block = lambda *args, **kwargs: None
    gateway._effective_symbol_min_notional = lambda *args, **kwargs: 1.0
    exchange = FakeExchange()
    result = gateway._entry_add_rate_limit_recovery(
        exchange=exchange, sdk_coin="BTC", intent=make_intent(c),
        price_max_dec=2, wire_size=2.0, initial_limit_px=10.0,
        initial_wire_notional=20.0, initial_error="rate limit",
        timing={}, resolved={
            "ok": True, "raw_coin": "BTC", "sdk_coin": "BTC",
            "min_order_value_usd": 1.0,
        },
    )
    return exchange, result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ratelimit_gate_") as temp_dir:
        tmp = Path(temp_dir)
        os.environ.update({
            "HL_LIVE_AUDIT_DIR": str(tmp / "audit"),
            "HL_LIVE_ENV_FILE": str(tmp / "missing.env"),
            "HL_LEADER_NETWORK": "testnet",
            "HL_FOLLOWER_NETWORK": "testnet",
            "HL_LIVE_ENTRY_ADD_RATE_LIMIT_RECOVERY_ENABLED": "1",
            "HL_LIVE_ENTRY_ADD_RATE_LIMIT_RECOVERY_MAX_AGE_MS": "180000",
            "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
        })
        import HL_Live_Copy_Service_Core as c

        over_cap, _ = run_case(c, tmp / "over-cap.json", 19.99, send_mode="ON")
        check("EXPECT_OVER_CAP_ZERO_EXCHANGE_CALLS", len(over_cap.calls) == 0, repr(over_cap.calls))
        # Over-cap refusal is proven by zero exchange calls above (switch armed, so the cap is what refuses).

        in_cap, _ = run_case(c, tmp / "in-cap.json", 20.0, send_mode="ON")  # Live recheck defaults a missing switch to OFF.
        check("EXPECT_IN_CAP_ONE_EXCHANGE_CALL", len(in_cap.calls) == 1, repr(in_cap.calls))

    print("TOTAL=%d FAILED=%d" % (len(RESULTS), RESULTS.count(False)))
    return 1 if False in RESULTS else 0


if __name__ == "__main__":
    raise SystemExit(main())
