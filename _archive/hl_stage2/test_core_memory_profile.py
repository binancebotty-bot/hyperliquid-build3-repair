#!/usr/bin/env python3
"""M1 engine memory profile (read-only tool; adds no engine code, edits nothing).

Builds synthetic audit CSVs of realistic row shape at 10 / 100 / 200 MB from the Core's own field lists, then
measures peak and retained memory (tracemalloc) and ms per call for the suspects in HERMES_MEMORY_PROFILE.md:
  (a) one read_csv_rows call                     (whole-file read + parse)
  (b) 1000 send_attempt_rows() calls             (incremental cache + a list() copy per call)
  (c) 1000 candidate lookups (send_attempt_by_oid, the matcher's O(1) path)
  (d) 100 x SenderGateway._owned_fill_size       (first use streams live_fills; then a dict lookup)
  (e) 10 x the reconciliation scan audit_orphan_attribution pays per call (iter_audit_history)
  (f) 5000 intents kept in a dict                (Core.intents_by_id)
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_memory_profile.py [--skip-large]
"""
from __future__ import annotations

import argparse
import csv
import gc
import io
import os
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

TMP = Path(tempfile.mkdtemp(prefix="memprof_"))
os.environ.update({"HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_AUDIT_DIR": str(TMP),
                   "HL_LIVE_AUTO_SEND_ENABLED": "0", "HL_LIVE_WS_ENABLED": "0",
                   "HL_LIVE_SEND_ROWS_WINDOW": "5000"})
import HL_Live_Copy_Service_Core as C  # noqa: E402

try:
    import psutil
    PROC = psutil.Process()
except Exception:
    PROC = None


def rss_mb():
    return PROC.memory_info().rss / 1e6 if PROC else float("nan")


def make_csv(path: Path, fields, target_mb: float, coin_pool=("BTC", "ETH", "SOL")):
    """Write rows of the real field shape until the file reaches target_mb."""
    target = int(target_mb * 1000 * 1000)
    n = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        while f.tell() < target:
            for _ in range(5000):
                n += 1
                oid = str(62000000000 + n)
                w.writerow({
                    "created_at": "2026-10-10T00:00:00.000000+00:00", "created_at_ms": str(1791660000000 + n),
                    "attempt_id": "a%08d" % n, "intent_id": "i%08d" % n, "leader_fill_id": "0x%064x" % n,
                    "leader_wallet": "0x" + "%040x" % n, "coin": coin_pool[n % len(coin_pool)], "side": "BUY",
                    "order_type": "REAL_IOC", "limit_price": "10.5", "copy_size": "1.0", "copy_notional": "10.5",
                    "reduce_only_sent": "False", "sleeve_id": "s%08d" % n, "position_id": "p%08d" % n,
                    "wallet_position_before": "0.0", "wallet_position_after_expected": "1.0",
                    "coin_net_before": "0.0", "coin_net_after_expected": "1.0", "status": "ORDER_FILLED",
                    "exchange_response": "{\"status\": \"ok\"}", "exchange_order_id": oid,
                    "error": "", "reject_category": "", "terminal_state": "FILLED_AWAITING_COPY_POLL",
                    "operator_action": "", "latency_classification": "", "notes": "real exchange IOC attempt",
                    "order_id": oid, "fill_size": "1.0", "totalSz": "1.0", "avgPx": "10.5",
                })
            f.flush()
    return n


