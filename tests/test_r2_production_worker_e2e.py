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
import typing
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
    "Any": typing.Any, "Dict": typing.Dict, "List": typing.List, "Tuple": typing.Tuple, "Optional": typing.Optional, "Callable": typing.Callable,
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

# Compile the production IntentBuilder.build and decision methods, not a test
# lambda that constructs invented intents. Exchange exposure is isolated at its
# leaf read so production sizing/decision/lifecycle code still executes.
BUILDER_CLASS = next(n for n in TREE.body
                     if isinstance(n, ast.ClassDef) and n.name == "IntentBuilder")
BUILDER_METHODS = ("build", "_decision", "_copy_notional", "_order_value_px",
                   "_is_leader_close_fill")
builder_nodes = [next(n for n in BUILDER_CLASS.body
                      if isinstance(n, ast.FunctionDef) and n.name == name)
                 for name in BUILDER_METHODS]
class IntentRecord(NS):
    @property
    def send_allowed(self):
        return self.decision in {"ENTRY_ALLOWED", "EXIT_ALLOWED"}
    @property
    def lifecycle(self):
        return "EXIT" if self.reduce_only_intended else (
            "ADD" if str(self.notes).startswith("lifecycle=ADD") else "ENTRY")

scope["Intent"] = IntentRecord
scope["_CAP_TLS"] = threading.local()
scope["POSITION_EPSILON"] = 1e-8
scope["FOLLOWER_NETWORK"] = "testnet"
scope["follower_mid"] = lambda coin, force=False: 1.0
scope["stable_hash"] = lambda fields: "-".join(map(str, fields))
scope["is_spot_pair"] = lambda coin: False
scope["bval"] = lambda value, default=False: bool(value) if value is not None else default
builder_scope = scope
exec(compile(ast.Module(body=builder_nodes, type_ignores=[]), str(CORE), "exec"), builder_scope)

class ProductionIntentBuilder:
    _exit_chain_event_target = lambda self, *a: None
    _leader_close_fraction = lambda self, *a: 1.0
    build = builder_scope["build"]
    _decision = builder_scope["_decision"]
    _copy_notional = builder_scope["_copy_notional"]
    _order_value_px = builder_scope["_order_value_px"]
    _is_leader_close_fill = staticmethod(builder_scope["_is_leader_close_fill"])
    _exposure_cap_block = lambda self, *a, **k: ""
    _trace_exposure_cap = lambda self, *a, **k: None

    def __init__(self, cfg, ledger):
        self.cfg, self.ledger = cfg, ledger
        self._exit_chain = {}
        self._sizing_block = {}
        self._coin_activity = {}
    def blocked_locally(self, fill, entry_block_reason=""):
        return ""


# Use the actual production SenderGateway wire boundary, with a no-network
# exchange spy. Only external exchange truth/risk collaborators are stubbed.
SENDER_CLASS = next(n for n in TREE.body
                    if isinstance(n, ast.ClassDef) and n.name == "SenderGateway")
WIRE_METHODS = ("_place_order", "_place_order_impl", "_missed_entry_rest_or_diff")
wire_nodes = [next(n for n in SENDER_CLASS.body
                   if isinstance(n, ast.FunctionDef) and n.name == name)
              for name in WIRE_METHODS]
wire_scope = dict(scope)
wire_scope.update({
    "FOLLOWER_NETWORK": "testnet", "MAINNET_ORDERS_CONFIRMED": False,
    "_sender_lease_owned": lambda: True,
    "_sdk_cloid": lambda x: x, "_exchange_accepts_cloid": lambda ex: False,
    "_open_orders_send_begin": lambda: None, "_open_orders_send_end": lambda: None,
    "PreWireNoCallFault": type("PreWireNoCallFault", (Exception,), {}),
    "PendingSendWriteFailed": type("PendingSendWriteFailed", (Exception,), {}),
})
exec(compile(ast.Module(body=wire_nodes, type_ignores=[]), str(CORE), "exec"), wire_scope)
# Production missed-entry policy (not a test-supplied recovery decision).
RECOVERY_FN = next(n for n in TREE.body
                   if isinstance(n, ast.FunctionDef) and n.name == "missed_entry_decision")
