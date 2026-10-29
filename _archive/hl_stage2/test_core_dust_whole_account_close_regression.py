#!/usr/bin/env python3
"""C7N20261029I2: prove the venue's sub-minimum WHOLE account-position close exception.

Offline real Core final-wire gate, with persisted exchange snapshot and independently owned
ledger net. No Core modifications, SDK order, wallet, network or mainnet action.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_dust_whole_account_close_regression.py
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"
os.environ["HL_LEADER_NETWORK"] = "testnet"
os.environ["HL_FOLLOWER_NETWORK"] = "testnet"
os.environ.pop("HL_LIVE_DUST_CLOSE_ATTEMPT", None)

with tempfile.TemporaryDirectory(prefix="dust_whole_account_") as temp:
    os.environ["HL_LIVE_AUDIT_DIR"] = temp
    import HL_Live_Copy_Service_Core as c

    results = []
    def check(name, ok, detail=""):
        results.append(bool(ok))
        print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL",
                                  (" | " + str(detail)[:220]) if not ok else ""))

    wallet = "0x" + "a" * 40
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": True, "global_controls": {},
        "wallets": {wallet: {"enabled": True, "mode": "ON"}}
    })
    min_usd = c.DEFAULT_MIN_NOTIONAL
    px = 100.0
    tiny = min_usd / px / 2.0
    resolved = {"ok": True, "sdk_coin": "BTC", "raw_coin": "BTC",
                "min_order_value_usd": min_usd}

    def gateway(ex_net, ledger_net=None):
        ledger = c.ManualLedger(path=Path(temp) / "isolated_ledger.json")
        ledger.coin_net = lambda key: ex_net if ledger_net is None else ledger_net
        c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {
            "positions_by_coin": {"BTC": {"signed_size": ex_net}}
        })
        return c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)

    def intent(lifecycle="EXIT", side="SELL", size=tiny):
        close = lifecycle in {"EXIT", "REDUCE"}
        fill = c.LeaderFill("C7-whole-dust", wallet, "BTC", side, px,
                            size, c.utc_now_ms(), "TEST")
        return c.Intent("C7-whole-dust-intent", fill, side, size, size * px,
                        "ON", "fixed", "EXIT_ALLOWED" if close else "ENTRY_ALLOWED",
                        lifecycle, "s", "", "LONG", 1.0, 1.0, close, close,
                        c.utc_now_ms(), "lifecycle=%s;" % lifecycle)

    def validate(gw, it, size=tiny):
        timing = {}
        ok, info = gw._validate_final_wire_order(
            it, dict(resolved), "BTC", size, px, timing)
        return ok, str(info.get("terminal_state", "")), timing

    g = gateway(tiny)
    it = intent("EXIT", "SELL")
    check("ORDER_IS_GENUINELY_SUB_MINIMUM", 0 < tiny * px < min_usd,
          (tiny, px, min_usd))
    check("EXIT_REQUESTS_REDUCE_ONLY", it.reduce_only_intended
          and g._reduce_only_for_intent(it))
    check("EXCHANGE_WHOLE_POSITION_PROVEN", g._closes_whole_account_position(it, tiny))
    check("CLOSE_DELTA_EXACTLY_FLATTENS_ACCOUNT",
          abs(tiny + c.ManualLedger.signed_delta(it.copy_side, tiny))
          <= c.POSITION_EPSILON)
    ok, status, timing = validate(g, it)
    check("D_SUBMIN_WHOLE_POSITION_CLOSE_SENT", ok is True,
          (ok, status, timing))
    check("WIRE_GATE_RECORDS_DUST_EXCEPTION",
          "dust_close_below_min_notional" in timing, timing)

    ok, status, _ = validate(gateway(2*tiny), intent("EXIT", "SELL"))
    check("PARTIAL_EXCHANGE_POSITION_CLOSE_BLOCKED",
          ok is False and status == "DUST_BELOW_MIN_NOTIONAL", (ok, status))

    ok, status, _ = validate(gateway(tiny, ledger_net=2*tiny),
                             intent("EXIT", "SELL"))
    check("LEDGER_MUST_AGREE_WITH_EXCHANGE",
          ok is False and status == "DUST_BELOW_MIN_NOTIONAL", (ok, status))

    ok, status, _ = validate(gateway(tiny), intent("EXIT", "BUY"))
    check("CLOSE_MUST_NOT_ADD_EXPOSURE",
          ok is False and status == "DUST_BELOW_MIN_NOTIONAL", (ok, status))

    ok, status, _ = validate(gateway(0.0), intent("ENTRY", "BUY"))
    check("SUBMIN_ENTRY_HAS_NO_EXEMPTION",
          ok is False and status == "DUST_BELOW_MIN_NOTIONAL", (ok, status))

    os.environ["HL_LIVE_DUST_CLOSE_ATTEMPT"] = "0"
    try:
        ok, status, _ = validate(gateway(tiny), intent("EXIT", "SELL"))
        check("DISABLING_EXCEPTION_REPRODUCES_DUST_BLOCK",
              ok is False and status == "DUST_BELOW_MIN_NOTIONAL", (ok, status))
    finally:
        os.environ.pop("HL_LIVE_DUST_CLOSE_ATTEMPT", None)

    print("TOTAL=%d FAILED=%d" % (len(results), results.count(False)))
    sys.exit(1 if False in results else 0)
