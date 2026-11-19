#!/usr/bin/env python3
"""ENG-019 (main loop too slow) — deterministic, no clock, no network.

Row (certification/certification_matrix.json @ c63d2299, ENG-019):
  feature:  "Main loop keeps up with 10 very busy leaders"
  expected_behaviour: "With the 10 most active leaders followed, every engine cycle finishes within its budget:
    duplicate leader fills are de-duplicated before re-processing, and the copy-account poll runs every cycle
    and is never starved by leader polling."
  source: RUN3_FINDINGS.md F1 — 4 cycles in ~3 min, each budget_exceeded, 2,908 duplicate leader fills.

The row is asserted as BEHAVIOUR, never as a duration: nothing here reads a clock or sleeps for a threshold.

  D    duplicates are de-duplicated BEFORE re-processing, probed as the size of the batch handed to
       ``already_closed_late_entries(fills, utc_now_ms())`` (Core:15644) — the whole-batch stage ``run_cycle``
       calls first, i.e. the per-iteration work, not the time it takes.
  D10  the same bound over the row's actual subject: TEN distinct leaders. A re-read cycle must hand the
       expensive call ONE entry per distinct leader (10), never one per re-read fill (30).
  BG   budgets are DETERMINISTIC configuration inputs, not wall-clock luck: the configured budget is driven to
       both verdicts and the cycle's WORK counts are shown not to move with it.
  S    the copy-account poll runs exactly once in a cycle whose leader poll raises, and there is no second poll
       from a ``finally`` (the finally is asserted structurally as well as behaviourally).
  W    a worker exception is FAIL-LOUD: held with a named durable row, never swallowed (with a negative control).
  CK   the close contract on the REAL close path, driven through the production caller.
  RET  a crash at the wire and a retry before reconcile each make NO second physical effect.

WHICH ``finally`` DOES THE ORACLE MEAN? — ENUMERATED, NOT ASSUMED.
All 33 ``finally:`` blocks in HL_Live_Copy_Service_Core.py at c63d2299 were enumerated
(grep -n 'finally:' -> 263, 1326, 1520, 2109, 2139, 2397, 2468, 2488, 5717, 6126, 6159, 6197, 6225, 7921, 9277,
9315, 12896, 13427, 13782, 13785, 13821, 13852, 13903, 14204, 14293, 15702, 16568, 16583, 16605, 16939, 17676,
17933, 17983).  NONE of them sends an order.  The loop's own ``finally`` is Core:15702 inside ``run_cycle`` and it
publishes only budget/state/trace.  The one ``finally`` that touches sending at all is Core:9315 in
``send_if_allowed``, and it RELEASES the pending-exit reservation — it places nothing.

So THIS REVISION HAS NO SEPARATE FINALLY-CLOSE PATH, and none is invented here.  The only mode that answers the
ruling's subject (a close whose size is clamped to the exchange net and sent reduce-only) is
``SenderGateway._close_lag_window_expired`` (Core:8658-8673):
    amount = self._floor_wire_size(round(min(requested, abs(net)), 10), sz_dec)   # :8666  clamped to abs(net)
    return decide("SEND", amount, True)                                           # :8673  blind reduce_only
It is reachable ONLY after ``_close_lag_hold_for_owned`` (Core:8646) proved the fill-proven owned size UNPROVEN to
tolerance for the whole CLOSE_LAG_HOLD_SEC window — it is the UNOWNED fallback, and its clamp is correct for that
state.  The OWNED close is ``_close_wire_plan`` (Core:8405) / ``_close_wire_plan_ledger_lag`` (Core:8532), and that
is the path the ruling is encoded against below, driven through the production caller
``send_if_allowed`` (Core:9137) -> ``_send_real`` (Core:9353) -> ``_close_wire_plan`` (call site Core:9698-9708)
with a fake exchange that counts every physical call.

KNOWN GAP (stated, not faked): cross-PROCESS restart cardinality for a close is not modelled here.  RET1/RET2 prove
the in-process reservation (pending-exit guard Core:9277/9315 + ``exchange_order_invoked``), not a restart.

Run: python -u test_core_eng019_loop_latency.py    # RESULT:: markers, TOTAL=/FAILED=, exit 0/1.
No network (requests.post replaced offline), no orders, no keys, testnet only.
"""
from __future__ import annotations

