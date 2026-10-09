#!/usr/bin/env python3
"""Testnet run 4 fixes (2026-10-09): the send queue keeps up, every order's fills are owned, closes go flat, resting
limits stay few and inside the caps, and switching sending off stops at once.

Q  queue: a fill already waiting is not queued again; with proportional sizing a leader's consecutive same-direction
   fills in a coin go out as ONE copy, never larger than the max order size (fixed sizing stays one copy per leader
   fill); closes of held positions go first; merged fills stay handled after a restart. Reproduces run 4's backlog
   (one busy leader order arriving as hundreds of fills, re-queued by every poll).
R  standing recovery closes are written to send_attempts with their order id, so their fills match the ledger
   (run 4: 190+ recovery orders' fills went unmatched and the ledger kept ~24 coins the exchange had closed).
P  a close that part-fills leaves the rest as a standing reduce-only close (run 4: dust left open); the sleeve's next
   close withdraws it first, so the two never both fill (the surplus would close another leader's position).
U  a close held by the pending-exit guard is not also written as BLOCKED_SEND_UNCLASSIFIED (run 4: 1,661 rows).
C  resting entry limits count toward the total, per-asset and per-wallet caps (run 4: $2,256 resting outside caps).
O  at most one resting entry limit per leader, coin and side (run 4: 3,885 missed-entry limits).
D  switching sending off on screen stops the very next order (run 4: 33 queued orders went out over ~35 s).
L  Boss's rule: within tolerance or better executes at once however late; no stale cutoff anywhere.

Run: python test_core_run4_fixes.py   # RESULT:: markers, exit 0/1. No network, no orders.
"""
from __future__ import annotations

