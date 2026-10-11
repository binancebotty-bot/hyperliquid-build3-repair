#!/usr/bin/env python3
"""GAP-1 (outage recovery) OFFLINE classifier.

The live run (process/PC_RUN_SCRIPTS_2026-10-11.md section 1) writes two windows
(an engine stop and an armed restart) and then classifies every leader fill in the
outage window against the engine's own audit rows. That classifier only needs two
things: the leader fills in the window and the audit CSVs. This script takes both
as FILES (copies), so the jump can be re-classified offline, any number of times,
without the engine, the network or the exchange.

Inputs (read-only):
  --audit-dir DIR    copies of send_attempts.csv / reconciliation.csv / order_intents.csv
                     (rotated reconciliation.2026*.csv / order_intents.2026*.csv are picked up too)
  --leader-fills F   JSON list of leader fills in the window:
                     [{"coin": "BTC", "dir": "Open Long", "wallet": "0x..", "hash": "0x..", "time": 1791705404255}, ...]
                     (produce it once with tools/cert/export_leader_fills.py, which is the only
                      network-touching step and is read-only)
  --stop-ms N        engine stop epoch ms (start of the outage window)
  --restart-ms N     armed restart epoch ms (end of the window)
  --blocked-coins    comma-separated coins blocked by design (symbol_blocklist); excluded from "missed"

Pass line (last line, exit 0):
  GAP1_RESULT:: PASS missed=0 duplicates=0 replay_last_s=<k> fills=<f> orders=<g>
FAIL (exit 1) when any leader order has no engine row ("missed") or any leader order
was sent twice ("duplicates"). INCONCLUSIVE (exit 3) when there are no leader fills
to classify. Baseline for comparison: run5/OUTAGE_RESULT_fc7efd7.txt (720 missed, 0
duplicated, median replay 215 s) and run5/OUTAGE_RESULT_5e88e89.txt (96 missed).

Offline: no network, no engine, no keys. Read-only inputs.
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cert_common as cc  # noqa: E402

TAG = 'GAP1_RESULT'


def load_fills(path):
    data = cc.load_json(path, [])
    if isinstance(data, dict):
        data = data.get('fills') or []
    if not isinstance(data, list):
        return None
    return [f for f in data if isinstance(f, dict) and f.get('hash')]


def index_audit(audit_dir):
    """leader_fill_id (the leader order hash) -> {file name -> [rows]}."""
    by_hash = collections.defaultdict(lambda: collections.defaultdict(list))
    for path in cc.audit_files(audit_dir):
        name = path.name
        for row in cc.load_rows(path):
            h = str(row.get('leader_fill_id') or '')
            if h:
                by_hash[h][name].append(row)
    return by_hash


def classify(fills, by_hash, blocked):
    """One outcome per leader order, exactly the run5/outage_outcomes.py taxonomy."""
    orders = collections.defaultdict(list)
    for f in fills:
        orders[(str(f.get('wallet') or '').lower(), str(f['hash']))].append(f)

    counts = collections.Counter()
    examples = collections.defaultdict(list)
    duplicates = []
    replay_ms = []

    for (wallet, h), group in orders.items():
        coin = str(group[0].get('coin') or '')
        files = by_hash.get(h, {})
        blob = ' '.join(' '.join(str(v) for v in r.values()) for rows in files.values() for r in rows)
        send_statuses = [r.get('status') for r in files.get('send_attempts.csv', [])]

        if coin.upper() in blocked:
            outcome = 'blocked coin (by design)'
        elif send_statuses.count('ORDER_FILLED') > 1:
            outcome = 'sent (filled)'
            duplicates.append((coin, wallet[:8], send_statuses))
        elif 'ORDER_FILLED' in send_statuses:
            outcome = 'sent (filled)'
        elif 'ORDER_RESTING' in blob:
            outcome = 'sent (resting limit)'
        elif 'ORDER_REJECTED' in blob:
            outcome = 'sent (refused by exchange)'
        elif 'MISSED_ENTRY_LEADER_ALREADY_CLOSED' in blob:
            outcome = 'skipped: leader already flat'
        elif 'NO_MANUAL_POSITION' in blob:
            outcome = 'skipped: close with no owned sleeve'
        elif 'UNOWNED_INVENTORY' in blob:
            outcome = 'blocked: UNOWNED_INVENTORY'
        elif 'BLOCKED_OFF' in blob:
            outcome = 'blocked: wallet OFF'
        elif files:
            outcome = 'other: ' + ','.join(sorted({(r.get('decision') or r.get('status') or r.get('event') or '?')
                                                   for rows in files.values() for r in rows}))[:60]
        else:
            outcome = 'no engine row (missed)'
        counts[outcome] += 1
        examples[outcome].append((coin, wallet[:8]))
        if outcome == 'no engine row (missed)':
            examples['no engine row (missed)'] = examples['no engine row (missed)'][-8:]

        for r in files.get('send_attempts.csv', []):
            ms = cc.as_int_ms(r.get('created_at_ms'), 0)
            if ms:
                replay_ms.append(ms)
    return orders, counts, examples, duplicates, replay_ms


def decide(missed, duplicates):
    return missed <= 0 and duplicates <= 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Offline outage-recovery classifier (GAP-1).')
    ap.add_argument('--audit-dir', required=True)
    ap.add_argument('--leader-fills', required=True)
    ap.add_argument('--stop-ms', type=int, default=0)
    ap.add_argument('--restart-ms', type=int, default=0)
    ap.add_argument('--blocked-coins', default='')
    args = ap.parse_args(argv)

    audit_dir = Path(args.audit_dir)
    if (audit_dir / 'append_only').is_dir():
        audit_dir = audit_dir / 'append_only'  # accept the engine state dir or the append_only dir itself
    if not audit_dir.is_dir():
        return cc.emit(TAG, cc.INCONCLUSIVE, 'audit_dir_not_found=%s' % audit_dir)

    fills = load_fills(args.leader_fills)
    if fills is None:
        return cc.emit(TAG, cc.INCONCLUSIVE, 'leader_fills_not_a_list=%s' % args.leader_fills)

    stop_ms = args.stop_ms or (min((cc.as_int_ms(f.get('time')) for f in fills), default=0))
    restart_ms = args.restart_ms or stop_ms
    blocked = {c.strip().upper() for c in args.blocked_coins.split(',') if c.strip()}

    orders, counts, examples, duplicates, replay_ms = classify(fills, index_audit(audit_dir), blocked)

    print('outage window %d..%d (%ds); leader fills in window: %d in %d orders across %d wallets'
          % (stop_ms, restart_ms, max(0, restart_ms - stop_ms) / 1000, len(fills), len(orders),
             len({k[0] for k in orders})))
    for name, n in counts.most_common():
        print('  %s: %d   e.g. %s' % (name, n, examples[name][:3]))
    print('  replayed twice (more than one filled send for one leader order): %d %s'
          % (len(duplicates), duplicates[:5]))

    replay_after = sorted(ms - restart_ms for ms in replay_ms if restart_ms and ms >= restart_ms)
    if replay_after:
        print('  replay sends after restart: first %.0fs, median %.0fs, last %.0fs'
              % (replay_after[0] / 1000, statistics.median(replay_after) / 1000, replay_after[-1] / 1000))

    if not fills:
        return cc.emit(TAG, cc.INCONCLUSIVE, 'no_leader_fills_in_window')

    missed = counts['no engine row (missed)']
    last_s = int(replay_after[-1] / 1000) if replay_after else 0
    ok = decide(missed, len(duplicates))
    detail = 'missed=%d duplicates=%d replay_last_s=%d fills=%d orders=%d' % (
        missed, len(duplicates), last_s, len(fills), len(orders))
    return cc.emit(TAG, cc.PASS if ok else cc.FAIL, detail)


if __name__ == '__main__':
    raise SystemExit(main())
