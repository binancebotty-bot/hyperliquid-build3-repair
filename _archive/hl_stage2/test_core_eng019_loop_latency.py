#!/usr/bin/env python3
"""ENG-019 (main loop too slow) — deterministic, no clock, no network.

Row (certification/certification_matrix.json @ c63d2299, ENG-019):
  feature:  "Main loop keeps up with 10 very busy leaders"
  expected_behaviour: "With the 10 most active leaders followed, every engine cycle finishes within its budget:
    duplicate leader fills are de-duplicated before re-processing, and the copy-account poll runs every cycle
    and is never starved by leader polling."
  source: RUN3_FINDINGS.md F1 — 4 cycles in ~3 min, each budget_exceeded, 2,908 duplicate leader fills.

The row is asserted as BEHAVIOUR, never as a duration: nothing here reads a clock or sleeps for a threshold.

  D  duplicates are de-duplicated BEFORE re-processing: when a cycle re-reads fills it has already handled, the
     per-fill catch-up scan and the per-fill loop see only the fills that are new in that cycle. Probed as the
     size of the batch handed to the closed-late scan (the whole-batch stage run_cycle calls first), i.e. the
     per-iteration work, not the time it takes.
  S  the copy-account poll runs in a cycle whose leader poll fails: leader polling cannot starve it.
  C  control — a duplicate-free cycle is processed exactly as before: every new fill reaches per-fill
     processing once, nothing is dropped early, and the healthy leader-poll path still advances its cursor and
     lets the copy poll run.

Run: python test_core_eng019_loop_latency.py    # RESULT:: markers, TOTAL=/FAILED=, exit 0/1.
No network (requests.post replaced offline), no orders, no keys, testnet only.
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
A = "0x" + "a" * 40


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="eng019_"))
    os.environ.update({
        "HL_LIVE_AUDIT_DIR": str(tmp),
        "HL_LEADER_NETWORK": "testnet",          # never mainnet
        "HL_FOLLOWER_NETWORK": "testnet",
        "HL_LIVE_ENV_FILE": str(tmp / "none.env"),
        "HL_LIVE_DISABLE_NETWORK_REFRESH": "1",
        "HL_LIVE_SCOPE_SWEEP_THREAD": "0",
        "HL_LIVE_PREWARM_SYMBOL_META": "0",
        "HL_LIVE_PREWARM_SDK_CLIENT": "0",
        "HL_LIVE_SNAPSHOT_REFRESH_INTERVAL_SEC": "100000",
    })
    import requests
    import HL_Live_Copy_Service_Core as c

    def offline(*_a, **_k):
        raise RuntimeError("offline test: no network")
    requests.post = offline
    c.requests.post = offline
    c.USER_WALLET = FOLLOWER
    c.atomic_write_json(c.LIVE_CONFIG_FILE, {
        "auto_send_enabled": False,
        "global_controls": {"min_notional": 10, "max_order_notional_usd": 0, "marketable_bps": 25},
        "wallets": {A: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}},
    })

    scan_sizes = []
    real_scan = c.already_closed_late_entries

    def spy_scan(fills, now_ms):
        scan_sizes.append(len(fills))
        return real_scan(fills, now_ms)
    c.already_closed_late_entries = spy_scan

    def batch(n: int, t0: int, tag: str, coin_each: bool = False):
        """Fresh LeaderFill objects: one wallet, WS source (never collapsed), ascending fresh timestamps."""
        return [c.LeaderFill(f"{tag}{i}", A, (f"COIN{i}" if coin_each else "BTC"), "BUY", 100.0, 0.001, t0 + i,
                             "WS_CAPTURED", 0, {"dir": "Open Long", "startPosition": str(round(0.001 * i, 8))})
                for i in range(n)]

    def new_core():
        core = c.LiveCopyCore(source_csv=tmp / "none.csv")
        core.async_dispatch = False          # the synchronous cycle the loop also drives
        return core

    # ---- C: control — a duplicate-free cycle behaves exactly as before -------------------------------------
    core = new_core()
    processed = []
    real_proc = core._process_leader_fill

    def spy_proc(fill, summary=None, reason=""):
        processed.append(fill.leader_fill_id)
        return real_proc(fill, summary, reason)
    core._process_leader_fill = spy_proc

    class HealthyLeaderIngestor:
        calls = 0

        def poll_hyperliquid_fills(self, wallet, start_ms, end_ms=None):
            HealthyLeaderIngestor.calls += 1
            return [], "POLL_OK"

    class SpyCopyIngestor:
        calls = 0

        def poll_copy_account_fills(self, user_wallet, start_ms, end_ms=None, **_k):
            SpyCopyIngestor.calls += 1
            return [], "COPY_ACCOUNT_POLLED"

    core.ingestor = HealthyLeaderIngestor()
    core.copy_ingestor = SpyCopyIngestor()
    fresh = batch(40, c.utc_now_ms() - 50_000, "c", coin_each=True)
    core.ws.drain = lambda: list(fresh)
    scan_sizes.clear()
    sum_c = core.run_cycle(use_source_csv=False, poll_live=True, poll_copy=True, reconcile_exchange=False)
    check("C1_CONTROL_EVERY_NEW_FILL_REACHES_PROCESSING_ONCE",
          sorted(processed) == sorted(f.leader_fill_id for f in fresh) and len(processed) == len(fresh),
          f"processed={len(processed)} of {len(fresh)}: {processed[:5]}")
    check("C2_CONTROL_NOTHING_DROPPED_EARLY_AND_SCAN_SEES_THE_WHOLE_BATCH",
          sum_c.leader_fills_seen == 40 and sum_c.leader_fills_deduped == 0 and scan_sizes == [40],
          f"seen={sum_c.leader_fills_seen} deduped={sum_c.leader_fills_deduped} scan={scan_sizes}")
    rt = c.load_json(c.CORE_RUNTIME_STATE_FILE, {})
    check("C3_CONTROL_HEALTHY_LEADER_POLL_ADVANCES_CURSOR_AND_COPY_POLL_RUNS",
          HealthyLeaderIngestor.calls == 1 and SpyCopyIngestor.calls == 1
          and int((rt.get("last_leader_poll_cursor_ms") or {}).get(A, 0)) > 0
          and sum_c.network_errors == 0,
          f"leader_calls={HealthyLeaderIngestor.calls} copy_calls={SpyCopyIngestor.calls} "
          f"cursor={(rt.get('last_leader_poll_cursor_ms') or {}).get(A)} net_err={sum_c.network_errors}")
    core.stop()

    # ---- D: duplicates are de-duplicated before re-processing ----------------------------------------------
    core = new_core()
    t0 = c.utc_now_ms() - 50_000
    core.ws.drain = lambda: list(batch(60, t0, "h"))          # cycle 1: 60 new leader fills
    sum_d1 = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
    check("D0_SETUP_FIRST_CYCLE_HANDLES_THE_BATCH",
          sum_d1.leader_fills_seen == 60 and sum_d1.leader_fills_deduped == 0,
          f"seen={sum_d1.leader_fills_seen} deduped={sum_d1.leader_fills_deduped}")
    scan_sizes.clear()
    # cycle 2: the same 60 fills are re-read (poll overlap / WS replay — run 3's 2,908 duplicates) plus 2 new ones
    core.ws.drain = lambda: list(batch(60, t0, "h")) + list(batch(2, t0 + 500, "n"))
    sum_d2 = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
    print(f"MEASURE:: cycle-2 catch-up scan input = {scan_sizes} (2 new fills among 60 re-read duplicates)")
    check("D1_DUPLICATES_DEDUPED_BEFORE_REPROCESSING",
          scan_sizes == [2],
          f"per-fill catch-up scan re-processed {scan_sizes} for 2 new fills: "
          f"{sum_d2.leader_fills_deduped} duplicates reached it")
    check("D2_DUPLICATE_COUNT_STILL_REPORTED",
          sum_d2.leader_fills_deduped == 60 and sum_d2.leader_fills_seen == 62,
          f"deduped={sum_d2.leader_fills_deduped} seen={sum_d2.leader_fills_seen}")
    core.stop()

    # ---- S: a failing leader poll does not starve that cycle's copy-account poll ---------------------------
    core = new_core()

    class FailingLeaderIngestor:
        calls = 0

        def poll_hyperliquid_fills(self, wallet, start_ms, end_ms=None):
            FailingLeaderIngestor.calls += 1
            raise RuntimeError("429 rate limited: leader poll failed this cycle")

    class CountingCopyIngestor:
        calls = 0

        def poll_copy_account_fills(self, user_wallet, start_ms, end_ms=None, **_k):
            CountingCopyIngestor.calls += 1
            return [], "COPY_ACCOUNT_POLLED"

    core.ingestor = FailingLeaderIngestor()
    core.copy_ingestor = CountingCopyIngestor()
    core.ws.drain = lambda: []
    sum_s = core.run_cycle(use_source_csv=False, poll_live=True, poll_copy=True, reconcile_exchange=False)
    check("S0_LEADER_POLL_WAS_ATTEMPTED_IN_THE_CYCLE", FailingLeaderIngestor.calls == 1,
          f"leader poll calls={FailingLeaderIngestor.calls}")
    check("S1_COPY_POLL_NOT_STARVED_BY_A_FAILING_LEADER_POLL",
          CountingCopyIngestor.calls == 1,
          f"copy poll calls={CountingCopyIngestor.calls} after the leader poll raised "
          f"(ok={sum_s.ok} fatal_errors={sum_s.fatal_errors})")
    check("S2_CYCLE_COMPLETED_AROUND_THE_FAILED_LEADER_POLL",
          sum_s.fatal_errors == 0 and sum_s.network_errors >= 1,
          f"ok={sum_s.ok} fatal={sum_s.fatal_errors} net_err={sum_s.network_errors}")
    core.stop()

    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
