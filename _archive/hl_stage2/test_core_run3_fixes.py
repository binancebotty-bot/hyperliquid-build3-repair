#!/usr/bin/env python3
"""Testnet run 3 fixes (2026-10-09): keep up with 10 very active leaders, send in parallel, and let leaders net.

K  the loop keeps up: repeat leader fills are dropped before any processing, the coin-key table is not re-read
   on every call, leaders are read in parallel and re-read only 30 s back, polled fills go to the send
   workers in loop mode, the leader poll is a 30 s backstop while the live feed is up, a capped copy read
   resumes where it stopped.
S  sends: exchange calls of different workers overlap (only the pacing slot is serialised), 4 workers by
   default, one coin always on one worker (in order); an entry older than the stale cutoff (Global Controls,
   default 30 s) is not taken within tolerance: it rests at the leader's price with a diff.
N  Boss's F3 ruling "Let them net": leaders trading opposite ways net on the one account like the exchange; a
   close goes reduce-only only when it fits in the account's net, otherwise (ledger = exchange) without it, so
   the ledger's sum of leaders always equals the exchange; opposite entries are never skipped; the screen
   shows each coin's net with which leader holds what.

Run: python test_core_run3_fixes.py   # RESULT:: markers, exit 0/1. No network, no orders.
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
FOLLOWER = "0x" + "c" * 40
A = "0x" + "a" * 40
B = "0x" + "b" * 40
RO_REJECT = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
    {"error": "Reduce only order would increase position. asset=0"}]}}}


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="run3fix_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0"})
    for k in ("HL_LIVE_HOT_SEND_WORKERS", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS", "HL_LIVE_STALE_ENTRY_SEC"):
        os.environ.pop(k, None)
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*a, **k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    mids = {"px": 100.0}
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": str(mids["px"]), "ETH": str(mids["px"])}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

    def set_mid(px):
        mids["px"] = px
        c._FOLLOWER_MIDS.update(px={}, ms=0)
        c._LEADER_MIDS.update(px={}, ms=0)

    def config(wallets=(A, B), **gc):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": False, "global_controls": gc, "wallets": {
            w: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 1000} for w in wallets}})

    seq = [0]

    def fill(side="BUY", price=100.0, size=1.0, wallet=A, coin="BTC", ts=None):
        seq[0] += 1
        return c.LeaderFill(f"f{seq[0]}", wallet, coin, side, price, size, ts or (c.utc_now_ms() + seq[0]), "TEST", 0, {})

    config()

    # ---- S: defaults ---------------------------------------------------------------------------------
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    check("S_FOUR_SEND_WORKERS_BY_DEFAULT", core.hot_send_workers == 4 and len(core._hot_queues) == 4, str(core.hot_send_workers))
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    check("S_ORDER_GAP_DEFAULT_250_MS", 'fnum(os.getenv("HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS"), 250)' in src)
    check("S_LOOP_MODE_SENDS_POLLED_FILLS_TO_WORKERS", "core.async_dispatch = bool(args.loop)" in src)

    # ---- K1: coin-key table read once per file change ----------------------------------------------------
    c.atomic_write_json(c.ASSET_UNIVERSE_SNAPSHOT_FILE, {"symbols": {"KPEPE": {"canonical_symbol": "kPEPE"}}})
    reads = [0]
    real_load = c.load_json

    def counting_load(path, default=None):
        if Path(path) == Path(c.ASSET_UNIVERSE_SNAPSHOT_FILE):
            reads[0] += 1
        return real_load(path, default)
    c.load_json = counting_load
    keys = [c.canonical_coin_key("kpepe") for _ in range(2000)]
    check("K1_COIN_KEY_TABLE_NOT_RE_READ_EVERY_CALL", reads[0] <= 1 and set(keys) == {"KPEPE"}, f"reads={reads[0]} {set(keys)}")
    time.sleep(0.02)
    c.atomic_write_json(c.ASSET_UNIVERSE_SNAPSHOT_FILE, {"symbols": {"KPEPE": {"canonical_symbol": "PEPE1000"}}})
    check("K1_TABLE_RE_READ_WHEN_THE_FILE_CHANGES", c.canonical_coin_key("kpepe") == "PEPE1000" and reads[0] == 2, str(reads))
    c.load_json = real_load

    # ---- K2/K3: repeat fills dropped first; polled fills go to the workers ------------------------------
    config()
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    handled = []
    lock = threading.Lock()

    def record(f, summary=None, block=""):
        with lock:
            handled.append((f.leader_fill_id, f.coin, threading.current_thread().name))
        return False, "T", None
    core._process_leader_fill = record
    seen_before = [fill("BUY") for _ in range(500)]
    for f in seen_before:
        core._idem_accepted.add(f.leader_fill_id)
    new = [fill("BUY", coin="BTC"), fill("SELL", coin="BTC"), fill("BUY", coin="ETH")]
    core.ingestor.poll_hyperliquid_fills = lambda w, s, t=None: ((seen_before + new) if w == A else [], "POLL_OK")
    summary = core.run_cycle(use_source_csv=False, poll_live=True)
    check("K2_REPEAT_FILLS_DROPPED_BEFORE_PROCESSING", summary.leader_fills_deduped == 500
          and [h[0] for h in handled] == [f.leader_fill_id for f in new], f"{summary.leader_fills_deduped} {handled}")
    handled.clear()
    core.async_dispatch = True
    new2 = [fill("BUY", coin="BTC"), fill("SELL", coin="BTC"), fill("BUY", coin="BTC"), fill("BUY", coin="ETH")]
    core.ingestor.poll_hyperliquid_fills = lambda w, s, t=None: (new2 if w == A else [], "POLL_OK")
    summary = core.run_cycle(use_source_csv=False, poll_live=True)
    deadline = time.time() + 5
    while len(handled) < 4 and time.time() < deadline:
        time.sleep(0.02)
    btc = [h for h in handled if h[1] == "BTC"]
    check("K3_LOOP_MODE_QUEUES_POLLED_FILLS_FOR_THE_WORKERS", summary.leader_fills_queued == 4 and len(handled) == 4
          and all(h[2].startswith("HLCoreWS-hot-send") for h in handled), f"{summary.leader_fills_queued} {handled}")
    check("K3_ONE_COIN_ONE_WORKER_IN_ORDER", [h[0] for h in btc] == [f.leader_fill_id for f in new2[:3]]
          and len({h[2] for h in btc}) == 1, str(btc))
    core.stop()

    # ---- K4/K5/K6: leaders read in parallel, 30 s back, every 30 s while the live feed is up ------------
    many = ["0x" + format(i, "x") * 40 for i in range(1, 9)]
    config(wallets=many)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    starts = {}

    def slow_poll(w, s, t=None):
        time.sleep(0.4)
        starts[w] = s
        return [], "POLL_OK"
    core.ingestor.poll_hyperliquid_fills = slow_poll
    now = c.utc_now_ms()
    st = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    st["last_leader_poll_cursor_ms"] = {w: now - 60000 for w in many}
    c.atomic_write_json(c.CORE_RUNTIME_STATE_FILE, st)
    t0 = time.time()
    core.run_cycle(use_source_csv=False, poll_live=True)
    took = time.time() - t0
    check("K4_EIGHT_LEADERS_READ_IN_PARALLEL", len(starts) == 8 and took < 1.6, f"{len(starts)} {took:.2f}s")
    check("K5_LEADERS_RE_READ_ONLY_30_S_BACK", all(abs(s - (now - 60000 - 30000)) < 2000 for s in starts.values()),
          str(list(starts.values())[:2]))
    starts.clear()
    core.ws.enabled, core.ws._socket_open = True, True
    core._last_leader_poll_ms = 0
    core.run_cycle(use_source_csv=False, poll_live=True)
    first = len(starts)
    starts.clear()
    core.run_cycle(use_source_csv=False, poll_live=True)
    check("K6_LIVE_FEED_UP_POLL_IS_A_30_S_BACKSTOP", first == 8 and not starts, f"{first} {len(starts)}")
    core.ws.enabled, core.ws._socket_open = False, False
    core.run_cycle(use_source_csv=False, poll_live=True)
    check("K6_LIVE_FEED_DOWN_POLL_EVERY_CYCLE", len(starts) == 8, str(len(starts)))
    core.stop()

    # ---- K7: a copy read that hits the page cap resumes after its newest fill ------------------------------
    config()
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.dedupe.copy_account_baseline_set = True
    capped = [{"coin": "BTC", "oid": 1, "side": "B", "sz": "1", "px": "1", "hash": f"x{i}", "tid": i, "time": 1000 + i,
               "timestamp_ms": 1000 + i, "copy_fill_id": f"x{i}"} for i in range(3)]
    core.copy_ingestor.poll_copy_account_fills = lambda w, s0, s1, **k: (capped, "COPY_ACCOUNT_POLL_PARTIAL")
    core.matcher.match_and_apply = lambda raw, intents: True
    core.reconciler.fetch_snapshot = lambda: ({}, "SNAPSHOT_UNAVAILABLE")
    core.run_cycle(use_source_csv=False, poll_copy=True)
    last = c.load_json(c.CORE_RUNTIME_STATE_FILE, {}).get("last_copy_poll_ms")
    check("K7_CAPPED_COPY_READ_RESUMES_AFTER_ITS_NEWEST_FILL", last == 1002 + c.POLL_OVERLAP_MS, str(last))
    core.stop()

    # ---- S1: exchange calls overlap, the pacing slot does not ---------------------------------------------
    os.environ["HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS"] = "50"
    gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter())
    began = []

    class SlowExchange:
        def order(self, *a, **k):
            began.append(time.time())
            time.sleep(0.4)
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"filled": {"totalSz": "1", "avgPx": "1", "oid": 1}}]}}}
    ths = [threading.Thread(target=gw._place_order, args=(SlowExchange(), "BTC", True, 1.0, 100.0, "Ioc", False)) for _ in range(4)]
    t0 = time.time()
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    took = time.time() - t0
    gaps = [b - a for a, b in zip(sorted(began), sorted(began)[1:])]
    check("S1_FOUR_ORDERS_IN_FLIGHT_TOGETHER", took < 1.0, f"{took:.2f}s")
    check("S1_STARTS_STILL_PACED", all(g >= 0.045 for g in gaps), str(gaps))
    os.environ["HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS"] = "0"

    # ---- harness: fake exchange through _send_real ---------------------------------------------------------
    class FakeExchange:
        def __init__(self, replies=None):
            self.calls, self.replies = [], list(replies or [])

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"px": px, "tif": tif["limit"]["tif"], "buy": is_buy, "size": size, "reduce_only": reduce_only})
            if self.replies:
                return self.replies.pop(0)
            if tif["limit"]["tif"] == "Gtc":
                return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 4242}}]}}}
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}]}}}

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def gateway(fake, ledger=None):
        g = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
        g._resolve_coin = lambda coin: dict(resolved)
        g._get_exchange_client = lambda *a, **k: fake
        g._exchange_client_has_symbol = lambda *a, **k: True
        g._validate_final_wire_order = lambda *a, **k: (True, {})
        g._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        g._exchange_client_for_coin = lambda coin: (fake, "BTC")
        return g

    def send_real(g, intent):
        os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64   # placeholder; the fake exchange never signs
        saved = c.HLAccount, c.HLExchange
        c.HLAccount, c.HLExchange = object, object
        try:
            return g._send_real(intent)
        finally:
            c.HLAccount, c.HLExchange = saved
            os.environ.pop("HL_LIVE_HL_PRIVATE_KEY", None)

    # ---- S2: stale entries ------------------------------------------------------------------------------------
    config(marketable_bps=20)
    set_mid(100.1)   # 10 bps worse than the leader: inside tolerance
    led = c.ManualLedger(path=tmp / "s2.json")
    fresh = c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY"))
    fake = FakeExchange()
    send_real(gateway(fake), fresh)
    check("S2_FRESH_ENTRY_INSIDE_TOLERANCE_TAKEN", fake.calls and fake.calls[0]["tif"] == "Ioc", str(fake.calls))
    stale = c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY", ts=c.utc_now_ms() - 45000))
    fake = FakeExchange()
    ok, status, res = send_real(gateway(fake), stale)
    check("S2_STALE_ENTRY_RESTS_AT_THE_LEADER_PRICE", fake.calls and fake.calls[0]["tif"] == "Gtc"
          and fake.calls[0]["px"] == 100.0 and status == "ORDER_RESTING", f"{status} {fake.calls}")
    check("S2_STALE_ENTRY_DIFF_SAYS_WHY", "stale cutoff" in res.get("notes", "")
          and res.get("terminal_state") == "ENTRY_LIMIT_RESTING_PRICE_MOVED", res.get("notes", "")[:200])
    set_mid(99.9)    # better than the leader: the limit at the leader's price fills at once
    fake = FakeExchange([{"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"filled": {"totalSz": "10", "avgPx": "99.9", "oid": 7}}]}}}])
    ok, status, res = send_real(gateway(fake), c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY", ts=c.utc_now_ms() - 45000)))
    check("S2_STALE_ENTRY_SAME_OR_BETTER_STILL_TAKEN", ok and status == "ORDER_FILLED" and fake.calls[0]["px"] == 100.0, f"{status} {fake.calls}")
    config(marketable_bps=20, stale_entry_sec=0)
    set_mid(100.1)
    fake = FakeExchange()
    send_real(gateway(fake), c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY", ts=c.utc_now_ms() - 45000)))
    check("S2_CUTOFF_ZERO_IS_OFF", fake.calls and fake.calls[0]["tif"] == "Ioc", str(fake.calls))
    config(stale_entry_sec=45)
    check("S2_CUTOFF_FROM_GLOBAL_CONTROLS", c.ConfigManager().stale_entry_sec() == 45.0)
    config()
    check("S2_CUTOFF_DEFAULT_30_S", c.ConfigManager().stale_entry_sec() == 30.0)
    set_mid(100.0)

    # ---- N: leaders net like the exchange ---------------------------------------------------------------------
    def snapshot(net):
        c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {"BTC": {"signed_size": net}}})

    def ledger(**sleeves):
        led = c.ManualLedger(path=tmp / f"n{seq[0]}.json")
        for w, s in sleeves.items():
            led.sleeve({"a": A, "b": B}[w], "BTC")["signed_size"] = s
        led._recompute_net(led.data)
        return led

    def exit_intent(led, wallet, side, size):
        it = c.IntentBuilder(c.ConfigManager(), led).build(fill(side, size=size, wallet=wallet))
        return it

    led = ledger(a=447.0, b=-447.0)
    snapshot(0.0)
    g = gateway(FakeExchange(), led)
    it = exit_intent(led, A, "SELL", 447.0)
    check("N1_TWO_LEADERS_OPPOSITE_CLOSE_NOT_REDUCE_ONLY", c.classify_send_lifecycle(it) in {"EXIT", "REDUCE"}
          and g._reduce_only_on_wire(it, 447.0) is False, c.classify_send_lifecycle(it))
    led = ledger(a=2.0)
    snapshot(2.0)
    g = gateway(FakeExchange(), led)
    check("N2_SINGLE_LEADER_CLOSE_STAYS_REDUCE_ONLY", g._reduce_only_on_wire(exit_intent(led, A, "SELL", 2.0), 2.0) is True)
    led = ledger(a=447.0, b=-447.0)
    snapshot(447.0)   # records and exchange disagree: never open what the records don't explain
    g = gateway(FakeExchange(), led)
    check("N3_RECORDS_DISAGREE_STAYS_REDUCE_ONLY", g._reduce_only_on_wire(exit_intent(led, A, "SELL", 447.0), 447.0) is True)
    led = ledger(a=1.0, b=-3.0)
    snapshot(-2.0)
    g = gateway(FakeExchange(), led)
    check("N4_FLIP_THROUGH_FLAT_NOT_REDUCE_ONLY", g._reduce_only_on_wire(exit_intent(led, A, "SELL", 1.0), 1.0) is False)
    led = ledger(a=2.0, b=-1.0)
    snapshot(1.0)
    g = gateway(FakeExchange(), led)
    check("N5_PARTIAL_CLOSE_INSIDE_THE_NET_REDUCE_ONLY", g._reduce_only_on_wire(exit_intent(led, A, "SELL", 1.0), 1.0) is True)
    check("N5_PARTIAL_CLOSE_PAST_THE_NET_NOT_REDUCE_ONLY", g._reduce_only_on_wire(exit_intent(led, A, "SELL", 2.0), 2.0) is False)
    led = ledger(a=1.0, b=-1.0)
    snapshot(0.0)
    g = gateway(FakeExchange(), led)
    check("N6_FLATTEN_EITHER_LEADER_FIRST", g._reduce_only_on_wire(exit_intent(led, B, "BUY", 1.0), 1.0) is False
          and g._reduce_only_on_wire(exit_intent(led, A, "SELL", 1.0), 1.0) is False)

    # the ledger's sum of leaders follows the exchange through opposite entries, partial fills, flips and flattening
    led = c.ManualLedger(path=tmp / "n7.json")
    exchange = 0.0
    steps = [(A, "BUY", 447.0), (B, "SELL", 447.0), (B, "SELL", 100.0), (A, "SELL", 200.0), (A, "SELL", 247.0),
             (B, "BUY", 300.0), (B, "BUY", 247.0), (A, "BUY", 5.0), (A, "SELL", 5.0)]
    agree = []
    for i, (w, side, sz) in enumerate(steps):
        it = c.IntentBuilder(c.ConfigManager(), led).build(fill(side, size=sz, wallet=w))
        it.copy_side, it.copy_size = side, sz
        led.apply_copy_fill(it, {"side": side, "sz": str(sz), "px": "100", "hash": f"n7_{i}"})
        exchange += sz if side == "BUY" else -sz
        agree.append(abs(led.coin_net("BTC") - exchange) < 1e-9)
    check("N7_LEDGER_SUM_EQUALS_EXCHANGE_EVERY_STEP", all(agree) and abs(led.coin_net("BTC")) < 1e-9
          and abs(led.wallet_coin_position(B, "BTC") - 0.0) < 1e-9, f"{agree} net={led.coin_net('BTC')}")
    led = ledger(a=447.0)
    it = c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=447.0, wallet=B))
    check("N8_OPPOSITE_ENTRY_NEVER_SKIPPED", c.classify_send_lifecycle(it) == "ENTRY" and it.copy_side == "SELL"
          and "BLOCK" not in str(it.decision), f"{c.classify_send_lifecycle(it)} {it.decision}")

    # a close rejected because the account moved first: once the records catch up it is resent without reduce-only
    led = ledger(a=447.0)
    snapshot(447.0)   # stale: B's opposite fill not seen yet by either view
    fake = FakeExchange([RO_REJECT])
    g = gateway(fake, led)
    it = exit_intent(led, A, "SELL", 447.0)
    it.copy_size = 447.0

    def catch_up():
        time.sleep(0.6)
        led.sleeve(B, "BTC")["signed_size"] = -447.0
        led._recompute_net(led.data)
        snapshot(0.0)
    threading.Thread(target=catch_up).start()
    os.environ["HL_LIVE_NETTING_RETRY_WAIT_SEC"] = "5"
    set_mid(100.0)
    ok, status, res = send_real(g, it)
    check("N9_REDUCE_ONLY_REJECT_RESENT_AFTER_CATCH_UP", ok and [x["reduce_only"] for x in fake.calls] == [True, False]
          and res.get("reduce_only_sent") is False and "net on one account" in res.get("notes", ""),
          f"{status} {fake.calls} {res.get('notes', '')[:120]}")
    led = ledger(a=447.0)
    snapshot(0.0)     # records never catch up: stays reduce-only, gives up after the wait, diff as usual
    fake = FakeExchange([RO_REJECT])
    g = gateway(fake, led)
    os.environ["HL_LIVE_NETTING_RETRY_WAIT_SEC"] = "0.6"
    ok, status, res = send_real(g, exit_intent(led, A, "SELL", 447.0))
    check("N9_NO_CATCH_UP_NO_BLIND_RESEND", not ok and len(fake.calls) == 1 and res.get("reject_category") == "REDUCE_ONLY_REJECTED",
          f"{status} {fake.calls}")

    # ---- N10: the screen shows each coin's net and which leader holds what --------------------------------------
    ui = (HERE / "HL_Copy_App_SSOT.py").read_text(encoding="utf-8-sig")
    check("N10_SCREEN_NET_BY_COIN_WITH_LEADERS", 'id="lcNetByCoinRows"' in ui and "function netByCoin(owned)" in ui
          and "Which leader holds what" in ui)
    check("S3_STALE_CUTOFF_ON_GLOBAL_CONTROLS", 'id="gcStaleSec"' in ui and "stale_entry_sec:g('gcStaleSec')" in ui
          and '"stale_entry_sec": 30.0' in ui)

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    os._exit(1 if failed else 0)


if __name__ == "__main__":
    main()
