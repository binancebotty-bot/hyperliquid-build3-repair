#!/usr/bin/env python3
"""CASE 1 - test_readinv_malformed.py
Target: _finite_net_or_none (lines 8206-8213); guard is line 8213 `return val if math.isfinite(val) else None`.
Drive: feed NaN, +inf, a str and a dict through it, then through a close plan.
Assert: unreadable is never substituted - net is None and the close takes a HOLD (CLOSE_PROOF_HOLD_NONFINITE_NET or the unreadable path), with ZERO wire calls.
Mutation: change 8213 to `return val` -> this test must go RED.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

RESULTS = []
A = "0x" + "a" * 40
FOLLOWER = "0x" + "c" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="readinv_malformed_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "testnet",
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
        "HL_FOLLOWER_DEXES": "xyz",
        "HL_LIVE_DISABLE_NETWORK_REFRESH": "0",
        "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
        "HL_LIVE_HL_PRIVATE_KEY": "0x" + "1" * 64,
        "HL_LIVE_HL_ACCOUNT_ADDRESS": FOLLOWER,
    })
    os.environ["HL_LIVE_GLOBAL_LOCK_FILE"] = str(Path(tempfile.mkdtemp(prefix="hl_lock_")) / "engine-global.lock")

    import HL_Live_Copy_Service_Core as c
    state_dir = Path(tempfile.mkdtemp(prefix="hl_state_"))
    c.acquire_global_instance_lock(state_dir)

    c.USER_WALLET = FOLLOWER
    c.HLAccount, c.HLExchange = object, object
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})

    # Fake exchange that records wire calls
    class Ex:
        def __init__(self):
            self.calls = []

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            self.calls.append({"coin": coin, "size": size, "px": px, "reduce_only": reduce_only})
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 3}}]}}}

    # Resolved coin mock for BTC
    resolved_btc = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                    "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def mk_intent(iid, coin, kind):
        side = "SELL" if kind == "EXIT" else "BUY"
        fill = c.LeaderFill("f_" + iid, A, coin, side, 100.0, 1.0, c.utc_now_ms(), "TEST")
        return c.Intent(iid, fill, side, 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", kind, "sleeve:%s:%s" % (A, coin), "",
                        "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=%s;" % kind)

    def run_close_test(malformed_value, test_name):
        """Run a close test with _fresh_exchange_net returning malformed_value."""
        ledger = c.ManualLedger(path=tmp / f"ledger_{test_name}.json")
        ledger.sleeve(A, "BTC")["signed_size"] = 10.0

        ex = Ex()
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
        g._resolve_coin = lambda coin: dict(resolved_btc)
        g._get_exchange_client = lambda *a, **k: ex
        g._exchange_client_has_symbol = lambda *a, **k: True
        g._validate_final_wire_order = lambda *a, **k: (True, {})
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._exchange_client_for_coin = lambda coin: (ex, coin)
        g._pre_send_ownership_gate = lambda it: (True, {})
        g.leader_reduced_since = lambda f: 0
        g.cfg.master_switch_now = lambda: True
        g.cfg.liq_parity_enabled = lambda: False

        # Override _fresh_exchange_net to return the malformed value
        g._fresh_exchange_net = lambda coin: malformed_value

        intent = mk_intent(f"e_{test_name}", "BTC", "EXIT")
        ok, status, res = g._send_real(intent)
        return ok, status, ex.calls

    # ----- Test 1: _finite_net_or_none with NaN -----
    nan_result = c.SenderGateway._finite_net_or_none(float("nan"))
    check("NAN_RETURNS_NONE", nan_result is None)

    ok1, status1, calls1 = run_close_test(float("nan"), "nan")
    check("NAN_CLOSE_HOLDS", ok1 is False and "CLOSE_PROOF_HOLD" in status1 and not calls1, "%s %s" % (status1, calls1))

    # ----- Test 2: _finite_net_or_none with +inf -----
    inf_result = c.SenderGateway._finite_net_or_none(float("inf"))
    check("INF_RETURNS_NONE", inf_result is None)

    ok2, status2, calls2 = run_close_test(float("inf"), "inf")
    check("INF_CLOSE_HOLDS", ok2 is False and "CLOSE_PROOF_HOLD" in status2 and not calls2, "%s %s" % (status2, calls2))

    # ----- Test 3: _finite_net_or_none with str -----
    str_result = c.SenderGateway._finite_net_or_none("not a number")
    check("STR_RETURNS_NONE", str_result is None)

    ok3, status3, calls3 = run_close_test("not a number", "str")
    check("STR_CLOSE_HOLDS", ok3 is False and "CLOSE_PROOF_HOLD" in status3 and not calls3, "%s %s" % (status3, calls3))

    # ----- Test 4: _finite_net_or_none with dict -----
    dict_result = c.SenderGateway._finite_net_or_none({"key": "value"})
    check("DICT_RETURNS_NONE", dict_result is None)

    ok4, status4, calls4 = run_close_test({"key": "value"}, "dict")
    check("DICT_CLOSE_HOLDS", ok4 is False and "CLOSE_PROOF_HOLD" in status4 and not calls4, "%s %s" % (status4, calls4))

    # ----- Test 5: valid finite number passes through -----
    valid_result = c.SenderGateway._finite_net_or_none(123.45)
    check("VALID_FINITE_PASSES", valid_result == 123.45)

    c.release_global_instance_lock()
    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()