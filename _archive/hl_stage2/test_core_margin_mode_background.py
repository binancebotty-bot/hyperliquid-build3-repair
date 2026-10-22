#!/usr/bin/env python3
"""Hot path (move 1): the first-use margin-mode setup (exchange.update_leverage) runs on a background thread before the
first order, not inside the order's critical path. If the background setup has not finished when the order arrives the
order does it inline exactly as before (never lost, never sent with the wrong margin mode); a failed setup never blocks.

Run (from _archive/hl_stage2):  HL_LIVE_ENV_FILE=/nonexistent python3 test_core_margin_mode_background.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. No network, no orders.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
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
    tmp = Path(tempfile.mkdtemp(prefix="mmbg_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
                       "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0"})
    import HL_Live_Copy_Service_Core as c

    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100", "ETH": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": True, "global_controls": {},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}}})
    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}
    main_thread = threading.current_thread()

    class FakeExchange:
        def __init__(self, fail_leverage=0, gate=None):
            self.calls = []  # (kind, thread, in_send)
            self.fail_leverage = fail_leverage
            self.gate = gate
            self.in_send = threading.local()

        def update_leverage(self, leverage, name, is_cross=True):
            if self.gate is not None:
                self.gate.wait(10)
            self.calls.append(("update_leverage", threading.current_thread(), bool(getattr(self.in_send, "v", False))))
            if self.fail_leverage > 0:
                self.fail_leverage -= 1
                raise RuntimeError("exchange refused update_leverage")
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append(("order", threading.current_thread(), True))
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}]}}}

    def gateway(fake):
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), c.ManualLedger(path=tmp / ("l%d.json" % id(fake))))
        g._resolve_coin = lambda coin: dict(resolved)
        g._get_exchange_client = lambda *a, **k: fake
        g._exchange_client_has_symbol = lambda *a, **k: True
        g._validate_final_wire_order = lambda *a, **k: (True, {})
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._exchange_client_for_coin = lambda coin: (fake, "BTC")
        g._pre_send_ownership_gate = lambda it: (True, {})
        g.leader_reduced_since = lambda f: 0
        return g

    def send_real(g, intent):
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64  # placeholder; the fake exchange never signs
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        try:
            return g._send_real(intent)
        finally:
            c.HLAccount, c.HLExchange = saved
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)

    def mk_intent(coin="BTC"):
        fill = c.LeaderFill("f1", A, coin, "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST")
        return c.Intent("i1", fill, "BUY", 1.0, 100.0, "ON", "fixed", "ENTRY_ALLOWED", "ENTRY",
                        "sleeve:%s:%s" % (A, coin), "", "FLAT", 0.0, 0.0, False, False, c.utc_now_ms(), "lifecycle=ENTRY;")

    def kinds(fake):
        return [k for k, _t, _s in fake.calls]

    # ---- B1: setup runs on a background thread BEFORE the first order; the order then makes no network leverage call
    fake = FakeExchange()
    g = gateway(fake)
    queued = g.schedule_margin_mode_setup("BTC")
    g.wait_margin_mode_setup(5.0)
    lev = [x for x in fake.calls if x[0] == "update_leverage"]
    check("B1_SETUP_RUNS_BEFORE_FIRST_ORDER_ON_BACKGROUND_THREAD",
          queued and len(lev) == 1 and lev[0][1] is not main_thread and "order" not in kinds(fake), str(fake.calls))
    ok, status, _ = send_real(g, mk_intent())
    check("B1B_ORDER_PATH_MAKES_NO_LEVERAGE_CALL_AFTER_SETUP",
          ok and kinds(fake) == ["update_leverage", "order"], "ok=%s status=%s calls=%s" % (ok, status, kinds(fake)))
    check("B1C_SCHEDULING_AGAIN_IS_A_NOOP", g.schedule_margin_mode_setup("BTC") is False)

    # ---- B2: background setup not finished -> the order waits for that one call (no second call, no lost order)
    gate = threading.Event()
    fake2 = FakeExchange(gate=gate)
    g2 = gateway(fake2)
    g2.schedule_margin_mode_setup("BTC")
    result = {}
    t = threading.Thread(target=lambda: result.update(r=send_real(g2, mk_intent())), daemon=True)
    t.start()
    time.sleep(0.3)
    blocked_while_setup_pending = t.is_alive() and "order" not in kinds(fake2)
    gate.set()
    t.join(10)
    check("B2_ORDER_WAITS_FOR_UNFINISHED_SETUP_THEN_SENDS_ONCE",
          blocked_while_setup_pending and result.get("r", (False,))[0] is True
          and kinds(fake2) == ["update_leverage", "order"], str(kinds(fake2)))

    # ---- B3: never scheduled -> today's inline behaviour (setup then order on the sending thread)
    fake3 = FakeExchange()
    g3 = gateway(fake3)
    ok3, _s3, _ = send_real(g3, mk_intent())
    check("B3_INLINE_FALLBACK_STILL_SETS_MARGIN_MODE_BEFORE_ORDER",
          ok3 and kinds(fake3) == ["update_leverage", "order"] and fake3.calls[0][1] is main_thread, str(fake3.calls))

    # ---- B4: a failed background setup never raises, never blocks; the order retries inline
    fake4 = FakeExchange(fail_leverage=1)
    g4 = gateway(fake4)
    g4.schedule_margin_mode_setup("BTC")
    g4.wait_margin_mode_setup(5.0)
    ok4, _s4, _ = send_real(g4, mk_intent())
    check("B4_BACKGROUND_FAILURE_DOES_NOT_BLOCK_ORDER_RETRIES_INLINE",
          ok4 and kinds(fake4) == ["update_leverage", "update_leverage", "order"], str(kinds(fake4)))
    # ... and when the exchange keeps refusing, the entry still fails closed (MARGIN_MODE_UNSET), as before
    fake5 = FakeExchange(fail_leverage=5)
    g5 = gateway(fake5)
    g5.schedule_margin_mode_setup("BTC")
    g5.wait_margin_mode_setup(5.0)
    ok5, s5, _ = send_real(g5, mk_intent())
    check("B4B_STILL_FAILS_CLOSED_WHEN_EXCHANGE_REFUSES", ok5 is False and "MARGIN_MODE_UNSET" in str(s5)
          and "order" not in kinds(fake5), "%s %s %s" % (ok5, s5, kinds(fake5)))
    # an unresolvable symbol / unconfigured sender in the background thread is swallowed
    g6 = gateway(FakeExchange())
    g6._exchange_client_for_coin = lambda coin: (_ for _ in ()).throw(ValueError("real sender not configured"))
    g6.schedule_margin_mode_setup("BTC")
    check("B4C_BACKGROUND_EXCEPTION_IS_CONTAINED", g6.wait_margin_mode_setup(5.0) is True)

    # ---- B5: a fill for a wallet that is armed (mode ON, sending on) triggers setup; an OFF wallet / close does not
    fake7 = FakeExchange()
    g7 = gateway(fake7)
    entry = c.LeaderFill("f2", A, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", raw={"dir": "Open Long"})
    g7.prewarm_margin_mode_for_fill(entry)
    g7.wait_margin_mode_setup(5.0)
    check("B5_ARMED_WALLET_FILL_TRIGGERS_BACKGROUND_SETUP", kinds(fake7) == ["update_leverage"], str(fake7.calls))
    fake8 = FakeExchange()
    g8 = gateway(fake8)
    g8.prewarm_margin_mode_for_fill(c.LeaderFill("f3", A, "BTC", "SELL", 100.0, 1.0, c.utc_now_ms(), "TEST", raw={"dir": "Close Long"}))
    other = "0x" + "b" * 40
    g8.prewarm_margin_mode_for_fill(c.LeaderFill("f4", other, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", raw={"dir": "Open Long"}))
    g8.wait_margin_mode_setup(5.0)
    check("B5B_CLOSE_AND_UNARMED_WALLET_DO_NOT_TRIGGER_SETUP", kinds(fake8) == [], str(fake8.calls))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
