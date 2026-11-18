#!/usr/bin/env python3
"""Gap 4 (plan check 18 Nov): the missed-entry diff path must not send an order whose floored size is under the
minimum notional ($10 or the symbol minimum). Normal entry path already checks this after rounding; this file
pins the missed-entry path (_missed_entry_rest_or_diff).

G4_1 floored size x leader price below $10 -> named refusal MISSED_ENTRY_DIFF_BELOW_MIN_NOTIONAL, no exchange call.
G4_2 a size that still clears $10 after flooring is NOT refused by this guard.
Mutation check: remove the guard and G4_1 goes RED.

Run: python test_core_gap4_min_notional.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
LEADER = "0x" + "d" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="gap4_"))
    os.environ.update({"HL_LIVE_LIQ_PARITY": "0", "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "mainnet",
                       "HL_FOLLOWER_NETWORK": "testnet", "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                       "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    import requests
    import HL_Live_Copy_Service_Core as c
    lockdir = Path(tempfile.mkdtemp(prefix="gap4lock_"))
    os.environ["HL_LIVE_GLOBAL_LOCK_FILE"] = str(lockdir / "engine-global.lock")
    c.acquire_global_instance_lock(lockdir / "state")

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER

    class FakeExchange:
        def __init__(self):
            self.calls = []

        def order(self, *a, **k):
            self.calls.append((a, k))
            raise RuntimeError("fake exchange: must not be reached by a refused entry")

        def update_leverage(self, *a, **k):
            self.calls.append(("update_leverage", a, k))
            raise RuntimeError("fake exchange: must not be reached by a refused entry")

        def cancel(self, *a, **k):
            self.calls.append(("cancel", a, k))
            raise RuntimeError("fake exchange: must not be reached by a refused entry")

    def run(sz_dec: int, copy_size: float, price: float):
        resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": sz_dec, "price_max_decimals": 2, "perp_dexs": [""],
                    "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
        led = c.ManualLedger(path=tmp / f"l{copy_size}_{price}.json")
        fill = c.LeaderFill("g4fill", LEADER, "BTC", "BUY", price, 1.0, c.utc_now_ms(), "TEST", 0, {})
        intent = c.IntentBuilder(c.ConfigManager(), led).build(fill)
        intent.copy_size = copy_size
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
        gw._resolve_coin = lambda coin: dict(resolved)
        fake = FakeExchange()
        gw._exchange_client_for_coin = lambda coin: (fake, "BTC")
        gw._get_exchange_client = lambda *a, **k: fake
        try:
            res = gw._missed_entry_rest_or_diff(intent, "MARGIN_REJECT_AT_REFUSAL")
        except Exception as exc:  # the old code runs on into the exchange, which the fake refuses
            res = {"outcome": f"RAISED:{type(exc).__name__}"}
        return res, fake

    # 0.667 at sz_decimals 1 floors to 0.6; 0.6 x 15 = 9.0 < 10 -> must be refused, nothing sent
    res, fake = run(sz_dec=1, copy_size=0.667, price=15.0)
    check("G4_1_FLOORED_BELOW_MIN_NOTIONAL_REFUSED_NO_SEND",
          res.get("outcome") == "MISSED_ENTRY_DIFF_BELOW_MIN_NOTIONAL" and not fake.calls, str(res)[:300])
    # 1.0 at sz_decimals 1 stays 1.0; 1.0 x 15 = 15 >= 10 -> the guard does not fire
    res, fake = run(sz_dec=1, copy_size=1.0, price=15.0)
    check("G4_2_ABOVE_MIN_NOTIONAL_NOT_REFUSED_BY_GUARD",
          res.get("outcome") != "MISSED_ENTRY_DIFF_BELOW_MIN_NOTIONAL", str(res)[:300])

    failed = [n for n, ok in RESULTS if not ok]
    print("RESULT::SUMMARY_%d_PASS_%d_FAIL" % (len(RESULTS) - len(failed), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
