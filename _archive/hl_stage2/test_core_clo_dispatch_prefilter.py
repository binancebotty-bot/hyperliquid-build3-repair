#!/usr/bin/env python3
"""Offline contract for the CLO pure-entry dispatch filter."""
import csv
import json
import os
import queue
import sys
import tempfile
import threading
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="clo_dispatch_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent",
                   "HL_LEADER_NETWORK": "testnet", "HL_FOLLOWER_NETWORK": "testnet",
                   "HL_LIVE_EARLY_PREWARM": "0"})
import HL_Live_Copy_Service_Core as c

R = []


class WarmPool:
    def __init__(self):
        self.submitted = []

    def submit(self, fn, *args, **kwargs):
        self.submitted.append((fn, args, kwargs))


warm_pool = WarmPool()
c._EARLY_WARM_POOL = warm_pool
os.environ["HL_LIVE_EARLY_PREWARM"] = "1"


def check(name, ok, detail=""):
    R.append(bool(ok))
    print("RESULT::%s_%s%s" % (name, "PASS" if ok else "FAIL", (" | " + str(detail)) if detail and not ok else ""))


CLO = "0x" + "a" * 40
LIVE = "0x" + "b" * 40


class Config:
    modes = {CLO: "CLO", LIVE: "ON"}

    def wallet_mode(self, wallet):
        return self.modes.get(wallet, "OFF")

    def wallet_enabled(self, wallet):
        return True

    def copy_mode(self, wallet):
        return "fixed"

    def fixed_notional(self, wallet):
        return 12.0


cfg = Config()
core = c.LiveCopyCore.__new__(c.LiveCopyCore)
core.intent_builder = SimpleNamespace(cfg=cfg)
core.audit = c.AuditLogWriter()
core.dedupe = c.DedupeStore()
core.ledger = SimpleNamespace(classify_leader_side_for_wallet=lambda _w, _coin, _side: ("EXIT", True)
                              if str(_side).upper() == "SELL" else ("ENTRY", False))
core._idem_lock = threading.Lock()
core._idem_accepted = set()
core._idem_duplicate_audited = set()
core._queued_lock = threading.Lock()
core._queued_keys = set()
core._pending_ts = {}
core._pending_seen = {}
core._coin_lane = {}
core._hot_queues = [queue.Queue(maxsize=50000)]
core._hot_queue = core._hot_queues[0]
core._prio_queues = [queue.Queue(maxsize=50000)]
core.sender = SimpleNamespace(known_dispatch_reject=lambda _fill: "")
core._fill_trace_condition = threading.Condition()
core._fill_trace_buffer = deque()
core._fill_trace_dropped = 0
core._fill_trace_writer_done = False
trace_writer = threading.Thread(target=core._fill_trace_writer_loop, daemon=True)
trace_writer.start()


def fill(fid, wallet, direction, side):
    raw = {"dir": direction} if direction is not None else {}
    return c.LeaderFill(fid, wallet, "BTC", side, 100.0, 0.12, c.utc_now_ms(), "WS_CAPTURED", 0, raw)


# A 500-fill CLO burst should be audited at dispatch without occupying either worker queue.
dispatch_results = []
for i in range(500):
    direction, side = (("Open Long", "BUY") if i % 2 == 0 else ("Open Short", "SELL"))
    dispatch_results.append(core._dispatch_fill(fill("clo-%d" % i, CLO, direction, side)))
c.flush_intent_writer(30.0)  # the intent audit rows are written behind the dispatch by the writer thread
rows = []
if c.ORDER_INTENTS_CSV.exists():
    with c.ORDER_INTENTS_CSV.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
check("CLO_BURST_NOT_QUEUED", core._hot_queues[0].qsize() == 0 and core._prio_queues[0].qsize() == 0,
      (core._hot_queues[0].qsize(), core._prio_queues[0].qsize()))
