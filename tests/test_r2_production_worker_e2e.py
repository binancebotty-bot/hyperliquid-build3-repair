"""R2 execution-oriented production queue/worker/intent/sender contract tests.

The methods under test are compiled unmodified from LiveCopyCore in the checked
out production file. Dependencies that would contact exchanges are in-memory
spies. Do not mistake fake exchange timings for actual network performance.
"""
from __future__ import annotations

import ast
import csv
import math
import os
import queue
import statistics
import threading
import time
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

CORE = Path(__file__).resolve().parents[1] / "_archive/hl_stage2/HL_Live_Copy_Service_Core.py"
TREE = ast.parse(CORE.read_text(encoding="utf-8-sig"))
CLASS = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == "LiveCopyCore")

METHODS = (
    "_dispatch_fill", "_release_queued", "hot_backlog",
    "drain_startup_hot_queue", "_hot_send_loop_inner", "_plan_batch",
    "_run_plan", "_drain_priority", "_drain_priority_inner", "_coin_lock",
    "_process_leader_fill", "_process_leader_fill_inner",
    "_apply_missed_entry_rule_on_refusal",
)
nodes = [next(n for n in CLASS.body if isinstance(n, ast.FunctionDef) and n.name == key)
         for key in METHODS]
RECON_FIELDS = ["created_at", "created_at_ms", "event", "status", "leader_wallet",
                "leader_fill_id", "coin", "action", "notes"]
events_lock = threading.Lock()
errors = []


def append_csv(path, fields, data, durable=False):
    assert durable is True, "overflow must be persisted"
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with events_lock:
        new_file = not p.exists()
        with p.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            if new_file:
                writer.writeheader()
            writer.writerow(data)
            f.flush()
            os.fsync(f.fileno())
    return True


def now_ms():
    return int(time.time() * 1000)


def stamp_fill(fill, key):
    fill.raw.setdefault("_stamps", {})[key] = now_ms()


def log_error(*args):
    errors.append(args)


scope = {
    "Any": object, "Dict": dict, "List": list, "Tuple": tuple, "Optional": object,
    "LeaderFill": NS, "CycleSummary": NS, "Intent": NS,
    "time": time, "os": os, "queue": queue, "threading": threading,
    "math": math, "Path": Path,
    "fnum": lambda v, default=0.0: float(v if v is not None else default),
    "canonical_coin_key": lambda coin: str(coin).upper(),
    "normalise_wallet": lambda wallet: str(wallet).lower(),
    "utc_now_ms": now_ms,
    "utc_now_iso": lambda: "2026-11-09T00:00:00Z",
    "stamp_fill": stamp_fill, "log_error": log_error,
    "append_csv": append_csv,
    "RECONCILIATION_CSV": None,
    "RECONCILIATION_FIELDS": RECON_FIELDS,
    "_EARLY_WARM_POOL": NS(submit=lambda *args, **kw: None),
    "classify_send_lifecycle": lambda intent: intent.lifecycle,
    "stale_snapshot_replay_reason": lambda fill: "",
    "follower_entry_exclusion": lambda *args, **kwargs: ("", ""),
    "ENTRY_MAX_AGE_MS": 30_000,
    "MISSED_ENTRY_INCIDENT_EVENT": "MISSED_ENTRY_INCIDENT",
    "PROCESS_STARTED_AT_MS": now_ms(),
    "STALE_REPLAY_GRACE_MS": 0,
    "COPY_MATCH_WINDOW_MS": 0,
    "mergeable_fills": lambda *_: False,
    "merge_leader_fills": lambda batch: batch[0],
    "prof": lambda *_: __import__("contextlib").nullcontext(),
}
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(CORE), "exec"), scope)


class Journal:
    def __init__(self):
        self.rows = []
        self.intents = []
    def append_reconciliation(self, event, status, **kw):
        self.rows.append((event, status, kw))
    def append_order_intent(self, intent):
        self.intents.append(intent)
    def has_fill_row(self, fid):
        return any(row[2].get("leader_fill_id") == fid for row in self.rows)


class FakeSender:
    def __init__(self, host):
        self.host = host
        self._market_halted_until_ms = {}
        self.orders = []
        self.remedies = []
    def known_dispatch_reject(self, fill):
        return ""
    def cancel_resting_entries_against(self, fill):
        return []
    def _missed_entry_rest_or_diff(self, intent, cause):
        # Physical send must not have been pre-marked before the reoffer.
        assert self.host._guard_key(intent.fill) not in self.host._past_send_keys
        self.remedies.append((intent.fill.leader_fill_id, cause))
        self.orders.append(("MISSED_REOFFER", intent.fill.leader_fill_id, now_ms()))
        return {"outcome": "MISSED_ENTRY_RESTED", "notes": "offline order spy",
                "wallet_alias": intent.fill.leader_wallet}
    def send_if_allowed(self, intent, block=""):
        self.orders.append(("PHYSICAL_SEND", intent.fill.leader_fill_id, now_ms()))
        return True, "ORDER_SENT"


