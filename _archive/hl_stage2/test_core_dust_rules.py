#!/usr/bin/env python3
"""F1 - dust rules (Boss: a sub-$10 order goes out ONLY if it closes the WHOLE account position; otherwise it
is a dust diff - never sent, never lost). Drives the engine's real pre-exchange gate
(`SenderGateway._validate_final_wire_order`, Gate B) with the engine's own mock-send setup: no exchange is touched,
no order is placed.

Cases:
 (a) sub-min ENTRY never sent, recorded as a diff (terminal DUST_BELOW_MIN_NOTIONAL + HOLD_DUST_OR_AGGREGATE);
 (b) sub-min REDUCE that is NOT the whole position not sent, recorded;
 (c) sub-min CLOSE of the WHOLE account position IS sent (reduce-only), and the entry-side round-up-to-min is NOT
     applied to an exit;
 (d) boundary: exactly at the minimum is sent; one cent below is blocked;
 (e) several leaders on one coin: the ACCOUNT position, not the single sleeve, decides "whole".

A failing check is a FINDING about the engine; the test is not weakened. Run (from _archive/hl_stage2):
  HL_LIVE_ENV_FILE=/nonexistent python -u test_core_dust_rules.py
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
A = "0x" + "a" * 40
B = "0x" + "b" * 40
FOLLOWER = "0x" + "c" * 40
BLOCKED = "SEND_NOT_ATTEMPTED_BELOW_MIN_NOTIONAL"
DUST_TERMINAL = "DUST_BELOW_MIN_NOTIONAL"


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="f1dust_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MOCK_SEND": "1", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
                       "HL_LIVE_MIN_NOTIONAL": "10"})
    os.environ.pop("HL_LIVE_AUTO_SEND_ENABLED", None)
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.DEFAULT_MIN_NOTIONAL = 10.0

    def write_cfg():
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True,
                                                 "global_controls": {"min_notional": 10},
                                                 "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed",
                                                                 "fixed_notional": 12}}})

    write_cfg()
    ledger = c.ManualLedger(path=tmp / "led.json")

    def gateway(coin_net_by_coin):
        """Real SenderGateway; only the exchange-truth read is stubbed (no network). The ledger is seeded to agree
        with the exchange, the realistic state the whole-position-close rule requires."""
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
        g._persisted_exchange_positions = lambda: ({c.canonical_coin_key(k): v for k, v in coin_net_by_coin.items()}, "")
        ledger.data.setdefault("by_coin_net", {})
        for k, v in coin_net_by_coin.items():
            ledger.data["by_coin_net"][c.canonical_coin_key(k)] = {"signed_size": v}
        return g

    def intent(lifecycle, side, size, reduce_only, wallet=A, price=100.0):
        fill = c.LeaderFill("f1", wallet, "BTC", side, price, size, c.utc_now_ms(), "TEST")
        return c.Intent("i1", fill, side, size, size * price, "ON", "fixed", "EXIT_ALLOWED", lifecycle,
                        "sleeve:%s:BTC" % wallet, "", "LONG", 0.0, 0.0, reduce_only, reduce_only,
                        c.utc_now_ms(), "lifecycle=%s;" % lifecycle)

    def gate(g, it, wire_size, limit_px, resolved=None, timing=None):
        resolved = resolved or {"raw_coin": "BTC", "sdk_coin": "BTC", "min_order_value_usd": 0.0}
        timing = {} if timing is None else timing
        ok, info = g._validate_final_wire_order(it, resolved, "BTC", wire_size, limit_px, timing)
        return ok, info, timing

    # ---- (a) sub-min ENTRY: never sent, recorded as a diff -------------------------------------------
    ok, info, _tm = gate(gateway({}), intent("ENTRY", "BUY", 0.05, False), 0.05, 100.0)     # $5 < $10
    check("DUST_A_SUBMIN_ENTRY_NOT_SENT", ok is False, "ok=%s info=%s" % (ok, info.get("status")))
    check("DUST_A_ENTRY_RECORDED_AS_DIFF",
          info.get("status") == BLOCKED and info.get("terminal_state") == DUST_TERMINAL
          and info.get("write_send_attempt") is True and info.get("exchange_called") is False
          and info.get("operator_action") == "HOLD_DUST_OR_AGGREGATE", str(info)[:260])

    # ---- (b) sub-min REDUCE that is NOT the whole position: not sent, recorded -----------------------
    # account is short 5.0; this close is a 0.5 sliver -> not the whole position
    ok, info, _tm = gate(gateway({"BTC": -5.0}), intent("EXIT", "BUY", 0.5, True), 0.5, 0.0001)
    check("DUST_B_SUBMIN_PARTIAL_REDUCE_NOT_SENT", ok is False, "ok=%s info=%s" % (ok, info.get("status")))
    check("DUST_B_PARTIAL_REDUCE_RECORDED", info.get("terminal_state") == DUST_TERMINAL
          and info.get("write_send_attempt") is True, str(info)[:200])

    # ---- (c) sub-min CLOSE of the WHOLE account position IS sent (reduce-only) ------------------------
    # account is short 0.05 BTC (~$5 at 100): closing it entirely is allowed under the exchange minimum
    ok, info, _tm = gate(gateway({"BTC": -0.05}), intent("EXIT", "BUY", 0.05, True), 0.05, 100.0)
    check("DUST_C_SUBMIN_WHOLE_CLOSE_SENT", ok is True, "ok=%s info=%s" % (ok, info))
    # the engine records the exception it used
    ok2, info2, timing2 = gate(gateway({"BTC": -0.05}), intent("EXIT", "BUY", 0.05, True), 0.05, 100.0)
    check("DUST_C_WHOLE_CLOSE_BELOW_MIN_FLAGGED",
          ok2 is True and "dust_close_below_min_notional" in timing2, "timing=%s" % timing2)
    # the entry-side round-up-to-min must NOT apply to an exit (structural + behavioural)
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    uplift_entry_only = bool(re.search(r'lifecycle in \{"ENTRY", "ADD"\} and should_uplift', src))
    check("DUST_C_UPLIFT_IS_ENTRY_ADD_ONLY", uplift_entry_only,
          "the round-up-to-min branch is not gated to ENTRY/ADD in the source")

    # ---- (d) boundary exactly at the minimum ---------------------------------------------------------
    ok_lo, info_lo, _tmlo = gate(gateway({}), intent("ENTRY", "BUY", 0.0999, False), 0.0999, 100.0)   # $9.99
    ok_hi, info_hi, _tmhi = gate(gateway({}), intent("ENTRY", "BUY", 0.10, False, ), 0.10, 100.0)      # $10.00 exactly
    check("DUST_D_JUST_BELOW_MIN_BLOCKED", ok_lo is False and info_lo.get("terminal_state") == DUST_TERMINAL,
          "9.99 -> ok=%s %s" % (ok_lo, info_lo.get("status")))
    check("DUST_D_EXACTLY_AT_MIN_SENT", ok_hi is True, "10.00 exactly -> ok=%s info=%s" % (ok_hi, info_hi))

    # ---- (e) several leaders on one coin: the ACCOUNT position decides "whole" ------------------------
    # two sleeves of -0.5 each = account -1.0. Closing ONE sleeve (0.5) is NOT the whole account -> blocked.
    ok_sleeve, info_sleeve, _tms = gate(gateway({"BTC": -1.0}), intent("EXIT", "BUY", 0.5, True, wallet=A), 0.5, 0.0001)
    check("DUST_E_ONE_SLEEVE_OF_TWO_NOT_WHOLE_BLOCKED", ok_sleeve is False,
          "close 0.5 of a -1.0 account -> ok=%s %s" % (ok_sleeve, info_sleeve.get("status")))
    # closing the whole ACCOUNT (-1.0) is the whole position even though this intent's sleeve is only 0.5
    ok_acct, info_acct, _tma = gate(gateway({"BTC": -1.0}), intent("EXIT", "BUY", 1.0, True, wallet=B), 1.0, 100.0)
    check("DUST_E_WHOLE_ACCOUNT_CLOSE_SENT", ok_acct is True, "close 1.0 of a -1.0 account -> ok=%s info=%s" % (ok_acct, info_acct))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    for n in failed:
        print("FINDING::%s failed against the engine" % n)
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
