#!/usr/bin/env python3
"""Audit CSV appends do not open the file to re-read its header every time (Q-run 18 Oct: 1,371 order_intents appends in one
copy-poll cycle starved the poll for 488 s behind the shared file lock), and read_csv_rows no longer holds the lock for the byte read.
The header is still verified/migrated whenever the file is new, rotated, replaced or shrank.

Run: HL_LIVE_ENV_FILE=/nonexistent python test_core_audit_header_cache.py
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
tmp = Path(tempfile.mkdtemp(prefix="hdrcache_"))
os.environ.update({"HL_LIVE_AUDIT_DIR": str(tmp), "HL_LIVE_ENV_FILE": "/nonexistent", "HL_LIVE_WS_ENABLED": "0"})
import HL_Live_Copy_Service_Core as c  # noqa: E402

RESULTS = []
F = ["a", "b", "c"]


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("RESULT::%s_%s%s" % (name, "PASS" if cond else "FAIL", (" | " + detail) if (detail and not cond) else ""))


p = tmp / "x.csv"
real_reader = c.csv.DictReader
opens = {"n": 0}


class CountingReader(real_reader):
    def __init__(self, *a, **k):
        opens["n"] += 1
        super().__init__(*a, **k)


c.csv.DictReader = CountingReader
c.append_csv(p, F, {"a": 1, "b": 2, "c": 3})
first = opens["n"]
for i in range(50):
    c.append_csv(p, F, {"a": i, "b": 2, "c": 3})
check("H1_NO_HEADER_READ_AFTER_FIRST_APPEND", opens["n"] == first, "reads %d -> %d" % (first, opens["n"]))
rows = list(real_reader(p.open(encoding="utf-8")))
check("H2_ALL_ROWS_WRITTEN", len(rows) == 51 and rows[-1]["a"] == "49", str(len(rows)))

# new columns appended later: the header is migrated once, rows kept
F2 = F + ["d"]
c.append_csv(p, F2, {"a": 7, "d": 9})
rows = list(real_reader(p.open(encoding="utf-8")))
check("H3_NEW_COLUMN_MIGRATES_ONCE_ROWS_KEPT", len(rows) == 52 and rows[0]["d"] == "" and rows[-1]["d"] == "9", str(rows[-1]))
n0 = opens["n"]
c.append_csv(p, F2, {"a": 8, "d": 10})
check("H4_NO_READ_AFTER_MIGRATION", opens["n"] == n0)

# rotation: the file is renamed away and a fresh one with its header starts; the next append must still be right
q = tmp / "order_intents.csv"
c.append_csv(q, c.ORDER_INTENT_FIELDS, {"intent_id": "i1"})
c._rotate_audit_file(q)
c.append_csv(q, c.ORDER_INTENT_FIELDS, {"intent_id": "i2"})
rows = list(real_reader(q.open(encoding="utf-8")))
check("H5_ROTATED_FILE_NEW_ROWS_OK", [r["intent_id"] for r in rows] == ["i2"], str(rows))

# replaced file (deleted and recreated with an OLD header): the cache must not trust it
r = tmp / "y.csv"
c.append_csv(r, F2, {"a": 1})
r.unlink()
with r.open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=F)
    w.writeheader()
c.append_csv(r, F2, {"a": 2, "d": 5})
rows = list(real_reader(r.open(encoding="utf-8")))
check("H6_REPLACED_FILE_REVERIFIED", rows and rows[-1]["d"] == "5", str(rows))

# a reader and a writer at the same time: the reader never sees a half row
s = tmp / "z.csv"
c.append_csv(s, F, {"a": 0, "b": "x" * 200, "c": 0})
stop = threading.Event()
bad = []


def writer():
    i = 1
    while not stop.is_set():
        c.append_csv(s, F, {"a": i, "b": "x" * 200, "c": i})
        i += 1


t = threading.Thread(target=writer)
t.start()
for _ in range(30):
    for row in c.read_csv_rows(s):
        if row.get("c") is None or row.get("b") != "x" * 200:
            bad.append(row)
stop.set()
t.join()
check("H7_READER_SEES_ONLY_WHOLE_ROWS", not bad, str(bad[:1]))
final = c.read_csv_rows(s)
check("H8_READ_ALL_AFTER_WRITES", len(final) >= 1 and final[0]["a"] == "0")

# rewritten IN PLACE (same inode) with an older header and more bytes than before: a size we did not write is re-verified
u = tmp / "u.csv"
c.append_csv(u, F2, {"a": 1})
with u.open("r+", newline="", encoding="utf-8") as fh:
    fh.write("a,b,c\n" + "1,2,3\n" * 40)
    fh.truncate()
c.append_csv(u, F2, {"a": 9, "d": 4})
rows = list(real_reader(u.open(encoding="utf-8")))
check("H9_IN_PLACE_REWRITE_REVERIFIED", rows and "d" in rows[0] and rows[-1]["d"] == "4", str(rows[:1]))

# a verified entry exists, the file is replaced by an older-header file and the migration FAILS (Windows: a reader holds it open):
# the stale entry must not vouch for the new file, and the next append must verify again
w = tmp / "w.csv"
c.append_csv(w, F2, {"a": 1})
w.unlink()
with w.open("w", newline="", encoding="utf-8") as fh:
    cw = csv.DictWriter(fh, fieldnames=F)
    cw.writeheader()
    cw.writerow({"a": 1, "b": 2, "c": 3})
real_replace = c.os.replace


def failing_replace(*a, **k):
    raise PermissionError("held open by a reader")


c.os.replace = failing_replace
try:
    c.append_csv(w, F2, {"a": 5, "d": 6})
finally:
    c.os.replace = real_replace
check("H10_FAILED_MIGRATION_LEAVES_NO_CACHE_ENTRY", str(w) not in c._HEADER_OK, str(c._HEADER_OK.get(str(w))))
c.append_csv(w, F2, {"a": 7, "d": 8})
rows = list(real_reader(w.open(encoding="utf-8")))
check("H11_NEXT_APPEND_MIGRATES", rows and "d" in rows[0] and rows[-1]["d"] == "8", str(rows[:1]))

c.csv.DictReader = real_reader
failed = [n for n, ok in RESULTS if not ok]
print("TOTAL=%d FAILED=%d" % (len(RESULTS), len(failed)))
sys.exit(1 if failed else 0)
