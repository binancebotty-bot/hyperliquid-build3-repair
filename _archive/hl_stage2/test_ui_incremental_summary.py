#!/usr/bin/env python3
"""UI2: the audit summary must rebuild from APPENDED bytes, not by re-reading whole CSVs.

Builds a synthetic ~150 MB reconciliation CSV, then proves:
  - the first rebuild counts every row;
  - after appending 100 rows the next rebuild is < 1 s, the total count grows by exactly 100 and the new
    rows are returned;
  - a row without a trailing newline is not parsed until it is completed;
  - the cache resets when the file shrinks / is rewritten (no stale rows);
  - the /api/live-audit-summary payload built through the real builder stays under 1 MB on synthetic data
    (reconciliation rows are capped, the pre-cap total is kept as a `_total` count).

Run: HL_LIVE_ENV_FILE=/nonexistent python test_ui_incremental_summary.py   (RESULT:: markers, exit 0/1)
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["HL_LIVE_ENV_FILE"] = "/nonexistent"
RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


FIELDS = ["created_at", "event", "terminal_state", "leader_wallet", "coin", "action", "notes", "reason",
          "status", "execution_decision", "decision_reason", "manual_reconcile_required", "market_data_error",
          "source"]


def row(i: int, coin: str = "BTC", marker: str = "") -> dict:
    return {"created_at": "2026-10-10T00:00:00.000000+00:00", "event": "E", "terminal_state": "T",
            "leader_wallet": "0x" + "a" * 40, "coin": coin, "action": "A", "notes": marker or f"note {i}",
            "reason": "R", "status": "S", "execution_decision": "D", "decision_reason": "DR",
            "manual_reconcile_required": "False", "market_data_error": "", "source": "POLL"}


def _payload_check(ui, tmp: Path, reconfile: Path) -> None:
    """Run the REAL /api/live-audit-summary path (_live_audit_summary over _live_audit_summary_full) against
    a synthetic audit folder carrying the 150 MB reconciliation CSV, and assert the payload stays < 1 MB."""
    orig_dir = ui.LIVE_COPY_AUDIT_DIR
    pdir = tmp / "audit"
    (pdir / "append_only").mkdir(parents=True, exist_ok=True)
    saved = {}
    for name in dir(ui):
        v = getattr(ui, name, None)
        if isinstance(v, Path):
            try:
                rel = v.relative_to(orig_dir)
            except ValueError:
                continue
            saved[name] = v
            setattr(ui, name, pdir / rel)
    saved["LIVE_COPY_RECONCILIATION_CSV"] = ui.LIVE_COPY_RECONCILIATION_CSV
    ui.LIVE_COPY_RECONCILIATION_CSV = reconfile
    saved["_fetch_exchange_account_snapshot"] = ui._fetch_exchange_account_snapshot
    saved["_follower_account_value_safe"] = ui._follower_account_value_safe
    saved["_append_exchange_history"] = ui._append_exchange_history
    ui._fetch_exchange_account_snapshot = lambda *a, **k: {"available": False, "open_positions": []}
    ui._follower_account_value_safe = lambda *a, **k: {"ok": False, "reason": "synthetic"}
    ui._append_exchange_history = lambda *a, **k: None

    try:
        with (pdir / "append_only" / "order_intents.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
            for i in range(2000):
                w.writerow(row(i))
        saf = ["created_at", "status", "exchange_response", "side", "exchange_order_id", "leader_wallet", "coin"]
        with (pdir / "append_only" / "send_attempts.csv").open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=saf); w.writeheader()
            for i in range(2000):
                w.writerow({"created_at": "2026-10-10T00:00:00+00:00", "status": "ORDER_FILLED",
                            "exchange_response": "{}", "side": "BUY", "exchange_order_id": str(i),
                            "leader_wallet": "0x" + "a" * 40, "coin": "BTC"})
        ui._CSV_READER_CACHE.clear()
        out = ui._live_audit_summary()
        size = len(json.dumps(out))
        print("synthetic /api/live-audit-summary payload: %d bytes" % size)
        check("UI2_SUMMARY_PAYLOAD_UNDER_1MB", size < 1_000_000, "bytes=%d" % size)
        recon = out.get("reconciliation_rows") or []
        check("UI2_RECON_ROWS_CAPPED_TO_PAGE", len(recon) <= 500, "rows=%d" % len(recon))
        check("UI2_RECON_TOTAL_COUNT_KEPT", int(out.get("reconciliation_rows_total") or 0) >= 500,
              "total=%s" % out.get("reconciliation_rows_total"))
    finally:
        for name, val in saved.items():
            if name == "LIVE_COPY_RECONCILIATION_CSV":
                ui.LIVE_COPY_RECONCILIATION_CSV = val
            else:
                setattr(ui, name, val)
        ui._CSV_READER_CACHE.clear()


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="ui2inc_"))
    try:
        csvp = tmp / "reconciliation.csv"
        target_bytes = int(os.getenv("UI2_TARGET_MB", "150")) * 1000 * 1000
        n = 0
        with csvp.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            while csvp.stat().st_size < target_bytes:
                for _ in range(20000):
                    w.writerow(row(n)); n += 1
                f.flush()
        size_mb = csvp.stat().st_size / 1e6
        print("synthetic reconciliation.csv: %d rows, %.0f MB" % (n, size_mb))
        check("UI2_SYNTHETIC_BIG_ENOUGH", size_mb >= 140, "size=%.0f MB" % size_mb)

        import HL_Copy_App_SSOT as ui  # noqa: E402
        ui.LIVE_COPY_RECONCILIATION_CSV = csvp
        ui._CSV_READER_CACHE.clear()

        t0 = time.time(); rows1, total1 = ui._load_recent_reconciliation_rows(500); first = time.time() - t0
        print("first rebuild: %.2f s (total=%d)" % (first, total1))
        check("UI2_FIRST_CALL_COUNTS_ALL_ROWS", total1 == n, "total=%s n=%s" % (total1, n))
        check("UI2_FIRST_CALL_RETURNS_PAGE_ROWS", len(rows1) == 500)

        with csvp.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            for i in range(100):
                w.writerow(row(n + i, coin="NEWCOIN", marker="appended %d" % i))
        t0 = time.time(); rows2, total2 = ui._load_recent_reconciliation_rows(500); second = time.time() - t0
        print("second rebuild after +100 rows: %.3f s (total=%d)" % (second, total2))
        check("UI2_SECOND_CALL_UNDER_1S", second < 1.0, "%.3f s" % second)
        check("UI2_TOTAL_GROWS_BY_100", total2 - total1 == 100, "delta=%d" % (total2 - total1))
        check("UI2_NEW_ROWS_RETURNED", sum(1 for r in rows2 if str(r.get("coin")) == "NEWCOIN") == 100,
              "new=%d" % sum(1 for r in rows2 if str(r.get("coin")) == "NEWCOIN"))

        # the full payload path must stay under 1 MB even though the source CSV is ~150 MB
        _payload_check(ui, tmp, csvp)

        # a partial last line must not be parsed yet
        with csvp.open("a", newline="", encoding="utf-8") as f:
            f.write("2026-10-10T00:00:00.000000+00:00,E,T,0x" + "a" * 40 + ",PARTIAL,A,partial row,R,S,D,DR,False,,POLL")
        _r, total3 = ui._load_recent_reconciliation_rows(500)
        check("UI2_PARTIAL_LINE_NOT_PARSED", total3 == total2, "total=%s (was %s)" % (total3, total2))
        with csvp.open("a", newline="", encoding="utf-8") as f:
            f.write("\n")
        _r, total4 = ui._load_recent_reconciliation_rows(500)
        check("UI2_COMPLETED_LINE_PARSED", total4 == total2 + 1, "total=%s (was %s)" % (total4, total2 + 1))

        # shrink / rewrite must reset the cache (no stale rows)
        with csvp.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader()
            for i in range(10):
                w.writerow(row(i, coin="REWRITTEN"))
        _r, total5 = ui._load_recent_reconciliation_rows(500)
        check("UI2_SHRINK_RESETS_CACHE", total5 == 10, "total=%s" % total5)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = [x for x, ok in RESULTS if not ok]
    print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
