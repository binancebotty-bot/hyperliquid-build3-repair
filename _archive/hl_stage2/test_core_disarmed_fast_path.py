#!/usr/bin/env python3
"""Offline checks for the globally OFF leader-fill fast path and restart-safe cancel queue."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
LEADER = "0x" + "d" * 40
FOLLOWER = "0x" + "c" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="disarmed_fast_path_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp), "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"), "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
        "HL_LIVE_MOCK_SEND": "1", "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
    })
    os.environ.pop("HL_LIVE_DISARMED_PATH_DIAGNOSTICS", None)
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*_a, **_k):
        raise AssertionError("disarmed-path test attempted network I/O")

    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.MIDS_FETCHER = lambda p: [] if p.get("type") == "perpDexs" else {"BTC": "100"}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER

    def config(mode: str) -> None:
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            "auto_send_enabled": mode != "OFF",
            "global_controls": {"send_mode": mode},
            "wallets": {LEADER: {"enabled": True, "mode": "LIVE", "copy_mode": "fixed", "fixed_notional": 12}},
        })

    def fill(fid: str, side: str = "BUY", raw: dict | None = None) -> "c.LeaderFill":
        return c.LeaderFill(fid, LEADER, "BTC", side, 100.0, 0.1, c.utc_now_ms(), "TEST", 0, raw or {})

    config("OFF")
    core = c.LiveCopyCore(source_csv=tmp / "none.csv")
    original_build = core.intent_builder.build
    c._FOLLOWER_MIDS.update(px={"BTC": 101.0}, ms=c.utc_now_ms(), scope=[""])
    c._LEADER_MIDS.update(px={"BTC": 99.0}, ms=c.utc_now_ms(), dexes=[""])
    calls = {"build": 0, "prewarm": 0, "cancel_old": 0, "fill_read": 0, "send": 0}

    def unexpected(name):
        def fail(*_a, **_k):
            calls[name] += 1
            raise AssertionError(f"OFF path reached {name}")
        return fail

    core.intent_builder.build = unexpected("build")
    core._prewarm_with_parity = unexpected("prewarm")
    core.sender.cancel_resting_entries_against = unexpected("cancel_old")
    core._read_fills_of_withdrawn_limits = unexpected("fill_read")
    core.sender.send_if_allowed = unexpected("send")
    summary = c.CycleSummary()
    for i in range(5):
        result = core._process_leader_fill(fill(f"off-{i}"), summary, "")
        check(f"OFF_FILL_{i}_TERMINAL", result[1] == "MASTER_REAL_ORDERS_OFF" and result[2] is None, str(result[:2]))
    rows = c.read_csv_rows(c.RECONCILIATION_CSV)
    off_rows = [r for r in rows if r.get("leader_fill_id", "").startswith("off-")]
    check("ONE_RECONCILIATION_ROW_PER_SKIPPED_FILL", len(off_rows) == 5
          and {r.get("terminal_state") for r in off_rows} == {"SEND_NOT_ATTEMPTED_AUTO_SEND_DISABLED"}, str(off_rows))
    check("DIAGNOSTICS_DEFAULT_OFF", all(not r.get("fill_age_ms") and not r.get("cycle_backlog_high_water") for r in off_rows))
    check("OFF_PATH_SKIPS_BUILD_PREWARM_CANCEL_READ_AND_SEND", not any(calls.values()), str(calls))
    check("OFF_PATH_RECORDS_LEADER_SIDE_SEEN", core.sender._leader_side_seen_ms.get(
        (c.normalise_wallet(LEADER), "BTC", "BUY"), 0) > 0)
    check("OFF_PATH_INVALIDATES_NETWORK_MID_CACHES", not c._FOLLOWER_MIDS["px"] and not c._FOLLOWER_MIDS["ms"]
          and not c._LEADER_MIDS["px"] and not c._LEADER_MIDS["ms"])
    check("OFF_PATH_DOES_NOT_CHANGE_LEDGER", abs(core.ledger.wallet_coin_position(LEADER, "BTC")) < 1e-9)

    # A confirmed leader close still cancels a matching resting entry while OFF; its fill lookup is deferred.
    close_ts = c.utc_now_ms()
    core.sender._resting_entries["rest-close"] = {
        "oid": "rest-close", "leader_wallet": c.normalise_wallet(LEADER), "coin": "BTC", "side": "BUY",
        "size": 1.0, "leader_fill_ms": close_ts - 1, "placed_ms": close_ts - 1,
    }
    c.atomic_write_json(c.RESTING_ENTRY_ORDERS_FILE, core.sender._resting_entries)
    withdrawn = []

    def withdraw(rows, why, leader_fill_id, cancelled="RESTING_ENTRY_CANCELLED_LEADER_REDUCED", **_kwargs):
        withdrawn.extend(r["oid"] for r in rows)
        for row in rows:
            core.sender._resting_entries.pop(str(row["oid"]), None)
        out = [{**r, "withdraw_outcome": cancelled} for r in rows]
        if _kwargs.get("defer_fill_reads"):
            core.sender.defer_withdrawn_late(out)
        return out

    core.sender._withdraw_rows = withdraw
    os.environ["HL_LIVE_DISARMED_PATH_DIAGNOSTICS"] = "1"
    core._begin_backlog_cycle()
    with core._backlog_diag_lock:
        core._backlog_cycle_high_water = 17
        core._backlog_cycle_high_waters[core._backlog_cycle_id] = 17
    close = fill("off-close", "SELL", {"dir": "Close Long"})
    close.raw.setdefault("_stamps", {})["backlog_cycle_id"] = core._backlog_cycle_id
    result = core._process_leader_fill(close, summary, "")
    close_rows = [r for r in c.read_csv_rows(c.RECONCILIATION_CSV) if r.get("leader_fill_id") == "off-close"]
    pending = core.sender.pending_withdrawn_late()
    check("DISARMED_CONFIRMED_CLOSE_CANCELS_RESTING_ENTRY", withdrawn == ["rest-close"] and not core.sender.resting_entries())
    check("DISARMED_CLOSE_DEFERS_WITHDRAWN_FILL_READ", [r.get("oid") for r in pending] == ["rest-close"]
          and calls["fill_read"] == 0)
    check("DISARMED_CLOSE_HAS_ONE_FILL_TERMINAL_ROW", result[1] == "MASTER_REAL_ORDERS_OFF" and len(close_rows) == 1)
    check("FLAGGED_DIAGNOSTICS_STAMP_AGE_AND_CYCLE_HIGH_WATER", close_rows and int(close_rows[0].get("fill_age_ms") or -1) >= 0
          and close_rows[0].get("cycle_id") == str(core._backlog_cycle_id)
          and close_rows[0].get("cycle_backlog_high_water") == "17", str(close_rows))

    # The pending cancel-race list survives Core construction and is only consumed on an armed fill read.
    config("ON")
    resumed = c.LiveCopyCore(source_csv=tmp / "none.csv")
    resumed.sender._exchange_client_for_coin = lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("unexpected exchange use"))
    seen = []
    resumed._read_fills_of_withdrawn_limits = lambda rows: ([], "COPY_ACCOUNT_POLLED")
    resumed._apply_fills_of_withdrawn_limits = lambda rows, read, seen_oids=None: seen.extend(r["oid"] for r in rows) or 0
    resumed._process_deferred_withdrawn_entry_fills()
    check("WITHDRAWN_QUEUE_SURVIVES_RESTART_AND_DRAINS_WHEN_ARMED", seen == ["rest-close"]
          and not resumed.sender.pending_withdrawn_late(), str(seen))

    # N skipped fills must not mutate the ledger or change the next fixed-size order after arming.
    def arm_for_comparison(engine):
        config("ON")
        engine.cfg = c.ConfigManager()
        engine.intent_builder.cfg = engine.cfg
        engine.sender.cfg = engine.cfg
        if engine is core:
            engine.intent_builder.build = original_build
        engine.intent_builder._decision = lambda *_a, **_k: ("ENTRY_ALLOWED", "offline deterministic test")
        engine._prewarm_with_parity = lambda *_a, **_k: None
        engine.sender.cancel_resting_entries_against = lambda *_a, **_k: []
        sent = []
        engine.sender.send_if_allowed = lambda intent, *_a, **_k: sent.append(intent) or (True, "ORDER_FILLED")
        engine.copy_ingestor.poll_copy_account_fills = lambda *_a, **_k: ([], "COPY_ACCOUNT_POLLED")
        engine._read_fills_of_withdrawn_limits = lambda *_a, **_k: ([], "COPY_ACCOUNT_POLLED")
        engine._apply_fills_of_withdrawn_limits = lambda *_a, **_k: 0
        return sent

    target_sent = arm_for_comparison(core)
    base = c.LiveCopyCore(source_csv=tmp / "none.csv")
    base_sent = arm_for_comparison(base)
    calls.update({name: 0 for name in calls})
    next_fill = fill("after-off", "BUY", {"dir": "Open Long"})
    base_fill = fill("baseline-on", "BUY", {"dir": "Open Long"})
    target_result = core._process_leader_fill(next_fill)
    base_result = base._process_leader_fill(base_fill)
    target_order = target_sent[0] if target_sent else None
    baseline_order = base_sent[0] if base_sent else None
    check("ARMED_NEXT_FILL_HAS_SAME_SIZE_AND_SEND_DECISION", target_order is not None and baseline_order is not None
          and target_order.copy_size == baseline_order.copy_size == 0.12
          and target_order.decision == baseline_order.decision == "ENTRY_ALLOWED",
          str((target_order and (target_order.copy_size, target_order.decision),
               baseline_order and (baseline_order.copy_size, baseline_order.decision), target_result, base_result)))
    check("NO_NETWORK_CALLS_OCCURRED_IN_DISARMED_PATH", not any(calls.values()), str(calls))

    failed = [name for name, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
