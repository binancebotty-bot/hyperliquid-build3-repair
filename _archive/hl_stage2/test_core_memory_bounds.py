#!/usr/bin/env python3
"""Memory bounds: send_attempts cache is a bounded window + O(1) oid index; big CSVs stream; audit files rotate at a
size limit and startup scans still see the rotated history; per-order owned size needs no whole-file read.
Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_memory_bounds.py"""
import os, sys, tempfile, tracemalloc, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="mem_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_SEND_ROWS_WINDOW": "1000", "HL_LIVE_SEND_OID_INDEX_MAX": "20000",
                   "HL_LIVE_AUDIT_ROTATE_BYTES": str(300 * 1024), "HL_LIVE_AUDIT_ROTATE_KEEP": "3"})
import HL_Live_Copy_Service_Core as c
R = []
def check(n, ok, d=""):
    R.append(bool(ok)); print("RESULT::%s_%s%s" % (n, "PASS" if ok else "FAIL", (" | " + str(d)) if d and not ok else ""))

# ---- 1. big send_attempts: bounded memory, oid lookups work for old and new orders
c.ensure_csv_header(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS)
N = 60000
pad = "x" * 300
with c.SEND_ATTEMPTS_CSV.open("a", newline="", encoding="utf-8") as f:
    import csv
    w = csv.DictWriter(f, fieldnames=c.SEND_ATTEMPT_FIELDS)
    for i in range(N):
        w.writerow({"attempt_id": "a%d" % i, "intent_id": "i%d" % i, "coin": "BTC", "side": "BUY", "status": "ORDER_FILLED",
                    "exchange_order_id": str(1000000 + i), "exchange_response": pad, "notes": pad})
tracemalloc.start()
t0 = time.time()
rows = c.send_attempt_rows()
cur, peak = tracemalloc.get_traced_memory()
check("WINDOW_IS_BOUNDED", len(rows) == 1000, len(rows))
check("MEMORY_BOUNDED_NOT_FILE_SIZED", cur < 30 * 1024 * 1024 and len(c._SEND_ROWS_CACHE["by_oid"]) <= 20000, "%d vs file %d" % (cur, c.SEND_ATTEMPTS_CSV.stat().st_size))
check("NEWEST_OIDS_INDEXED_OLDEST_EVICTED", (c.send_attempt_by_oid("1059999") or {}).get("intent_id") == "i59999" and c.send_attempt_by_oid("1000000") is None)
t1 = time.time()
for _ in range(2000):
    c.send_attempt_rows()
    c.send_attempt_by_oid("1059999")
check("CALLS_ARE_CHEAP_WHEN_NOTHING_APPENDED", time.time() - t1 < 3.0, time.time() - t1)
c.append_csv(c.SEND_ATTEMPTS_CSV, c.SEND_ATTEMPT_FIELDS, {"attempt_id": "new", "intent_id": "inew", "status": "ORDER_RESTING", "exchange_order_id": "5555"})
check("APPENDED_ROW_SEEN_INCREMENTALLY", (c.send_attempt_by_oid("5555") or {}).get("intent_id") == "inew")
tracemalloc.stop()

# ---- 2. streaming reader sees every row, only up to the size at scan start
n = sum(1 for _ in c.iter_csv_rows(c.SEND_ATTEMPTS_CSV))
check("STREAM_COUNTS_ALL_ROWS", n == N + 1, n)

# ---- 3. rotation of order_intents / reconciliation; history readers see everything
c.ensure_csv_header(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS)
total = 0
for i in range(2500):
    c.append_csv(c.RECONCILIATION_CSV, c.RECONCILIATION_FIELDS, {"event": "E", "status": "S%d" % i, "notes": pad})
    total += 1
rot = c.rotated_audit_paths(c.RECONCILIATION_CSV)
check("ROTATED_AT_LIMIT", len(rot) >= 1 and c.RECONCILIATION_CSV.stat().st_size < 400 * 1024, [p.name for p in rot])
check("ONLY_KEEP_NEWEST_ROTATED", len(rot) <= 3, len(rot))
seen = [r["status"] for r in c.iter_audit_history(c.RECONCILIATION_CSV)]
check("HISTORY_SPANS_ROTATED_FILES_IN_ORDER", seen == sorted(seen, key=lambda s: int(s[1:])) and seen[-1] == "S2499" and len(seen) > 0, len(seen))
check("OLDEST_PRUNED_NOT_LOST_MIDDLE", len(set(seen)) == len(seen))
check("SEND_ATTEMPTS_NOT_ROTATED", not c.rotated_audit_paths(c.SEND_ATTEMPTS_CSV))

# ---- 4. owned fill size: streamed once, then kept current by appends
c.ensure_csv_header(c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS)
c.append_csv(c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS, {"exchange_order_id": "77", "fill_size": "1.5"})
check("OWNED_SIZE_INITIAL", abs(c.SenderGateway._owned_fill_size("77") - 1.5) < 1e-9)
c.append_csv(c.LIVE_FILLS_CSV, c.LIVE_FILL_FIELDS, {"exchange_order_id": "77", "fill_size": "0.5"})
check("OWNED_SIZE_UPDATED_BY_APPEND", abs(c.SenderGateway._owned_fill_size("77") - 2.0) < 1e-9)
check("OWNED_SIZE_UNKNOWN_ZERO", c.SenderGateway._owned_fill_size("999") == 0.0)
# ---- 5. rotation leaves a headed file; tail reader returns whole recent rows
check("FRESH_FILE_HAS_HEADER_AFTER_ROTATE", c.RECONCILIATION_CSV.exists() and c.RECONCILIATION_CSV.read_text().splitlines()[0].startswith("created_at"), c.RECONCILIATION_CSV.read_text()[:80] if c.RECONCILIATION_CSV.exists() else "missing")
tail = c.read_csv_tail_rows(c.SEND_ATTEMPTS_CSV, 2 * 1024 * 1024)
check("TAIL_ROWS_WHOLE_AND_RECENT", 0 < len(tail) < N and tail[-1]["attempt_id"] == "new" and all(r["attempt_id"] for r in tail), len(tail))
print("TOTAL=%d FAILED=%d" % (len(R), R.count(False))); sys.exit(1 if False in R else 0)
