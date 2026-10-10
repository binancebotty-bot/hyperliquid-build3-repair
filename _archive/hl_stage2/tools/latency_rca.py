#!/usr/bin/env python3
"""Read-only latency breakdown from the engine's own audit files (no network, no keys, writes nothing).

Usage: python tools/latency_rca.py <append_only dir> [--since-utc 2026-10-10T00:00] > latency_rca.txt

Answers: where does the time between a leader fill and our order go?
  A. per intent source (WS_CAPTURED / POLL / CONVERGE / ...): how many, detection lag (intent created - leader fill time)
  B. per send outcome (sent, each block reason): rows, and WORKER TIME each consumed (send_decision_started ->
     send_attempt_written), plus queue_wait, gate time (intent_to_send_start), exchange_call_ms
  C. per hour: intents, real orders, ownership-gate blocks, p50/p90 leader->send
"""
import csv, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

csv.field_size_limit(10**9)
d = Path(sys.argv[1])
since = 0
if "--since-utc" in sys.argv:
    since = int(datetime.fromisoformat(sys.argv[sys.argv.index("--since-utc") + 1]).replace(tzinfo=timezone.utc).timestamp() * 1000)


def rows(name):
    p = d / name
    if not p.exists():
        print(f"(missing {p})"); return
    with open(p, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            yield r


def num(v):
    try: return float(v)
    except Exception: return None


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return int(xs[min(len(xs) - 1, int(len(xs) * q))]) if xs else None


def hour(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%m-%d %H:00")


src = defaultdict(int); per_hour = defaultdict(lambda: defaultdict(int)); intent_ms = {}
for r in rows("order_intents.csv"):
    t = num(r.get("created_at_ms")) or 0
    if t < since: continue
    intent_ms[r.get("intent_id")] = t
    s = r.get("source") or "?"
    src[s] += 1; per_hour[hour(t)]["intents"] += 1; per_hour[hour(t)]["intents_" + s] += 1

coin_busy = defaultdict(list)
lag = defaultdict(list); by_status = defaultdict(lambda: defaultdict(list)); l2s = defaultdict(list)
for r in rows("send_attempts.csv"):
    t = num(r.get("created_at_ms")) or 0
    if t < since: continue
    st = r.get("status") or "?"
    ws, lt, ic = num(r.get("ws_received_ms")), num(r.get("leader_fill_timestamp_ms")), num(r.get("intent_created_at_ms"))
    sd, sw = num(r.get("send_decision_started_ms")), num(r.get("send_attempt_written_ms"))
    b = by_status[st]
    if sw and sd:
        coin_busy[(r.get("coin") or "?").upper()].append(sw - sd)
    b["n"].append(1)
    b["worker_ms"].append(sw - sd if sw and sd else None)
    b["queue_wait_ms"].append(num(r.get("queue_wait_ms")))
    b["gate_ms"].append(num(r.get("intent_to_send_start_ms")))
    b["exchange_call_ms"].append(num(r.get("exchange_call_ms")))
    b["leader_to_intent_ms"].append(num(r.get("leader_to_intent_ms")))
    if ws and lt: lag["ws_received - leader_fill"].append(ws - lt)
    if r.get("exchange_order_id") or st.startswith("ORDER_"):
        per_hour[hour(t)]["orders"] += 1
        l2s[hour(t)].append(num(r.get("leader_to_send_attempt_ms")))
    if "OWNERSHIP_GATE" in st:
        per_hour[hour(t)]["gate_blocks"] += 1

print("A. intents by source:", dict(src))
for k, v in lag.items():
    print(f"   detection {k}: n={len(v)} p50={pct(v,.5)} p90={pct(v,.9)} p99={pct(v,.99)} ms")
print("\nB. send outcomes (worker_ms = time a send worker was busy on that row)")
print(f"   {'status':52} {'rows':>7} {'worker_s_total':>14} {'worker p50/p90':>16} {'queue p50/p90':>18} {'gate p50/p90':>14} {'exch p50/p90':>14} {'l2i p50/p90':>18}")
tot = sum(sum(x for x in b['worker_ms'] if x) for b in by_status.values()) or 1
for st, b in sorted(by_status.items(), key=lambda kv: -sum(x for x in kv[1]['worker_ms'] if x)):
    w = [x for x in b["worker_ms"] if x is not None]
    f = lambda k: f"{pct(b[k],.5)}/{pct(b[k],.9)}"
    print(f"   {st[:52]:52} {len(b['n']):>7} {sum(w)/1000:>10.0f} ({100*sum(w)/tot:>2.0f}%) {f('worker_ms'):>16} {f('queue_wait_ms'):>18} {f('gate_ms'):>14} {f('exchange_call_ms'):>14} {f('leader_to_intent_ms'):>18}")
print("\nC. per hour: intents (by source), orders, ownership-gate blocks, leader->send p50/p90 ms")
for h in sorted(per_hour):
    ph = per_hour[h]
    srcs = ",".join(f"{k[8:]}={v}" for k, v in sorted(ph.items()) if k.startswith("intents_"))
    print(f"   {h}  intents={ph['intents']} ({srcs})  orders={ph['orders']}  gate_blocks={ph['gate_blocks']}  l2s={pct(l2s[h],.5)}/{pct(l2s[h],.9)}")
rec = defaultdict(int); held = defaultdict(list)
for r in rows("reconciliation.csv"):
    t = num(r.get("created_at_ms")) or 0
    if t >= since:
        k = (r.get("event") or "?") + ":" + (r.get("status") or "?")
        rec[k] += 1
        i = intent_ms.get(r.get("intent_id"))
        if i: held[k].append(t - i)   # intent written -> block written: worker time spent deciding to block
print("\nD. top reconciliation rows (held = ms from intent written to this row, i.e. worker time spent on a block)")
for k, v in sorted(rec.items(), key=lambda kv: -kv[1])[:30]:
    h = held.get(k, [])
    print(f"   {v:>8}  {k[:70]:70}  held_total_s={sum(h)/1000:.0f} p50={pct(h,.5)} p90={pct(h,.9)}")

import hashlib
print("\nE. send-worker busy time by coin and by worker shard (4 workers; sha1(coin) % 4 as in the engine)")
shard = defaultdict(float)
for coin, v in coin_busy.items():
    key = coin
    shard[int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) % 4] += sum(v)
for k in sorted(shard): print(f"   worker {k+1}: busy {shard[k]/1000:.0f} s")
for coin, v in sorted(coin_busy.items(), key=lambda kv: -sum(kv[1]))[:15]:
    print(f"   {coin:14} sends={len(v):>6} busy={sum(v)/1000:>7.0f} s")