def measure(fn, label, op_label, file_mb, repeats=1):
    gc.collect()
    before = rss_mb()
    tracemalloc.start()
    snap0 = tracemalloc.take_snapshot()
    t0 = time.perf_counter()
    for _ in range(repeats):
        fn()
    ms = (time.perf_counter() - t0) * 1000.0 / repeats
    _cur, peak = tracemalloc.get_traced_memory()
    snap1 = tracemalloc.take_snapshot()
    # retained by the operation = allocations that still exist after it (still tracing, so comparable)
    retained = sum(d.size_diff for d in snap1.compare_to(snap0, "filename") if d.size_diff > 0) / 1e6
    tracemalloc.stop()
    after = rss_mb()
    print("| %-34s | %7s | %9.1f | %9.1f | %9.1f | %8.2f |"
          % (op_label, ("%gMB" % file_mb) if file_mb else "-", peak / 1e6, retained,
             max(0.0, after - before), ms))
    return {"label": label, "op": op_label, "file_mb": file_mb, "peak_mb": peak / 1e6,
            "retained_mb": retained, "rss_delta_mb": max(0.0, after - before), "ms_per_call": ms}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-large", action="store_true")
    a = ap.parse_args()
    sizes = [10, 100] if a.skip_large else [10, 100, 200]

    files = {}
    print("building synthetic CSVs ...", flush=True)
    for mb in sizes:
        sa = TMP / ("send_attempts_%dmb.csv" % mb)
        lf = TMP / ("live_fills_%dmb.csv" % mb)
        rc = TMP / ("reconciliation_%dmb.csv" % mb)
        t0 = time.time()
        n1 = make_csv(sa, C.SEND_ATTEMPT_FIELDS, mb)
        n2 = make_csv(lf, C.LIVE_FILL_FIELDS, mb)
        n3 = make_csv(rc, C.RECONCILIATION_FIELDS, mb)
        files[mb] = (sa, lf, rc)
        print("  %dMB each: send_attempts %d rows, live_fills %d rows, reconciliation %d rows (%.1fs)"
              % (mb, n1, n2, n3, time.time() - t0), flush=True)

    print()
    print("| operation | file | peak MB | retained MB | RSS delta MB | ms/call |")
    print("|---|---|---|---|---|---|")
    rows = []
    for mb in sizes:
        sa, lf, rc = files[mb]
        C.SEND_ATTEMPTS_CSV = sa
        C.LIVE_FILLS_CSV = lf
        for name in ("RECONCILIATION_CSV", "LIVE_COPY_RECONCILIATION_CSV"):
            if hasattr(C, name):
                setattr(C, name, rc)

        rows.append(measure(lambda: C.read_csv_rows(sa), "read_csv_rows(send_attempts)", "(a) read_csv_rows", mb, 1))

        # (b) cold once, then 1000 warm calls
        C._SEND_ROWS_CACHE.update({"path": None, "ino": None, "size": 0, "mtime": None, "tail": b"",
                                   "rows": None, "fields": None, "by_oid": None, "recovery": None})
        rows.append(measure(lambda: C.send_attempt_rows(), "send_attempt_rows cold", "(b) send_attempt_rows COLD", mb, 1))
        rows.append(measure(lambda: C.send_attempt_rows(), "send_attempt_rows x1000", "(b) 1000x send_attempt_rows", mb, 1000))

        # (c) 1000 candidate lookups on the O(1) index
        cache = C._send_cache_refresh()
        by_oid = cache.get("by_oid") or {}
        oids = list(by_oid.keys())[:50] or ["62000000001"]
        rows.append(measure(lambda: [C.send_attempt_by_oid(oids[i % len(oids)]) for i in range(1000)],
                            "candidate lookup x1000", "(c) 1000x candidate lookup", mb, 1))

        # (d) _owned_fill_size: first use streams live_fills, then dict lookups
        C._OWNED_BY_OID.update({"path": None, "sizes": {}})
        rows.append(measure(lambda: C.SenderGateway._owned_fill_size("62000000001"),
                            "owned_fill_size cold", "(d) _owned_fill_size COLD", mb, 1))
        rows.append(measure(lambda: [C.SenderGateway._owned_fill_size("62000000001") for _ in range(100)],
                            "owned_fill_size x100", "(d) 100x _owned_fill_size", mb, 1))

        # (e) the reconciliation scan audit_orphan_attribution pays per call
        def recon_scan():
            return {str(r.get("coin") or "").upper() for r in C.iter_audit_history(rc)
                    if r.get("event") == "SERVICE_CREATED_UNLEDGERED_POSITION"}
        rows.append(measure(lambda: [recon_scan() for _ in range(10)], "recon scan x10", "(e) 10x reconcil scan (per call)", mb, 1))

    # (f) 5000 intents kept in a dict (size-independent)
    def build_intents():
        d = {}
        for i in range(5000):
            f = C.LeaderFill("f%06d" % i, "0x" + "%040x" % i, "BTC", "BUY", 10.5, 1.0, 1791660000000 + i, "POLL")
            d["i%06d" % i] = C.Intent(intent_id="i%06d" % i, fill=f, copy_side="BUY", copy_size=1.0,
                                      copy_notional=10.5, wallet_mode="", copy_mode="", decision="ENTRY_ALLOWED",
                                      reason="", sleeve_id="", position_id="", position_direction_before="",
                                      wallet_position_before=0.0, coin_net_before=0.0,
                                      reduce_only_intended=False, reduce_only_sent_planned=False)
        return d
    rows.append(measure(build_intents, "intents_by_id 5000", "(f) 5000 intents in a dict", 0, 1))

    print()
    print("== ranked by retained RSS delta (contribution per call site) ==")
    for r in sorted(rows, key=lambda x: -x["rss_delta_mb"])[:8]:
        print("  %-34s file=%-7s peak=%7.1f MB rss_delta=%7.1f MB  %.2f ms/call"
              % (r["op"], ("%gMB" % r["file_mb"]) if r["file_mb"] else "-", r["peak_mb"], r["rss_delta_mb"], r["ms_per_call"]))
    print()
    print("frequency: (a) per call - used by audit_orphan_attribution (reconciliation) and one-off index loads;"
          " (b)(c) per copy fill; (d) first use per run then per fill; (e) per cycle; (f) per fill (kept whole run)")


if __name__ == "__main__":
    main()