check("CLO_DISPATCH_REPORTS_NOT_QUEUED", dispatch_results == [None] * 500)
check("CLO_BURST_ONE_BLOCK_ROW_PER_FILL", len(rows) == 500 and all(
      r["decision"] == "BLOCKED_CLO_ENTRY" and r["reason"] == "CLO blocks entries/adds" for r in rows), len(rows))
check("CLO_AUDIT_SCHEMA_UNCHANGED", set(rows[0]) == set(c.ORDER_INTENT_FIELDS) if rows else False,
      tuple(rows[0]) if rows else ())
trace_path = c.AUDIT_DIR / "fill_trace.jsonl"
deadline = time.monotonic() + 5
trace_rows = []
while time.monotonic() < deadline:
    if trace_path.exists():
        trace_rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        if len([r for r in trace_rows if r.get("k") == "blocked_clo_entry_dispatch"]) == 500:
            break
    time.sleep(0.01)
check("CLO_DIR_RETAINED_IN_AUDIT_AND_TRACE",
      len(rows) == 500 and all('leader_dir_json="Open Long"' in rows[i]["notes"] if i % 2 == 0
                               else 'leader_dir_json="Open Short"' in rows[i]["notes"] for i in range(500))
      and len(warm_pool.submitted) == 0 and core._coin_lane == {} and core._pending_ts == {}
      and len([r for r in trace_rows if r.get("k") == "blocked_clo_entry_dispatch"
               and r.get("dir") in {"Open Long", "Open Short"}]) == 500)

# Five live exits and five live entries then pass to the send boundary with no CLO backlog ahead of them.
live_fills = [fill("live-exit-%d" % i, LIVE, "Close Long", "SELL") for i in range(5)]
live_fills += [fill("live-entry-%d" % i, LIVE, "Open Long", "BUY") for i in range(5)]
for f in live_fills:
    core._dispatch_fill(f)
worker_send_handler = []
core._process_leader_fill = lambda f, *_args: worker_send_handler.append(f.leader_fill_id)
while not core._prio_queues[0].empty():
    core._process_leader_fill(core._prio_queues[0].get_nowait())
while not core._hot_queues[0].empty():
    core._process_leader_fill(core._hot_queues[0].get_nowait())
check("LIVE_TEN_REACH_WORKER_SEND_HANDLER", len(worker_send_handler) == 10 and
      set(worker_send_handler) == {"live-exit-%d" % i for i in range(5)} | {"live-entry-%d" % i for i in range(5)}, worker_send_handler)

# Only exact pure-entry dirs are filtered. CLO closes, flips, unknown dirs, and a mode change all use the queue.
core._dispatch_fill(fill("clo-close", CLO, "Close Long", "SELL"))
core._dispatch_fill(fill("clo-flip", CLO, "Long > Short", "SELL"))
core._dispatch_fill(fill("clo-unknown", CLO, "Something Else", "BUY"))
core._dispatch_fill(fill("clo-missing", CLO, None, "BUY"))
core._dispatch_fill(fill("clo-case-variant", CLO, "open long", "BUY"))
cfg.modes[CLO] = "ON"
core._dispatch_fill(fill("mode-changed", CLO, "Open Long", "BUY"))
normal_path = []
for q in (core._prio_queues[0], core._hot_queues[0]):
    while not q.empty():
        normal_path.append(q.get_nowait().leader_fill_id)
check("CLO_CLOSE_FLIP_UNKNOWN_AND_NEXT_MODE_NORMAL", set(normal_path) ==
      {"clo-close", "clo-flip", "clo-unknown", "clo-missing", "clo-case-variant", "mode-changed"}, normal_path)

with core._fill_trace_condition:
    core._fill_trace_writer_done = True
    core._fill_trace_condition.notify_all()
trace_writer.join(timeout=2)

print("TOTAL=%d FAILED=%d" % (len(R), R.count(False)))
sys.exit(1 if False in R else 0)