import os
import queue
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
A = "0x" + "a" * 40
B = "0x" + "b" * 40
NO_MATCH = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
    {"error": "Order could not immediately match against any resting orders. asset=0"}]}}}


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="run4fix_"))
    os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                       "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0"})
    for k in ("HL_LIVE_HOT_SEND_WORKERS", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS", "HL_LIVE_STALE_ENTRY_SEC"):
        os.environ.pop(k, None)
    os.environ["HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS"] = "0"
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

    def config(wallets=(A, B), copy_mode="fixed", send=False, **gc):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {"auto_send_enabled": send, "global_controls": gc, "wallets": {
            w: {"enabled": True, "mode": "ON", "copy_mode": copy_mode, "fixed_notional": 12} for w in wallets}})

    seq = [0]

    def fill(side="BUY", price=100.0, size=1.0, wallet=A, coin="BTC", ts=None, oid="", d=""):
        seq[0] += 1
        raw = {**({"oid": oid} if oid else {}), **({"dir": d} if d else {})}
        return c.LeaderFill(f"f{seq[0]}", wallet, coin, side, price, size, ts or (c.utc_now_ms() + seq[0]), "TEST", 0, raw)

    class FakeExchange:
        def __init__(self, replies=None):
            self.calls, self.replies = [], list(replies or [])

        def order(self, coin, is_buy, size, px, tif, reduce_only=False):
            self.calls.append({"px": px, "tif": tif["limit"]["tif"], "buy": is_buy, "size": size, "reduce_only": reduce_only})
            if self.replies:
                return self.replies.pop(0)
            if tif["limit"]["tif"] == "Gtc":
                return {"status": "ok", "response": {"type": "order", "data": {"statuses": [{"resting": {"oid": 4242 + len(self.calls)}}]}}}
            return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
                {"filled": {"totalSz": str(size), "avgPx": str(px), "oid": 1}}]}}}

    resolved = {"ok": True, "sdk_coin": "BTC", "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": 1.0, "min_size": 0.0, "status": "OK"}

    def gateway(fake, ledger=None):
        c.atomic_write_json(c.STANDING_CLOSES_FILE, {})   # sleeve ids repeat across scenarios: start each one clean
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

    def snapshot(net, coin="BTC"):
        c.atomic_write_json(c.EXCHANGE_ACCOUNT_SNAPSHOT_FILE, {"positions_by_coin": {coin: {"signed_size": net}}})

    def ledger(name, **sleeves):
        led = c.ManualLedger(path=tmp / f"{name}.json")
        for key, s in sleeves.items():
            w, coin = key.split("_")
            led.sleeve({"a": A, "b": B}[w], coin.upper())["signed_size"] = s
        led._recompute_net(led.data)
        return led

    config()
    set_mid(100.0)

    # ---- Q: the send queue --------------------------------------------------------------------------------------
    f1, f2 = fill(oid="77", d="Open Long"), fill(oid="77", d="Open Long")
    check("Q1_FIXED_SIZING_NEVER_MERGES_ONE_COPY_PER_LEADER_FILL", not c.mergeable_fills(f1, f2, proportional=False))
    check("Q1_PROPORTIONAL_MERGES_ANY_RUN", c.mergeable_fills(fill(oid="77", d="Open Long"), fill(oid="78", d="Open Long"), True))
    check("Q1_NEVER_ACROSS_SIDE_DIRECTION_WALLET_OR_COIN",
          not c.mergeable_fills(fill(d="Open Long"), fill(side="SELL", d="Close Long"), True)
          and not c.mergeable_fills(fill(d="Close Short"), fill(d="Open Long"), True)
          and not c.mergeable_fills(fill(d="Open Long"), fill(wallet=B, d="Open Long"), True)
          and not c.mergeable_fills(fill(d="Open Long"), fill(coin="ETH", d="Open Long"), True))
    parts = [fill(price=p, size=s, oid="9", d="Open Long") for p, s in ((100.0, 1.0), (101.0, 3.0))]
    m = c.merge_leader_fills(parts)
    check("Q1_MERGE_SUMS_SIZE_WEIGHTS_PRICE_KEEPS_IDS",
          m.size == 4.0 and abs(m.price - 100.75) < 1e-9 and m.leader_fill_id == parts[0].leader_fill_id
          and m.timestamp_ms == parts[1].timestamp_ms and m.raw.get("merged_fill_ids") == [parts[1].leader_fill_id],
          f"{m.size} {m.price} {m.raw}")

    config(copy_mode="proportional")
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_queues = [queue.Queue() for _ in range(core.hot_send_workers)]   # not drained: look at what is queued
    burst = [fill(price=100.0 + i * 0.01, size=0.1, oid="555", d="Open Long", ts=c.utc_now_ms() - 600000 + i)
             for i in range(300)]
    for f in burst:          # the live feed
        core._dispatch_fill(f)
    for f in burst:          # the backstop poll re-reads the same fills while they still wait
        core._dispatch_fill(f)
    check("Q2_A_WAITING_FILL_IS_NEVER_QUEUED_TWICE", core.hot_backlog() == 300, str(core.hot_backlog()))
    waiting = []
    for q in core._hot_queues:
        while not q.empty():
            waiting.append(q.get_nowait())
    planned = core._plan_batch(waiting)
    check("Q2_RUN4_BACKLOG_300_FILLS_OF_ONE_LEADER_ORDER_ARE_ONE_COPY",
          len(planned) == 1 and abs(planned[0].size - 30.0) < 1e-9 and planned[0].raw.get("merged_fill_count") == 300,
          f"{len(planned)} {[p.size for p in planned]}")
    ok, status, intent = core._process_leader_fill(planned[0], None, "")
    check("Q2_THE_ONE_COPY_IS_ONE_INTENT_NAMING_ALL_MERGED_FILLS",
          intent is not None and "merged_leader_fills=300:" in intent.notes, str(getattr(intent, "notes", ""))[:200])
    with core._queued_lock:
        core._queued_keys.clear()
    for f in burst:          # a later poll of the same fills
        core._dispatch_fill(f)
    again = []
    for q in core._hot_queues:
        while not q.empty():
            again.append(q.get_nowait())
    check("Q2_MERGED_FILLS_ARE_HANDLED_NOT_SENT_AGAIN", core._plan_batch(again) == [], str(len(core._plan_batch(again))))
    with core._queued_lock:
        core._queued_keys.clear()
    core.stop()
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    check("Q2_MERGED_FILLS_STAY_HANDLED_AFTER_A_RESTART", all(f.leader_fill_id in core._idem_accepted for f in burst[1:]))
    core.stop()

    # a merged copy never grows past the max order size (caps block whole orders; they do not clamp)
    config(copy_mode="proportional", max_order_notional_usd=50)
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.intent_builder._copy_notional = lambda w, f: 10.0   # each leader fill copies as $10
    run = [fill(size=0.1, oid="556", d="Open Long", ts=c.utc_now_ms() - 500000 + i) for i in range(12)]
    sizes = [p.raw.get("merged_fill_count", 1) for p in core._plan_batch(run)]
    check("Q4_MERGED_RUN_SPLIT_UNDER_THE_MAX_ORDER_SIZE", sum(sizes) == 12 and max(sizes) * 10.0 <= 50 and len(sizes) == 3,
          str(sizes))
    core.stop()
    config(copy_mode="fixed")
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core._hot_queues = [queue.Queue() for _ in range(core.hot_send_workers)]
    fixed_run = [fill(oid="557", d="Open Long", ts=c.utc_now_ms() - 400000 + i) for i in range(5)]
    check("Q4_FIXED_SIZING_KEEPS_ONE_COPY_PER_LEADER_FILL", len(core._plan_batch(fixed_run)) == 5)
    boom = core._plan_batch
    core._plan_batch = lambda b: (_ for _ in ()).throw(RuntimeError("plan failed"))
    got = []
    core._process_leader_fill = lambda f, s=None, b="": got.append(f.leader_fill_id) or (False, "T", None)
    core._hot_stop_event.clear()
    import threading as _t
    q0 = core._hot_queues[0]
    for f in fixed_run:
        q0.put(f)
    th = _t.Thread(target=core._hot_send_loop, args=(0,), daemon=True)
    th.start()
    deadline = time.time() + 5
    while len(got) < 5 and time.time() < deadline:
        time.sleep(0.02)
    core._hot_stop_event.set()
    check("Q5_A_PLANNING_FAILURE_NEVER_DROPS_THE_BATCH", got == [f.leader_fill_id for f in fixed_run], str(got))
    core._plan_batch = boom
    core.stop()
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")

    core.ledger.sleeve(A, "ETH")["signed_size"] = 5.0
    core.ledger._recompute_net(core.ledger.data)
    t0 = c.utc_now_ms() - 60000
    e1 = fill(coin="BTC", oid="1", d="Open Long", ts=t0)
    e2 = fill(coin="BTC", oid="2", d="Open Long", ts=t0 + 1)
    x1 = fill(side="SELL", coin="ETH", oid="3", d="Close Long", ts=t0 + 2)
    order = [f.leader_fill_id for f in core._plan_batch([e1, e2, x1])]
    check("Q3_CLOSES_GO_FIRST_THEN_OLDEST_FIRST", order == [x1.leader_fill_id, e1.leader_fill_id, e2.leader_fill_id], str(order))
    q3 = fill(coin="BTC", oid="4", d="Open Long", ts=t0 + 3)
    core._idem_accepted.add(q3.leader_fill_id)
    check("Q3_ALREADY_HANDLED_DROPPED_BEFORE_PLANNING", core._plan_batch([q3]) == [])
    core.stop()

    # ---- R/P: recovery closes are recorded; a part-filled close leaves the rest standing -----------------------
    config(send=True, marketable_bps=20)   # sending on: a standing close is never placed while it is off
    led = ledger("r1", a_btc=2.0)
    snapshot(2.0)
    fake = FakeExchange([NO_MATCH])
    g = gateway(fake, led)
    exit_it = c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=2.0, d="Close Long"))
    ok, status, res = send_real(g, exit_it)
    gtc = [x for x in fake.calls if x["tif"] == "Gtc"]
    check("R1_UNFILLED_CLOSE_STANDS_AS_REDUCE_ONLY_LIMIT", len(gtc) == 1 and gtc[0]["reduce_only"] and gtc[0]["size"] == 2.0,
          str(fake.calls))
    rows = [r for r in c.read_csv_rows(c.SEND_ATTEMPTS_CSV) if r.get("order_type") == "REAL_GTC_RECOVERY_CLOSE"]
    check("R1_RECOVERY_ORDER_WRITTEN_TO_SEND_ATTEMPTS_WITH_ITS_ORDER_ID",
          len(rows) == 1 and rows[0]["status"] == "ORDER_RESTING" and rows[0]["exchange_order_id"] == "4244"
          and rows[0]["intent_id"] == exit_it.intent_id and rows[0]["reduce_only_sent"] == "True", str(rows)[:300])
    matcher = c.CopyFillMatcher(led, c.AuditLogWriter())
    now = c.utc_now_ms()
    owned = matcher.match_and_apply({"coin": "BTC", "side": "A", "px": "100", "sz": "2.0", "oid": 4244, "hash": "0xr1",
                                     "tid": 11, "time": now, "dir": "Close Long"}, {})
    check("R2_RUN4_RECOVERY_FILL_IS_MATCHED_AND_THE_LEDGER_GOES_FLAT",
          owned and abs(c.fnum(led.sleeve(A, "BTC").get("signed_size"))) < 1e-9, f"{owned} {led.sleeve(A, 'BTC')}")
    fake.calls.clear()
    g._queue_exit_recovery_if_needed(fake, "BTC", exit_it, 100.0, 2.0, NO_MATCH, "again")
    check("R3_ONE_STANDING_CLOSE_PER_CLOSE_EVEN_WITHOUT_RE_READING_THE_FILE", fake.calls == [], str(fake.calls))
    src = (HERE / "HL_Live_Copy_Service_Core.py").read_text(encoding="utf-8-sig")
    body = src.split("def _exit_recovery_exists", 1)[1].split("\n    def ", 1)[0]
    check("R3_RECOVERY_CHECK_KEPT_IN_MEMORY", "_recovery_intent_ids" in body and body.count("read_csv_rows") == 1)

    led = ledger("p1", a_btc=2.0)
    snapshot(2.0)
    part = {"status": "ok", "response": {"type": "order", "data": {"statuses": [
        {"filled": {"totalSz": "0.5", "avgPx": "100", "oid": 31}}]}}}
    fake = FakeExchange([part])
    g = gateway(fake, led)
    exit_it = c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=2.0, d="Close Long"))
    ok, status, res = send_real(g, exit_it)
    check("P1_PART_FILLED_CLOSE_LEAVES_THE_REST_AS_A_REDUCE_ONLY_CLOSE",
          ok and len(fake.calls) == 2 and fake.calls[1]["tif"] == "Gtc" and fake.calls[1]["reduce_only"]
          and abs(fake.calls[1]["size"] - 1.5) < 1e-9 and not fake.calls[1]["buy"], str(fake.calls))
    fake = FakeExchange()
    led = ledger("p2", a_btc=2.0)
    g = gateway(fake, led)
    ok, status, res = send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=2.0, d="Close Long")))
    check("P2_FULLY_FILLED_CLOSE_PLACES_NOTHING_MORE", ok and len(fake.calls) == 1, str(fake.calls))

    class CancelExchange(FakeExchange):
        def __init__(self, replies=None, cancel_reply=None):
            super().__init__(replies)
            self.cancels, self.cancel_reply = [], cancel_reply

        def cancel(self, coin, oid):
            self.cancels.append(oid)
            if isinstance(self.cancel_reply, Exception):
                raise self.cancel_reply
            return self.cancel_reply

    ok_cancel = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": ["success"]}}}
    gone_cancel = {"status": "ok", "response": {"type": "cancel", "data": {"statuses": [
        {"error": "Order was never placed, already canceled, or filled."}]}}}
    led = ledger("p3", a_btc=2.0)
    snapshot(2.0)
    fake = CancelExchange([part], ok_cancel)
    g = gateway(fake, led)
    first = c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=2.0, d="Close Long"))
    send_real(g, first)
    standing = c.load_json(c.STANDING_CLOSES_FILE, {})
    check("P3_STANDING_CLOSE_REMEMBERED_BY_SLEEVE", first.sleeve_id in standing and standing[first.sleeve_id]["size"] == 1.5,
          str(standing))
    led.sleeve(A, "BTC")["signed_size"] = 1.5   # the copy poll owned the 0.5 part fill
    led._recompute_net(led.data)
    snapshot(1.5)
    fake.calls.clear()
    nxt = c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=1.5, d="Close Long"))
    ok, status, res = send_real(g, nxt)
    check("P3_NEXT_CLOSE_WITHDRAWS_THE_STANDING_ONE_FIRST",
          fake.cancels == [int(standing[first.sleeve_id]["oid"])] and fake.calls and fake.calls[0]["tif"] == "Ioc"
          and abs(fake.calls[0]["size"] - 1.5) < 1e-9 and not c.load_json(c.STANDING_CLOSES_FILE, {}), f"{fake.cancels} {fake.calls}")
    # the standing close filled before the next close: the ledger (brought up to date) decides what is left
    led = ledger("p4", a_btc=2.0)
    snapshot(2.0)
    fake = CancelExchange([part], gone_cancel)
    g = gateway(fake, led)
    send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=2.0, d="Close Long")))
    nxt = c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=2.0, d="Close Long"))

    def owned_both():
        led.sleeve(A, "BTC")["signed_size"] = 0.0
        led._recompute_net(led.data)
    g.truth_refresh = owned_both
    fake.calls.clear()
    ok, status, res = send_real(g, nxt)
    check("P4_STANDING_CLOSE_ALREADY_FILLED_NOTHING_MORE_SENT", not fake.calls
          and status == "SEND_NOT_ATTEMPTED_STANDING_CLOSE_FILLED", f"{status} {fake.calls}")
    led = ledger("p5", a_btc=2.0)
    snapshot(2.0)
    fake = CancelExchange([part], RuntimeError("timeout"))
    g = gateway(fake, led)
    send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=2.0, d="Close Long")))
    fake.calls.clear()
    ok, status, res = send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=2.0, d="Close Long")))
    check("P5_CANCEL_FAILED_STANDING_CLOSE_KEEPS_WORKING_NO_SECOND_CLOSE",
          not fake.calls and status == "SEND_NOT_ATTEMPTED_STANDING_CLOSE_IN_PLACE"
          and res.get("terminal_state") == "PENDING_EXIT_GUARD_ACTIVE", f"{status} {fake.calls}")
    c.OPEN_ORDERS_FETCHER = lambda payload: []
    for row in g._standing_closes.values():
        row["placed_ms"] = 1
    check("P6_FILLED_STANDING_CLOSES_FORGOTTEN_EACH_CYCLE", g.prune_standing_closes() == 0 and not g._standing_closes)
    c.atomic_write_json(c.STANDING_CLOSES_FILE, {})
    led = ledger("p7", a_btc=2.0)
    fake = FakeExchange([NO_MATCH])
    g = gateway(fake, led)
    time.sleep(0.02)
    config(send=False, marketable_bps=20)   # switched off while the close was being sent
    send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", size=2.0, d="Close Long")))
    check("P7_NO_STANDING_CLOSE_PLACED_AFTER_SENDING_IS_SWITCHED_OFF", [x["tif"] for x in fake.calls] == ["Ioc"], str(fake.calls))

    # ---- U: pending-exit guard is not "unclassified" ------------------------------------------------------------
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    core.ledger.sleeve(A, "BTC")["signed_size"] = 2.0
    core.ledger._recompute_net(core.ledger.data)
    f_u = fill("SELL", size=2.0, d="Close Long")
    it_u = core.intent_builder.build(f_u)
    before = len(c.read_csv_rows(c.RECONCILIATION_CSV))
    core._append_send_terminal(f_u, it_u, "PENDING_EXIT_GUARD_ACTIVE")
    new = c.read_csv_rows(c.RECONCILIATION_CSV)[before:]
    check("U1_PENDING_EXIT_GUARD_NOT_WRITTEN_AS_UNCLASSIFIED", it_u.send_allowed
          and not [r for r in new if r.get("terminal_state") == "BLOCKED_SEND_UNCLASSIFIED"], str(new)[:300])
    core.stop()

    # ---- C: resting limits count toward the caps ---------------------------------------------------------------
    config(max_total_live_exposure_usd=1200, max_asset_directional_exposure_usd=300, max_wallet_exposure_usd=300)
    led = ledger("c1")
    b = c.IntentBuilder(c.ConfigManager(), led)
    b._exposure, b._exposure_ms = {"ok": True, "total_usd": 1000.0, "by_coin": {"BTC": {"net": 1.0, "value": 100.0}}}, c.utc_now_ms() + 600000
    resting = {"total_usd": 0.0, "buy_units": {}, "sell_units": {}, "by_wallet_usd": {}}
    b.resting_exposure = lambda: resting
    check("C1_UNDER_THE_TOTAL_CAP_WITHOUT_RESTING_LIMITS", b._exposure_cap_block(fill(), 12.0, 100.0) == "")
    b._exposure_pending = []
    resting.update(total_usd=190.0)
    check("C1_RESTING_LIMITS_COUNT_TOWARD_THE_TOTAL_CAP", "max total exposure" in b._exposure_cap_block(fill(), 12.0, 100.0))
    resting.update(total_usd=0.0, buy_units={"BTC": 1.9})
    b._exposure_pending = []
    check("C2_RESTING_BUYS_COUNT_TOWARD_THE_PER_ASSET_CAP",
          b._exposure_cap_block(fill(), 12.0, 100.0) == "max asset directional exposure exceeded")
    resting.update(buy_units={}, sell_units={"BTC": 4.5})
    b._exposure_pending = []
    check("C2_RESTING_SELLS_COUNT_ON_THE_SHORT_SIDE",
          b._exposure_cap_block(fill("SELL"), 12.0, 100.0) == "max asset directional exposure exceeded")
    resting.update(sell_units={"BTC": 0.5})
    b._exposure_pending = []
    check("C2_SMALL_RESTING_STILL_ALLOWED", b._exposure_cap_block(fill(), 12.0, 100.0) == "")
    resting.update(sell_units={}, by_wallet_usd={A: 295.0})
    b._exposure = {"ok": True, "total_usd": 0.0, "by_coin": {}}
    d, why = b._decision(A, fill(), "ENTRY", 12.0, 0.0)
    check("C3_RESTING_LIMITS_COUNT_TOWARD_THE_WALLET_CAP", d == "SEND_BLOCKED_RISK" and why == "max wallet exposure exceeded", f"{d} {why}")
    b.resting_exposure = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    b._exposure_pending = []
    check("C4_UNREADABLE_RESTING_LIST_FAILS_CLOSED", "unreadable" in b._exposure_cap_block(fill(), 12.0, 100.0))
    d, why = b._decision(A, fill(), "ENTRY", 12.0, 0.0)
    check("C4_UNREADABLE_RESTING_LIST_BLOCKS_THE_WALLET_CAP_TOO", d == "SEND_BLOCKED_RISK" and "unreadable" in why, f"{d} {why}")

    g = gateway(FakeExchange())
    g._resting_entries = {
        "1": {"oid": "1", "leader_wallet": A, "coin": "BTC", "side": "BUY", "limit_px": 100.0, "size": 2.0, "placed_ms": 1},
        "2": {"oid": "2", "leader_wallet": B, "coin": "ETH", "side": "SELL", "limit_px": 50.0, "size": 1.0, "placed_ms": 1},
        "3": {"oid": "3", "leader_wallet": A, "coin": "BTC", "side": "BUY", "limit_px": 100.0, "size": 1.0, "placed_ms": 1}}
    c.OPEN_ORDERS_FETCHER = lambda p: [{"oid": 1, "coin": "BTC", "side": "B", "sz": "0.5", "limitPx": "100"},
                                      {"oid": 2, "coin": "ETH", "side": "A", "sz": "1.0", "limitPx": "50"}]
    still = g.refresh_resting_open_sizes()
    exp = g.resting_entry_exposure()
    check("C5_OPEN_SIZE_READ_FROM_THE_EXCHANGE_FILLED_ONES_DROP_OUT",
          still == 2 and abs(exp["total_usd"] - 100.0) < 1e-9 and exp["buy_units"] == {"BTC": 0.5}
          and exp["sell_units"] == {"ETH": 1.0} and exp["by_wallet_usd"] == {A: 50.0, B: 50.0}, f"{still} {exp}")
    c.OPEN_ORDERS_FETCHER = lambda p: (_ for _ in ()).throw(RuntimeError("unreadable"))
    g._resting_entries["4"] = {"oid": "4", "leader_wallet": A, "coin": "ETH", "side": "BUY", "limit_px": 10.0, "size": 3.0, "placed_ms": 1}
    g.refresh_resting_open_sizes()
    check("C5_UNREADABLE_OPEN_ORDERS_KEEPS_THE_FULL_SIZE", abs(g.resting_entry_exposure()["total_usd"] - 130.0) < 1e-9,
          str(g.resting_entry_exposure()))
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    check("C6_THE_ENGINE_WIRES_RESTING_LIMITS_INTO_THE_CAPS",
          core.intent_builder.resting_exposure == core.sender.resting_entry_exposure)
    core.stop()

    # ---- O: one resting entry limit per leader, coin and side ---------------------------------------------------
    config(marketable_bps=20)
    saved_leader = c.LEADER_NETWORK
    c.LEADER_NETWORK = c.FOLLOWER_NETWORK
    try:
        set_mid(101.0)   # 1 % worse than the leader: beyond tolerance, rests at the leader's price
        c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, {})
        led = ledger("o1")
        fake = FakeExchange()
        g = gateway(fake, led)
        ok, status, _ = send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY")))
        check("O1_FIRST_ENTRY_BEYOND_TOLERANCE_RESTS", status == "ORDER_RESTING" and len(fake.calls) == 1, f"{status} {fake.calls}")
        ok, status, res = send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY")))
        check("O1_SECOND_ONE_WHILE_THE_FIRST_RESTS_IS_NOT_SENT",
              not ok and status == "SEND_NOT_ATTEMPTED_MISSED_ENTRY_ALREADY_RESTING" and len(fake.calls) == 1
              and res.get("terminal_state") == "MISSED_ENTRY_ALREADY_RESTING" and res.get("exchange_called") is False,
              f"{status} {fake.calls}")
        check("O1_IT_IS_A_CLASSIFIED_NO_SEND_NOT_A_RED",
              res.get("reject_category") == "RISK_OR_BUDGET_BLOCK" and res.get("write_send_attempt") is True)
        ok, status, _ = send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY", wallet=B)))
        ok2, status2, _ = send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("SELL", price=102.0)))
        check("O2_OTHER_LEADER_OR_OTHER_SIDE_STILL_RESTS", status == "ORDER_RESTING" and status2 == "ORDER_RESTING",
              f"{status} {status2}")
        for row in g._resting_entries.values():
            row["open_size"] = 0.0   # all filled
        ok, status, _ = send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY")))
        check("O3_ONCE_FILLED_A_NEW_ONE_MAY_REST", status == "ORDER_RESTING", status)
        set_mid(100.1)
        n = len(fake.calls)
        ok, status, _ = send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY")))
        check("O4_WITHIN_TOLERANCE_STILL_TAKEN_AT_ONCE_WHILE_ONE_RESTS",
              ok and len(fake.calls) == n + 1 and fake.calls[-1]["tif"] == "Ioc", f"{status} {fake.calls[n:]}")
        fake2 = FakeExchange([NO_MATCH, NO_MATCH])
        g._get_exchange_client = lambda *a, **k: fake2
        ok, status, _ = send_real(g, c.IntentBuilder(c.ConfigManager(), led).build(fill("BUY")))
        check("O5_NO_MATCH_WHILE_ONE_RESTS_ADDS_NO_SECOND_LIMIT", "Gtc" not in [x["tif"] for x in fake2.calls], str(fake2.calls))
    finally:
        c.LEADER_NETWORK = saved_leader
        set_mid(100.0)

    # ---- D: switching sending off stops the next order at once ------------------------------------------------
    config(send=True)
    cfg = c.ConfigManager()
    check("D1_ARMED_SWITCH_READS_ON", cfg.master_switch_now())
    time.sleep(0.02)
    config(send=False)
    check("D1_OFF_ON_DISK_IS_SEEN_BEFORE_THE_NEXT_CYCLE", cfg.master_real_orders_enabled and not cfg.master_switch_now())
    g = gateway(FakeExchange(), ledger("d1"))
    g.cfg = cfg
    led = ledger("d2")
    it = c.IntentBuilder(cfg, led).build(fill())
    it.decision = "ENTRY_ALLOWED"
    ok, status = g.send_if_allowed(it)
    check("D2_QUEUED_ORDER_AFTER_SWITCH_OFF_IS_NOT_SENT", not ok and status == "MASTER_REAL_ORDERS_OFF", status)
    time.sleep(0.02)
    config(send=True)
    check("D3_RE_ARMING_ON_DISK_WORKS_AGAIN", cfg.master_switch_now())
    check("D4_SWITCH_ALSO_CHECKED_AFTER_THE_GATE_WAIT",
          src.split("def send_if_allowed", 1)[1].split("\n    def ", 1)[0].count("master_switch_now()") == 2)

    # ---- L: no stale cutoff ------------------------------------------------------------------------------------
    ui = (HERE / "HL_Copy_App_SSOT.py").read_text(encoding="utf-8-sig")
    check("L1_NO_STALE_CUTOFF_IN_ENGINE_OR_SCREEN", "stale_entry_sec" not in src and "stale_entry_sec" not in ui
          and "gcStaleSec" not in ui)

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