class Harness:
    pass


for name in METHODS:
    setattr(Harness, name, scope[name])


def create_harness(reconciliation, capacity=384):
    h = Harness()
    h._hot_queues = [queue.Queue(maxsize=capacity)]
    h._prio_queues = [queue.Queue(maxsize=96)]
    h._entry_slots = threading.BoundedSemaphore(capacity)
    h._close_slots = threading.BoundedSemaphore(96)
    h._queued_lock = threading.RLock()
    h._queued_keys = set()
    h._pending_ts = {}
    h._pending_seen = {}
    h._pending_rowed = set()
    h._queue_slot_kind = {}
    h._coin_lane = {}
    h._converge_queued = set()
    h._coin_locks = {}
    h._coin_locks_guard = threading.Lock()
    h._idem_lock = threading.Lock()
    h._idem_accepted = set()
    h._idem_duplicate_audited = set()
    h._past_send_keys = set()
    h._send_lock = threading.RLock()
    h._hot_stop_event = threading.Event()
    h._deferred_lock = threading.Lock()
    h._deferred = {}
    h._inflight = {}
    h._stuck_dumped = set()
    h._entry_sends_blocked_reason = ""
    h._intent_inserts = 0
    h.intents_by_id = {}
    h.audit = Journal()
    h.ws = NS(queue=queue.Queue())
    h.cfg = NS(config={}, max_order_notional=lambda: 100,
               marketable_bps=lambda: 100,
               copy_mode=lambda wallet: "fixed",
               wallet_enabled=lambda wallet: True,
               wallet_mode=lambda wallet: "ON")
    h.ledger = NS(data={}, classify_leader_side_for_wallet=lambda w,c,side:
                  ("EXIT" if side == "SELL" else "ENTRY", None))
    h.dedupe = NS(live_start_ms=0, processed=set(), accept_leader=lambda fid: True)
    def build(fill):
        return NS(fill=fill, intent_id="intent-" + fill.leader_fill_id,
                  created_at_ms=now_ms(), lifecycle=("EXIT" if fill.side == "SELL" else "ENTRY"),
                  reason="", copy_size=1.0, send_allowed=True, decision="ALLOW")
    h.intent_builder = NS(cfg=h.cfg, build=build,
                          blocked_locally=lambda *a, **k: "",
                          _copy_notional=lambda *a: 1.0)
    h.sender = FakeSender(h)
    h._fill_trace = lambda *a, **k: None
    h._already_handled = lambda f: False
    h._guard_key = lambda f: f.leader_fill_id
    h._is_close_fill = lambda f: f.side == "SELL"
    h._shard = lambda f: 0
    h._prewarm_with_parity = lambda *a: None
    h._read_fills_of_withdrawn_limits = lambda *a: None
    h._apply_fills_of_withdrawn_limits = lambda *a: None
    h._defer_unreadable_truth = lambda *a: False
    h._rows_for_merged_siblings = lambda *a: None
    def fatal(fill, exc):
        errors.append((fill.leader_fill_id, exc))
    h._terminal_after_exception = fatal
    scope["RECONCILIATION_CSV"] = reconciliation
    return h


def fill(i, *, stale=False, close=False):
    return NS(leader_wallet="wallet", coin=f"C{i % 20}", side="SELL" if close else "BUY",
              leader_fill_id=f"fill-{i}", timestamp_ms=now_ms() - (60_000 if stale else 0),
              source="POLL", price=1.0, size=1.0, raw={})


def launch_worker(h):
    thread = threading.Thread(target=h._hot_send_loop_inner, args=(0,), daemon=True)
    thread.start()
    return thread


def shutdown(h, worker):
    h._hot_stop_event.set()
    worker.join(3)
    assert not worker.is_alive(), "production worker failed to stop"
    assert not errors, f"production worker raised: {errors!r}"


