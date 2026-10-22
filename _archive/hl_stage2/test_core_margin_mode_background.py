#!/usr/bin/env python3
"""Hot path (move 1): the first-use margin-mode setup (exchange.update_leverage) runs on a background thread before the
first order, not inside the order's critical path. If the background setup has not finished when the order arrives the
order does it inline exactly as before (never lost, never sent with the wrong margin mode); a failed setup never blocks.

Run (from _archive/hl_stage2):  HL_LIVE_ENV_FILE=/nonexistent python3 test_core_margin_mode_background.py
Prints RESULT::name_PASS/FAIL and TOTAL=n FAILED=m. No network, no orders.
"""
from __future__ import annotations

import argparse
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

    # ---- C: Codex findings -------------------------------------------------------------------------------------------
    # C1 (e): a non-dict / unrecognised reply is a failure (fail closed), never remembered as set
    for label, reply in (("NONE", None), ("EMPTY_DICT", {}), ("STRING", "ok"), ("ERR_STATUS", {"status": "err"})):
        fk = FakeExchange()
        fk.update_leverage = (lambda r: (lambda leverage, name, is_cross=True: r))(reply)
        gx = gateway(fk)
        okx, sx, _ = send_real(gx, mk_intent())
        check("C1_UNRECOGNISED_REPLY_%s_FAILS_CLOSED" % label,
              okx is False and "MARGIN_MODE_UNSET" in str(sx) and "BTC" not in gx.__dict__.get("_margin_mode_done", set()), "%s %s" % (okx, sx))

    # C2 (b): one serial worker: many coins queued, never two update_leverage calls in flight at once
    class SlowExchange(FakeExchange):
        def __init__(self):
            super().__init__()
            self.live = 0
            self.peak = 0
            self.lock = threading.Lock()
            self.seen = []

        def update_leverage(self, leverage, name, is_cross=True):
            with self.lock:
                self.live += 1
                self.peak = max(self.peak, self.live)
                self.seen.append(threading.current_thread().name)
            time.sleep(0.05)
            with self.lock:
                self.live -= 1
            return {"status": "ok"}
    slow = SlowExchange()
    gs = gateway(slow)
    names = ["COIN%d" % i for i in range(6)]
    gs._exchange_client_for_coin = lambda coin: (slow, coin)
    for n in names:
        gs.schedule_margin_mode_setup(n)
    drained = gs.wait_margin_mode_setup(10.0)
    check("C2_ONE_SERIAL_WORKER_NO_OVERLAP_ACROSS_COINS",
          drained and slow.peak == 1 and len(slow.seen) == 6 and set(slow.seen) == {"HLCore-margin-mode"}, "%s %s %s" % (drained, slow.peak, slow.seen))

    # C3 (a): background calls go through the order lane: paced slot reservation, 429 re-arms the shared cooldown and the
    # next background call waits it out
    os.environ["HL_LIVE_RATE_LIMIT_COOLDOWN_MS"] = "600"
    class Limited(FakeExchange):
        def __init__(self):
            super().__init__()
            self.stamps = []

        def update_leverage(self, leverage, name, is_cross=True):
            self.stamps.append((name, time.monotonic()))
            if len(self.stamps) == 1:
                raise RuntimeError("ClientError(429, 'Too Many Requests')")
            return {"status": "ok"}
    lim = Limited()
    gl = gateway(lim)
    slots = []
    real_slot = gl._reserve_exchange_order_slot
    gl._reserve_exchange_order_slot = lambda wait_for_cooldown=True: (slots.append(wait_for_cooldown), real_slot(wait_for_cooldown))[1]
    gl._exchange_client_for_coin = lambda coin: (lim, coin)
    gl.schedule_margin_mode_setup("AAA")
    gl.schedule_margin_mode_setup("BBB")
    gl.wait_margin_mode_setup(10.0)
    gap = lim.stamps[1][1] - lim.stamps[0][1] if len(lim.stamps) == 2 else -1
    check("C3_BACKGROUND_CALL_USES_ORDER_SLOT_AND_BACKS_OFF_ON_429",
          slots == [True, True] and gap >= 0.5 and "AAA" not in gl._mm_seen and "BBB" in gl._mm_seen,
          "slots=%s gap=%.2f seen=%s" % (slots, gap, gl._mm_seen))
    os.environ.pop("HL_LIVE_RATE_LIMIT_COOLDOWN_MS", None)

    # C4 (c): no startup prewarm of held coins; a coin is queued only by an armed opening/increasing fill
    held = gateway(FakeExchange())
    check("C4_NO_STARTUP_PREWARM_OF_HELD_COINS", not hasattr(held, "prewarm_margin_mode_at_startup")
          and held.wait_margin_mode_setup(0.5) and not held.__dict__.get("_mm_queue"))
    add = FakeExchange()
    ga = gateway(add)
    ga.prewarm_margin_mode_for_fill(c.LeaderFill("f5", A, "BTC", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", raw={"dir": "Long > Long"}))
    ga.prewarm_margin_mode_for_fill(c.LeaderFill("f6", A, "ETH", "BUY", 100.0, 1.0, c.utc_now_ms(), "TEST", raw={"dir": "Open Long"}))
    check("C4B_ONLY_FILLS_ABOUT_TO_BE_SENT_QUEUE_A_COIN", ga.wait_margin_mode_setup(5.0) and len(add.calls) == 1, str(add.calls))

    # C5 (d): stop drains with a bound: queued work is dropped, the in-flight call finishes, new work is refused
    gate5 = threading.Event()
    f5 = FakeExchange(gate=gate5)
    g5s = gateway(f5)
    g5s._exchange_client_for_coin = lambda coin: (f5, coin)
    g5s.schedule_margin_mode_setup("AAA")
    time.sleep(0.2)
    g5s.schedule_margin_mode_setup("BBB")
    g5s.schedule_margin_mode_setup("CCC")
    t0 = time.monotonic()
    idle_early = g5s.stop_margin_mode_worker(0.4)
    took = time.monotonic() - t0
    refused = g5s.schedule_margin_mode_setup("DDD") is False
    gate5.set()
    idle_late = g5s.wait_margin_mode_setup(5.0)
    g5s._mm_thread.join(5.0)
    check("C5_STOP_IS_BOUNDED_DROPS_QUEUE_REFUSES_NEW_AND_WORKER_EXITS",
          idle_early is False and took < 2.0 and refused and idle_late and not g5s._mm_thread.is_alive()
          and [k for k, _t, _s in f5.calls] == ["update_leverage"], "%s %.2f %s %s" % (idle_early, took, refused, f5.calls))
    check("C5B_STOP_WITH_NOTHING_RUNNING_IS_IDLE_TRUE", gateway(FakeExchange()).stop_margin_mode_worker(0.5) is True)

    # C6 (f): the order's wait for an in-flight setup is bounded and fail-closed
    os.environ["HL_LIVE_MM_WAIT_SEC"] = "0.3"
    gate6 = threading.Event()
    f6 = FakeExchange(gate=gate6)
    g6w = gateway(f6)
    g6w.schedule_margin_mode_setup("BTC")
    time.sleep(0.2)
    t0 = time.monotonic()
    ok6, s6, _ = send_real(g6w, mk_intent())
    took6 = time.monotonic() - t0
    gate6.set()
    g6w.wait_margin_mode_setup(5.0)
    os.environ.pop("HL_LIVE_MM_WAIT_SEC", None)
    check("C6_ORDER_WAIT_FOR_INFLIGHT_SETUP_IS_BOUNDED_AND_FAILS_CLOSED",
          ok6 is False and "MARGIN_MODE_UNSET" in str(s6) and took6 < 3.0 and "order" not in kinds(f6), "%s %s %.2f %s" % (ok6, s6, took6, kinds(f6)))

    # C7: the queue is bounded
    os.environ["HL_LIVE_MM_QUEUE_MAX"] = "2"
    gate7 = threading.Event()
    f7 = FakeExchange(gate=gate7)
    g7q = gateway(f7)
    g7q._exchange_client_for_coin = lambda coin: (f7, coin)
    res7 = [g7q.schedule_margin_mode_setup("Q%d" % i) for i in range(6)]
    gate7.set()
    g7q.wait_margin_mode_setup(5.0)
    os.environ.pop("HL_LIVE_MM_QUEUE_MAX", None)
    check("C7_QUEUE_IS_BOUNDED", res7.count(True) <= 3 and res7.count(False) >= 3, str(res7))

    # E1: an exchange client without update_leverage fails ENTRY/ADD closed; closes are never blocked
    class NoLeverage:
        pass
    gn = gateway(FakeExchange())
    stand = argparse.Namespace(fill=argparse.Namespace(coin="BTC"))
    blk_entry = gn._ensure_margin_mode(NoLeverage(), "BTC", stand, "ENTRY", {})
    blk_add = gn._ensure_margin_mode(NoLeverage(), "BTC", stand, "ADD", {})
    cl_exit = gn._ensure_margin_mode(NoLeverage(), "BTC", stand, "EXIT", {})
    cl_red = gn._ensure_margin_mode(NoLeverage(), "BTC", stand, "REDUCE", {})
    check("E1_MISSING_UPDATE_LEVERAGE_BLOCKS_ENTRY_AND_ADD_NOT_CLOSES",
          blk_entry is not None and blk_entry[0] is False and blk_entry[1] == "MARGIN_MODE_UNSET"
          and blk_add is not None and blk_add[1] == "MARGIN_MODE_UNSET" and cl_exit is None and cl_red is None
          and "BTC" not in gn.__dict__.get("_margin_mode_done", set()), str((blk_entry, blk_add, cl_exit, cl_red)))

    # E2: inline coin B while the worker is setting coin A: one call at a time across coins, both paced through the order slot
    class Tracked(FakeExchange):
        def __init__(self, gate=None):
            super().__init__(gate=gate)
            self.live = 0
            self.peak = 0
            self.names = []
            self.l = threading.Lock()

        def update_leverage(self, leverage, name, is_cross=True):
            with self.l:
                self.live += 1
                self.peak = max(self.peak, self.live)
                self.names.append(name)
            if name == "AAA" and self.gate is not None:
                self.gate.wait(10)
            time.sleep(0.05)
            with self.l:
                self.live -= 1
            return {"status": "ok"}
    gate_e = threading.Event()
    te = Tracked(gate=gate_e)
    ge = gateway(te)
    slots_e = []
    real_slot_e = ge._reserve_exchange_order_slot
    ge._reserve_exchange_order_slot = lambda wait_for_cooldown=True: (slots_e.append(wait_for_cooldown), real_slot_e(wait_for_cooldown))[1]
    ge._exchange_client_for_coin = lambda coin: (te, coin)
    ge.schedule_margin_mode_setup("AAA")
    time.sleep(0.2)
    res_b = {}
    stand_b = argparse.Namespace(fill=argparse.Namespace(coin="BBB"))
    tb = threading.Thread(target=lambda: res_b.update(r=ge._ensure_margin_mode(te, "BBB", stand_b, "ENTRY", {})), daemon=True)
    tb.start()
    time.sleep(0.3)
    b_waiting = tb.is_alive() and te.names == ["AAA"]
    gate_e.set()
    tb.join(10)
    ge.wait_margin_mode_setup(5.0)
    check("E2_INLINE_B_SERIALISED_BEHIND_WORKER_A_AND_PACED",
          b_waiting and res_b.get("r", "x") is None and te.peak == 1 and te.names == ["AAA", "BBB"] and slots_e == [True, True],
          "%s %s %s %s %s" % (b_waiting, res_b, te.peak, te.names, slots_e))
    # ... and an order for B waits no longer than HL_LIVE_MM_WAIT_SEC for the lock, then fails closed (no update_leverage call)
    os.environ["HL_LIVE_MM_WAIT_SEC"] = "0.3"
    gate_f = threading.Event()
    tf = Tracked(gate=gate_f)
    gf = gateway(tf)
    gf._exchange_client_for_coin = lambda coin: (tf, coin)
    gf.schedule_margin_mode_setup("AAA")
    time.sleep(0.2)
    stand_c = argparse.Namespace(fill=argparse.Namespace(coin="CCC"))
    t0 = time.monotonic()
    blocked = gf._ensure_margin_mode(tf, "CCC", stand_c, "ENTRY", {})
    took_f = time.monotonic() - t0
    closes_ok = gf._ensure_margin_mode(tf, "CCC", stand_c, "EXIT", {}) is None
    gate_f.set()
    gf.wait_margin_mode_setup(5.0)
    os.environ.pop("HL_LIVE_MM_WAIT_SEC", None)
    check("E2B_INLINE_B_WAIT_IS_BOUNDED_FAILS_CLOSED_CLOSES_UNBLOCKED",
          blocked is not None and blocked[1] == "MARGIN_MODE_UNSET" and took_f < 3.0 and closes_ok and "CCC" not in tf.names,
          "%s %.2f %s %s" % (blocked and blocked[1], took_f, closes_ok, tf.names))

    failed = [n for n, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
