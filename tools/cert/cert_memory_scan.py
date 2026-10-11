#!/usr/bin/env python3
"""GAP-2 (memory flat on current main) OFFLINE read-cost check.

The live half of GAP-2 samples the engine's RSS for 60-120 min (file sizes a busy
day produces are what decides it). The offline half - the M1 profile's finding - is
measurable here with no engine at all: parse COPIES of the audit CSVs through the
engine's OWN readers and look for a whole-file read where a bounded tail read
exists. The J4 pass line (process/PC_RUN_SCRIPTS_2026-10-11.md section 2) is:

    offline: no row with retained_mb > 10 and no row with rss_delta_mb > 15

Two readers exist in HL_Live_Copy_Service_Core.py and both are measured:
  read_csv_rows(path)            whole file into bytes -> text -> every row (L1221)
  read_csv_tail_rows(path, n)    header + last n bytes, bounded, whole rows only (L1198)

The whole-file reader is the remaining GAP-2 driver from M1: any call site that uses
it on reconciliation.csv (hundreds of MB after a busy day) re-materialises the file
every cycle. A FAIL here on a large reconciliation copy is the honest, expected
offline signal - it says "this call site must move to the tail/streaming reader",
which is exactly the change the live RSS gate cannot attribute on its own.

Inputs (read-only): a COPY of an engine state dir, i.e.
  --audit-dir DIR   containing append_only/{reconciliation,order_intents,send_attempts}.csv
                    (missing files are skipped, not fatal)
--core-dir DIR      checkout that holds HL_Live_Copy_Service_Core.py (default: the
                    repo's _archive/hl_stage2)
--tail-bytes N      bounded-read size (default 2 MiB)
--gate-mb X         retained gate per reader (default 10.0, the J4 pass line)
--rss-gate-mb X     RSS-delta gate (default 15.0, the J4 pass line)

Pass line (last line, exit 0):
  GAP2_RESULT:: PASS files=<n> max_retained_tail_mb=<a> max_retained_full_mb=<b> rss_delta_mb=<c>
FAIL exits 1, INCONCLUSIVE (no CSVs to measure) exits 3.

Offline: no network, no engine, no keys, no ports.
"""
from __future__ import annotations

import argparse
import os
import sys
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cert_common as cc  # noqa: E402

TAG = 'GAP2_RESULT'
DEFAULT_CORE_DIR = Path(__file__).resolve().parents[2] / '_archive' / 'hl_stage2'
RECON_GATE_BYTES = 100 * 1024 * 1024  # the live GAP-2 gate: reconciliation.csv under 100 MB


def measure(fn, *a):
    """Run fn and return (peak_retained_bytes, result)."""
    tracemalloc.start()
    tracemalloc.reset_peak()
    before = tracemalloc.get_traced_memory()[0]
    out = fn(*a)
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return max(0, peak - before), out


def rss_mb():
    try:
        import psutil
    except Exception:
        return None
    return psutil.Process().memory_info().rss / 1e6


def decide(max_tail_mb, max_full_mb, rss_delta_mb, gate_mb, rss_gate_mb):
    """The J4 offline pass line, as a pure function so it can be unit-tested."""
    if max_tail_mb > gate_mb or max_full_mb > gate_mb:
        return False
    if rss_delta_mb is not None and rss_delta_mb > rss_gate_mb:
        return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description='Offline audit-CSV read-cost check (GAP-2).')
    ap.add_argument('--audit-dir', required=True)
    ap.add_argument('--core-dir', default=str(DEFAULT_CORE_DIR))
    ap.add_argument('--tail-bytes', type=int, default=2 * 1024 * 1024)
    ap.add_argument('--gate-mb', type=float, default=10.0)
    ap.add_argument('--rss-gate-mb', type=float, default=15.0)
    args = ap.parse_args(argv)

    audit_dir = Path(args.audit_dir).resolve()
    append = audit_dir / 'append_only'
    if not append.is_dir():
        return cc.emit(TAG, cc.INCONCLUSIVE, 'no_append_only_dir=%s' % append)

    core = cc.core_import(args.core_dir)

    print('%-26s %12s %8s %14s %14s' % ('file', 'bytes', 'rows', 'tail_ret_mb', 'full_ret_mb'))
    max_tail = max_full = 0.0
    recon_bytes = 0
    measured = 0
    rss0 = rss_mb()
    for name in ('reconciliation.csv', 'order_intents.csv', 'send_attempts.csv'):
        path = append / name
        if not path.is_file() or path.stat().st_size <= 0:
            print('%-26s %12s' % (name, 'skip'))
            continue
        size = path.stat().st_size
        if name == 'reconciliation.csv':
            recon_bytes = size
        tail_bytes, tail_rows = measure(core.read_csv_tail_rows, path, args.tail_bytes)
        full_bytes, full_rows = measure(core.read_csv_rows, path)
        tail_mb, full_mb = tail_bytes / 1e6, full_bytes / 1e6
        max_tail, max_full = max(max_tail, tail_mb), max(max_full, full_mb)
        measured += 1
        print('%-26s %12d %8d %14.2f %14.2f' % (name, size, len(full_rows), tail_mb, full_mb))
        print('    tail rows=%d (bounded %d B); full rows=%d' % (len(tail_rows), args.tail_bytes, len(full_rows)))
    if not measured:
        return cc.emit(TAG, cc.INCONCLUSIVE, 'no_audit_csvs_in=%s' % append)
    rss1 = rss_mb()
    rss_delta = None if (rss0 is None or rss1 is None) else rss1 - rss0

    print('GAP2_GAP:: reconciliation_bytes=%d gate_bytes=%d exceeded=%s'
          % (recon_bytes, RECON_GATE_BYTES, recon_bytes >= RECON_GATE_BYTES))

    ok = decide(max_tail, max_full, rss_delta, args.gate_mb, args.rss_gate_mb)
    detail = 'files=%d max_retained_tail_mb=%.2f max_retained_full_mb=%.2f rss_delta_mb=%s' % (
        measured, max_tail, max_full, ('%.2f' % rss_delta) if rss_delta is not None else 'n/a')
    return cc.emit(TAG, cc.PASS if ok else cc.FAIL, detail)


if __name__ == '__main__':
    raise SystemExit(main())
