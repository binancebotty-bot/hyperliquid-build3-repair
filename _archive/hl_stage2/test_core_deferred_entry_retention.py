#!/usr/bin/env python3
"""Deferred-entry retention: one mechanism for every transient entry refusal.

The defect class: a fill is accepted into leader-fill dedupe, the entry is then refused on a condition that
clears by itself (UNIVERSE_STALE, MARKET_HALTED, MARGIN_MODE_UNSET), and nothing ever replays it. Retention
keeps the ENTRY/ADD, persisted by leader_fill_id, re-offers it once per trigger, drops it when the leader
reduces, and ages it out into a named diff after 25 minutes. SYMBOL_UNRESOLVED is a NAMED SKIP, not a retry.
Reductions, closes and exits are never retained and never wait on a retained entry (invariant C).

Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_deferred_entry_retention.py   # no network, no orders
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
tmp = Path(tempfile.mkdtemp(prefix="deferred_entry_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
                   "HL_LIVE_SCOPE_SWEEP_THREAD": "0", "HL_LIVE_LIQ_PARITY": "0"})
import HL_Live_Copy_Service_Core as c

R = []


def check(n, ok, d=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))


LEADER = "0x" + "d" * 40
_seq = [0]


def fill(coin="BTC", side="BUY", price=100.0, size=1.0, dr="Open Long", wallet=LEADER, fid=None, ts=None):
    _seq[0] += 1
    return c.LeaderFill(fid or f"df{_seq[0]}", wallet, coin, side, price, size, ts or (c.utc_now_ms() + _seq[0]),
                        "TEST", 0, {"dir": dr})


def rows(name=None):
    """Rows by EVENT or by STATUS: retention writes a shared event with a named status."""
    return [r for r in c.read_csv_rows(c.RECONCILIATION_CSV)
            if name is None or name in (r.get("event"), r.get("status"))]


def main() -> None:
    # ---- 1. persistence: durable, in the state dir, by leader_fill_id -------------------------------
    store = c.DeferredEntryRetention()
    check("RETENTION_FILE_LIVES_IN_STATE_DIR", store.path == c.AUDIT_DIR / "deferred_entry_retention.json", store.path)
    f1 = fill(fid="persist-1")
    check("RETAIN_ENTRY_TRUE", store.retain(f1, "UNIVERSE_STALE") is True)
    check("RETAINED_ITEM_ON_DISK", (c.AUDIT_DIR / "deferred_entry_retention.json").exists())
    reloaded = c.DeferredEntryRetention()
    item = reloaded.snapshot().get("persist-1")
    check("RESTART_RELOADS_ITEM", bool(item) and item["reason"] == "UNIVERSE_STALE" and item["coin"] == "BTC", item)
    first_ms = int(item["first_ms"]) if item else 0
    check("RETAIN_IDEMPOTENT_BY_FILL_ID", reloaded.retain(f1, "MARKET_HALTED") is True
          and len(reloaded.snapshot()) == 1
          and int(reloaded.snapshot()["persist-1"]["first_ms"]) == first_ms
          and reloaded.snapshot()["persist-1"]["reason"] == "MARKET_HALTED")
    check("REASONS_ARE_THE_THREE", c.DEFERRED_ENTRY_REASONS == ("UNIVERSE_STALE", "MARKET_HALTED", "MARGIN_MODE_UNSET"))
    check("SYMBOL_UNRESOLVED_NOT_A_RETENTION_REASON", reloaded.retain(fill(fid="sym-1"), "SYMBOL_UNRESOLVED") is False)
    check("SYMBOL_UNRESOLVED_STATUS_IS_NOT_RETRYABLE",
          c.deferred_entry_reason_for("SEND_NOT_ATTEMPTED_SYMBOL_UNRESOLVED", None) == "")

    # ---- ENTRY/ADD only: reduces, closes and exits can never enter retention -----------------------
    check("CLOSE_FILL_NOT_RETAINED", reloaded.retain(fill(dr="Close Long", side="SELL", fid="close-1"), "MARKET_HALTED") is False)
    check("OPEN_SHORT_IS_RETAINABLE", reloaded.retain(fill(dr="Open Short", side="SELL", fid="short-1"), "MARGIN_MODE_UNSET") is True)
    check("INCREASE_IS_RETAINABLE", c.fill_opens_exposure(fill(dr="Increase Long")) is True)
    check("CLOSE_FILL_OPENS_NO_EXPOSURE", c.fill_opens_exposure(fill(dr="Close Long", side="SELL")) is False)

    # ---- 2. take / rest / diff decision (the existing missed-entry rule, reused) -------------------
    take = c.missed_entry_decision("BUY", 100.0, 100.10, 100.10, 50.0)
    rest = c.missed_entry_decision("BUY", 100.0, 101.0, 101.0, 50.0)
    check("DECISION_TAKE_WITHIN_TOLERANCE", take["ok"] and take["take"] is True and take["adverse_bps"] < 50.0, take)
    check("DECISION_REST_BEYOND_TOLERANCE", rest["ok"] and rest["take"] is False and rest["desired_px"] == 100.0, rest)

    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    try:
        # ---- 3. leader reduce for that wallet+coin drops the item, with an audit row -----------------
        before = len(rows("DEFERRED_ENTRY_DROPPED_LEADER_REDUCED"))
        core.retention.retain(fill(fid="drop-1", coin="ETH"), "MARKET_HALTED")
        core.retention.retain(fill(fid="drop-2", coin="ETH"), "UNIVERSE_STALE")
        core.retention.retain(fill(fid="keep-1", coin="SOL"), "MARKET_HALTED")
        core._drop_retained_for_leader_reduce(fill(fid="reduce-1", coin="ETH", side="SELL", dr="Close Long"))
        snap = core.retention.snapshot()
        check("LEADER_REDUCE_DROPS_WALLET_COIN_ITEMS", "drop-1" not in snap and "drop-2" not in snap, sorted(snap))
        check("LEADER_REDUCE_LEAVES_OTHER_COINS", "keep-1" in snap)
        check("LEADER_REDUCE_DROP_ROW_WRITTEN", len(rows("DEFERRED_ENTRY_DROPPED_LEADER_REDUCED")) - before == 2,
              len(rows("DEFERRED_ENTRY_DROPPED_LEADER_REDUCED")) - before)

        # ---- 4. bounds: ages out into a NAMED diff row, never silently -----------------------------
        old = fill(fid="aged-1", coin="ADA")
        core.retention.retain(old, "UNIVERSE_STALE")
        with core.retention._lock:
            core.retention.items["aged-1"]["first_ms"] = c.utc_now_ms() - c.DEFERRED_ENTRY_MAX_AGE_MS - 1000
        core.retention._save()
        before = len(rows("DEFERRED_ENTRY_AGED_OUT_DIFF"))
        core._retention_tick()
        check("AGE_OUT_AFTER_25_MIN", "aged-1" not in core.retention.snapshot())
        check("AGE_OUT_IS_A_NAMED_DIFF_ROW", len(rows("DEFERRED_ENTRY_AGED_OUT_DIFF")) - before == 1)
        check("AGE_OUT_WINDOW_IS_25_MIN", c.DEFERRED_ENTRY_MAX_AGE_MS == 25 * 60 * 1000)

        # ---- 2b. one attempt per trigger, idempotent by leader_fill_id ------------------------------
        core.sender._market_halted_until_ms["doge"] = c.utc_now_ms() - 1  # cooldown already expired
        held = fill(fid="trig-1", coin="DOGE")
        core.retention.retain(held, "MARKET_HALTED")
        trig = core._retention_trigger(core.retention.snapshot()["trig-1"], c.utc_now_ms())
        check("HALT_TRIGGER_FIRES_ONCE_COOLDOWN_EXPIRED", trig.startswith("halt:"), trig)
        with core.retention._lock:
            core.retention.items["trig-1"]["triggers_done"] = [trig]
        core.retention._save()
        again = core._retention_trigger(core.retention.snapshot()["trig-1"], c.utc_now_ms())
        check("HALT_TRIGGER_NOT_REPEATED", again == "", again)
        with core.retention._lock:
            core.retention.items["trig-1"]["triggers_done"] = []
            core.retention.items["trig-1"]["reason"] = "UNIVERSE_STALE"
        core.retention._save()
        check("NO_TRIGGER_BEFORE_A_PUBLISH",
              core._retention_trigger(core.retention.snapshot()["trig-1"], c.utc_now_ms()) == "")
        # the trigger IS the publication: nothing to replay against until a read publishes the dex
        c._publish_authoritative_universe("", {"BTC": {"symbol_source": "core_meta"}}, "core_meta")
        core.retention.retain(fill(fid="trig-2", coin="BTC"), "UNIVERSE_STALE")
        check("UNIVERSE_PUBLISH_IS_A_TRIGGER",
              core._retention_trigger(core.retention.snapshot()["trig-2"], c.utc_now_ms()).startswith("universe:"))

        # ---- replay releases the dedupe entry exactly once -----------------------------------------
        victim = fill(fid="replay-1", coin="XRP")
        core.retention.retain(victim, "MARKET_HALTED")
        core.dedupe.processed.add("replay-1")
        core._retention_replay("replay-1", core.retention.snapshot()["replay-1"], "halt:xrp")
        check("REPLAY_ATTEMPT_RECORDED",
              core.retention.snapshot().get("replay-1", {}).get("attempts") == 1
              and core.retention.snapshot()["replay-1"]["triggers_done"] == ["halt:xrp"])
        core._retention_replay("replay-1", core.retention.snapshot()["replay-1"], "halt:xrp")
        check("REPLAY_IS_IDEMPOTENT_BY_TRIGGER", core.retention.snapshot()["replay-1"]["triggers_done"] == ["halt:xrp"])
        check("REPLAY_LEAVES_A_ROW", len(rows("DEFERRED_ENTRY_REPLAY_ATTEMPT")) >= 1)

        # ---- 8. a reduction is never blocked or delayed by a retained entry ------------------------
        core.retention = c.DeferredEntryRetention()
        for i in range(50):
            core.retention.retain(fill(fid=f"bulk-{i}", coin="AVAX"), "UNIVERSE_STALE")
        started = time.monotonic()
        core.sender._market_halted_until_ms["avax"] = c.utc_now_ms() + 600000  # a halt cooldown that blocks entries
        check("HALT_NEVER_BLOCKS_A_REDUCE",
              core.sender.known_dispatch_reject(fill(side="SELL", dr="Close Long", coin="AVAX")) == "")
        ok = core._dispatch_fill(fill(side="SELL", dr="Close Long", coin="AVAX", fid="reduce-fast"))
        check("REDUCE_DISPATCHED_WHILE_50_ENTRIES_RETAINED", ok is True, ok)
        elapsed = time.monotonic() - started
        check("REDUCE_NOT_DELAYED_BY_RETENTION", elapsed < 5.0, "%.3fs" % elapsed)

        # ---- 6. ONE live worker per dex ------------------------------------------------------------
        gate = threading.Event()
        busy = threading.Thread(target=lambda: gate.wait(2.0), daemon=True, name="fake-univrefresh")
        busy.start()
        c._UNIVERSE_REFRESH_THREADS["capdex"] = busy
        check("SECOND_WORKER_REFUSED_WHILE_ONE_IS_ALIVE", c.refresh_authoritative_universe("capdex") is False)
        gate.set()
        busy.join(3.0)

        # ---- 5. a stale (older) response cannot overwrite a newer universe ------------------------
        class _Resp:
            status_code = 200

            def __init__(self, name):
                self.name = name

            def json(self):
                return {"universe": [{"name": self.name}]}

        real_post = c.requests.post
        real_timeout = c._universe_refresh_timeout
        c.requests.post = lambda *a, **k: _Resp("NEWCOIN")
        try:
            c._AUTHORITATIVE_UNIVERSE.pop("", None)
            c._UNIVERSE_REFRESH[""] = {"until": 0, "seq": 7}   # a NEWER refresh owns the dex
            c._universe_refresh_worker("", 6)                        # the older one finishes late
            check("STALE_RESPONSE_DOES_NOT_PUBLISH", "" not in c._AUTHORITATIVE_UNIVERSE)
            c._UNIVERSE_REFRESH[""] = {"until": 0, "seq": 7}
            c._universe_refresh_worker("", 7)                        # the current one publishes
            check("CURRENT_RESPONSE_PUBLISHES", "" in c._AUTHORITATIVE_UNIVERSE
                  and "NEWCOIN" in c._AUTHORITATIVE_UNIVERSE[""]["symbols"])
            # ---- 6b. hard wall-clock deadline: a read past its bound is no proof of anything ------
            c._AUTHORITATIVE_UNIVERSE.pop("", None)
            c._UNIVERSE_REFRESH[""] = {"until": 0, "seq": 1}
            c._universe_refresh_timeout = lambda: 0.05
            c.requests.post = lambda *a, **k: (time.sleep(0.2), _Resp("LATECOIN"))[1]
            c._universe_refresh_worker("", 1)
            check("WORKER_DROPS_A_READ_PAST_ITS_DEADLINE", "" not in c._AUTHORITATIVE_UNIVERSE)
        finally:
            c.requests.post = real_post
            c._universe_refresh_timeout = real_timeout

        # ---- 7. per-window blocked / retained counters in the status output -----------------------
        status = c.build_live_integrity_status()
        counters = (status.get("counts") or {}).get("deferred_entry_retention") or {}
        check("STATUS_HAS_RETENTION_COUNTERS",
              {"retained_total", "blocked_fills_window", "retained_fills_window"} <= set(counters), counters)
        check("STATUS_COUNTERS_ARE_NUMBERS",
              isinstance(counters.get("blocked_fills_window"), int)
              and isinstance(counters.get("retained_fills_window"), int))
        check("STATUS_NAMES_THE_SYMBOL_POLICY", counters.get("symbol_unresolved_policy") == "NAMED_SKIP_NO_RETRY")
        caveat = str(counters.get("not_copyable_caveat") or "")
        check("STATUS_CAVEAT_IS_THE_OBSERVED_SNAPSHOT_WORDING",
              "not listed in the observed TESTNET main-dex snapshot; alternate DEXes unchecked" in caveat, caveat)
        check("STATUS_CAVEAT_DISTINGUISHES_MAINNET",
              "present in the MAINNET universe" in caveat and "genuinely not copyable" not in caveat, caveat)

        # ---- 1b. a restart neither loses nor double-sends ----------------------------------------
        core.retention.retain(fill(fid="restart-1", coin="LTC"), "MARKET_HALTED")
        core.retention.mark_attempting("restart-1", c.generate_cloid("restart-1-intent"), "restart-1-intent")  # dies mid-send
        restarted = c.DeferredEntryRetention()   # what the next process loads
        item = restarted.snapshot().get("restart-1")
        check("RESTART_KEEPS_THE_ITEM_AND_ITS_CLOID", bool(item) and item["state"] == "ATTEMPTING" and item["cloid"], item)
        check("RESTART_CLEARS_USED_TRIGGERS", bool(item) and item["triggers_done"] == [], item)
        core.sender._market_halted_until_ms["ltc"] = c.utc_now_ms() - 1
        check("RESTART_TRIGGER_IS_OFFERED_ONCE_AGAIN", core._retention_trigger(item, c.utc_now_ms()) == "halt:ltc")
    finally:
        core.stop()

    print("TOTAL=%d FAILED=%d" % (len(R), R.count(False)))
    sys.exit(1 if False in R else 0)


if __name__ == "__main__":
    main()