wire_scope["FOLLOWER_NETWORK"] = "testnet"
wire_scope["LEADER_NETWORK"] = "testnet"
wire_scope["follower_mid"] = lambda coin, force=False: 1.0
wire_scope["classify_send_lifecycle"] = lambda intent: intent.lifecycle
wire_scope["json"] = __import__("json")
wire_scope["sys"] = __import__("sys")
wire_scope["classify_reject_category"] = lambda *args: ""
wire_scope["classify_operator_action"] = lambda *args: ""
wire_scope["update_send_attempt_row"] = lambda *args, **kw: True
exec(compile(ast.Module(body=[RECOVERY_FN], type_ignores=[]), str(CORE), "exec"), wire_scope)



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


class OrderSpy:
    def __init__(self, sender):
        self.sender = sender
    def order(self, *args, **kw):
        self.sender.orders.append((self.sender._wire_label,
                                   self.sender._current_fill_id, now_ms()))
        return {"status": "ok", "response": {"type": "order", "data":
                {"statuses": [{"resting": {"oid": 123}}]}}}


class FakeSender:
    _missed_entry_rest_or_diff = wire_scope["_missed_entry_rest_or_diff"]
    _place_order = wire_scope["_place_order"]
    _place_order_impl = wire_scope["_place_order_impl"]
    _master_gate_reason = lambda self, *a, **kw: ""
    _wire_entry_exposure_block = lambda self, *a, **kw: ""
    _final_close_proof = lambda self, *a, **kw: ""
    _reduce_only_for_intent = lambda self, intent: intent.lifecycle == "EXIT"
    _reserve_exchange_order_slot = lambda self, **kw: now_ms()
    _gate_refusal_row = lambda self, *a, **kw: None
    _journal_authorised_close_refusal = lambda self, *a, **kw: None
    _note_sender_key_rejection = lambda self, *a, **kw: None

    def __init__(self, host):
        self.host = host
        self._market_halted_until_ms = {}
        self._wire_cap_lock = threading.RLock()
        self.orders = []
        self.remedies = []
        self._physical_exchange = OrderSpy(self)

    def _send_to_wire(self, intent, label):
        self._wire_label = label
        self._current_fill_id = intent.fill.leader_fill_id
        result = self._place_order(self._physical_exchange, intent.fill.coin, True,
                                   1.0, 1.0, "Ioc", intent.lifecycle == "EXIT",
                                   timing={}, intent=intent, path="R2_TEST_OFFLINE")
        assert result["status"] == "ok"

    def known_dispatch_reject(self, fill):
        return ""
    def cancel_resting_entries_against(self, fill):
        return []
    # Only external SDK/metadata/ledger I/O are test doubles. The branch and
    # _place_order invocation are executed by production missed-entry recovery.
    _base_timing = lambda self, intent: {}
    _resolve_coin = lambda self, coin: {
        "ok": True, "snapshot_only": False, "sdk_order_compatible": True,
        "sz_decimals": 4, "price_max_decimals": 4}
    _floor_wire_size = staticmethod(lambda size, decimals: round(size, decimals))
    resting_entry_for = lambda self, *a: None
    _exchange_client_for_coin = lambda self, coin: (self._physical_exchange, coin)
    _ensure_margin_mode = lambda self, *a, **k: None
    _format_limit_px = staticmethod(lambda px, dec: round(px, dec))
    _px_passive = staticmethod(lambda px, dec, buy: round(px, dec))
    _pre_exchange_asset_safety = lambda self, *a: (True, {})
    _pre_send_ownership_gate = lambda self, *a: (True, {})
    _parse_hl_response = staticmethod(lambda response: (True, "ORDER_RESTING", "123", ""))
    _register_resting_entry = lambda self, *a: None

    def _recovery_send_hooks(self, intent, tif, order_type, px, size, reduce_only,
                             timing, label):
        assert self.host._guard_key(intent.fill) not in self.host._past_send_keys, (
            "stale ENTRY marked as a physical send before production recovery")
        self.remedies.append((intent.fill.leader_fill_id, "ORD_010_ENTRY_AGE_OVER_30S"))
        self._wire_label = "MISSED_REOFFER"
        self._current_fill_id = intent.fill.leader_fill_id
        return "", None
    def send_if_allowed(self, intent, block=""):
        self._send_to_wire(intent, "PHYSICAL_SEND")
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
               wallet_mode=lambda wallet: "ON",
               fixed_notional=lambda wallet: 1.0,
               min_notional=lambda: 0.1,
               is_symbol_allowed=lambda coin: (True, ""),
               max_wallet_exposure=lambda wallet: 0.0,
               max_total_exposure=lambda: 0.0,
               max_asset_directional_exposure=lambda: 0.0,
               auto_send_enabled=False)
    h.ledger = NS(data={}, classify_leader_side_for_wallet=lambda w,c,side:
                  ("EXIT" if side == "SELL" else "ENTRY", side == "SELL"),
                  sleeve_id=lambda w,c: w + ":" + c,
                  wallet_coin_position=lambda w,c: 1.0 if c == "C12" else 0.0,
                  direction_from_size=lambda x: "LONG" if x > 0 else "SHORT" if x < 0 else "FLAT",
                  signed_delta=lambda side, size: size if side == "BUY" else -size,
                  position_id=lambda w,c,d,i: "pos-" + i,
                  coin_net=lambda coin: 0.0,
                  sleeve=lambda w,c: {"position_id": "pos-previous"},
                  wallet_abs_exposure_usd=lambda *a: 0.0)
    h.dedupe = NS(live_start_ms=0, processed=set(), accept_leader=lambda fid: True)
    h.intent_builder = ProductionIntentBuilder(h.cfg, h.ledger)
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
    assert sum(ok is False for ok in attempted.values()) == 2
    assert attempted[4] is True, "close must survive full entry queue"
    with audit.open(newline="", encoding="utf-8") as f:
        durable = list(csv.DictReader(f))
    assert len(durable) == 2 and all(r["status"] == "HOT_QUEUE_CAP_RETRY" for r in durable)
    # Simulate restart: new object and fresh re-read of a real persisted feed.
    restarted = create_harness(audit, capacity=5)
    worker = launch_worker(restarted)
    # The fsynced retry journal is authoritative: derive retry keys from it
    # (no hard-coded overflow IDs or guesses from the independent source).
    retry_ids = [row["leader_fill_id"] for row in durable
                 if row["status"] == "HOT_QUEUE_CAP_RETRY"]
    assert retry_ids and len(retry_ids) == len(set(retry_ids))
    recorded = {}
    with source.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            recorded["fill-" + row["id"]] = (int(row["id"]), row["side"] == "SELL")
    assert all(key in recorded for key in retry_ids), "retry evidence missing source fill"
    for key in retry_ids:
        i, close = recorded[key]
        assert restarted._dispatch_fill(fill(i, close=close))
    # Close was admitted to the priority lane rather than overflow. Retain and
    # replay it independently of the journal's ENTRY retry set.
    priority_closes = [key for key, (i, close) in recorded.items()
                       if close and key not in retry_ids]
    for key in priority_closes:
        i, close = recorded[key]
        assert restarted._dispatch_fill(fill(i, close=close))
    assert restarted.drain_startup_hot_queue(timeout_sec=5)
    shutdown(restarted, worker)
    sent = {order[1] for order in restarted.sender.orders}
    assert set(retry_ids + priority_closes).issubset(sent)
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