def test_production_worker_stale_entry_reoffers_without_premark(tmp_path, monkeypatch):
    errors.clear()
    monkeypatch.setenv("HL_LIVE_HOT_INNER", "1")
    h = create_harness(tmp_path / "reconcile.csv")
    worker = launch_worker(h)
    stale = fill(1, stale=True)
    assert h._dispatch_fill(stale) is True
    assert h.drain_startup_hot_queue(timeout_sec=5)
    shutdown(h, worker)
    assert h.sender.remedies == [(stale.leader_fill_id, "ORD_010_ENTRY_AGE_OVER_30S")]
    assert len(h.sender.orders) == 1 and h.sender.orders[0][:2] == ("MISSED_REOFFER", stale.leader_fill_id)
    assert not h._past_send_keys
    assert len(h.audit.intents) == 1


def test_overflow_persisted_and_reoffered_from_fresh_source_reader(tmp_path, monkeypatch):
    errors.clear()
    monkeypatch.setenv("HL_LIVE_HOT_INNER", "1")
    audit = tmp_path / "reconcile.csv"
    source = tmp_path / "leader_feed.csv"
    with source.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "side"])
        w.writeheader()
        for i in range(5):
            w.writerow({"id": i, "side": "SELL" if i == 4 else "BUY"})
    old = create_harness(audit, capacity=2)
    attempted = {}
    with source.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            i = int(row["id"])
            attempted[i] = old._dispatch_fill(fill(i, close=i == 4))
    assert [i for i, ok in attempted.items() if ok is False] == [2, 3]
    assert attempted[4] is True, "close must survive full entry queue"
    with audit.open(newline="", encoding="utf-8") as f:
        durable = list(csv.DictReader(f))
    assert len(durable) == 2 and all(r["status"] == "HOT_QUEUE_CAP_RETRY" for r in durable)
    # Simulate restart: new object and fresh re-read of a real persisted feed.
    restarted = create_harness(audit, capacity=5)
    worker = launch_worker(restarted)
    with source.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            i = int(row["id"])
            if i in (2, 3, 4):
                assert restarted._dispatch_fill(fill(i, close=i == 4))
    assert restarted.drain_startup_hot_queue(timeout_sec=5)
    shutdown(restarted, worker)
    sent = {order[1] for order in restarted.sender.orders}
    assert {"fill-2", "fill-3", "fill-4"}.issubset(sent)
    assert restarted.hot_backlog() == 0


def test_restart_drain_retains_close_and_reaches_idle(tmp_path, monkeypatch):
    errors.clear()
    monkeypatch.setenv("HL_LIVE_HOT_INNER", "1")
    old = create_harness(tmp_path / "reconcile.csv", capacity=2)
    assert old._dispatch_fill(fill(10))
    assert old._dispatch_fill(fill(11))
    assert old._dispatch_fill(fill(12, close=True))
    # Persist the independent source feed, then re-open from disk in a fresh object.
    source = tmp_path / "restart_source.csv"
    with source.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["id", "side"])
        writer.writeheader()
        for i in (10, 11, 12):
            writer.writerow({"id": i, "side": "SELL" if i == 12 else "BUY"})
    new = create_harness(tmp_path / "reconcile.csv", capacity=5)
    worker = launch_worker(new)
    with source.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            i = int(row["id"])
            assert new._dispatch_fill(fill(i, close=row["side"] == "SELL"))
    assert new.drain_startup_hot_queue(timeout_sec=5)
    shutdown(new, worker)
    assert new.hot_backlog() == 0
    assert not new._queued_keys and not new._inflight and not new._deferred
    assert "fill-12" in {item[1] for item in new.sender.orders}


@pytest.mark.host_benchmark
def test_physical_send_latency_p95_5217_fill_load(tmp_path, monkeypatch):
    errors.clear()
    monkeypatch.setenv("HL_LIVE_HOT_INNER", "1")
    h = create_harness(tmp_path / "reconcile.csv", capacity=384)
    worker = launch_worker(h)
    emitted = {}
    count = 5217
    for i in range(count):
        item = fill(i)
        emitted[item.leader_fill_id] = now_ms()
        # Source is retained until the production admission accepts the fill.
        deadline = time.monotonic() + 20
        while h._dispatch_fill(item) is False:
            assert time.monotonic() < deadline, "overflow source never reoffered"
            time.sleep(.001)
    assert h.drain_startup_hot_queue(timeout_sec=60)
    shutdown(h, worker)
    durations = [at - emitted[fid] for kind, fid, at in h.sender.orders
                 if kind == "PHYSICAL_SEND" and fid in emitted]
    assert len(durations) == count, f"physical sends={len(durations)} expected={count}"
    p95 = sorted(durations)[math.ceil(.95 * len(durations)) - 1]
    print(f"R2_HOST_PHYSICAL_SEND_P95_MS={p95}; N={len(durations)}")
    assert p95 <= 2000, f"p95 physical-send latency {p95} ms exceeds 2000 ms"