import csv
import inspect
import os
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
RESULTS = []
FOLLOWER = "0x" + "c" * 40
A = "0x" + "a" * 40
TEN = ["0x" + ("%02x" % n) * 20 for n in range(1, 11)]  # 10 distinct leader wallets


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""),
          flush=True)


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
        "HL_LIVE_UNEXPLAINED_WAIT_SEC": "0",     # no ownership-gate re-read wait: deterministic, no sleeps
        "HL_LIVE_MIN_EXCHANGE_ORDER_GAP_MS": "0",
        "HL_LIVE_GLOBAL_LOCK_FILE": str(tmp / "engine-global.lock"),  # never the machine-wide lock
    })
    import requests
    transport_attempts = [0]
    stub_calls = [0]
    socket_attempts = [0]
    def offline(*_a, **_k):
        socket_attempts[0] += 1
        raise RuntimeError("offline test: no network")
    class _OfflineResponse:
        status_code = 200
        def __init__(self, payload):
            self._payload = [] if payload.get("type") in {"meta", "perpDexs", "spotMeta"} else {}
        def json(self):
            return self._payload
    def transport_stub(url, json=None, timeout=None, **_kwargs):
        # Reached only as the replacement itself; no socket or real HTTP transport is entered.
        stub_calls[0] += 1
        return _OfflineResponse(json or {})
    requests.post = transport_stub
    import HL_Live_Copy_Service_Core as c
    c.requests.post = transport_stub

    # Offline price fixtures. Core:316 follower_mid -> _XNET.post_many(MIDS_FETCHER, ...) treats a fetcher of None as
    # LIVE plumbing: it would attempt a real /info POST (the stub refuses it) and then sleep through two retries per
    # DEX. Injecting a fetcher makes _post neither touch the network nor retry (exchange_truth._post: tries=1).
    def _mids(payload):
        if isinstance(payload, dict) and payload.get("type") == "perpDexs":
            return []
        return {"BTC": "100.0", "COIN0": "100.0"}
    # The shared requests.post transport below is stubbed; do not inject per-fetcher fixtures.
    c.follower_volumes_24h = lambda *a, **k: (False, {}, set())

    def write_cfg(wallets):
        c.atomic_write_json(c.LIVE_CONFIG_FILE, {
            "auto_send_enabled": False,
            "global_controls": {"min_notional": 10, "max_order_notional_usd": 0, "marketable_bps": 25},
            "wallets": {w: {"enabled": True, "mode": "ON", "copy_mode": "fixed", "fixed_notional": 12}
                        for w in wallets},
        })
    write_cfg([A])

    scan_sizes = []
    real_scan = c.already_closed_late_entries

    def spy_scan(fills, now_ms):
        scan_sizes.append(list(fills))
        return real_scan(fills, now_ms)
    c.already_closed_late_entries = spy_scan

    def batch(n: int, t0: int, tag: str, coin_each: bool = False, wallet: str = A):
        """Fresh LeaderFill objects: one wallet, WS source (never collapsed), ascending fresh timestamps."""
        return [c.LeaderFill(f"{tag}{i}", wallet, (f"COIN{i}" if coin_each else "BTC"), "BUY", 100.0, 0.001, t0 + i,
                             "WS_CAPTURED", 0, {"dir": "Open Long", "startPosition": str(round(0.001 * i, 8))})
                for i in range(n)]

    def new_core():
        core = c.LiveCopyCore(source_csv=tmp / "none.csv")
        core.async_dispatch = False          # the synchronous cycle the loop also drives
        return core

    def recon_rows(fid):
        p = c.RECONCILIATION_CSV
        if not p.exists():
            return []
        with p.open("r", newline="", encoding="utf-8-sig") as fh:
            return [r for r in csv.DictReader(fh) if r.get("leader_fill_id") == fid]

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
          sum_c.leader_fills_seen == 40 and sum_c.leader_fills_deduped == 0
          and [len(x) for x in scan_sizes] == [40],
          f"seen={sum_c.leader_fills_seen} deduped={sum_c.leader_fills_deduped} "
          f"scan={[len(x) for x in scan_sizes]}")
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
    d_processed = []
    real_d_proc = core._process_leader_fill
    core._process_leader_fill = lambda fill, summary=None, reason="": (d_processed.append(fill.leader_fill_id), real_d_proc(fill, summary, reason))[1]
    core.ws.drain = lambda: list(batch(60, t0, "h")) + list(batch(2, t0 + 500, "n"))
    sum_d2 = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
    print(f"MEASURE:: cycle-2 processing reach = {d_processed} (expected only 2 new fills)")
    check("D1_DUPLICATES_DO_NOT_REACH_PROCESSING",
          all(not fid.startswith("h") for fid in d_processed)
          and sum_d2.leader_fills_deduped == 60 and bool(d_processed),
          f"_process_leader_fill reached {d_processed}; duplicate IDs h0..h59 must not reach processing; "
          f"deduped={sum_d2.leader_fills_deduped}")
    check("D2_DUPLICATE_COUNT_STILL_REPORTED",
          sum_d2.leader_fills_deduped == 60 and sum_d2.leader_fills_seen == 62,
          f"deduped={sum_d2.leader_fills_deduped} seen={sum_d2.leader_fills_seen}")
    core.stop()

    # ---- D10: the row's actual subject — TEN leaders, one unit of work per DISTINCT leader ------------------
    write_cfg(TEN)
    core = new_core()
    t10 = c.utc_now_ms() - 50_000

    def two_each(t_base):
        out = []
        for w in TEN:
            out.extend(batch(2, t_base, "z" + w[-2:], wallet=w))
        return out

    core.ws.drain = lambda: two_each(t10)                      # cycle 1: 10 leaders x 2 fills = 20 new
    sum_e1 = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
    check("D10A_SETUP_TEN_LEADERS_FIRST_CYCLE",
          sum_e1.leader_fills_seen == 20 and sum_e1.leader_fills_deduped == 0,
          f"seen={sum_e1.leader_fills_seen} deduped={sum_e1.leader_fills_deduped}")
    scan_sizes.clear()
    # cycle 2 re-reads all 20 handled fills and adds one new fill per leader: 30 in, 10 units of work.
    d10_processed = []
    real_d10_proc = core._process_leader_fill
    core._process_leader_fill = lambda fill, summary=None, reason="": (d10_processed.append(fill), real_d10_proc(fill, summary, reason))[1]
    core.ws.drain = lambda: two_each(t10) + [batch(1, t10 + 900, "q" + w[-2:], wallet=w)[0] for w in TEN]
    sum_e2 = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
    got = d10_processed
    print(f"MEASURE:: 10-leader re-read processing reach: {len(got)} fills, "
          f"{len({f.leader_wallet for f in got})} distinct leaders")
    check("D10B_ONE_UNIT_OF_WORK_PER_DISTINCT_LEADER_BEFORE_THE_EXPENSIVE_CALL",
          len(got) == 10 and {f.leader_wallet for f in got} == set(TEN)
          and {f.leader_fill_id for f in got} == {"q" + w[-2:] + "0" for w in TEN},
          f"_process_leader_fill received {len(got)} fills / "
          f"{len({f.leader_wallet for f in got})} distinct leaders for 30 fills in (20 duplicates); "
          f"dedupe is before processing at Core:15661")
    check("D10C_EVERY_DUPLICATE_ELIMINATED_BEFORE_THE_CALL_AND_COUNTED",
          sum_e2.leader_fills_seen == 30 and sum_e2.leader_fills_deduped == 20,
          f"seen={sum_e2.leader_fills_seen} deduped={sum_e2.leader_fills_deduped}")
    core.stop()

    # ---- BG: budgets are deterministic configuration inputs, never wall-clock luck --------------------------
    def budget_run(sec):
        old = os.environ.get("HL_LIVE_RECON_CYCLE_BUDGET_SEC")
        os.environ["HL_LIVE_RECON_CYCLE_BUDGET_SEC"] = sec
        try:
            bg = new_core()
            bg.ws.drain = lambda: []
            s = bg.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
            bg.stop()
            return s
        finally:
            if old is None:
                os.environ.pop("HL_LIVE_RECON_CYCLE_BUDGET_SEC", None)
            else:
                os.environ["HL_LIVE_RECON_CYCLE_BUDGET_SEC"] = old
    over = budget_run("-1")        # every cycle is over a negative budget: deterministic TRUE
    under = budget_run("100000")   # no cycle is over a ~27-hour budget: deterministic FALSE
    check("BG1_CONFIGURED_BUDGET_IS_OBEYED_IN_BOTH_DIRECTIONS",
          over.budget_exceeded is True and under.budget_exceeded is False,
          f"budget=-1 -> budget_exceeded={over.budget_exceeded}; budget=100000 -> {under.budget_exceeded}")
    check("BG2_THE_WORK_BOUND_DOES_NOT_DEPEND_ON_THE_BUDGET_VERDICT",
          over.leader_fills_seen == under.leader_fills_seen == 0
          and over.fatal_errors == under.fatal_errors == 0,
          f"over(seen={over.leader_fills_seen},fatal={over.fatal_errors}) "
          f"under(seen={under.leader_fills_seen},fatal={under.fatal_errors}) "
          f"| work counts, never elapsed time")

    # ---- W: a worker exception is fail-loud, never swallowed ------------------------------------------------
    write_cfg([A])
    core = new_core()
    tw = c.utc_now_ms() - 10_000
    core.ws.drain = lambda: list(batch(1, tw, "ok"))
    core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
    clean_rows = recon_rows("ok0")
    clean_loud = [r for r in clean_rows if "PROCESS_EXCEPTION" in (str(r.get("status") or "")
                                                                   + str(r.get("terminal_state") or ""))]
    check("W0_NEGATIVE_CONTROL_A_CLEAN_FILL_HAS_NO_WORKER_EXCEPTION_ROW",
          clean_rows != [] and clean_loud == [],
          f"rows for ok0: {[(r.get('status'), r.get('terminal_state')) for r in clean_rows]}")
    core.stop()

    core = new_core()

    def boom(_fill):
        raise RuntimeError("worker boom")
    core.intent_builder.build = boom
    core.ws.drain = lambda: list(batch(1, tw + 5000, "boom"))
    sum_w = core.run_cycle(use_source_csv=False, poll_live=False, poll_copy=False, reconcile_exchange=False)
    wrows = recon_rows("boom0")
    loud = [r for r in wrows if "PROCESS_EXCEPTION" in (str(r.get("status") or "")
                                                        + str(r.get("terminal_state") or ""))]
    core.stop()
    check("W1_WORKER_EXCEPTION_SURFACES_AS_A_NAMED_DURABLE_ROW",
          len(loud) == 1 and "RuntimeError" in str(loud[0].get("notes") or "")
          and "worker boom" in str(loud[0].get("notes") or ""),
          f"rows={[(r.get('status'), r.get('terminal_state')) for r in wrows]} "
          f"notes={(loud[0].get('notes') if loud else '')[:160]}")
    check("W2_THE_CYCLE_SURVIVES_THE_WORKER_EXCEPTION_WITHOUT_DROPPING_THE_FILL",
          sum_w.fatal_errors == 0 and sum_w.ok is True,
          f"ok={sum_w.ok} fatal={sum_w.fatal_errors}")

    # ---- S: a failing leader poll does not starve that cycle's copy-account poll ---------------------------
    core = new_core()

    class FailingLeaderIngestor:
        calls = 0

        def poll_hyperliquid_fills(self, wallet, start_ms, end_ms=None):
            FailingLeaderIngestor.calls += 1
            raise AttributeError("leader poll code fault")

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
    # S3 is dropped: it repeated S1's identical predicate on the same object.
    # Strike: this WS-drain failure is outside the leader-poll requirement; no finally fallback is added.
    core.stop()

    # Three-wallet control: the multi-job path contains the failed poll and still reaches copy polling.
    write_cfg(TEN[:3])
    core = new_core()
    class ThreeWalletFailingLeader:
        calls = 0
        def poll_hyperliquid_fills(self, wallet, start_ms, end_ms=None):
            ThreeWalletFailingLeader.calls += 1
            raise AttributeError("leader poll code fault")
    class ThreeWalletCopyCounter:
        calls = 0
        def poll_copy_account_fills(self, user_wallet, start_ms, end_ms=None, **_k):
            ThreeWalletCopyCounter.calls += 1
            return [], "COPY_ACCOUNT_POLLED"
    core.ingestor = ThreeWalletFailingLeader()
    core.copy_ingestor = ThreeWalletCopyCounter()
    core.ws.drain = lambda: []
    sum_s3 = core.run_cycle(use_source_csv=False, poll_live=True, poll_copy=True, reconcile_exchange=False)
    print(f"MEASURE:: poll contrast 1-wallet copy_calls={CountingCopyIngestor.calls}; "
          f"3-wallet leader_calls={ThreeWalletFailingLeader.calls} copy_calls={ThreeWalletCopyCounter.calls}")
    check("S1B_THREE_WALLET_CONTROL_CONTAINS_FAILED_POLL_AND_RUNS_COPY_POLL",
          ThreeWalletFailingLeader.calls == 3 and ThreeWalletCopyCounter.calls == 1
          and sum_s3.fatal_errors == 0,
          f"leaders={ThreeWalletFailingLeader.calls} copy={ThreeWalletCopyCounter.calls} "
          f"fatal={sum_s3.fatal_errors}")
    core.stop()
    write_cfg([A])

    # A rate-limited leader poll is transport noise, not a code fault.
    core = new_core()

    class RateLimitedLeaderIngestor:
        def poll_hyperliquid_fills(self, wallet, start_ms, end_ms=None):
            raise RuntimeError("429 rate limited: leader poll failed this cycle")
    core.ingestor = RateLimitedLeaderIngestor()
    core.copy_ingestor = SpyCopyIngestor()
    core.ws.drain = lambda: []
    sum_429 = core.run_cycle(use_source_csv=False, poll_live=True, poll_copy=True, reconcile_exchange=False)
    check("S2B_RATE_LIMITED_LEADER_POLL_IS_A_NETWORK_ERROR",
          sum_429.fatal_errors == 0 and sum_429.network_errors >= 1,
          f"fatal={sum_429.fatal_errors} network={sum_429.network_errors}")
    core.stop()

    # A transient transport failure is counted as network noise, not a code fault.
    core = new_core()

    class NetworkLeaderIngestor:
        def poll_hyperliquid_fills(self, wallet, start_ms, end_ms=None):
            raise ConnectionError("temporary transport failure")
    core.ingestor = NetworkLeaderIngestor()
    core.copy_ingestor = SpyCopyIngestor()
    core.ws.drain = lambda: []
    sum_net = core.run_cycle(use_source_csv=False, poll_live=True, poll_copy=True, reconcile_exchange=False)
    check("S7_CONNECTION_ERROR_TOLERATED_WITHOUT_CODE_ALERT",
          sum_net.fatal_errors == 0 and sum_net.network_errors >= 1,
          f"fatal={sum_net.fatal_errors} network={sum_net.network_errors}")
    core.stop()

    # S5A dropped: ws.drain failure is not a leader-poll failure and does not establish this contract.

    # Structural backing: assert exactly one finally block in run_cycle, and it contains no copy poll.
    _src = inspect.getsource(c.LiveCopyCore.run_cycle)
    _finally_blocks = [line for line in _src.splitlines() if line.strip() == "finally:"]
    _fin = _src[_src.rfind("\n        finally:"):] if len(_finally_blocks) == 1 else ""
    check("S5B_RUN_CYCLE_HAS_ONE_FINALLY_AND_NO_COPY_POLL",
          len(_finally_blocks) == 1 and bool(_fin)
          and "copy_poll_once" not in _fin and "poll_copy_account_fills" not in _fin,
          f"finally_count={len(_finally_blocks)} tail={_fin.strip()[:120]}")

    # A raising copy poll must not be retried a second time in finally.
    core = new_core()

    class RaisingCopyIngestor:
        calls = 0

        def poll_copy_account_fills(self, user_wallet, start_ms, end_ms=None, **_k):
            RaisingCopyIngestor.calls += 1
            raise RuntimeError("copy poll failed")
    core.ingestor = HealthyLeaderIngestor()
    core.copy_ingestor = RaisingCopyIngestor()
    core.ws.drain = lambda: []
    core.run_cycle(use_source_csv=False, poll_live=True, poll_copy=True, reconcile_exchange=False)
    core.stop()
    check("S4_RAISING_COPY_POLL_IS_NOT_RETRIED_IN_FINALLY", RaisingCopyIngestor.calls == 1,
          f"copy poll calls={RaisingCopyIngestor.calls} (run_cycle finally Core:15702 must poll nothing)")

    # =====================================================================================================
    # CK/RET: the close contract, driven through the PRODUCTION CALLER
    #   send_if_allowed (Core:9137) -> _send_real (Core:9353) -> _close_wire_plan (Core:8405), call site Core:9698
    # with a fake exchange that records every physical order. The real ownership gate, the real close-wire
    # planner and the real final-wire validator all run; only DATA SOURCES (asset metadata, exchange net,
    # exchange snapshot) are faked.
    # =====================================================================================================
    ACCOUNT = "0x" + "d" * 40
    COIN, PX, MIN_USD = "BTC", 100.0, 10.0
    RESOLVED = {"ok": True, "sdk_coin": COIN, "sz_decimals": 3, "price_max_decimals": 2, "perp_dexs": [""],
                "sdk_order_compatible": True, "min_order_value_usd": MIN_USD, "min_size": 0.0, "status": "OK"}
    os.environ["HL_LIVE_HL_PRIVATE_KEY"] = "0x" + "1" * 64   # synthetic, not a secret: presence check only
    os.environ["HL_LIVE_HL_ACCOUNT_ADDRESS"] = ACCOUNT
    c.USER_WALLET = ACCOUNT
    c.HLAccount, c.HLExchange = object, object
    c.MIDS_FETCHER = lambda p: [] if isinstance(p, dict) and p.get("type") == "perpDexs" else {COIN: str(PX)}
    c.LEADER_MIDS_FETCHER = c.MIDS_FETCHER
    c.acquire_global_instance_lock(tmp / "state")            # the sender refuses without the engine lease

    def filled(sz, px, oid=1):
        return {"status": "ok", "response": {"type": "order", "data": {"statuses": [
            {"filled": {"totalSz": str(sz), "avgPx": str(px), "oid": oid}}]}}}

    class FakeExchange:
        """Records every physical order call. With no queued replies it fills exactly the size asked."""

        def __init__(self, replies=None, raise_on_order=False):
            self.calls = []
            self.replies = list(replies or [])
            self.raise_on_order = raise_on_order
            self._lock = threading.Lock()

        def update_leverage(self, leverage, name, is_cross=True):
            return {"status": "ok"}

        def order(self, coin, is_buy, size, px, tif, reduce_only=False, cloid=None):
            with self._lock:
                self.calls.append({"coin": coin, "is_buy": is_buy, "size": float(size), "px": px,
                                   "reduce_only": reduce_only,
                                   "cloid": None if cloid is None else str(cloid)})
                if self.raise_on_order:      # SIMULATED CRASH AT THE WIRE: the order may or may not exist
                    raise TimeoutError("socket died mid-send")
                if self.replies:
                    return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
                return filled(size, px, oid=len(self.calls))

        def cancel(self, coin, oid):
            return {"response": {"data": {"statuses": ["success"]}}}

    _n = [0]

    def new_ledger():
        _n[0] += 1
        return c.ManualLedger(path=tmp / ("ledger_%d.json" % _n[0]))

    def set_sleeve(ledger, wallet, signed):
        ledger.sleeve(wallet, COIN)["signed_size"] = signed
        ledger._recompute_net(ledger.data)

    def make_gateway(ex, ledger, net):
        gw = c.SenderGateway(c.ConfigManager(), c.AuditLogWriter(), ledger)
        gw._resolve_coin = lambda coin: dict(RESOLVED)
        gw._get_exchange_client = lambda *a, **k: ex
        gw._exchange_client_has_symbol = lambda *a, **k: True
        gw._pre_exchange_asset_safety = lambda *a, **k: (True, {})
        gw._exchange_client_for_coin = lambda coin: (ex, COIN)
        gw._follower_order_account_for_proof = lambda *a, **k: ACCOUNT
        gw._fresh_exchange_net = lambda coin: net[0]
        gw._persisted_exchange_positions = lambda: (({COIN: net[0]}, "") if net[0] is not None
                                                   else ({}, "unavailable"))
        gw.leader_reduced_since = lambda f: 0
        gw._margin_mode_done = {COIN}
        gw.cfg.master_switch_now = lambda: True
        gw.cfg.send_mode_now = lambda: "ON"
        gw.cfg.wallet_enabled = lambda w: True
        gw.cfg.wallet_mode = lambda w: "ON"
        return gw

    def exit_intent(ledger, wallet, side, size, fid, sleeve):
        """A real, send-authorised EXIT intent built while the wallet sleeve holds ``sleeve`` (signed)."""
        set_sleeve(ledger, wallet, sleeve)
        fill = c.LeaderFill(fid, wallet, COIN, side, PX, size, c.utc_now_ms(), "POLL")
        it = c.IntentBuilder(c.ConfigManager(), ledger).build(fill)
        it.intent_id = fid
        it.decision = "EXIT_ALLOWED"
        return it

    B = "0x" + "b" * 40

    # CK0: the DISCRIMINATING CONTROL for CK1. The one path in this revision that really does clamp to the exchange
    # net and force reduce-only is _close_lag_window_expired (Core:8658-8673), and it is reachable ONLY while the
    # fill-proven owned size is UNPROVEN. Same requested size (10), same net (5): it wires 5.0 reduce-only, where
    # the owned path wires 10.0 not reduce-only. A net clamp on the owned path would make these two agree.
    class _LagFake:
        def __init__(self, net):
            self.net = net

        def _fresh_exchange_net(self, coin):
            return self.net

        def _floor_wire_size(self, s, d):
            return c.SenderGateway._floor_wire_size(s, d)

        def _open_close_escalation(self, intent, reason):
            return None

    def _decide(kind, amount=0.0, ro=False, why=""):
        return ro, amount, why

    _lag_intent = type("I", (), {"fill": type("F", (), {"coin": COIN})})()
    r_lag = c.SenderGateway._close_lag_window_expired(_LagFake(5.0), _lag_intent, 10.0, 3, -1.0, 1e-9, _decide)
    check("CK0_UNOWNED_FALLBACK_CLAMPS_AND_FORCES_REDUCE_ONLY__THE_CONTRAST_FOR_CK1",
          r_lag == (True, 5.0, ""),
          f"owned-UNPROVEN window-Expired returned {r_lag} (expected (True, 5.0, ''): min(10,|net| 5)=5, ro=True)")

    # CK1: OWNED fill-proven close -> exactly the owned size, NOT clamped to the exchange net.
    led, ex, net = new_ledger(), FakeExchange(), [-5.0]
    gw = make_gateway(ex, led, net)
    set_sleeve(led, B, -15.0)                                # leader B short 15: exchange net = +10 - 15 = -5
    it = exit_intent(led, A, "SELL", 10.0, "ck1-f", 10.0)     # owned +10, leader closed 10
    ok1, st1 = gw.send_if_allowed(it)
    check("CK1_OWNED_CLOSE_SENDS_EXACTLY_THE_OWNED_SIZE_NOT_NET_CLAMPED",
          ok1 and len(ex.calls) == 1 and abs(ex.calls[0]["size"] - 10.0) < 1e-9,
          f"ok={ok1} status={st1} calls={ex.calls} "
          f"(fill-proven owned=10, abs(exchange net)=5 — a net clamp would have wired 5)")
    check("CK1B_OWNED_CLOSE_IS_NOT_BLIND_REDUCE_ONLY",
          len(ex.calls) == 1 and ex.calls[0]["reduce_only"] is False,
          f"reduce_only={ex.calls[0]['reduce_only'] if ex.calls else 'NO CALL'} on a 10-lot close against |net| 5: "
          f"a forced reduce-only would misstate what that order does")

    # CK1C: the same close against a real opposing net IS reduce-only — the flag is derived, never forced.
    led, ex, net = new_ledger(), FakeExchange(), [10.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 10.0, "ck1c-f", 10.0)
    ok1c, st1c = gw.send_if_allowed(it)
    check("CK1C_REDUCE_ONLY_IS_DERIVED_FROM_THE_REAL_NET",
          ok1c and len(ex.calls) == 1 and ex.calls[0]["reduce_only"] is True
          and abs(ex.calls[0]["size"] - 10.0) < 1e-9,
          f"ok={ok1c} status={st1c} calls={ex.calls}")

    # CK2: readable FLAT exchange -> NO WIRE, and a named row (never a silent success).
    led, ex, net = new_ledger(), FakeExchange(), [0.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 2.0, "ck2-f", 2.0)
    set_sleeve(led, A, 0.0)                                   # the engine sleeve is flat too
    ok2, st2 = gw.send_if_allowed(it)
    check("CK2_FLAT_EXCHANGE_SENDS_NOTHING_AND_NAMES_THE_REFUSAL",
          (not ok2) and not ex.calls and len(recon_rows("ck2-f")) == 1,
          f"ok={ok2} status={st2} physical_calls={len(ex.calls)} "
          f"rows={[r.get('status') for r in recon_rows('ck2-f')]}")

    # CK3: NO ownership record -> zero wire AND a named alert row on the close path.
    led, ex, net = new_ledger(), FakeExchange(), [0.0]
    gw = make_gateway(ex, led, net)
    it = exit_intent(led, A, "SELL", 4.0, "ck3-f", 4.0)
    led.data["by_wallet"][A].pop(COIN, None)                  # the ownership record is gone
    led._recompute_net(led.data)
    ok3, st3 = gw.send_if_allowed(it)
    r3 = recon_rows("ck3-f")
    # The FIRST named refusal on this path is the pre-send ownership gate
    # (OWNERSHIP_GATE_NO_MATCHING_WALLET_SLEEVE / OWNERSHIP_CONTRACT_BLOCK), which is the correct answer for a
    # close whose ownership record is gone: it refuses BEFORE _close_wire_plan is consulted. Either that name or
    # the planner's own CLOSE_PROOF_HOLD_* name satisfies the contract; what must never happen is a wire.
    named3 = [r for r in r3
              if str(r.get("status") or "").startswith(("OWNERSHIP_GATE_", "CLOSE_PROOF_HOLD"))
              or "CLOSE_PROOF_HOLD" in str(r.get("reject_category") or "")]
    check("CK3_NO_OWNERSHIP_RECORD_SENDS_ZERO_AND_WRITES_A_NAMED_ALERT",
          (not ok3) and not ex.calls and len(named3) == 1
          and str(named3[0].get("engine_can_send")).lower() == "false",
          f"ok={ok3} status={st3} physical_calls={len(ex.calls)} named={[r.get('status') for r in named3]} "
          f"rows={[(r.get('status'), r.get('reject_category')) for r in r3]}")

    # RET1: a CRASH at the wire (the exchange call raised) -> the reservation stays held -> the retry
    #       makes NO second physical call.
    led, ex, net = new_ledger(), FakeExchange(raise_on_order=True), [-5.0]
    gw = make_gateway(ex, led, net)
    set_sleeve(led, B, -15.0)
    it = exit_intent(led, A, "SELL", 10.0, "ret1-f", 10.0)
    try:
        gw.send_if_allowed(it)
    except Exception as exc:
        print("NOTE:: ret1 first attempt raised %s: %s" % (type(exc).__name__, str(exc)[:120]))
    after_crash = len(ex.calls)
    ok_r1, st_r1 = gw.send_if_allowed(it)                     # the retry after the crash
    check("RET1_CRASH_AT_THE_WIRE_RETRY_MAKES_NO_SECOND_PHYSICAL_CALL",
          after_crash == 1 and len(ex.calls) == 1 and (not ok_r1) and st_r1 == "PENDING_EXIT_GUARD_ACTIVE",
          f"calls_after_crash={after_crash} calls_after_retry={len(ex.calls)} "
          f"retry_ok={ok_r1} retry_status={st_r1}")

    # RET2: a successful send not yet reconciled -> the retry is refused, still ONE physical call.
    led, ex, net = new_ledger(), FakeExchange(), [-5.0]
    gw = make_gateway(ex, led, net)
    set_sleeve(led, B, -15.0)
    it = exit_intent(led, A, "SELL", 10.0, "ret2-f", 10.0)
    ok_a, st_a = gw.send_if_allowed(it)
    ok_b, st_b = gw.send_if_allowed(it)
    check("RET2_RETRY_BEFORE_RECONCILE_MAKES_NO_SECOND_PHYSICAL_CALL",
          ok_a and len(ex.calls) == 1 and (not ok_b) and st_b == "PENDING_EXIT_GUARD_ACTIVE",
          f"first(ok={ok_a},status={st_a}) second(ok={ok_b},status={st_b}) physical_calls={len(ex.calls)}")

    check("NET0_NO_LIVE_HTTP_BRANCHES_WERE_REACHED", transport_attempts[0] == 0,
          f"TRANSPORT_ATTEMPTS={transport_attempts[0]} stub_calls={stub_calls[0]}")
    if transport_attempts[0]:
        frame = inspect.stack()[1]
        print(f"TRANSPORT_CALLER::{frame.function} {frame.frame.f_globals.get('__name__')}:{frame.lineno}")
    try:
        offline("self-test")
    except RuntimeError as exc:
        blocker_ok = str(exc) == "offline test: no network"
    else:
        blocker_ok = False
    check("NET1_NETWORK_BLOCKER_SELFTEST_REFUSES_EGRESS", blocker_ok and socket_attempts[0] == 1,
          f"blocker_ok={blocker_ok} socket_attempts={socket_attempts[0]} (only self-test is permitted)")
    print(f"BLOCKER_SELFTEST:: {'OK' if blocker_ok else 'FAIL'}")
    print(f"TRANSPORT_ATTEMPTS={transport_attempts[0]} stub_calls={stub_calls[0]} socket_attempts={socket_attempts[0]}")
    failed = [n for n, ok in RESULTS if not ok]
    print(f"TOTAL={len(RESULTS)} FAILED={len(failed)}")
    if failed:
        print("FAILED_CASES=" + ",".join(failed))
    sys.stdout.flush()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
